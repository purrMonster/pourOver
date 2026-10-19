"""HTTP surface: /inbound for chat adapters, /healthz for Gatus."""

from __future__ import annotations

import hmac
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .meowgram import MeowGramBot, MeowGramClient
from .model import ModelClient
from .ntfy import Ntfy
from .service import Service
from .store import Store
from .vikunja import Vikunja

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class Inbound(BaseModel):
    sender: str = Field(description="meowGram user id")
    text: str = Field(min_length=1, max_length=2000)
    channel: str = "meowgram"


def build_service(settings: Settings) -> Service:
    model = ModelClient(settings.llm_url, settings.llm_model) if settings.llm_url else None
    return Service(
        users=settings.users,
        backend_for=lambda u: Vikunja(settings.vikunja_url, u.vikunja_token),
        store=Store(settings.db_path),
        model=model,
        ntfy=Ntfy(settings.ntfy_url),
        now=lambda: datetime.now(settings.tz),
        queue_expiry_hours=settings.queue_expiry_hours,
    )


def create_app(settings: Settings | None = None, service: Service | None = None) -> FastAPI:
    settings = settings or load_settings()
    service = service or build_service(settings)
    stop = threading.Event()

    def queue_loop():
        while not stop.wait(settings.queue_interval_s):
            try:
                service.drain_queue()
            except Exception:
                logging.getLogger("pourover").exception("queue drain failed")

    threads = [threading.Thread(target=queue_loop, name="queue", daemon=True)]
    if settings.meowgram_url:
        bot = MeowGramBot(
            MeowGramClient(settings.meowgram_url, settings.meowgram_bot_user, settings.meowgram_bot_password,
                           channel_id=settings.meowgram_channel),
            service.handle, settings.users, service.store,
            trigger=settings.meowgram_trigger, bot_username=settings.meowgram_bot_user,
        )
        threads.append(threading.Thread(target=bot.run, args=(stop, settings.meowgram_poll_s), name="meowgram",
                                        daemon=True))

    @asynccontextmanager
    async def lifespan(_app):
        for t in threads:
            t.start()
        yield
        stop.set()

    app = FastAPI(title="pourOver", lifespan=lifespan)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "db": service.store.ping()}

    @app.post("/inbound")
    def inbound(body: Inbound, x_pourover_token: str = Header(default="")):
        if not hmac.compare_digest(x_pourover_token, settings.inbound_token):
            raise HTTPException(status_code=401, detail="bad token")
        user = settings.user_by_meowgram(body.sender)
        if user is None:
            raise HTTPException(status_code=403, detail="unknown sender")
        return {"reply": service.handle(user, body.text, body.channel)}

    return app
