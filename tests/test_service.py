import json

import httpx
import pytest

from pourover.model import ModelClient
from pourover.service import Service
from pourover.store import Store

from .conftest import NOW
from .fakes import USERS, FakeNtfy, FakeVikunja

A, B = USERS["user_a"], USERS["user_b"]


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env(world, tmp_path):
    vik = FakeVikunja(world)
    ntfy = FakeNtfy()
    clock = Clock(NOW)
    state = {"model_up": False, "answer": None}

    def handler(request):
        if not state["model_up"]:
            raise httpx.ConnectError("roastery asleep")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(state["answer"])}}]})

    model = ModelClient("http://llm", "t", client=httpx.Client(transport=httpx.MockTransport(handler)))
    store = Store(str(tmp_path / "p.db"))
    svc = Service(USERS, lambda u: vik, store, model, ntfy, clock)
    return svc, vik, ntfy, clock, state, store


def test_query_reports_all_users_tasks(env):
    svc, *_ = env
    out = svc.handle(A, "what's due today")
    assert "Pay electricity bill" in out and "Buy milk (Meera" in out and "Return library book" in out
    assert "Renew bike insurance" not in out


def test_done_marks_task(env):
    svc, vik, *_ = env
    assert svc.handle(A, "done electricity bill").startswith("Done: Pay electricity bill")
    assert ("complete", 101) in vik.calls


def test_delete_needs_yes(env):
    svc, vik, *_ = env
    assert "Reply yes" in svc.handle(A, "delete bike insurance")
    assert not any(c[0] == "delete" for c in vik.calls)
    assert svc.handle(A, "yes") == "Deleted: Renew bike insurance"
    assert ("delete", 104) in vik.calls


def test_delete_cancelled_by_other_message(env):
    svc, vik, *_ = env
    svc.handle(A, "delete bike insurance")
    svc.handle(A, "whats due today")
    svc.handle(A, "yes")  # pending was dropped, so this is just a message now
    assert not any(c[0] == "delete" for c in vik.calls)


def test_delete_others_task_refused(env):
    svc, vik, *_ = env
    assert "only they can delete" in svc.handle(A, "delete library book")
    assert not vik.calls


def test_offline_time_files_to_inbox_and_undo(env):
    svc, vik, *_ = env
    out = svc.handle(B, "remind me to pay rent tmrw evening")
    assert "Pay rent → Inbox · Wed 11 Nov 18:00" in out and "napping" in out
    assert "Reply yes" in svc.handle(B, "undo")
    assert svc.handle(B, "haan").startswith("Deleted: Pay rent")


def test_offline_without_time_queues_then_drains(env):
    svc, vik, ntfy, clock, state, store = env
    assert "napping" in svc.handle(A, "palak paneer ka saman")
    assert svc.drain_queue() == 0  # still asleep
    state["model_up"] = True
    state["answer"] = {"kind": "plan", "ops": [
        {"op": "create_task", "title": "Buy spinach", "project": "Groceries", "labels": ["shopping"], "assignee": "user_a"},
        {"op": "create_task", "title": "Buy paneer", "project": "Groceries", "labels": ["shopping"], "assignee": "user_a"}]}
    assert svc.drain_queue() == 1
    assert [c[1] for c in vik.calls if c[0] == "create"] == ["Buy spinach", "Buy paneer"]
    assert ntfy.sent[-1][0] == "pourover-a" and "Buy paneer → Groceries" in ntfy.sent[-1][1]


def test_queue_expires_after_6h(env):
    from datetime import timedelta
    svc, vik, ntfy, clock, state, store = env
    svc.handle(A, "palak paneer ka saman")
    clock.t = NOW + timedelta(hours=7)
    state["model_up"] = True
    assert svc.drain_queue() == 1
    assert "Gave up" in ntfy.sent[-1][1] and not vik.calls


def test_model_assigns_to_partner_and_labels(env):
    svc, vik, ntfy, clock, state, store = env
    state["model_up"] = True
    state["answer"] = {"kind": "plan", "ops": [{"op": "create_task", "title": "Book cab", "project": "Errands",
                       "labels": ["urgent"], "assignee": "user_b", "due_at": "2026-11-13T18:00:00+05:30"}]}
    out = svc.handle(A, "ask meera to book the cab friday evening, urgent")
    assert out.startswith("Added: Book cab → Errands · Fri 13 Nov 18:00 · for Meera · #urgent")
    _, title, project_id, label_ids, assignee = vik.calls[0]
    assert assignee == 2 and len(label_ids) == 2  # pourover + urgent


def test_vikunja_failure_is_reported_and_logged(env):
    svc, vik, ntfy, *_, store = env
    vik.fail_on_create = True
    out = svc.handle(A, "remind me to call bank at 5pm")
    assert "Stopped at an error" in out
    assert store.commands()[-1]["outcome"] == "partial"


def test_every_command_is_logged(env):
    svc, *_, store = env
    for msg in ["whats due today", "asdfgh", "done milk"]:
        svc.handle(A, msg)
    rows = store.commands()
    assert [r["text"] for r in rows] == ["whats due today", "asdfgh", "done milk"]
    assert all(r["reply"] for r in rows)
