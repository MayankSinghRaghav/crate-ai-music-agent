"""Vector store abstraction.

`VectorStore` is the seam the spec calls for: the default `LocalNumpyVectorStore`
keeps the MVP to a single data service (SQLite), while `PgVectorStore` documents
the one-env-var swap to Postgres+pgvector (and Pinecone) for production.

Vectors are L2-normalised on write, so cosine similarity == dot product.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

import numpy as np

from . import db
from .config import settings


@dataclass
class Candidate:
    track: dict
    similarity: float


class VectorStore(Protocol):
    def query(
        self, vector: list[float], top: int = 200, exclude_artist_ids: Optional[Iterable[str]] = None
    ) -> list[Candidate]:
        ...


class LocalNumpyVectorStore:
    """In-process cosine search over the catalog embeddings stored in SQLite."""

    def query(
        self, vector: list[float], top: int = 200, exclude_artist_ids: Optional[Iterable[str]] = None
    ) -> list[Candidate]:
        if not vector:
            return []
        exclude = set(exclude_artist_ids or [])
        tracks = db.all_tracks(with_embeddings=True)
        q = np.asarray(vector, dtype=np.float32)
        qn = float(np.linalg.norm(q))
        if qn > 0:
            q = q / qn

        scored: list[Candidate] = []
        for t in tracks:
            if t.get("artist_id") in exclude:
                continue
            emb = t.get("embedding")
            if not emb:
                continue
            v = np.asarray(emb, dtype=np.float32)
            sim = float(np.dot(q, v))  # both unit vectors
            scored.append(Candidate(track={k: t[k] for k in t if k != "embedding"}, similarity=sim))

        scored.sort(key=lambda c: (-c.similarity, c.track["id"]))
        return scored[:top]


class PgVectorStore:
    """Documented production path (Postgres + pgvector).

    Swap in by setting VECTOR_BACKEND=pgvector (and DB_BACKEND=postgres). The query
    becomes a single SQL statement:

        select *, 1 - (embedding <=> :q) as similarity
        from catalog_tracks
        where artist_id <> all(:exclude)
        order by embedding <=> :q
        limit :top;

    Left intentionally unimplemented in the local-first MVP.
    """

    def query(self, vector, top=200, exclude_artist_ids=None):  # pragma: no cover
        raise NotImplementedError(
            "VECTOR_BACKEND=pgvector requires DB_BACKEND=postgres (docker compose up). "
            "The local-first MVP uses VECTOR_BACKEND=local."
        )


def get_vectorstore() -> VectorStore:
    if settings.vector_backend in ("pgvector", "pinecone"):
        return PgVectorStore()
    return LocalNumpyVectorStore()
