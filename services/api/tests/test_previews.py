"""Audio-preview resolver: iTunes lookup, caching, graceful failure, and the
/catalog/preview endpoint. httpx is mocked so tests stay offline + deterministic.
"""
from fastapi.testclient import TestClient

from app import previews
from app.main import app

client = TestClient(app)

TRACK_ID = "tame-impala-the-less-i-know-the-better"


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _clear():
    previews._cache.clear()


def test_resolves_and_caches(monkeypatch):
    _clear()
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return _FakeResp({"results": [{"previewUrl": "https://audio.example/p.m4a"}]})

    monkeypatch.setattr("httpx.get", fake_get)
    assert previews.preview_url(TRACK_ID) == "https://audio.example/p.m4a"
    # second call is served from cache — no extra HTTP hit
    assert previews.preview_url(TRACK_ID) == "https://audio.example/p.m4a"
    assert calls["n"] == 1


def test_no_results_caches_none(monkeypatch):
    _clear()
    monkeypatch.setattr("httpx.get", lambda *a, **k: _FakeResp({"results": []}))
    assert previews.preview_url(TRACK_ID) is None
    assert TRACK_ID in previews._cache  # negative result cached


def test_lookup_failure_returns_none(monkeypatch):
    _clear()

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("httpx.get", boom)
    assert previews.preview_url(TRACK_ID) is None


def test_unknown_track_returns_none():
    _clear()
    assert previews.preview_url("does-not-exist") is None


def test_endpoint_shape(monkeypatch):
    _clear()
    monkeypatch.setattr(
        "httpx.get", lambda *a, **k: _FakeResp({"results": [{"previewUrl": "https://a/x.m4a"}]})
    )
    r = client.get(f"/catalog/preview/{TRACK_ID}")
    assert r.status_code == 200
    assert r.json() == {"track_id": TRACK_ID, "preview_url": "https://a/x.m4a"}


def test_endpoint_unknown_track_404():
    assert client.get("/catalog/preview/nope").status_code == 404
