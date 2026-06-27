"""Phase 3 Verify — grounded bridges + grounding guard."""
from app import db
from app.llm import generate_bridge, grounded_shared
from app.recommender import recommend

ALL_USERS = [
    "comfort-looper", "aspirational-explorer", "lapsed-digger",
    "active-digger", "mood-listener", "genre-curious",
]


def test_every_shown_bridge_is_grounded():
    for uid in ALL_USERS:
        profile = db.get_taste_profile(uid)
        valid_set = set(profile["top_genres"]) | set(profile["top_moods"])
        recs = recommend(uid, comfort=0.5, k=5)
        assert recs, f"no recs for {uid}"
        for r in recs:
            track = r["track"]
            bridge = generate_bridge(uid, profile, track)
            assert bridge is not None, f"{uid}: bridge dropped for shown track"
            assert bridge["shared"], f"{uid}: empty shared"
            track_attrs = set(track.get("genres") or []) | set(track.get("moods") or [])
            for tag in bridge["shared"]:
                assert tag in valid_set, f"{uid}: '{tag}' not in listener profile"
                assert tag in track_attrs, f"{uid}: '{tag}' not in track metadata"


def test_bridge_word_limit():
    uid = "comfort-looper"
    profile = db.get_taste_profile(uid)
    for r in recommend(uid, comfort=0.3, k=5):
        bridge = generate_bridge(uid, profile, r["track"])
        assert len(bridge["bridge_text"].split()) <= 20  # ~16-word target + slack


def test_ungrounded_candidate_is_dropped():
    profile = db.get_taste_profile("comfort-looper")  # soul/pop/indie listener
    alien = {
        "id": "fake-alien-track",
        "title": "Nothing In Common",
        "artist": "Test Artist",
        "artist_id": "test-artist",
        "genres": ["metal"],          # not in listener top_genres
        "moods": ["intense", "dark"], # not in listener top_moods
        "era": "1980s",
        "audio_features": {},
    }
    assert grounded_shared(profile, alien) == []
    assert generate_bridge("comfort-looper", profile, alien) is None


def test_bridge_is_cached():
    uid = "active-digger"
    profile = db.get_taste_profile(uid)
    track = recommend(uid, 0.5, 5)[0]["track"]
    first = generate_bridge(uid, profile, track)
    cached = db.get_cached_bridge(uid, track["id"])
    assert cached is not None
    assert cached["bridge_text"] == first["bridge_text"]
