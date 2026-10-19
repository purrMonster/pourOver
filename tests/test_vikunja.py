"""Pins the requests pourOver sends to Vikunja's v2 API. The live check against a
real, pinned Vikunja is tests/contract (run with scripts/contract-vikunja.sh)."""

import json

import httpx

from pourover.schema import CreateTask, Repeat
from pourover.vikunja import WORLD_LABELS, Vikunja


def client(responses):
    seen = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, dict(request.url.params), body,
                     request.headers.get("authorization"), request.headers.get("content-type")))
        key = (request.method, request.url.path, request.url.params.get("page"))
        resp = responses.get(key, responses.get((request.method, request.url.path), {}))
        return httpx.Response(204 if request.method == "DELETE" else 200, json=None if request.method == "DELETE" else resp)

    return Vikunja("http://vik:3456/", "tok", client=httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_create_sends_task_labels_and_assignee():
    v, seen = client({("POST", "/api/v2/projects/3/tasks"): {"id": 77}})
    op = CreateTask(title="Clean litter box", project="Pets", labels=["chores", "pourover"], assignee="user_a",
                    due_at="2026-11-11T20:00:00+05:30", reminder_at="2026-11-11T20:00:00+05:30",
                    repeat=Repeat(every=1, unit="day"))
    assert v.create(op, 3, [1, 2], 9)["id"] == 77
    method, path, _, body, auth, _ = seen[0]
    assert (method, path, auth) == ("POST", "/api/v2/projects/3/tasks", "Bearer tok")
    assert body["due_date"] == "2026-11-11T20:00:00+05:30"
    assert body["reminders"] == [{"reminder": "2026-11-11T20:00:00+05:30"}]
    assert body["repeat_after"] == 86400
    assert [(m, p, b) for m, p, _, b, _, _ in seen[1:]] == [
        ("POST", "/api/v2/tasks/77/labels", {"label_id": 1}),
        ("POST", "/api/v2/tasks/77/labels", {"label_id": 2}),
        ("POST", "/api/v2/tasks/77/assignees", {"user_id": 9}),
    ]


def test_weekly_and_monthly_repeat():
    v, seen = client({("POST", "/api/v2/projects/1/tasks"): {"id": 1}})
    v.create(CreateTask(title="x", project="Home", labels=[], assignee="a", repeat=Repeat(every=2, unit="week")), 1, [], None)
    v.create(CreateTask(title="y", project="Home", labels=[], assignee="a", repeat=Repeat(every=1, unit="month")), 1, [], None)
    assert seen[0][3]["repeat_after"] == 14 * 86400
    assert seen[1][3]["repeat_mode"] == 1 and "repeat_after" not in seen[1][3]


def test_complete_is_a_merge_patch():
    v, seen = client({("PATCH", "/api/v2/tasks/5"): {"id": 5, "done": True}})
    assert v.complete(5)["done"] is True
    assert seen[0][:2] == ("PATCH", "/api/v2/tasks/5") and seen[0][3] == {"done": True}
    assert seen[0][5] == "application/merge-patch+json"


def test_delete():
    v, seen = client({})
    v.delete(9)
    assert seen[0][:2] == ("DELETE", "/api/v2/tasks/9")


def test_world_pages_maps_owners_and_skips_empty_dates():
    labels = [{"id": i, "title": t} for i, t in enumerate(WORLD_LABELS, 4)] + [{"id": 99, "title": "random"}]
    v, seen = client({
        ("GET", "/api/v2/projects"): {"items": [{"id": 1, "title": "Inbox"}, {"id": 2, "title": "Old", "is_archived": True}],
                                      "total_pages": 1},
        ("GET", "/api/v2/labels"): {"items": labels, "total_pages": 1},
        ("GET", "/api/v2/tasks", "1"): {"items": [{"id": 9, "title": "Pay rent", "project_id": 1, "created_by": {"id": 2},
                                                  "due_date": "0001-01-01T00:00:00Z", "done": False}], "total_pages": 2},
        ("GET", "/api/v2/tasks", "2"): {"items": [{"id": 10, "title": "Call mom", "project_id": 1, "created_by": {"id": 1},
                                                  "due_date": "2026-11-11T09:00:00+05:30", "done": False}], "total_pages": 2},
    })
    world, projects, label_ids = v.world({1: "user_a", 2: "user_b"}, {"user_a": "Ravi", "user_b": "Meera"})
    assert world.projects == ["Inbox"] and "random" not in label_ids and label_ids["pourover"] == 5
    assert [(t.id, t.owner, t.due_at is None) for t in world.tasks] == [(9, "user_b", True), (10, "user_a", False)]
    task_calls = [s for s in seen if s[1] == "/api/v2/tasks"]
    assert [c[2]["page"] for c in task_calls] == ["1", "2"] and task_calls[0][2]["filter"] == "done = false"


def test_missing_labels_are_created_once():
    v, seen = client({
        ("GET", "/api/v2/projects"): {"items": [], "total_pages": 1},
        ("GET", "/api/v2/labels"): {"items": [{"id": 1, "title": "pourover"}], "total_pages": 1},
        ("GET", "/api/v2/tasks"): {"items": [], "total_pages": 1},
        ("POST", "/api/v2/labels"): {"id": 50},
    })
    v.world({}, {})
    created = [s[3]["title"] for s in seen if s[0] == "POST"]
    assert created == ["chores", "shopping", "urgent"]
    v.world({}, {})
    assert len([s for s in seen if s[0] == "POST"]) == 3  # not again
