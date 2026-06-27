"""Idempotent seed.

Loads catalog + personas, embeds the catalog, creates the 6 demo users with their
listening history, and builds each taste profile (taste_vector + LLM/stub summary).
Safe to re-run: upserts + per-user seed-history reset mean no duplicates.
"""
from __future__ import annotations

import logging
from collections import Counter

from . import db
from .catalog import get_catalog
from .embeddings import embed_tracks, weighted_average

logger = logging.getLogger("crate.seed")


def _top_moods(history: list[dict], track_by_id: dict[str, dict]) -> list[str]:
    counter: Counter = Counter()
    for h in history:
        t = track_by_id.get(h["track_id"])
        if not t:
            continue
        for m in t.get("moods") or []:
            counter[m] += h.get("plays", 1)
    return [m for m, _ in counter.most_common(3)]


def _top_artists(history: list[dict]) -> list[str]:
    counter: Counter = Counter()
    for h in history:
        counter[h["artist_id"]] += h.get("plays", 1)
    return [a for a, _ in counter.most_common(6)]


def _top_genres(persona: dict, history: list[dict], track_by_id: dict[str, dict]) -> list[str]:
    if persona.get("top_genres"):
        return persona["top_genres"]
    counter: Counter = Counter()
    for h in history:
        t = track_by_id.get(h["track_id"])
        if not t:
            continue
        for g in t.get("genres") or []:
            counter[g] += h.get("plays", 1)
    return [g for g, _ in counter.most_common(3)]


def seed() -> dict:
    db.init_db()
    catalog = get_catalog()
    tracks = catalog.tracks()
    personas = catalog.personas()

    # 1) embed + upsert catalog
    vectors, vocab, mode = embed_tracks(tracks)
    emb_by_id: dict[str, list[float]] = {}
    track_by_id: dict[str, dict] = {}
    for t, v in zip(tracks, vectors):
        db.upsert_track(t, v)
        emb_by_id[t["id"]] = v
        track_by_id[t["id"]] = t
    db.set_meta("embed_vocab", vocab)
    db.set_meta("embed_mode", mode)

    # 2) users + history + taste profiles
    from .llm import taste_summary  # local import keeps Phase 1 deps tidy

    for p in personas:
        uid = p["id"]
        db.upsert_user(
            uid, p["display_name"], float(p.get("comfort_pref", 0.5)),
            p.get("persona"), p.get("mission_seed_genre"),
        )

        history = p.get("listening_history", [])
        db.clear_seed_history(uid)
        for h in history:
            db.insert_listening(
                uid, h["track_id"], h["artist_id"], prompted=False, source="seed"
            )

        # taste_vector = play-weighted average of played-track embeddings
        vecs, weights = [], []
        for h in history:
            emb = emb_by_id.get(h["track_id"])
            if emb:
                vecs.append(emb)
                weights.append(float(h.get("plays", 1)))
        taste_vector = weighted_average(vecs, weights) if vecs else []

        top_artists = _top_artists(history)
        top_genres = _top_genres(p, history, track_by_id)
        top_moods = _top_moods(history, track_by_id)
        summary = taste_summary(top_genres, top_artists, top_moods)
        db.upsert_taste_profile(uid, summary, taste_vector, top_artists, top_genres, top_moods)

    summary = {
        "embed_mode": mode,
        "embed_dim": len(vectors[0]) if vectors else 0,
        "tracks": db.count("catalog_tracks"),
        "users": db.count("users"),
        "taste_profiles": db.count("taste_profile"),
        "listening_log": db.count("listening_log"),
    }
    logger.info("Seed complete: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(seed())
