"""Text embeddings for review docs.

Stub (no OpenAI key): TF-IDF (1-2 grams) — lightweight, deterministic, and good
enough for near-duplicate detection and theme clustering on short review text.
Live: OpenAI text-embedding-3-large for semantic vectors. The pipeline is
embedding-agnostic, so the two swap freely.
"""
from __future__ import annotations

import logging

import numpy as np

from .config import settings

logger = logging.getLogger("ingest.embed")


def _l2(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def embed(texts: list[str]) -> tuple[np.ndarray, str]:
    if settings.embed_stub:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vec = TfidfVectorizer(
            stop_words="english", max_features=512, ngram_range=(1, 2), min_df=1
        )
        X = vec.fit_transform(texts).toarray().astype("float32")
        logger.info("Embedded %d docs via TF-IDF stub (dim=%d)", len(texts), X.shape[1])
        return _l2(X), "tfidf"

    from openai import OpenAI  # lazy

    client = OpenAI(api_key=settings.openai_api_key)
    out: list[list[float]] = []
    for i in range(0, len(texts), 128):
        resp = client.embeddings.create(model=settings.embed_model, input=texts[i : i + 128])
        out.extend(d.embedding for d in resp.data)
    M = np.asarray(out, dtype="float32")
    logger.info("Embedded %d docs via OpenAI %s (dim=%d)", len(texts), settings.embed_model, M.shape[1])
    return _l2(M), "openai"
