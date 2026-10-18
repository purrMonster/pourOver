"""Pins the requests pourOver sends to Vikunja. The real contract test against a
pinned Vikunja container is backlog S5.2.1."""

import json

import httpx

from pourover.schema import CreateTask, Repeat
from pourover.vikunja import Vikunja


def client(responses):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.url.params, request.content and json.loads(request.content),
                     request.headers.get("authorization")))
        return httpx.Response(200, json=responses.get((request.method, request.url.path), {}))

    return Vikunja("http://vik:3456/", "tok", client=httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_create_sends_task_labels_and_assignee():
    v, seen = client({("PUT", "/api/v1/projects/3/tasks"): {"id": 77}})
    op = CreateTask(title="Clean litter box", project="Pets", labels=["chores", "pourover"], assignee="user_a",
                    due_at="2026-11-11T20:00:00+05:30", reminder_at="2026-11-11T20:00:00+05:30",
                    repeat=Repeat(every=1, unit="day"))
    assert v.create(op, 3, [1, 2], 9)["id"] == 77
    method, path, _, body, auth = seen[0]
    assert (method, path, auth) == ("PUT", "/api/v1/projects/3/tasks", "Bearer tok")
    assert body["due_date"] == "2026-11-11T20:00:00+05:30"
    assert body["reminders"] == [{"reminder": "2026-11-11T20:00:00+05:30"}]
    assert body["repeat_after"] == 86400
    assert [(m, p, b) for m, p, _, b, _ in seen[1:]] == [
        ("PUT", "/api/v1/tasks/77/labels", {"label_id": 1}),
        ("PUT", "/api/v1/tasks/77/labels", {"label_id": 2}),
        ("PUT", "/api/v1/tasks/77/assignees", {"user_id": 9}),
    ]


def test_weekly_and_monthly_repeat():
    v, seen = client({("PUT", "/api/v1/projects/1/tasks"): {"id": 1}})
    v.create(CreateTask(title="x", project="Home", labels=[], assignee="a", repeat=Repeat(every=2, unit="week")), 1, [], None)
    v.create(CreateTask(title="y", project="Home", labels=[], assignee="a", repeat=Repeat(every=1, unit="month")), 1, [], None)
    assert seen[0][3]["repeat_after"] == 14 * 86400
    assert seen[1][3]["repeat_mode"] == 1 and "repeat_after" not in seen[1][3]


def test_complete_sends_whole_task_back():
    v, seen = client({("GET", "/api/v1/tasks/5"): {"id": 5, "title": "t", "done": False, "due_date": "x"}})
    v.complete(5)
    assert seen[1][:2] == ("POST", "/api/v1/tasks/5") and seen[1][3] == {"id": 5, "title": "t", "done": True, "due_date": "x"}


def test_world_maps_owners_and_skips_empty_dates():
    v, seen = client({
        ("GET", "/api/v1/projects"): [{"id": 1, "title": "Inbox"}, {"id": 2, "title": "Old", "is_archived": True}],
        ("GET", "/api/v1/labels"): [{"id": 4, "title": "pourover"}, {"id": 5, "title": "random"}],
        ("GET", "/api/v1/tasks/all"): [{"id": 9, "title": "Pay rent", "project_id": 1, "created_by": {"id": 2},
                                        "due_date": "0001-01-01T00:00:00Z", "done": False}],
    })
    world, projects, labels = v.world({2: "user_b"}, {"user_b": "Meera"})
    assert world.projects == ["Inbox"] and labels == {"pourover": 4}
    t = world.tasks[0]
    assert (t.owner, t.project, t.due_at) == ("user_b", "Inbox", None)
    assert seen[2][2]["filter"] == "done = false"
