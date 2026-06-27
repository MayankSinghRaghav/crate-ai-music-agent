"""Phase 7 Verify — Discovery Missions.

Create "into jazz" -> dig includes mission items -> simulate -> progress
increments -> completion + celebration.
"""
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def _play(uid, track_id, action="played"):
    return client.post("/events", json={"user_id": uid, "track_id": track_id, "action": action})


def test_catalog_genres_exposes_jazz():
    genres = client.get("/catalog/genres").json()
    assert len(genres) >= 10
    jazz = next(g for g in genres if g["genre"] == "jazz")
    assert jazz["artists"] >= 3  # enough to plan an on-ramp


def test_create_mission_into_jazz_returns_3_week_plan():
    uid = "genre-curious"
    db.reset_runtime(uid)
    r = client.post("/missions", json={"user_id": uid, "target_genre": "jazz"})
    assert r.status_code == 200
    m = r.json()
    assert m["status"] == "active"
    assert m["target_genre"] == "jazz"
    assert len(m["weeks"]) == 3

    jazz_artist_ids = {t["artist_id"] for t in db.tracks_by_genre("jazz")}
    all_artists = set()
    for w in m["weeks"]:
        assert w["theme"]
        assert w["tracks"]
        for t in w["tracks"]:
            assert t["artist_id"] in jazz_artist_ids  # mission never leaves the genre
            all_artists.add(t["artist_id"])
    assert len(all_artists) >= 3
    # a fresh mission starts at zero progress
    assert m["progress"]["adopted_artists"] == 0
    assert m["progress"]["percent"] == 0
    assert m["progress"]["status"] == "active"


def test_dig_includes_mission_items():
    uid = "genre-curious"
    db.reset_runtime(uid)
    client.post("/missions", json={"user_id": uid, "target_genre": "jazz"})
    dig = client.get("/dig", params={"user_id": uid, "comfort": 0.4}).json()
    mission_items = [it for it in dig["items"] if it["surface"] == "mission"]
    assert mission_items, "an active mission must inject mission picks into the dig"
    for it in mission_items:
        assert it["bridge_text"]
        assert "jazz" in it["shared"]  # the target genre is always shown


def test_simulate_advances_progress_to_completion_with_celebration():
    uid = "genre-curious"
    db.reset_runtime(uid)
    client.post("/missions", json={"user_id": uid, "target_genre": "jazz"})

    saw_mission_celebration = False
    completed = False
    last_pct = -1
    for _ in range(5):
        dig = client.get("/dig", params={"user_id": uid, "comfort": 0.4}).json()
        mission_items = [it for it in dig["items"] if it["surface"] == "mission"]
        if not mission_items:
            break
        for it in mission_items:
            _play(uid, it["track"]["id"])
        res = client.post("/dev/simulate", params={"user_id": uid, "days": 4, "plays": 1}).json()
        if res.get("celebration") and "mission" in res["celebration"].lower():
            saw_mission_celebration = True

        m = client.get(f"/missions/{uid}").json()
        assert m is not None
        pct = m["progress"]["percent"]
        assert pct >= last_pct  # progress never goes backwards
        last_pct = pct
        if m["status"] == "completed":
            completed = True
            break

    assert saw_mission_celebration, "adopting a mission artist should celebrate the goal"
    assert completed, "adopting enough mission artists should complete the mission"


def test_mission_prompts_substitute_without_format_keyerror():
    """The system prompts embed literal JSON braces; substitution must use replace,
    not str.format (which would raise KeyError: '"weeks"' on the live LLM path)."""
    from app import llm

    s = llm.MISSION_SYSTEM.replace("{genre}", "jazz")
    assert "{genre}" not in s and '"weeks"' in s  # placeholders gone, JSON intact
    b = llm.MISSION_BRIDGE_SYSTEM.replace("{genre}", "jazz").replace("{week}", "1")
    assert "{genre}" not in b and "{week}" not in b and '"bridge"' in b


def test_llm_plan_path_dedupes_artists(monkeypatch):
    """Exercise the non-stub planning branch: it must drop repeated artists and
    still build the prompt (covers the .replace regression end-to-end)."""
    from collections import Counter
    from types import SimpleNamespace

    from app import llm

    cands = db.tracks_by_genre("jazz")
    counts = Counter(t["artist_id"] for t in cands)
    dup_artist = next(a for a, c in counts.items() if c >= 2)
    dup_ids = [t["id"] for t in cands if t["artist_id"] == dup_artist][:2]
    distinct_others, seen = [], set()
    for t in cands:
        if t["artist_id"] != dup_artist and t["artist_id"] not in seen:
            seen.add(t["artist_id"])
            distinct_others.append(t)

    fake_plan = {"weeks": [
        {"week": 1, "theme": "wk1", "track_ids": dup_ids + [distinct_others[0]["id"]]},
        {"week": 2, "theme": "wk2", "track_ids": [distinct_others[1]["id"]]},
        {"week": 3, "theme": "wk3", "track_ids": [distinct_others[2]["id"]]},
    ]}
    monkeypatch.setattr(llm, "settings", SimpleNamespace(llm_stub=False))
    monkeypatch.setattr(llm, "_llm_json", lambda *a, **k: fake_plan)

    plan = llm.plan_mission_weeks("jazz", {}, cands)
    artist_of = {t["id"]: t["artist_id"] for t in cands}
    week1 = [artist_of[i] for i in plan["weeks"][0]["track_ids"]]
    assert len(week1) == len(set(week1)), "a week must not repeat an artist"
    assert len(plan["weeks"]) == 3 and all(w["track_ids"] for w in plan["weeks"])


def test_create_mission_unknown_user_404():
    r = client.post("/missions", json={"user_id": "nobody", "target_genre": "jazz"})
    assert r.status_code == 404


def test_end_mission():
    uid = "lapsed-digger"
    db.reset_runtime(uid)
    client.post("/missions", json={"user_id": uid, "target_genre": "afrobeat"})
    assert client.get(f"/missions/{uid}").json() is not None
    assert client.delete(f"/missions/{uid}").json()["ended"] is True
    assert client.get(f"/missions/{uid}").json() is None
