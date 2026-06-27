"""Theme clustering.

Default: KMeans with k auto-selected by silhouette (lightweight, deterministic,
always installable). BERTopic is the documented production swap — same role
(group reviews into themes), better topic coherence, but a heavy dependency
(torch + sentence-transformers + umap + hdbscan), so it's left out of the
offline-first slice exactly like pgvector/Pinecone in the runtime app.

    # production:
    #   from bertopic import BERTopic
    #   topics, _ = BERTopic(min_topic_size=5).fit_transform(texts, embeddings)
"""
from __future__ import annotations

import logging

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

logger = logging.getLogger("ingest.cluster")


def cluster(vectors: np.ndarray, k_min: int = 4, k_max: int = 8) -> tuple[np.ndarray, int]:
    n = len(vectors)
    if n < 6:
        return np.zeros(n, dtype=int), 1

    hi = min(k_max, n - 1)
    best_k, best_score, best_labels = 1, -2.0, np.zeros(n, dtype=int)
    for k in range(k_min, hi + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(vectors)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(vectors, labels)
        if score > best_score:
            best_k, best_score, best_labels = k, score, labels
    logger.info("Clustered into k=%d themes (silhouette=%.3f)", best_k, best_score)
    return best_labels, best_k
