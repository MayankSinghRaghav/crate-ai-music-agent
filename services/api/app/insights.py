"""Grounded Q&A over the discovery-opportunity backlog.

The Insights dashboard renders a ranked list of themes mined from public
review sources (see ingest/). This module lets the UI ask natural-language
questions that are answered *only* from those themes, with citations back to
each theme's `rank`. There is deliberately no offline template answer: when no
live LLM provider is configured (or a call fails) the API reports the assistant
as unavailable rather than fabricating a grounded reply.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Optional

from . import llm
from .config import REPO_ROOT

logger = logging.getLogger("crate.insights")

# Canonical source: the daily-refreshed snapshot committed by ingest/. Identical
# to the copy the web app bundles; a single source keeps them from drifting.
SNAPSHOT_PATH = REPO_ROOT / "ingest" / "snapshots" / "opportunities-latest.json"

# Only the fields the model needs to reason + cite. Quotes are capped so a large
# theme can't blow up the prompt.
_MAX_QUOTES = 4
_MAX_HISTORY_TURNS = 6


@lru_cache(maxsize=1)
def load_themes() -> tuple[dict, ...]:
    """Load and cache the opportunity backlog. Empty tuple if unavailable."""
    try:
        raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Insights snapshot unavailable (%s): %s", SNAPSHOT_PATH, exc)
        return ()
    if not isinstance(raw, list):
        return ()
    return tuple(raw)


def _theme_context(t: dict) -> dict:
    return {
        "rank": t.get("rank"),
        "topic": t.get("topic"),
        "sentiment": t.get("sentiment"),
        "segment": t.get("segment"),
        "unmet_need": t.get("unmet_need"),
        "size": t.get("size"),
        "share": t.get("share"),
        "opportunity_score": t.get("opportunity_score"),
        "keywords": t.get("keywords") or [],
        "example_quotes": (t.get("example_quotes") or [])[:_MAX_QUOTES],
    }


def _as_ranks(value: object, valid: set[int]) -> list[int]:
    """Coerce a model-supplied citations list to real, de-duped theme ranks."""
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for v in value:
        try:
            r = int(v)
        except (TypeError, ValueError):
            continue
        if r in valid and r not in out:
            out.append(r)
    return out


def answer(question: str, history: Optional[list[dict]] = None) -> Optional[dict]:
    """Return a grounded, citation-validated answer dict, or None if the
    assistant is unavailable (no live provider / call failed / no data)."""
    themes = load_themes()
    if not themes:
        return None

    turns = [
        {"role": h.get("role"), "content": h.get("content")}
        for h in (history or [])
        if h.get("role") in ("user", "assistant") and h.get("content")
    ][-_MAX_HISTORY_TURNS:]

    out = llm.answer_insights(question, turns, [_theme_context(t) for t in themes])
    if not out:
        return None

    answer_text = str(out.get("answer") or "").strip()
    if not answer_text:
        return None

    valid_ranks = {int(t["rank"]) for t in themes if t.get("rank") is not None}
    citations = _as_ranks(out.get("citations"), valid_ranks)
    refused = bool(out.get("refused"))

    confidence = out.get("confidence")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"
    # Trust guard: an answer that claims to be grounded but cites nothing is
    # not trustworthy — never let it read as high confidence.
    if not refused and not citations:
        confidence = "low"

    return {
        "answer": answer_text,
        "citations": citations,
        "confidence": confidence,
        "refused": refused,
    }
