"""Cluster tagging — topic · sentiment · unmet-need · segment.

Live: Claude reads a sample of each cluster's reviews and returns structured tags.
Stub: keyword/lexicon rules over the cluster text. The stub themes are aligned to
the six research questions so the offline backlog is still decision-useful.
"""
from __future__ import annotations

import json
import logging

from .config import settings

logger = logging.getLogger("ingest.tag")

# theme -> (topic label, unmet need, research question, keywords)
THEMES = [
    ("Recommendations recycle the familiar (echo chamber)",
     "Genuinely novel recommendations that expand taste, not reinforce it",
     "Q2 recommendation frustrations",
     ["echo chamber", "same five", "same artists", "repetitive", "stale", "safe",
      "cautious", "already have", "already follow", "reminder feed"]),
    ("Discovery surfaces don't lead anywhere new",
     "Discovery that introduces artists you'd never have found yourself",
     "Q1 why discovery struggles",
     ["discover weekly", "release radar", "never discover", "find new", "genuinely new",
      "random", "disconnected"]),
    ("Stuck in a listening loop / same songs on repeat",
     "Gentle nudges that expand the rotation without losing comfort",
     "Q4 repeat-listening of the same content",
     ["same 50", "on repeat", "rut", "stuck", "loop", "comfort playlist", "fall back",
      "comfort food"]),
    ("New music never sticks (discovery without adoption)",
     "Reinforcement that converts a first play into a lasting habit",
     "Q4 / core: adoption, not one-off plays",
     ["forget", "stick", "sticks", "once", "rotation", "retention", "habit",
      "adoption", "revisit", "reinforc", "never come back", "convert"]),
    ("No guided on-ramp into a new genre",
     "Staged, goal-based exploration that coaches you into a genre",
     "Q3 listening behaviours users want",
     ["get into", "genre", "jazz", "classical", "afrobeat", "beginner", "on-ramp",
      "guided", "journey", "mission", "progress", "week by week"]),
    ("Recommendations lack a 'why'",
     "A clear bridge explaining why a track fits your existing taste",
     "Q2 recommendation frustrations",
     ["why", "reason", "bridge", "context", "explain", "trust"]),
    ("Discovery is too high-effort / overwhelming",
     "Low-effort discovery that comes to you and respects your time",
     "Q1 / Q5 effort & segments",
     ["overwhelm", "too much", "paralysis", "effort", "energy", "no time",
      "zero effort", "firehose"]),
    ("Users want control over adventurousness",
     "A comfort-to-curiosity control over how far recommendations stretch",
     "Q2 recommendation frustrations",
     ["dial", "slider", "adventurous", "control", "risk", "push me", "out there"]),
]

NEG = ["frustrat", "stale", "repetitive", "same", "stuck", "rut", "loop", "boring",
       "bored", "hate", "annoy", "overwhelm", "give up", "broken", "terrible",
       "never", "no help", "forget", "noise", "paralysis", "too cautious", "echo"]
POS = ["love", "magic", "great", "helps", "discover", "found", "celebrate", "pay for"]

SEGMENTS = [
    ("Time-poor (busy parent)", ["parent", "kids", "mom", "busy", "no time", "after work", "two kids"]),
    ("Power digger", ["crate dig", "deep cuts", "obscure", "power user", "nerd", "serious", "below a certain popularity"]),
    ("Overwhelmed casual", ["casual", "don't want effort", "overwhelm", "beginner", "paralysis", "intimidat"]),
    ("Aspirational explorer", ["high intent", "save", "forget", "aspirational", "want new", "miss out"]),
]


def top_terms(texts: list[str], n: int = 6) -> list[str]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not texts:
        return []
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=200)
        X = vec.fit_transform(texts)
        means = X.mean(axis=0).A1
        terms = vec.get_feature_names_out()
        order = means.argsort()[::-1][:n]
        return [terms[i] for i in order]
    except ValueError:
        return []


def _score_keywords(blob: str, keywords: list[str]) -> int:
    return sum(blob.count(k) for k in keywords)


def _stub_tag(texts: list[str]) -> dict:
    blob = " \n ".join(texts).lower()
    theme = max(THEMES, key=lambda t: _score_keywords(blob, t[3]))
    seg = max(SEGMENTS, key=lambda s: _score_keywords(blob, s[1]))
    seg_label = seg[0] if _score_keywords(blob, seg[1]) > 0 else "General listener"
    neg = sum(blob.count(w) for w in NEG)
    pos = sum(blob.count(w) for w in POS)
    sentiment = "negative" if neg > pos * 1.5 else ("positive" if pos > neg else "mixed")
    return {
        "topic": theme[0],
        "unmet_need": theme[1],
        "research_question": theme[2],
        "segment": seg_label,
        "sentiment": sentiment,
        "keywords": top_terms(texts, 6),
    }


TAG_SYSTEM = (
    "You analyse clusters of user reviews about a music app's discovery. "
    "Given sample reviews from ONE cluster, return JSON: "
    '{"topic": "<short theme>", "sentiment": "negative|mixed|positive", '
    '"unmet_need": "<the underlying unmet need>", '
    '"segment": "<user segment, e.g. busy parent / power digger / casual>"}. '
    "Be specific and grounded in the reviews."
)


def _extract_json(text: str) -> dict | None:
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except json.JSONDecodeError:
            return None
    return None


def _groq_tag(texts: list[str]) -> dict | None:
    try:
        import httpx

        body = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": TAG_SYSTEM},
                {"role": "user", "content": json.dumps({"reviews": texts[:12]})},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
            "max_tokens": 300,
        }
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json=body, timeout=30,
        )
        r.raise_for_status()
        return _extract_json(r.json()["choices"][0]["message"]["content"])
    except Exception as exc:
        logger.warning("Groq tag failed (%s); using stub.", exc)
        return None


def _gemini_tag(texts: list[str]) -> dict | None:
    try:
        import httpx

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
        )
        body = {
            "system_instruction": {"parts": [{"text": TAG_SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps({"reviews": texts[:12]})}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 300,
                                 "responseMimeType": "application/json"},
        }
        r = httpx.post(url, params={"key": settings.gemini_api_key}, json=body, timeout=30)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json(text)
    except Exception as exc:
        logger.warning("Gemini tag failed (%s); using stub.", exc)
        return None


def _claude_tag(texts: list[str]) -> dict | None:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.claude_model, max_tokens=300, system=TAG_SYSTEM,
            messages=[{"role": "user", "content": json.dumps({"reviews": texts[:12]})}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return _extract_json(text)
    except Exception as exc:
        logger.warning("Claude tag failed (%s); using stub.", exc)
        return None


def tag_cluster(texts: list[str]) -> dict:
    provider = settings.llm_provider
    out = (
        _groq_tag(texts) if provider == "groq"
        else _gemini_tag(texts) if provider == "gemini"
        else _claude_tag(texts) if provider == "claude"
        else None
    )
    if out and out.get("topic"):
        out.setdefault("research_question", "")
        out["keywords"] = top_terms(texts, 6)
        return out
    return _stub_tag(texts)
