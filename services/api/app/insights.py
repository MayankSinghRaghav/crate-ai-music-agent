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


# ------------------------------------------------ review classifier ---

# keyword -> frustration type, checked in order (first match wins)
_CLASSIFY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("paywall", "free user", "free plan", "skip limit", "can't skip", "forced shuffle"),
     "Paywall friction"),
    (("mood", "context", "workout", "studying", "study", "chill", "vibe", "energetic"),
     "Mood & context mismatch"),
    (("same song", "same 30", "on repeat", "stuck", "loop", "recycle", "recycled", "shuffle"),
     "Repetitive / stuck in loop"),
    (("algorithm", "recommend", "trust", "understand me", "ignores", "wrong"),
     "Algorithm distrust"),
    (("overwhelm", "too much", "effort", "firehose", "no time", "keep up", "too many"),
     "Discovery effort / overwhelm"),
]

_JTBD = {
    "Paywall friction": "Discover freely without hitting plan limits",
    "Mood & context mismatch": "Get music that fits my current mood and context",
    "Repetitive / stuck in loop": "Hear more of my library, not the same few songs",
    "Algorithm distrust": "Trust that recommendations actually fit me",
    "Discovery effort / overwhelm": "Find good new music without the effort",
    "Other": "Discover new music that sticks",
}

_HIGH_INTENSITY = ("never", "always", "completely", "hate", "worst", "unusable", "every single")


def _stub_classify(review: str) -> dict:
    t = (review or "").lower()
    ftype = next((label for kws, label in _CLASSIFY_RULES if any(k in t for k in kws)), "Other")
    if any(k in t for k in ("free user", "free plan", "paywall")):
        segment = "Free-tier user"
    elif any(k in t for k in ("liked songs", "500", "library")):
        segment = "Active library user"
    elif any(k in t for k in ("busy", "parent", "no time", "commute")):
        segment = "Time-poor listener"
    else:
        segment = "General listener"
    intensity = "high" if any(k in t for k in _HIGH_INTENSITY) else "medium"
    return {
        "frustration_type": ftype,
        "job_to_be_done": _JTBD[ftype],
        "segment": segment,
        "intensity": intensity,
    }


def classify(review: str) -> dict:
    """Classify one review. LLM when configured, deterministic heuristic otherwise
    (so the tool always works, offline and in CI)."""
    out = llm.classify_review(review)
    if not out or not out.get("frustration_type"):
        return _stub_classify(review)
    intensity = str(out.get("intensity", "")).lower()
    if intensity not in ("low", "medium", "high"):
        intensity = "medium"
    stub = _stub_classify(review)
    return {
        "frustration_type": str(out.get("frustration_type") or stub["frustration_type"]),
        "job_to_be_done": str(out.get("job_to_be_done") or stub["job_to_be_done"]),
        "segment": str(out.get("segment") or stub["segment"]),
        "intensity": intensity,
    }


# --------------------------------------------------- core finding ---


def _stub_core_finding(themes: tuple[dict, ...]) -> str:
    ranked = sorted(themes, key=lambda t: t.get("rank", 99))
    top = ranked[:2]
    if not top:
        return "No discovery themes are available yet."
    share = round(sum(float(t.get("share", 0)) for t in top) * 100)
    names = " and ".join(f"“{t.get('topic')}”" for t in top)
    need = top[0].get("unmet_need", "better discovery")
    return (
        f"The top themes — {names} — together account for about {share}% of the "
        f"discovery feedback, pointing to a shared need: {need}."
    )


def core_finding() -> Optional[dict]:
    """A synthesised 'core finding' over the backlog. LLM when configured, else a
    deterministic summary. None only when there are no themes at all."""
    themes = load_themes()
    if not themes:
        return None
    ai = llm.summarize_themes([_theme_context(t) for t in themes])
    return {
        "summary": ai or _stub_core_finding(themes),
        "themes_analysed": len(themes),
        "reviews_analysed": sum(int(t.get("size", 0)) for t in themes),
        "generated": bool(ai),
    }
