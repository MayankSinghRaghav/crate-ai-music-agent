"""Embeddings.

Stub mode (no OpenAI key): a *feature-based* deterministic embedding — multi-hot
over genres/moods/era plus normalised audio features, L2-normalised. Unlike a
random hash, cosine similarity here is semantically meaningful: tracks that share
genre/mood/energy sit close, so the comfort dial and grounded bridges work with
zero API keys.

Live mode (OpenAI key set): text-embedding-3-large over a text description of the
track. The rest of the system is dimension-agnostic, so the two paths swap freely.
"""
from __future__ import annotations

import logging

import numpy as np

from .config import settings

logger = logging.getLogger("crate.embeddings")

# Feature-block weights — genre/mood dominate the taste signal; audio adds the
# continuous "bridgeable" component that links tracks across genres.
GENRE_W, MOOD_W, ERA_W, AUDIO_W = 1.0, 0.7, 0.5, 0.4


def l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def build_vocab(tracks: list[dict]) -> dict:
    genres, moods, eras = set(), set(), set()
    for t in tracks:
        genres.update(t.get("genres") or [])
        moods.update(t.get("moods") or [])
        if t.get("era"):
            eras.add(t["era"])
    return {"genres": sorted(genres), "moods": sorted(moods), "eras": sorted(eras)}


def _tempo_norm(tempo) -> float:
    try:
        return min(1.0, max(0.0, (float(tempo) - 60.0) / 100.0))
    except (TypeError, ValueError):
        return 0.5


def stub_embed_track(track: dict, vocab: dict) -> list[float]:
    af = track.get("audio_features") or {}
    tg, tm, te = set(track.get("genres") or []), set(track.get("moods") or []), track.get("era")
    vec: list[float] = []
    vec += [GENRE_W if g in tg else 0.0 for g in vocab["genres"]]
    vec += [MOOD_W if m in tm else 0.0 for m in vocab["moods"]]
    vec += [ERA_W if e == te else 0.0 for e in vocab["eras"]]
    vec += [
        AUDIO_W * float(af.get("energy", 0.5)),
        AUDIO_W * float(af.get("valence", 0.5)),
        AUDIO_W * float(af.get("acousticness", 0.5)),
        AUDIO_W * _tempo_norm(af.get("tempo", 110)),
    ]
    return l2_normalize(np.asarray(vec, dtype=np.float32)).tolist()


def _track_text(track: dict) -> str:
    af = track.get("audio_features") or {}
    return (
        f"{track.get('title','')} by {track.get('artist','')}. "
        f"Genres: {', '.join(track.get('genres') or [])}. "
        f"Moods: {', '.join(track.get('moods') or [])}. "
        f"Era: {track.get('era','')}. "
        f"Energy {af.get('energy')}, valence {af.get('valence')}, "
        f"acousticness {af.get('acousticness')}, tempo {af.get('tempo')}."
    )


def _openai_embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI  # lazy import — only when a key is present

    client = OpenAI(api_key=settings.openai_api_key)
    out: list[list[float]] = []
    # batch to stay well within request limits
    for i in range(0, len(texts), 128):
        chunk = texts[i : i + 128]
        resp = client.embeddings.create(model=settings.embed_model, input=chunk)
        for item in resp.data:
            out.append(l2_normalize(np.asarray(item.embedding, dtype=np.float32)).tolist())
    return out


def embed_tracks(tracks: list[dict]) -> tuple[list[list[float]], dict, str]:
    """Return (vectors, vocab, mode). vocab is {} in live mode."""
    if settings.embed_stub:
        vocab = build_vocab(tracks)
        vectors = [stub_embed_track(t, vocab) for t in tracks]
        logger.info("Embedded %d tracks via feature-based stub (dim=%d)", len(tracks), len(vectors[0]) if vectors else 0)
        return vectors, vocab, "stub"

    vectors = _openai_embed([_track_text(t) for t in tracks])
    logger.info("Embedded %d tracks via OpenAI %s (dim=%d)", len(tracks), settings.embed_model, len(vectors[0]) if vectors else 0)
    return vectors, {}, "openai"


def weighted_average(vectors: list[list[float]], weights: list[float]) -> list[float]:
    """Weighted mean of unit vectors, re-normalised — used to build taste_vector."""
    if not vectors:
        return []
    mat = np.asarray(vectors, dtype=np.float32)
    w = np.asarray(weights, dtype=np.float32).reshape(-1, 1)
    avg = (mat * w).sum(axis=0) / max(float(w.sum()), 1e-9)
    return l2_normalize(avg).tolist()
