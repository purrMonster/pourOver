"""Settings from the environment, users from a YAML file. Secrets only via env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import yaml


@dataclass(frozen=True)
class User:
    key: str  # user_a, user_b: the id used in plans and logs
    name: str
    meowgram_id: str
    vikunja_user_id: int
    vikunja_token: str
    ntfy_topic: str | None = None
    ntfy_token: str | None = None


@dataclass(frozen=True)
class Settings:
    db_path: str
    inbound_token: str
    vikunja_url: str
    llm_url: str | None
    llm_model: str
    ntfy_url: str | None
    tz: ZoneInfo
    queue_expiry_hours: int
    queue_interval_s: int
    users: dict[str, User]
    llm_user: str = ""
    llm_password: str = ""
    llm_timeout_s: float = 60.0
    meowgram_url: str | None = None
    meowgram_bot_user: str = ""
    meowgram_bot_password: str = ""
    meowgram_trigger: str = "@pourover"
    meowgram_channel: str = ""
    meowgram_poll_s: float = 3.0

    def user_by_meowgram(self, meowgram_id: str) -> User | None:
        return next((u for u in self.users.values() if u.meowgram_id == str(meowgram_id)), None)


def load_users(path: str, env: dict[str, str]) -> dict[str, User]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    users = {}
    for key, u in (raw.get("users") or {}).items():
        token = env.get(u["vikunja_token_env"], "")
        if not token:
            raise RuntimeError(f"{u['vikunja_token_env']} is not set for {key}")
        users[key] = User(
            key=key,
            name=u["name"],
            meowgram_id=str(u["meowgram_id"]),
            vikunja_user_id=int(u["vikunja_user_id"]),
            vikunja_token=token,
            ntfy_topic=u.get("ntfy_topic"),
            ntfy_token=env.get(u["ntfy_token_env"]) if u.get("ntfy_token_env") else None,
        )
    return users


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    return Settings(
        db_path=env.get("POUROVER_DB", "/data/pourover.db"),
        inbound_token=env["POUROVER_INBOUND_TOKEN"],
        vikunja_url=env["VIKUNJA_URL"].rstrip("/"),
        llm_url=env.get("LLM_URL") or None,
        llm_model=env.get("LLM_MODEL", "pourover"),
        llm_user=env.get("LLM_USER", ""),
        llm_password=env.get("LLM_PASSWORD", ""),
        llm_timeout_s=float(env.get("LLM_TIMEOUT_S", "60")),
        ntfy_url=(env.get("NTFY_URL") or "").rstrip("/") or None,
        tz=ZoneInfo(env.get("POUROVER_TZ", "Asia/Kolkata")),
        queue_expiry_hours=int(env.get("POUROVER_QUEUE_EXPIRY_HOURS", "6")),
        queue_interval_s=int(env.get("POUROVER_QUEUE_INTERVAL_S", "60")),
        users=load_users(env.get("POUROVER_USERS_FILE", "/config/users.yaml"), env),
        meowgram_url=(env.get("MEOWGRAM_URL") or "").rstrip("/") or None,
        meowgram_bot_user=env.get("MEOWGRAM_BOT_USER", ""),
        meowgram_bot_password=env.get("MEOWGRAM_BOT_PASSWORD", ""),
        meowgram_trigger=env.get("MEOWGRAM_TRIGGER", "@pourover"),
        meowgram_channel=env.get("MEOWGRAM_CHANNEL", ""),
        meowgram_poll_s=float(env.get("MEOWGRAM_POLL_S", "3")),
    )
