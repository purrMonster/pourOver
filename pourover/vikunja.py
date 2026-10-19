"""Thin Vikunja REST client (API v2), one instance per user token.

Written and checked against Vikunja 2.7.0 (tests/contract). v1 is frozen at
2.4.0 and goes away at 4.0; its /tasks/all route already returns 400 on 2.7.
Keep the contract test green before bumping the pinned Vikunja version.

Things learned against a real 2.7.0 that shape this client:
- Lists come wrapped in {"items": [...], "total_pages": n}, at most 50 per page.
- Labels belong to the user who made them, so each user gets their own set of
  pourOver labels (ensure_labels creates any that are missing).
- Anyone with write access to a shared project can delete any task in it, so
  "delete only your own tasks" is pourOver's rule to enforce, not Vikunja's.
- A task with no due date comes back as 0001-01-01T00:00:00Z.
- Marking a repeating task done re-opens it with the next due date.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from .schema import CreateTask
from .world import TaskRef, World

WORLD_LABELS = ["chores", "pourover", "shopping", "urgent"]
DAY = 86400
MAX_PAGES = 40  # 2,000 items at 50 a page; more than a household will ever have open


def _date(value: Optional[str]) -> Optional[datetime]:
    if not value or value.startswith("0001-01-01"):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class VikunjaError(Exception):
    pass


class Vikunja:
    def __init__(self, base_url: str, token: str, client: Optional[httpx.Client] = None):
        self.api = base_url.rstrip("/") + "/api/v2"
        self.client = client or httpx.Client(timeout=15.0)
        self.headers = {"Authorization": f"Bearer {token}"}
        self._labels_checked = False

    def _call(self, method: str, path: str, *, json=None, params=None, headers=None):
        try:
            r = self.client.request(method, self.api + path, json=json, params=params,
                                    headers={**self.headers, **(headers or {})})
        except httpx.HTTPError as exc:
            raise VikunjaError(f"Vikunja unreachable: {exc}") from exc
        if r.status_code >= 400:
            raise VikunjaError(f"Vikunja {method} {path} -> {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else None

    def _all(self, path: str, params: Optional[dict] = None) -> list[dict]:
        items: list[dict] = []
        page = 1
        while page <= MAX_PAGES:
            body = self._call("GET", path, params={**(params or {}), "page": page, "per_page": 50}) or {}
            items.extend(body.get("items") or [])
            if page >= (body.get("total_pages") or 1):
                break
            page += 1
        return items

    # ---- reads -------------------------------------------------------
    def projects(self) -> list[dict]:
        return self._all("/projects")

    def labels(self) -> list[dict]:
        return self._all("/labels")

    def open_tasks(self) -> list[dict]:
        return self._all("/tasks", {"filter": "done = false"})

    def ensure_labels(self) -> dict[str, int]:
        """Create any missing pourOver labels for this user; returns title -> id."""
        have = {lb["title"]: lb["id"] for lb in self.labels() if lb["title"] in WORLD_LABELS}
        for title in WORLD_LABELS:
            if title not in have:
                have[title] = self._call("POST", "/labels", json={"title": title})["id"]
        self._labels_checked = True
        return have

    def world(self, owners: dict[int, str], names: dict[str, str]) -> tuple[World, dict, dict]:
        """World snapshot plus name->id maps for projects and labels."""
        projects = {p["title"]: p["id"] for p in self.projects() if not p.get("is_archived")}
        if self._labels_checked:
            labels = {lb["title"]: lb["id"] for lb in self.labels() if lb["title"] in WORLD_LABELS}
        else:
            labels = self.ensure_labels()
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
        task = self._call("POST", f"/projects/{project_id}/tasks", json=body)
        for lid in label_ids:
            self._call("POST", f"/tasks/{task['id']}/labels", json={"label_id": lid})
        if assignee_id is not None:
            self._call("POST", f"/tasks/{task['id']}/assignees", json={"user_id": assignee_id})
        return task

    def complete(self, task_id: int) -> dict:
        """Mark done. For a repeating task Vikunja re-opens it with the next due date."""
        return self._call("PATCH", f"/tasks/{task_id}", json={"done": True},
                          headers={"Content-Type": "application/merge-patch+json"})

    def delete(self, task_id: int) -> None:
        self._call("DELETE", f"/tasks/{task_id}")
