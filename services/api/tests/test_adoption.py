"""Phase 6 Verify — adoption loop, North Star metric, time simulation, re-serve."""
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def _play(uid, track_id, action="played"):
    return client.post("/events", json={"user_id": uid, "track_id": track_id, "action": action})


def test_simulate_drives_adoption_and_metric():
    uid = "active-digger"
    db.reset_runtime(uid)
    dig = client.get("/dig", params={"user_id": uid, "comfort": 0.4}).json()
    played = []
    for it in dig["items"][:2]:
        _play(uid, it["track"]["id"])
        played.append(it["track"]["artist_id"])

    # before simulation: nobody adopted (prompted plays don't count)
    m0 = client.get("/metrics/adoption", params={"user_id": uid}).json()
    assert m0["adopted"] == []

    res = client.post("/dev/simulate", params={"user_id": uid, "days": 4, "plays": 1}).json()
    assert res["newly_adopted"], "simulate should flip at least one artist to adopted"
    assert res["celebration"]

    m1 = client.get("/metrics/adoption", params={"user_id": uid}).json()
    assert m1["adopted"], "metrics should list adopted artists"
    assert m1["adoption_rate"] > 0
    adopted_ids = {a["artist_id"] for a in m1["adopted"]}
    assert any(a in adopted_ids for a in played)
    # threshold actually met
    top = m1["adopted"][0]
    assert top["distinct_days"] >= 4 and top["span_weeks"] >= 3


def test_adopted_artist_has_event_row():
    uid = "active-digger"  # adopted in the test above (shared session db)
    rows = db.get_adoptions(uid)
    assert any(r["status"] == "adopted" and r["adopted_at"] for r in rows)


def test_reserve_after_play():
    uid = "mood-listener"
    db.reset_runtime(uid)
    dig = client.get("/dig", params={"user_id": uid, "comfort": 0.3}).json()
    track = dig["items"][0]["track"]
    _play(uid, track["id"])

    dig2 = client.get("/dig", params={"user_id": uid, "comfort": 0.3}).json()
    reserve = [it for it in dig2["items"] if it["surface"] == "re-serve"]
    assert reserve, "a played-not-adopted track should be re-served"
    assert any(it["track"]["id"] == track["id"] for it in reserve)


def test_skip_guardrail_lowers_comfort():
    uid = "genre-curious"
    db.reset_runtime(uid)
    db.set_comfort_pref(uid, 0.5)
    dig = client.get("/dig", params={"user_id": uid, "comfort": 0.5}).json()
    for it in dig["items"]:
        _play(uid, it["track"]["id"], action="skipped")
    res = client.post("/loop/tick", json={"user_id": uid}).json()
    assert res["comfort_pref"] < 0.5  # high skip-rate pulled comfort back


def test_simulate_unknown_user_404():
    assert client.post("/dev/simulate", params={"user_id": "nobody"}).status_code == 404
