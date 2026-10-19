"""Applies plans to Vikunja and answers the sender. One call per message."""

from __future__ import annotations

import logging
import re
import time as clock
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, Protocol

from . import replies
from .config import User
from .model import ModelClient
from .ntfy import Ntfy
from .planner import PlanResult, make_plan
from .schema import CreateTask, DeleteTask, Plan
from .store import Store
from .world import World

log = logging.getLogger("pourover")

YES = re.compile(r"^\s*(yes|y|haan|ha|han|confirm|ok|okay|sure)\s*[.!]*\s*$", re.I)
UNDO = re.compile(r"^\s*undo\s*[.!]*\s*$", re.I)


class Backend(Protocol):
    def world(self, owners: dict[int, str], names: dict[str, str]) -> tuple[World, dict, dict]: ...
    def create(self, op: CreateTask, project_id: int, label_ids: list[int], assignee_id: Optional[int]) -> dict: ...
    def complete(self, task_id: int) -> dict: ...
    def delete(self, task_id: int) -> None: ...


@dataclass
class Reply:
    text: str
    outcome: str
    path: Optional[str] = None
    plan: Optional[Plan] = None
    created: Optional[list[int]] = None


class Service:
    def __init__(self, users: dict[str, User], backend_for: Callable[[User], Backend], store: Store,
                 model: Optional[ModelClient], ntfy: Ntfy, now: Callable[[], datetime], queue_expiry_hours: int = 6):
        self.users = users
        self.backend_for = backend_for
        self.store = store
        self.model = model
        self.ntfy = ntfy
        self.now = now
        self.expiry = timedelta(hours=queue_expiry_hours)
        self.owners = {u.vikunja_user_id: u.key for u in users.values()}
        self.names = {u.key: u.name for u in users.values()}

    # ---- entry point -------------------------------------------------
    def handle(self, user: User, text: str, channel: str = "meowgram") -> str:
        started = clock.monotonic()
        now = self.now()
        try:
            reply = self._handle(user, text, channel, now)
        except Exception as exc:  # never leave the sender without an answer
            log.exception("command failed")
            reply = Reply(f"Something broke on my side: {exc}. Check Vikunja before retrying.", "error")
            self.ntfy.send(user.ntfy_topic, user.ntfy_token, f"pourOver error on '{text}': {exc}", "pourOver error")
        self.store.log(
            now=now, sender=user.key, channel=channel, text=text, path=reply.path,
            plan=reply.plan.model_dump_json() if reply.plan else None, outcome=reply.outcome, reply=reply.text,
            created_task_ids=reply.created, latency_ms=int((clock.monotonic() - started) * 1000),
        )
        return reply.text

    def _handle(self, user: User, text: str, channel: str, now: datetime) -> Reply:
        backend = self.backend_for(user)

        pending = self.store.pop_pending(user.key)
        if pending is not None:
            if YES.match(text):
                plan = Plan.model_validate_json(pending["plan"])
                world, _, _ = backend.world(self.owners, self.names)
                return self._apply(user, backend, world, plan, "confirm", now, confirmed=True)
            if re.match(r"^\s*(no|nahi|nope|cancel|keep)\b", text, re.I):
                return Reply(f"Kept it. {replies.NOTHING_CHANGED}", "cancelled")
            # anything else: the pending delete is dropped and the message is handled normally

        world, _, _ = backend.world(self.owners, self.names)

        if UNDO.match(text):
            ids = [i for i in self.store.last_created(user.key) if world.task(i)]
            if not ids:
                return Reply(f"Nothing of yours to undo. {replies.NOTHING_CHANGED}", "no_plan", "fast")
            plan = Plan(kind="plan", ops=[DeleteTask(task_id=i) for i in ids])
            return self._ask_confirm(user, world, plan, "fast", now)

        result = make_plan(text, user.key, world, now, self.model)
        return self._respond(user, backend, world, result, text, channel, now)

    def _respond(self, user: User, backend: Backend, world: World, result: PlanResult, text: str, channel: str,
                 now: datetime) -> Reply:
        if result.path == "queue":
            self.store.enqueue(user.key, channel, text, now)
            hours = int(self.expiry.total_seconds() // 3600)
            return Reply(replies.QUEUED.format(hours=hours), "queued", "queue")
        if not result.ok:
            log.warning("invalid plan for %r: %s", text, result.errors)
            return Reply(replies.INVALID, "invalid", result.path)

        plan = result.plan
        if plan.kind == "no_plan":
            return Reply(replies.NO_PLAN, "no_plan", result.path, plan)
        if plan.kind == "needs_clarification":
            return Reply(replies.clarify(plan.candidates or [], world), "clarify", result.path, plan)
        if plan.kind == "refused":
            target = next((op.task_id for op in plan.ops or [] if isinstance(op, DeleteTask)), None)
            return Reply(replies.refused(world.task(target) if target else None, world), "refused", result.path, plan)
        if plan.destructive:
            return self._ask_confirm(user, world, plan, result.path, now)
        reply = self._apply(user, backend, world, plan, result.path, now)
        if result.path == "fallback":
            reply.text += " " + replies.OFFLINE_NOTE
        return reply

    def _ask_confirm(self, user: User, world: World, plan: Plan, path: str, now: datetime) -> Reply:
        titles = [world.task(op.task_id).title for op in plan.ops if isinstance(op, DeleteTask)]
        summary = ", ".join(f"'{t}'" for t in titles)
        self.store.set_pending(user.key, plan.model_dump_json(), summary, now)
        return Reply(f"Delete {summary}? Reply yes to delete; anything else keeps it.", "awaiting_confirm", path, plan)

    # ---- applying ----------------------------------------------------
    def _apply(self, user: User, backend: Backend, world: World, plan: Plan, path: str, now: datetime,
               confirmed: bool = False) -> Reply:
        _, project_ids, label_ids = backend.world(self.owners, self.names)
        lines, created = [], []
        for op in plan.ops or []:
            try:
                if op.op == "create_task":
                    assignee = self.users.get(op.assignee)
                    task = backend.create(
                        op,
                        project_ids[op.project],
                        [label_ids[lb] for lb in op.labels if lb in label_ids],
                        assignee.vikunja_user_id if assignee else None,
                    )
                    created.append(task["id"])
                    lines.append(replies.created(op, world, user.key))
                elif op.op == "complete_task":
                    after = backend.complete(op.task_id) or {}
                    line = f"Done: {world.task(op.task_id).title} ✓"
                    if after.get("done") is False and after.get("due_date"):  # a repeat: Vikunja re-opened it
                        line += f" (next: {replies.when(after['due_date'], now.tzinfo)})"
                    lines.append(line)
                elif op.op == "list_due":
                    lines.append(replies.due_list(world, op.window, now))
                elif op.op == "delete_task":
                    task = world.task(op.task_id)
                    if task is None or task.owner != user.key or not confirmed:  # belt and braces
                        lines.append(replies.refused(task, world))
                        continue
                    backend.delete(op.task_id)
                    lines.append(f"Deleted: {task.title}")
            except Exception as exc:
                log.exception("apply failed")
                done = "\n".join(lines) or "Nothing was changed."
                return Reply(f"{done}\nStopped at an error: {exc}", "partial", path, plan, created)
        if created:
            lines.append("Reply undo to remove what I just added.")
        return Reply("\n".join(lines), "applied", path, plan, created)

    # ---- queue ---------------------------------------------------------
    def drain_queue(self) -> int:
        """Run waiting messages once the model is back. Returns how many were handled."""
        now = self.now()
        handled = 0
        for item in self.store.waiting():
            user = self.users.get(item["sender"])
            if user is None:
                self.store.set_status(item["id"], "dropped")
                continue
            age = now - datetime.fromisoformat(item["created_at"])
            if age > self.expiry:
                self.store.set_status(item["id"], "expired")
                self.ntfy.send(user.ntfy_topic, user.ntfy_token,
                               f"Gave up on '{item['text']}' (AI was away too long). {replies.NOTHING_CHANGED}")
                handled += 1
                continue
            backend = self.backend_for(user)
            world, _, _ = backend.world(self.owners, self.names)
            result = make_plan(item["text"], user.key, world, now, self.model)
            if result.path == "queue":
                break  # still napping; try again next round
            reply = self._respond(user, backend, world, result, item["text"], item["channel"], now)
            self.store.set_status(item["id"], "done")
            self.store.log(now=now, sender=user.key, channel="queue", text=item["text"], path=reply.path,
                           plan=reply.plan.model_dump_json() if reply.plan else None, outcome=reply.outcome,
                           reply=reply.text, created_task_ids=reply.created)
            self.ntfy.send(user.ntfy_topic, user.ntfy_token, f"'{item['text']}'\n{reply.text}")
            handled += 1
        return handled
