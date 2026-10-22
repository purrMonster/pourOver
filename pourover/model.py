"""Model client for any OpenAI-compatible endpoint (llama-swap / llama.cpp).

The response is constrained to the plan JSON schema, then validated again
with Pydantic. The model gets no tools: it can only return one plan.
"""

from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta
from importlib import resources
from typing import Optional

import httpx
from pydantic import ValidationError

from .schema import Plan, wire_schema
from .timeparse import TimeResult, iso
from .world import World


class ModelUnavailable(Exception):
    """roastery is off, in game mode without the model, or not answering."""


class InvalidPlan(Exception):
    """The model answered, but not with a usable plan."""


def _calendar(now: datetime) -> str:
    lines = []
    for i in range(0, 8):
        d = (now + timedelta(days=i)).date()
        tag = {0: "today", 1: "tomorrow / kal", 2: "day after tomorrow / parso"}.get(i, "")
        lines.append(f"- {d.isoformat()} {calendar.day_name[d.weekday()]}{(' (' + tag + ')') if tag else ''}")
    lines.append("A weekday name means the next one after today (never today).")
    last = calendar.monthrange(now.year, now.month)[1]
    lines.append(f"End of month: {now.date().replace(day=last).isoformat()}")
    return "\n".join(lines)


def build_messages(text: str, sender: str, world: World, now: datetime, hint: Optional[TimeResult] = None) -> list[dict]:
    template = resources.files("pourover").joinpath("prompts/system.md").read_text(encoding="utf-8")
    tasks = "\n".join(
        f"- {t.id} | {t.title} | {t.project} | {t.owner} | {iso(t.due_at) or '-'}" for t in world.open_tasks()[:200]
    ) or "- (none)"
    parser_hint = ""
    if hint is not None and hint.found:
        parser_hint = (
            "A date parser read this message as: "
            f"due_at={iso(hint.due)}, repeat={hint.repeat.model_dump() if hint.repeat else None}. "
            "Use these values unless the message clearly means something else."
        )
    values = {
        "{users}": ", ".join(f"{k}: {v}" for k, v in world.users.items()),
        "{sender}": sender,
        "{sender_name}": world.users.get(sender, sender),
        "{projects}": ", ".join(world.projects),
        "{labels}": ", ".join(world.labels),
        "{tasks}": tasks,
        "{now}": iso(now),
        "{weekday}": calendar.day_name[now.weekday()],
        "{calendar}": _calendar(now),
        "{parser_hint}": parser_hint,
    }
    system = template
    for key, val in values.items():
        system = system.replace(key, val)
    user = f"Message from {sender}:\n<<<\n{text}\n>>>"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class ModelClient:
    def __init__(self, base_url: str, model: str, timeout: float = 30.0, client: Optional[httpx.Client] = None,
                 auth: Optional[tuple[str, str]] = None):
        """auth: HTTP Basic (user, password), for an endpoint behind a login such as
        purrBrews' Authelia in front of llama-swap. None sends no credentials."""
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=timeout, auth=auth)
        self.last_raw: Optional[str] = None  # last model reply, kept for eval reports and debugging

    def plan(self, text: str, sender: str, world: World, now: datetime, hint: Optional[TimeResult] = None) -> Plan:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": build_messages(text, sender, world, now, hint),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "plan", "strict": True, "schema": wire_schema()},
            },
        }
        self.last_raw = None
        try:
            r = self.client.post(f"{self.base_url}/v1/chat/completions", json=body)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ModelUnavailable(str(exc)) from exc
        if r.status_code >= 500 or r.status_code in (404, 408, 429):
            raise ModelUnavailable(f"model endpoint returned {r.status_code}")
        r.raise_for_status()
        try:
            content = r.json()["choices"][0]["message"]["content"]
            self.last_raw = content
            return Plan.model_validate(json.loads(content))
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
            raise InvalidPlan(str(exc)) from exc
