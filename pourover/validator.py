"""Every plan passes through here, fast path and model alike.

normalise() fixes harmless details (pourover label, label order, reminder
defaulting to the due time, a mislabelled envelope). check() rejects anything that points outside
the world snapshot.
"""

from __future__ import annotations

from datetime import datetime

from .schema import CreateTask, DeleteTask, Plan
from .world import World


def normalise(plan: Plan) -> Plan:
    # Small models write the envelope ("kind", "reason") before the operations and often get it
    # wrong while the operations themselves are right ({"kind": "no_plan", "ops": [complete 109]}).
    # Concrete operations win over a "no_plan" label; refusals and clarifications stand as given.
    if plan.kind == "no_plan" and plan.ops:
        plan = plan.model_copy(update={"kind": "plan"})
    if plan.kind != "plan":
        return plan.model_copy(update={
            "ops": None,
            "reason": plan.reason if plan.kind == "refused" else None,
            "candidates": (plan.candidates or []) if plan.kind == "needs_clarification" else None,
        })
    ops = []
    for op in plan.ops or []:
        if isinstance(op, CreateTask):
            labels = set(op.labels) | {"pourover"}
            if op.repeat is None:
                labels.discard("chores")  # chores means repeating housework; models sprinkle it on one-offs
            labels = sorted(labels)
            op = op.model_copy(
                update={
                    "title": op.title.strip(),
                    "labels": labels,
                    "reminder_at": op.reminder_at or op.due_at,
                    "description": (op.description or "").strip() or None,
                }
            )
        ops.append(op)
    return plan.model_copy(update={"ops": ops, "candidates": None, "reason": None})


def _bad_time(value: str | None) -> bool:
    if value is None:
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is None
    except ValueError:
        return True


def check(plan: Plan, sender: str, world: World) -> list[str]:
    errors: list[str] = []
    open_ids = {t.id for t in world.open_tasks()}

    if plan.kind == "plan" and not plan.ops:
        errors.append("plan has no operations")
    if plan.kind == "needs_clarification":
        stray = set(plan.candidates or []) - open_ids
        if stray:
            errors.append(f"unknown candidate tasks {sorted(stray)}")
    if plan.kind == "refused" and plan.reason != "not_owner":
        errors.append("refused without a reason")

    for op in plan.ops or []:
        if op.op == "create_task":
            if not op.title:
                errors.append("empty title")
            if op.project not in world.projects:
                errors.append(f"unknown project {op.project!r}")
            unknown = set(op.labels) - set(world.labels)
            if unknown:
                errors.append(f"unknown labels {sorted(unknown)}")
            if op.assignee not in world.users:
                errors.append(f"unknown assignee {op.assignee!r}")
            if _bad_time(op.due_at) or _bad_time(op.reminder_at):
                errors.append("time without a timezone or unreadable")
        elif op.op in ("complete_task", "delete_task"):
            if op.task_id not in open_ids:
                errors.append(f"task {op.task_id} is not an open task")
    return errors


def not_owned_deletes(plan: Plan, sender: str, world: World) -> bool:
    for op in plan.ops or []:
        if isinstance(op, DeleteTask):
            task = world.task(op.task_id)
            if task is None or task.owner != sender:
                return True
    return False
