"""Comfort-banded recommender (vector-based, no collaborative filtering).

The comfort dial selects a *similarity band*: comfort 0 serves the listener's
nearest neighbours (safe); comfort 1 serves the farthest still-*bridgeable* tracks
(a stretch you can follow). We realise that band by ranking the candidate pool by
similarity and sliding a k-wide window from the top (comfort 0) toward the
bridgeable tail (comfort 1) — robust to the embedding's similarity distribution,
where a fixed absolute cutoff (the spec's 0.92->0.62) would be brittle.

"Bridgeable" = shares >=1 of the listener's top genres or moods, so every served
track has a real, groundable connection (Phase 3 writes the bridge on top of it).
The point isn't a fancy ranker — it's the loop + memory + explanation around it.
"""
from __future__ import annotations

from . import db
from .vectorstore import Candidate, get_vectorstore


def excluded_artist_ids(user_id: str) -> set[str]:
    """Artists already in rotation OR explicitly down-voted — never served as new."""
    return db.known_artist_ids(user_id) | db.rejected_artist_ids(user_id)


def _is_bridgeable(track: dict, top_genres: set[str], top_moods: set[str]) -> bool:
    return bool(set(track.get("genres") or []) & top_genres) or bool(
        set(track.get("moods") or []) & top_moods
    )


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, float(x)))


def recommend(user_id: str, comfort: float, k: int = 5, *, exclude_track_ids=None) -> list[dict]:
    """Return up to k {track, similarity} dicts, deterministic for a fixed input."""
    prof = db.get_taste_profile(user_id)
    if not prof or not prof.get("taste_vector"):
        return []

    top_genres = set(prof.get("top_genres") or [])
    top_moods = set(prof.get("top_moods") or [])
    skip_tracks = set(exclude_track_ids or [])

    vs = get_vectorstore()
    candidates = vs.query(
        prof["taste_vector"], top=200, exclude_artist_ids=excluded_artist_ids(user_id)
    )
    candidates = [c for c in candidates if c.track["id"] not in skip_tracks]
    if not candidates:
        return []

    # keep only groundable candidates so every bridge holds; fall back if empty
    pool = [c for c in candidates if _is_bridgeable(c.track, top_genres, top_moods)] or candidates

    # candidates arrive sorted by similarity desc; diversify to one-per-artist
    ranked: list[Candidate] = []
    seen_artists: set[str] = set()
    for c in pool:
        aid = c.track.get("artist_id")
        if aid in seen_artists:
            continue
        seen_artists.add(aid)
        ranked.append(c)
    if not ranked:
        return []

    # Comfort selects a target similarity, interpolated across THIS listener's
    # achievable band (nearest -> farthest bridgeable); we then take the k tracks
    # closest to that target. comfort 0 -> their nearest neighbours; comfort 1 ->
    # the bridgeable stretch. (Spec §6.1's lerp, anchored to the real distribution
    # so it bites regardless of the embedding's absolute similarity scale.)
    hi, lo = ranked[0].similarity, ranked[-1].similarity
    target = hi - (hi - lo) * _clamp01(comfort)
    chosen = sorted(ranked, key=lambda c: (abs(c.similarity - target), c.track["id"]))[:k]
    chosen.sort(key=lambda c: (-c.similarity, c.track["id"]))  # nicest-first for display
    return [{"track": c.track, "similarity": round(c.similarity, 4)} for c in chosen]
