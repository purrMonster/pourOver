"""meowGram adapter: pourOver as a bot in the household lounge.

Written against meowGram Release 2's bot API as planned in its
docs/releases/release-2 (epics 2.3 and 2.4), which is not merged yet:

- Bots authenticate with HTTP Basic (an LLDAP account in the bot group).
- New messages: GET /api/messages/sync?after=<RFC 3339>&after_id=<uuid>, oldest
  first, at most 500 a page, header X-Has-More: true when there is more.
- Sending: POST /api/messages with an Idempotency-Key header, so a retried send
  never posts twice. The body shape ({"text_content": ...}) is an assumption
  until UST-2.4.2 lands; it is the field name messages already use.
- 429 carries Retry-After; 503 means back off.

Channels: set MEOWGRAM_CHANNEL to a channel id and the bot reads and posts only
there: it sends channel_id on sync and send, and drops any message whose
channel_id is another channel. meowGram has no channels yet, so these names
(query parameter and body field channel_id, message field channel_id) are the
contract for meowGram to follow when it adds them. With no channel set, the bot
works in the one shared lounge as before.

The trigger (default "@pourover") decides which messages are for pourOver. In
a dedicated channel it can be switched off (MEOWGRAM_TRIGGER empty): then every
message there is a command. The bot always ignores other bots including
itself, and senders it doesn't know.

Delivery is at most once: a message id is recorded before it is handled, so a
crash mid-way can lose a reply (the sender just asks again) but can never file
the same task twice.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from .config import User

log = logging.getLogger("pourover.meowgram")

SYNC_PATH = "/api/messages/sync"
SEND_PATH = "/api/messages"


class MeowGramError(Exception):
    pass


class RetryLater(MeowGramError):
    def __init__(self, seconds: float):
        super().__init__(f"retry in {seconds:.0f}s")
        self.seconds = seconds


@dataclass(frozen=True)
class Message:
    id: str
    sender_id: str
    username: str
    sender_kind: str
    text: str
    created_at: str
    channel_id: str = ""


class MeowGramClient:
    def __init__(self, base_url: str, bot_user: str, bot_password: str, client: Optional[httpx.Client] = None,
                 channel_id: str = ""):
        self.base = base_url.rstrip("/")
        self.channel_id = channel_id
        self.client = client or httpx.Client(timeout=15.0, auth=(bot_user, bot_password))

    def _check(self, r: httpx.Response) -> httpx.Response:
        if r.status_code == 429 or r.status_code == 503:
            try:
                wait = float(r.headers.get("Retry-After", "30"))
            except ValueError:
                wait = 30.0
            raise RetryLater(max(wait, 1.0))
        if r.status_code >= 400:
            raise MeowGramError(f"meowGram {r.request.method} {r.request.url.path} -> {r.status_code}: {r.text[:200]}")
        return r

    def sync(self, after: str, after_id: str = "") -> tuple[list[Message], bool]:
        params = {"after": after}
        if after_id:
            params["after_id"] = after_id
        if self.channel_id:
            params["channel_id"] = self.channel_id
        try:
            r = self._check(self.client.get(self.base + SYNC_PATH, params=params))
        except httpx.HTTPError as exc:
            raise MeowGramError(f"meowGram unreachable: {exc}") from exc
        msgs = [
            Message(
                id=m["id"],
                sender_id=str(m.get("sender_id", "")),
                username=m.get("username", ""),
                sender_kind=m.get("sender_kind") or "human",
                text=m.get("text_content", ""),
                created_at=m["created_at"],
                channel_id=str(m.get("channel_id") or ""),
            )
            for m in r.json() or []
        ]
        return msgs, r.headers.get("X-Has-More", "").lower() == "true"

    def send(self, text: str, idempotency_key: str) -> None:
        try:
            body = {"text_content": text}
            if self.channel_id:
                body["channel_id"] = self.channel_id
            self._check(self.client.post(self.base + SEND_PATH, json=body,
                                         headers={"Idempotency-Key": idempotency_key}))
        except httpx.HTTPError as exc:
            raise MeowGramError(f"meowGram unreachable: {exc}") from exc


def addressed(text: str, trigger: str) -> Optional[str]:
    """The command if the message is for pourOver ("@pourover buy milk" -> "buy milk"), else None.
    With no trigger (a dedicated channel) every message is a command."""
    if not trigger:
        return text.strip()
    m = re.match(rf"^\s*{re.escape(trigger)}\b[\s,:\-]*(.*)$", text, re.I | re.S)
    if not m:
        return None
    return m.group(1).strip()


class MeowGramBot:
    """Polls meowGram, hands addressed messages to the service, posts the replies."""

    def __init__(self, client: MeowGramClient, handle: Callable[[User, str, str], str], users: dict[str, User],
                 store, trigger: str = "@pourover", bot_username: str = "", now: Callable[[], datetime] = None):
        self.client = client
        self.handle = handle
        self.users = users
        self.store = store
        self.trigger = trigger
        self.bot_username = bot_username.lower()
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _user(self, msg: Message) -> Optional[User]:
        for u in self.users.values():
            if u.meowgram_id in (msg.sender_id, msg.username):
                return u
        return None

    def poll_once(self) -> int:
        """One sync pass. Returns how many messages it answered."""
        after, after_id = self.store.get_cursor("meowgram")
        if after is None:  # first start: begin from now, never replay old history
            after, after_id = self.now().astimezone(timezone.utc).isoformat(), ""
            self.store.set_cursor("meowgram", after, after_id)
        answered = 0
        while True:
            msgs, more = self.client.sync(after, after_id)
            for msg in msgs:
                answered += self._process(msg)
                after, after_id = msg.created_at, msg.id
                self.store.set_cursor("meowgram", after, after_id)
            if not more or not msgs:
                return answered

    def _process(self, msg: Message) -> int:
        if self.client.channel_id and msg.channel_id and msg.channel_id != self.client.channel_id:
            return 0  # another channel: not ours, even if the server sent it
        if msg.sender_kind == "bot" or (self.bot_username and msg.username.lower() == self.bot_username):
            return 0
        command = addressed(msg.text, self.trigger)
        if command is None:
            return 0
        if not self.store.mark_seen("meowgram", msg.id):
            return 0  # already handled (at most once)
        user = self._user(msg)
        if user is None:
            log.warning("ignoring message from unknown meowGram user %r", msg.username or msg.sender_id)
            return 0
        if not command:
            reply = f"Tell me what to do, e.g. {(self.trigger + ' ') if self.trigger else ''}buy eggs tomorrow evening"
        else:
            reply = self.handle(user, command, "meowgram")
        self.client.send(f"@{msg.username or user.name} {reply}", idempotency_key=f"pourover-reply-{msg.id}")
        return 1

    def run(self, stop: threading.Event, interval_s: float = 3.0) -> None:
        wait = interval_s
        while not stop.is_set():
            try:
                self.poll_once()
                wait = interval_s
            except RetryLater as exc:
                wait = exc.seconds
                log.info("meowGram asked to back off: %s", exc)
            except Exception:
                wait = min(max(wait * 2, interval_s), 300)
                log.exception("meowGram poll failed; next try in %.0fs", wait)
            stop.wait(wait)
