from fastapi.testclient import TestClient

from pourover.app import create_app
from pourover.config import Settings
from pourover.service import Service
from pourover.store import Store

from .conftest import NOW
from .fakes import USERS, FakeNtfy, FakeVikunja


def make(world, tmp_path):
    from zoneinfo import ZoneInfo
    settings = Settings(db_path=str(tmp_path / "a.db"), inbound_token="s3cret", vikunja_url="http://v", llm_url=None,
                        llm_model="t", ntfy_url=None, tz=ZoneInfo("Asia/Kolkata"), queue_expiry_hours=6,
                        queue_interval_s=3600, users=USERS)
    svc = Service(USERS, lambda u: FakeVikunja(world), Store(settings.db_path), None, FakeNtfy(), lambda: NOW)
    return TestClient(create_app(settings, svc))


def test_healthz(world, tmp_path):
    with make(world, tmp_path) as c:
        assert c.get("/healthz").json() == {"status": "ok", "db": True}


def test_inbound_requires_token_and_known_sender(world, tmp_path):
    with make(world, tmp_path) as c:
        body = {"sender": "mg-1", "text": "whats due today"}
        assert c.post("/inbound", json=body).status_code == 401
        assert c.post("/inbound", json={**body, "sender": "stranger"}, headers={"X-Pourover-Token": "s3cret"}).status_code == 403
        r = c.post("/inbound", json=body, headers={"X-Pourover-Token": "s3cret"})
        assert r.status_code == 200 and "Pay electricity bill" in r.json()["reply"]
