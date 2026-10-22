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


def test_model_endpoint_gets_basic_auth_when_a_user_is_set(tmp_path):
    import httpx
    from zoneinfo import ZoneInfo

    from pourover.app import build_service

    base = dict(db_path=str(tmp_path / "b.db"), inbound_token="x", vikunja_url="http://v", llm_url="http://llm",
                llm_model="t", ntfy_url=None, tz=ZoneInfo("Asia/Kolkata"), queue_expiry_hours=6,
                queue_interval_s=60, users=USERS)
    plain = build_service(Settings(**base)).model
    assert plain.client.auth is None
    model = build_service(Settings(**base, llm_user="siamese", llm_password="pw", llm_timeout_s=90)).model
    assert isinstance(model.client.auth, httpx.BasicAuth)
    assert model.client.timeout.read == 90
    request = next(model.client.auth.auth_flow(httpx.Request("POST", "http://llm/v1/chat/completions")))
    assert request.headers["Authorization"] == httpx.BasicAuth("siamese", "pw")._auth_header
