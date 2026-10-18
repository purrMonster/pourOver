"""Thin Vikunja REST client, one instance per user token.

Endpoints follow the Vikunja v1 API. Pin the Vikunja version in the stack and
keep the contract test (backlog S5.2.1) green before upgrading: field names
and the task filter syntax have changed between releases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from .schema import CreateTask
from .world import TaskRef, World

NO_DATE = "0001-01-01T00:00:00Z"
WORLD_LABELS = ["chores", "pourover", "shopping", "urgent"]
DAY = 86400


def _date(value: Optional[str]) -> Optional[datetime]:
    if not value or value.startswith("0001-01-01"):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class VikunjaError(Exception):
    pass


class Vikunja:
    def __init__(self, base_url: str, token: str, client: Optional[httpx.Client] = None):
        self.api = base_url.rstrip("/") + "/api/v1"
        self.client = client or httpx.Client(timeout=15.0)
        self.headers = {"Authorization": f"Bearer {token}"}

    def _call(self, method: str, path: str, **kw):
        try:
            r = self.client.request(method, self.api + path, headers=self.headers, **kw)
        except httpx.HTTPError as exc:
            raise VikunjaError(f"Vikunja unreachable: {exc}") from exc
        if r.status_code >= 400:
            raise VikunjaError(f"Vikunja {method} {path} -> {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else None

    # ---- reads -------------------------------------------------------
    def projects(self) -> list[dict]:
        return self._call("GET", "/projects", params={"per_page": 200}) or []

    def labels(self) -> list[dict]:
        return self._call("GET", "/labels", params={"per_page": 200}) or []

    def open_tasks(self) -> list[dict]:
        return self._call("GET", "/tasks/all", params={"filter": "done = false", "per_page": 500}) or []

    def task(self, task_id: int) -> dict:
        return self._call("GET", f"/tasks/{task_id}")

    def world(self, owners: dict[int, str], names: dict[str, str]) -> tuple[World, dict, dict]:
        """World snapshot plus name->id maps for projects and labels."""
        projects = {p["title"]: p["id"] for p in self.projects() if not p.get("is_archived")}
        labels = {lb["title"]: lb["id"] for lb in self.labels() if lb["title"] in WORLD_LABELS}
        id_to_project = {v: k for k, v in projects.items()}
        tasks = [
            TaskRef(
                id=t["id"],
                title=t["title"],
                project=id_to_project.get(t.get("project_id"), "?"),
                owner=owners.get((t.get("created_by") or {}).get("id"), "unknown"),
                due_at=_date(t.get("due_date")),
                done=bool(t.get("done")),
            )
            for t in self.open_tasks()
        ]
        world = World(projects=list(projects), labels=sorted(labels), users=names, tasks=tasks)
        return world, projects, labels

    # ---- writes ------------------------------------------------------
    def create(self, op: CreateTask, project_id: int, label_ids: list[int], assignee_id: Optional[int]) -> dict:
        body: dict = {"title": op.title, "description": op.description or ""}
        if op.due_at:
            body["due_date"] = op.due_at
        if op.reminder_at:
            body["reminders"] = [{"reminder": op.reminder_at}]
        if op.repeat:
            if op.repeat.unit == "month":
                body["repeat_mode"] = 1  # monthly, from the due date
            else:
                body["repeat_after"] = op.repeat.every * DAY * (7 if op.repeat.unit == "week" else 1)
        task = self._call("PUT", f"/projects/{project_id}/tasks", json=body)
        for lid in label_ids:
            self._call("PUT", f"/tasks/{task['id']}/labels", json={"label_id": lid})
        if assignee_id is not None:
            self._call("PUT", f"/tasks/{task['id']}/assignees", json={"user_id": assignee_id})
        return task

    def complete(self, task_id: int) -> dict:
        task = self.task(task_id)  # Vikunja updates replace the whole task, so send it back complete
        task["done"] = True
        return self._call("POST", f"/tasks/{task_id}", json=task)

    def delete(self, task_id: int) -> None:
        self._call("DELETE", f"/tasks/{task_id}")
