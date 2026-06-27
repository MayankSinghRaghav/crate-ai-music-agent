"""Near-duplicate removal by embedding cosine (spec: cosine > 0.92).

Reviews get cross-posted and echoed; dedupe stops one loud complaint from
dominating a cluster. Vectors are unit-normalised, so cosine == dot product.
"""
from __future__ import annotations

import logging

import numpy as np

from .sources.base import RawDoc

logger = logging.getLogger("ingest.dedupe")


def dedupe(
    docs: list[RawDoc], vectors: np.ndarray, threshold: float = 0.92
) -> tuple[list[RawDoc], np.ndarray, int]:
    kept_idx: list[int] = []
    for i in range(len(docs)):
        if kept_idx:
            sims = vectors[kept_idx] @ vectors[i]
            if float(sims.max()) > threshold:
                continue
        kept_idx.append(i)
    dropped = len(docs) - len(kept_idx)
    logger.info("Dedupe: %d -> %d (dropped %d near-duplicates @ cos>%.2f)",
                len(docs), len(kept_idx), dropped, threshold)
    return [docs[i] for i in kept_idx], vectors[kept_idx], dropped
