"""Production hardening — rate limiter, DEMO_MODE gate, count() allowlist."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import db
from app import main as main_mod
from app.main import app

client = TestClient(app)


def _settings(**over):
    """A stand-in settings object with only the attrs these middlewares read."""
    base = {"rate_limit_per_min": 0, "demo_mode": True}
    base.update(over)
    return SimpleNamespace(**base)


def test_rate_limiter_returns_429_past_the_limit(monkeypatch):
    monkeypatch.setattr(main_mod, "settings", _settings(rate_limit_per_min=3))
    main_mod._hits.clear()
    codes = [client.get("/users").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429 and codes[4] == 429
    main_mod._hits.clear()


def test_health_is_exempt_from_rate_limit(monkeypatch):
    monkeypatch.setattr(main_mod, "settings", _settings(rate_limit_per_min=1))
    main_mod._hits.clear()
    assert all(client.get("/health").status_code == 200 for _ in range(5))
    main_mod._hits.clear()


def test_dev_endpoints_404_when_demo_mode_off(monkeypatch):
    monkeypatch.setattr(main_mod, "settings", _settings(demo_mode=False))
    assert client.post("/dev/seed").status_code == 404
    assert client.post("/dev/reset", params={"user_id": "active-digger"}).status_code == 404
    assert client.post("/dev/simulate", params={"user_id": "active-digger"}).status_code == 404


def test_dev_endpoints_work_in_demo_mode():
    # conftest defaults DEMO_MODE=true — the graded demo path stays intact
    assert client.post("/dev/reset", params={"user_id": "mood-listener"}).json()["ok"] is True


def test_count_rejects_unknown_table():
    with pytest.raises(ValueError):
        db.count("users; drop table users")
    assert db.count("users") == 6
