"""Contract test against a real Vikunja (v2 API).

Skipped unless VIKUNJA_CONTRACT_URL points at a throwaway Vikunja with
registration enabled. scripts/contract-vikunja.sh starts the pinned version
and runs this file. Never point it at the household Vikunja: it registers
users and writes tasks.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from pourover.config import User
from pourover.schema import CreateTask, Repeat
from pourover.service import Service
from pourover.store import Store
from pourover.vikunja import WORLD_LABELS, Vikunja

URL = os.environ.get("VIKUNJA_CONTRACT_URL")
pytestmark = pytest.mark.skipif(not URL, reason="VIKUNJA_CONTRACT_URL not set (see scripts/contract-vikunja.sh)")

IST = timezone(timedelta(hours=5, minutes=30))
PASSWORD = "Contract-Test-9-Battery!"


def register(api, name):
    r = httpx.post(f"{api}/register", json={"username": name, "email": f"{name}@example.test", "password": PASSWORD})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    r = httpx.post(f"{api}/login", json={"username": name, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return uid, r.json()["token"]


@pytest.fixture(scope="module")
def household():
    api = URL.rstrip("/") + "/api/v2"
    tag = uuid.uuid4().hex[:6]
    a_id, a_tok = register(api, f"ravi{tag}")
    b_id, b_tok = register(api, f"meera{tag}")
    auth = {"Authorization": f"Bearer {a_tok}"}
    projects = {}
    for title in ("Home", "Bills", "Groceries"):
        r = httpx.post(f"{api}/projects", headers=auth, json={"title": title})
        assert r.status_code == 201, r.text
        projects[title] = r.json()["id"]
        r = httpx.post(f"{api}/projects/{projects[title]}/users", headers=auth,
                       json={"username": f"meera{tag}", "permission": 1})
        assert r.status_code == 201, r.text
    users = {
        "user_a": User("user_a", "Ravi", "mg-a", a_id, a_tok),
        "user_b": User("user_b", "Meera", "mg-b", b_id, b_tok),
    }
    return users, projects


def test_world_sees_projects_and_creates_labels(household):
    users, projects = household
    v = Vikunja(URL, users["user_a"].vikunja_token)
    world, project_ids, label_ids = v.world({u.vikunja_user_id: k for k, u in users.items()}, {})
    assert set(projects) <= set(world.projects)
    assert sorted(label_ids) == sorted(WORLD_LABELS)
    _, _, again = v.world({}, {})
    assert again == label_ids  # created once, then found


def test_create_with_due_reminder_repeat_labels_assignee(household):
    users, projects = household
    a, b = users["user_a"], users["user_b"]
    v = Vikunja(URL, a.vikunja_token)
    _, project_ids, label_ids = v.world({}, {})
    op = CreateTask(title="Pay rent", project="Bills", labels=["pourover", "urgent"], assignee="user_b",
                    due_at="2026-11-11T18:00:00+05:30", reminder_at="2026-11-11T18:00:00+05:30",
                    repeat=Repeat(every=1, unit="week", weekday="wed"))
    task = v.create(op, project_ids["Bills"], [label_ids["pourover"], label_ids["urgent"]], b.vikunja_user_id)

    seen_by_b = {t["id"]: t for t in Vikunja(URL, b.vikunja_token).open_tasks()}
    t = seen_by_b[task["id"]]  # shared project: Meera sees Ravi's task
    assert t["title"] == "Pay rent" and t["created_by"]["id"] == a.vikunja_user_id
    assert datetime.fromisoformat(t["due_date"]) == datetime(2026, 11, 11, 18, 0, tzinfo=IST)
    assert [datetime.fromisoformat(r["reminder"]) for r in t["reminders"]] == [datetime(2026, 11, 11, 18, 0, tzinfo=IST)]
    assert t["repeat_after"] == 7 * 86400
    assert sorted(lb["title"] for lb in t["labels"]) == ["pourover", "urgent"]
    assert [u["id"] for u in t["assignees"]] == [b.vikunja_user_id]


def test_monthly_repeat_and_done_reopens(household):
    users, _ = household
    v = Vikunja(URL, users["user_a"].vikunja_token)
    _, project_ids, _ = v.world({}, {})
    op = CreateTask(title="Pay maid salary", project="Bills", labels=[], assignee="user_a",
                    due_at="2026-12-01T09:00:00+05:30", repeat=Repeat(every=1, unit="month"))
    task = v.create(op, project_ids["Bills"], [], None)
    after = v.complete(task["id"])
    assert after["done"] is False  # repeating: re-opened
    assert datetime.fromisoformat(after["due_date"]) == datetime(2027, 1, 1, 9, 0, tzinfo=IST)


def test_done_one_off_leaves_the_open_list(household):
    users, _ = household
    v = Vikunja(URL, users["user_a"].vikunja_token)
    _, project_ids, _ = v.world({}, {})
    task = v.create(CreateTask(title="Fix wobbly chair", project="Home", labels=[], assignee="user_a"),
                    project_ids["Home"], [], None)
    open_ids = {t["id"]: t for t in v.open_tasks()}
    assert open_ids[task["id"]]["due_date"].startswith("0001-01-01")  # how Vikunja says "no date"
    assert v.complete(task["id"])["done"] is True
    assert task["id"] not in {t["id"] for t in v.open_tasks()}


def test_delete(household):
    users, _ = household
    v = Vikunja(URL, users["user_a"].vikunja_token)
    _, project_ids, _ = v.world({}, {})
    task = v.create(CreateTask(title="Temp", project="Home", labels=[], assignee="user_a"), project_ids["Home"], [], None)
    v.delete(task["id"])
    assert task["id"] not in {t["id"] for t in v.open_tasks()}


def test_service_end_to_end_without_a_model(household, tmp_path):
    """The real service, real Vikunja, no model: fast path and offline fallback."""
    users, _ = household
    now = datetime(2026, 11, 10, 9, 15, tzinfo=IST)
    svc = Service(users, lambda u: Vikunja(URL, u.vikunja_token), Store(str(tmp_path / "e2e.db")), None,
                  _NoNtfy(), lambda: now)
    a, b = users["user_a"], users["user_b"]

    out = svc.handle(a, "add batteries to home tomorrow evening")
    assert out.startswith("Added: Batteries → Home · Wed 11 Nov 18:00"), out
    assert "Batteries" in svc.handle(b, "what's due this week")  # Meera sees Ravi's task
    assert "only they can delete" in svc.handle(b, "delete batteries")  # pourOver's rule, not Vikunja's
    assert "Reply yes" in svc.handle(a, "delete batteries")
    assert svc.handle(a, "yes") == "Deleted: Batteries"
    assert "Inbox" in svc.handle(a, "remind me to call the bank friday 5pm")  # no model: timed message to Inbox
    assert svc.handle(a, "done call the bank").startswith("Done: Call the bank ✓")


class _NoNtfy:
    def send(self, *a, **k):
        return False
