"""Short, plain replies that always say whether anything changed."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from .schema import CreateTask
from .world import TaskRef, World

NOTHING_CHANGED = "Nothing changed."


def when(dt: Optional[datetime | str], tz=None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if tz is not None:
        dt = dt.astimezone(tz)
    return dt.strftime("%a %d %b %H:%M").replace(" 0", " ")


def repeat_text(op: CreateTask) -> str:
    r = op.repeat
    if r is None:
        return ""
    unit = {"day": "day", "week": "week", "month": "month"}[r.unit]
    base = f"every {unit}" if r.every == 1 else f"every {r.every} {unit}s"
    return base + (f" ({r.weekday.title()})" if r.weekday else "")


def created(op: CreateTask, world: World, sender: str) -> str:
    parts = [f"{op.title} → {op.project}"]
    if op.due_at:
        parts.append(when(op.due_at))
    if op.repeat:
        parts.append("repeats " + repeat_text(op))
    if op.assignee != sender:
        parts.append(f"for {world.users.get(op.assignee, op.assignee)}")
    extra = [lb for lb in op.labels if lb != "pourover"]
    if extra:
        parts.append(" ".join("#" + lb for lb in extra))
    return "Added: " + " · ".join(parts)


def due_list(world: World, window: str, now: datetime) -> str:
    end_today = datetime.combine(now.date(), time(23, 59, 59), tzinfo=now.tzinfo)
    if window == "overdue":
        limit, title = now, "Overdue"
    elif window == "week":
        days_to_sunday = 6 - now.weekday()
        limit, title = end_today + timedelta(days=days_to_sunday), "Due this week"
    else:
        limit, title = end_today, "Due today (and overdue)"
    items = sorted((t for t in world.open_tasks() if t.due_at and t.due_at <= limit), key=lambda t: t.due_at)
    if window == "overdue":
        items = [t for t in items if t.due_at < now]
    if not items:
        return f"{title}: nothing. 🎉"
    lines = [f"{title}:"]
    for t in items:
        flag = " ⚠️" if t.due_at < now else ""
        lines.append(f"• {t.title} ({world.users.get(t.owner, t.owner)}, {when(t.due_at, now.tzinfo)}){flag}")
    return "\n".join(lines)


def clarify(ids: list[int], world: World) -> str:
    if not ids:
        return f"Couldn't find an open task matching that. {NOTHING_CHANGED}"
    opts = [world.task(i) for i in ids]
    listed = "  ".join(f"{n}) {t.title} ({world.users.get(t.owner, t.owner)})" for n, t in enumerate(opts, 1) if t)
    return f"Which one? {listed}. Send it again with the full name. {NOTHING_CHANGED}"


def refused(task: Optional[TaskRef], world: World) -> str:
    who = world.users.get(task.owner, "someone else") if task else "someone else"
    return f"That task belongs to {who}, so only they can delete it. {NOTHING_CHANGED}"


NO_PLAN = f"Couldn't turn that into tasks. {NOTHING_CHANGED} Try: buy eggs tomorrow evening"
INVALID = f"Couldn't file that. {NOTHING_CHANGED}"
QUEUED = "AI is napping. Saved: I'll file it when it's back and tell you on ntfy (gives up after {hours} h)."
OFFLINE_NOTE = "(AI is napping, so it went to Inbox.)"
