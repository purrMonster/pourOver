"""A snapshot of what exists: projects, labels, users and open tasks.

The model only ever sees this snapshot, and the validator only accepts plans
that point at things inside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import yaml


@dataclass(frozen=True)
class TaskRef:
    id: int
    title: str
    project: str
    owner: str  # user key, e.g. user_a
    due_at: Optional[datetime] = None
    done: bool = False


@dataclass
class World:
    projects: list[str]
    labels: list[str]
    users: dict[str, str]  # user key -> display name used in messages
    tasks: list[TaskRef] = field(default_factory=list)

    def open_tasks(self) -> list[TaskRef]:
        return [t for t in self.tasks if not t.done]

    def task(self, task_id: int) -> Optional[TaskRef]:
        return next((t for t in self.tasks if t.id == task_id), None)

    def user_by_name(self, name: str) -> Optional[str]:
        name = name.strip().lower()
        return next((k for k, v in self.users.items() if v.lower() == name), None)


def load_world(path: str) -> World:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    tasks = [
        TaskRef(
            id=t["id"],
            title=t["title"],
            project=t["project"],
            owner=t["owner"],
            due_at=datetime.fromisoformat(t["due_at"]) if t.get("due_at") else None,
            done=t.get("done", False),
        )
        for t in raw.get("tasks", [])
    ]
    return World(projects=raw["projects"], labels=raw["labels"], users=raw["users"], tasks=tasks)
