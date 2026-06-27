"""Phase 2 Verify — comfort-banded recommender."""
import statistics

from app import db
from app.recommender import recommend


def _mean_sim(recs):
    return statistics.mean(r["similarity"] for r in recs)


def test_comfort_returns_higher_similarity_than_curiosity():
    near = recommend("comfort-looper", comfort=0.0, k=5)
    far = recommend("comfort-looper", comfort=1.0, k=5)
    assert near and far
    assert _mean_sim(near) > _mean_sim(far)


def test_excludes_known_artists():
    known = db.known_artist_ids("aspirational-explorer")
    recs = recommend("aspirational-explorer", comfort=0.5, k=5)
    assert recs
    assert all(r["track"]["artist_id"] not in known for r in recs)


def test_excludes_rejected_artists():
    user = "ravi"  # any seeded user id prefix; use real id below
    user = "lapsed-digger"
    recs_before = recommend(user, comfort=0.4, k=5)
    assert recs_before
    target_artist = recs_before[0]["track"]["artist_id"]
    target_track = recs_before[0]["track"]["id"]
    db.insert_feedback(user, target_track, "down", "not my thing")
    recs_after = recommend(user, comfort=0.4, k=5)
    assert all(r["track"]["artist_id"] != target_artist for r in recs_after)


def test_one_track_per_artist():
    recs = recommend("active-digger", comfort=0.5, k=5)
    artist_ids = [r["track"]["artist_id"] for r in recs]
    assert len(artist_ids) == len(set(artist_ids))


def test_deterministic_for_fixed_input():
    a = recommend("mood-listener", comfort=0.3, k=5)
    b = recommend("mood-listener", comfort=0.3, k=5)
    assert [r["track"]["id"] for r in a] == [r["track"]["id"] for r in b]


def test_returns_k_items():
    recs = recommend("genre-curious", comfort=0.5, k=5)
    assert 1 <= len(recs) <= 5
