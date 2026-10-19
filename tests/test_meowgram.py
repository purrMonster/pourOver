"""meowGram adapter against a fake meowGram that follows the Release 2 bot API plan."""

import base64
import json
import threading
from datetime import datetime, timezone

import httpx
import pytest

from pourover.meowgram import MeowGramBot, MeowGramClient, RetryLater, addressed
from pourover.store import Store

from .fakes import USERS

START = datetime(2026, 11, 10, 3, 45, tzinfo=timezone.utc)


class FakeMeowGram:
    """Lounge with an append-only message list; sync pages by (created_at, id)."""

    def __init__(self, page_size=500):
        self.messages = []
        self.sent = []
        self.page_size = page_size
        self.fail_next = None
        self.n = 0
        self.auth_seen = set()

    def post(self, username, text, kind="human", sender_id=None):
        self.n += 1
        self.messages.append({"id": f"00000000-0000-0000-0000-{self.n:012d}", "sender_id": sender_id or f"sid-{username}",
                              "sender_kind": kind, "username": username, "text_content": text,
                              "created_at": f"2026-11-10T04:{self.n:02d}:00Z"})

    def handler(self, request: httpx.Request):
        self.auth_seen.add(request.headers.get("authorization"))
        if self.fail_next:
            code, self.fail_next = self.fail_next, None
            return httpx.Response(code, headers={"Retry-After": "7"})
        if request.method == "GET":
            after = request.url.params["after"].replace("Z", "+00:00")
            after_id = request.url.params.get("after_id", "")
            key = (datetime.fromisoformat(after), after_id)
            rows = [m for m in self.messages
                    if (datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")), m["id"]) > key]
            page = rows[: self.page_size]
            headers = {"X-Has-More": "true"} if len(rows) > self.page_size else {}
            return httpx.Response(200, json=page, headers=headers)
        body = json.loads(request.content)
        key = request.headers["Idempotency-Key"]
        if key not in {k for k, _ in self.sent}:
            self.sent.append((key, body["text_content"]))
        return httpx.Response(201, json={})


@pytest.fixture
def lounge(tmp_path):
    fake = FakeMeowGram()
    client = MeowGramClient("http://mg", "pourover-bot", "pw",
                            client=httpx.Client(transport=httpx.MockTransport(fake.handler), auth=("pourover-bot", "pw")))
    handled = []

    def handle(user, text, channel):
        handled.append((user.key, text, channel))
        return f"ok: {text}"

    users = {k: u.__class__(**{**u.__dict__, "meowgram_id": {"user_a": "ravi", "user_b": "meera"}[k]})
             for k, u in USERS.items()}
    bot = MeowGramBot(client, handle, users, Store(str(tmp_path / "s.db")), bot_username="pourover-bot",
                      now=lambda: START)
    return fake, bot, handled


def test_addressed():
    assert addressed("@pourover buy milk", "@pourover") == "buy milk"
    assert addressed("  @PourOver: kal subah rent", "@pourover") == "kal subah rent"
    assert addressed("@pourover", "@pourover") == ""
    assert addressed("did you tell @pourover?", "@pourover") is None
    assert addressed("@pourovers are great", "@pourover") is None
    assert addressed("buy milk", "@pourover") is None


def test_first_start_skips_history(lounge):
    fake, bot, handled = lounge
    fake.messages.append({"id": "old", "sender_id": "x", "username": "ravi", "sender_kind": "human",
                          "text_content": "@pourover buy milk", "created_at": "2026-11-09T10:00:00Z"})
    assert bot.poll_once() == 0 and handled == []


def test_only_addressed_messages_from_known_humans(lounge):
    fake, bot, handled = lounge
    fake.post("ravi", "dinner at 8?")
    fake.post("meera", "@pourover kal subah rent dena hai")
    fake.post("pourover-bot", "@pourover loop?", kind="bot")
    fake.post("guest", "@pourover delete everything")
    fake.post("ravi", "@pourover what's due today")
    assert bot.poll_once() == 2
    assert handled == [("user_b", "kal subah rent dena hai", "meowgram"), ("user_a", "what's due today", "meowgram")]
    assert [t for _, t in fake.sent] == ["@meera ok: kal subah rent dena hai", "@ravi ok: what's due today"]
    assert fake.auth_seen == {"Basic " + base64.b64encode(b"pourover-bot:pw").decode()}


def test_cursor_survives_restart_and_nothing_is_handled_twice(lounge, tmp_path):
    fake, bot, handled = lounge
    fake.post("ravi", "@pourover buy eggs")
    bot.poll_once()
    bot.store.set_cursor("meowgram", "2026-11-10T03:00:00Z", "")  # e.g. a restored backup with an old cursor
    fake.post("ravi", "@pourover buy bread")
    bot.poll_once()
    assert [t for _, t, _ in handled] == ["buy eggs", "buy bread"]
    assert len(fake.sent) == 2


def test_pages_until_no_more(lounge):
    fake, bot, handled = lounge
    fake.page_size = 2
    for i in range(5):
        fake.post("ravi", f"@pourover task {i}")
    assert bot.poll_once() == 5
    assert [t for _, t, _ in handled] == [f"task {i}" for i in range(5)]


def test_empty_command_gets_a_hint(lounge):
    fake, bot, handled = lounge
    fake.post("meera", "@pourover")
    bot.poll_once()
    assert handled == [] and "e.g. @pourover buy eggs" in fake.sent[0][1]


def test_429_backs_off_with_retry_after(lounge):
    fake, bot, _ = lounge
    fake.fail_next = 429
    with pytest.raises(RetryLater) as exc:
        bot.poll_once()
    assert exc.value.seconds == 7


def test_run_loop_keeps_going_after_errors(lounge):
    fake, bot, handled = lounge
    fake.fail_next = 500
    fake.post("ravi", "@pourover buy eggs")
    stop = threading.Event()
    t = threading.Thread(target=bot.run, args=(stop, 0.05))
    t.start()
    for _ in range(100):
        if handled:
            break
        stop.wait(0.05)
    stop.set()
    t.join(2)
    assert handled == [("user_a", "buy eggs", "meowgram")]


def test_lounge_to_vikunja_end_to_end(tmp_path, world):
    """A message in the lounge, through the real service (fake Vikunja, no model), back to the lounge."""
    from pourover.service import Service
    from .fakes import FakeNtfy, FakeVikunja
    from .conftest import NOW

    fake = FakeMeowGram()
    client = MeowGramClient("http://mg", "pourover-bot", "pw",
                            client=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    users = {k: u.__class__(**{**u.__dict__, "meowgram_id": {"user_a": "ravi", "user_b": "meera"}[k]})
             for k, u in USERS.items()}
    vik = FakeVikunja(world)
    store = Store(str(tmp_path / "e2e.db"))
    svc = Service(users, lambda u: vik, store, None, FakeNtfy(), lambda: NOW)
    bot = MeowGramBot(client, svc.handle, users, store, now=lambda: START)

    fake.post("ravi", "@pourover add batteries to home tomorrow evening")
    fake.post("meera", "@pourover delete batteries")
    bot.poll_once()
    assert fake.sent[0][1].startswith("@ravi Added: Batteries → Home · Wed 11 Nov 18:00")
    assert "only they can delete" in fake.sent[1][1]
    assert [r["channel"] for r in store.commands()] == ["meowgram", "meowgram"]
