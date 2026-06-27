"""Phase 8 Verify — metrics dashboard + engagement guardrail.

Dashboard values match DB queries; driving up skip-rate lowers the comfort
default on the next dig.
"""
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def _play(uid, track_id, action="played"):
    return client.post("/events", json={"user_id": uid, "track_id": track_id, "action": action})


def test_funnel_and_guardrail_match_db():
    uid = "aspirational-explorer"
    db.reset_runtime(uid)
    db.set_comfort_pref(uid, 0.5)
    items = client.get("/dig", params={"user_id": uid, "comfort": 0.5}).json()["items"]
    assert len(items) >= 3

    _play(uid, items[0]["track"]["id"], "played")          # 1 tried
    for it in items[1:]:
        _play(uid, it["track"]["id"], "skipped")           # rest skipped -> high skip-rate

    m = client.get("/metrics/adoption", params={"user_id": uid}).json()

    # funnel maps directly to DB queries
    surfaced = set(db.discovery_artist_ids(uid))
    assert m["surfaced_artists"] == len(surfaced)
    assert m["tried_artists"] == len(surfaced & db.played_artist_ids(uid))
    assert m["tried_artists"] >= 1

    # guardrail reflects skip-rate vs threshold
    assert m["skip_rate"] > m["skip_guardrail_threshold"]
    assert m["guardrail_active"] is True


def test_high_skip_rate_lowers_comfort_default_on_next_dig():
    uid = "mood-listener"
    db.reset_runtime(uid)
    db.set_comfort_pref(uid, 0.5)
    dig = client.get("/dig", params={"user_id": uid, "comfort": 0.5}).json()
    for it in dig["items"]:
        _play(uid, it["track"]["id"], "skipped")  # all skips -> skip_rate well over the limit

    # the agent loop applies the guardrail
    res = client.post("/loop/tick", json={"user_id": uid}).json()
    assert res["comfort_pref"] < 0.5

    # the NEXT dig (no explicit comfort) inherits the lowered default
    nxt = client.get("/dig", params={"user_id": uid}).json()
    assert nxt["comfort"] < 0.5


def test_guardrail_idle_when_engaged():
    uid = "active-digger"
    db.reset_runtime(uid)
    items = client.get("/dig", params={"user_id": uid, "comfort": 0.5}).json()["items"]
    for it in items:
        _play(uid, it["track"]["id"], "played")  # all played -> 0% skip
    m = client.get("/metrics/adoption", params={"user_id": uid}).json()
    assert m["skip_rate"] == 0.0
    assert m["guardrail_active"] is False
