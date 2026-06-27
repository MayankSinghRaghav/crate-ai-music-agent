"""Phase 4 Verify — API integration (httpx TestClient)."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_users_returns_six_personas():
    r = client.get("/users")
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 6
    assert all("display_name" in u for u in users)


def test_taste_profile():
    r = client.get("/taste/comfort-looper")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]
    assert body["top_genres"]


def test_dig_returns_3_to_5_grounded_items():
    r = client.get("/dig", params={"user_id": "active-digger", "comfort": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert body["greeting"]
    assert 3 <= len(body["items"]) <= 5
    for item in body["items"]:
        assert item["bridge_text"]
        assert item["shared"]  # grounded
        assert item["track"]["id"]


def test_events_played_persists_to_listening_log():
    db.reset_runtime("mood-listener")
    dig = client.get("/dig", params={"user_id": "mood-listener", "comfort": 0.3}).json()
    track_id = dig["items"][0]["track"]["id"]
    artist_id = dig["items"][0]["track"]["artist_id"]

    before = len(db.unprompted_plays_for_artist("mood-listener", artist_id))
    r = client.post("/events", json={"user_id": "mood-listener", "track_id": track_id, "action": "played"})
    assert r.json()["ok"] is True
    # played-from-dig is prompted, so it must NOT add to the unprompted (adoption) count
    after = len(db.unprompted_plays_for_artist("mood-listener", artist_id))
    assert after == before
    # but it is recorded in the listening log
    with db._connect() as c:
        n = c.execute(
            "select count(*) n from listening_log where user_id='mood-listener' and track_id=?",
            (track_id,),
        ).fetchone()["n"]
    assert n >= 1


def test_feedback_downvote_excludes_artist_next_dig():
    db.reset_runtime("aspirational-explorer")
    dig1 = client.get("/dig", params={"user_id": "aspirational-explorer", "comfort": 0.4}).json()
    target = dig1["items"][0]["track"]
    artist_id = target["artist_id"]

    r = client.post(
        "/feedback",
        json={"user_id": "aspirational-explorer", "track_id": target["id"],
              "sentiment": "down", "reason": "not feeling it"},
    )
    assert r.json()["ok"] is True

    dig2 = client.get("/dig", params={"user_id": "aspirational-explorer", "comfort": 0.4}).json()
    assert all(it["track"]["artist_id"] != artist_id for it in dig2["items"])


def test_dig_unknown_user_404():
    assert client.get("/dig", params={"user_id": "nobody"}).status_code == 404
