"""Fast path: common commands handled with no model call.

Returns None when the message needs the model.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from .matching import find_tasks
from .rules import clean_title, labels_for
from .schema import CompleteTask, CreateTask, DeleteTask, ListDue, Plan
from .timeparse import iso, parse
from .world import World

_TRAIL = r"[\s!.?🙏✅👍]*$"

QUERY = re.compile(
    r"^(?:what'?s|whats|what\s+is|what\s+are|anything|kya|show|list|any)\b.*\b(due|pending|left|baaki|baki|overdue|today|aaj|week|hafte)\b"
    r"|^(?:due|overdue|today|aaj\s+kya\s+hai|pending)" + _TRAIL,
    re.I,
)
DONE_PREFIX = re.compile(r"^(?:done|completed|finished)\s*[:\-]?\s+(.+?)" + _TRAIL, re.I)
DONE_SUFFIX = re.compile(r"^(.+?)\s+(?:done|ho\s*gaya|ho\s*gya|kar\s+diya|kar\s+liya|completed|finished)" + _TRAIL, re.I)
DELETE_PREFIX = re.compile(r"^(?:delete|remove|cancel|drop|hatao|hata\s+do)\s*[:\-]?\s+(.+?)" + _TRAIL, re.I)
DELETE_SUFFIX = re.compile(r"^(.+?)\s+(?:delete\s+kar\s+do|hata\s+do|delete\s+karo)" + _TRAIL, re.I)
ADD_TO_PROJECT = re.compile(r"^(?:add|todo|task)\s*[:\-]?\s+(.+?)\s+(?:to|in|under)\s+([a-z]+)" + _TRAIL, re.I)


def _window(text: str) -> str:
    low = text.lower()
    if "overdue" in low:
        return "overdue"
    if "week" in low or "hafte" in low:
        return "week"
    return "today"


def _resolve(query: str, world: World) -> list[int]:
    return [t.id for t in find_tasks(query, world.open_tasks())]


def fast_plan(text: str, sender: str, world: World, now: datetime) -> Optional[Plan]:
    t = text.strip()
    if not t:
        return Plan(kind="no_plan")

    if QUERY.search(t):
        return Plan(kind="plan", ops=[ListDue(window=_window(t))])

    m = DONE_PREFIX.match(t) or DONE_SUFFIX.match(t)
    if m:
        ids = _resolve(m.group(1), world)
        if len(ids) == 1:
            return Plan(kind="plan", ops=[CompleteTask(task_id=ids[0])])
        if ids:
            return Plan(kind="needs_clarification", candidates=ids)
        # no match: maybe it isn't a "done" at all ("make sure laundry is done"); let the model judge

    m = DELETE_PREFIX.match(t) or DELETE_SUFFIX.match(t)
    if m:
        ids = _resolve(m.group(1), world)
        if len(ids) > 1:
            return Plan(kind="needs_clarification", candidates=ids)
        if not ids:
            return None  # the model decides between "no such task" and something else
        task = world.task(ids[0])
        if task.owner != sender:
            return Plan(kind="refused", reason="not_owner")
        return Plan(kind="plan", ops=[DeleteTask(task_id=task.id)])

    tr = parse(t, now)
    m = ADD_TO_PROJECT.match(tr.rest)
    if m:
        project = next((p for p in world.projects if p.lower() == m.group(2).lower()), None)
        if project:
            return Plan(kind="plan", ops=[_create(m.group(1), tr, t, sender, project, world)])

    return None


def create_from_text(body: str, full_text: str, sender: str, project: str, world: World, now: datetime) -> CreateTask:
    """Deterministic task from text. Used by the fast path and the offline fallback."""
    tr = parse(body, now)
    return _create(tr.rest or body, tr, full_text, sender, project, world)


def _create(title_text: str, tr, full_text: str, sender: str, project: str, world: World) -> CreateTask:
    title = clean_title(title_text) or clean_title(full_text)
    return CreateTask(
        title=title,
        project=project,
        labels=labels_for(title, full_text, tr.repeat, world.labels),
        assignee=sender,
        due_at=iso(tr.due),
        reminder_at=iso(tr.due),
        repeat=tr.repeat,
    )
