"""In-memory stand-ins for Vikunja so service tests need no network."""

from __future__ import annotations

from datetime import datetime

from pourover.config import User
from pourover.world import TaskRef, World

USERS = {
    "user_a": User("user_a", "Ravi", "mg-1", 1, "tok-a", "pourover-a", "ntfy-a"),
    "user_b": User("user_b", "Meera", "mg-2", 2, "tok-b", "pourover-b", "ntfy-b"),
}


class FakeVikunja:
    def __init__(self, world: World):
        self.projects = {p: i for i, p in enumerate(world.projects, 1)}
        self.labels = {lb: i for i, lb in enumerate(world.labels, 1)}
        self.tasks = {t.id: t for t in world.tasks}
        self.calls: list[tuple] = []
        self.next_id = 500
        self.fail_on_create = False

    def world(self, owners, names):
        w = World(projects=list(self.projects), labels=list(self.labels), users=names,
                  tasks=[t for t in self.tasks.values() if not t.done])
        return w, self.projects, self.labels

    def create(self, op, project_id, label_ids, assignee_id):
        if self.fail_on_create:
            raise RuntimeError("Vikunja said no")
        self.next_id += 1
        owner = "user_a" if assignee_id == 1 else "user_b"
        due = datetime.fromisoformat(op.due_at) if op.due_at else None
        self.tasks[self.next_id] = TaskRef(self.next_id, op.title, op.project, owner, due)
        self.calls.append(("create", op.title, project_id, tuple(label_ids), assignee_id))
        return {"id": self.next_id}

    def complete(self, task_id):
        t = self.tasks[task_id]
        self.tasks[task_id] = TaskRef(t.id, t.title, t.project, t.owner, t.due_at, True)
        self.calls.append(("complete", task_id))
        return {"done": True}

    def delete(self, task_id):
        self.tasks.pop(task_id)
        self.calls.append(("delete", task_id))


class FakeNtfy:
    def __init__(self):
        self.sent = []

    def send(self, topic, token, message, title="pourOver"):
        self.sent.append((topic, message))
        return True
