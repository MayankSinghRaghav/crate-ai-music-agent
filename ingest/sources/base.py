"""Source interface — every channel (Reddit, App Store, Play Store, X, YouTube,
Product Hunt) implements this same shape so the pipeline is source-agnostic.

Shared guardrail helpers live here too: author anonymisation (PII stripped), an
on-topic relevance filter (mine discovery/recommendation signal, not chatter), and
a fixtures loader so every source runs end-to-end offline on bundled samples.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class RawDoc:
    id: str
    source: str        # 'reddit' | 'app_store' | 'play_store' | 'twitter' | ...
    channel: str       # e.g. 'r/spotify', 'App Store (US)', '@mentions'
    kind: str          # 'post' | 'comment' | 'review' | 'tweet'
    author: str        # anonymised (PII stripped)
    created_utc: float
    url: str
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


class Source(Protocol):
    name: str
    last_mode: str     # 'live' | 'fixtures' — set during fetch()

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        ...


# --------------------------------------------------------------- guardrails ---

# on-topic filter so we mine discovery/recommendation signal, not random chatter
RELEVANCE = (
    "discover", "recommend", "algorithm", "discover weekly", "release radar",
    "new music", "same songs", "same five", "on repeat", "stuck", "rut", "stale",
    "rotation", "playlist", "suggest", "echo chamber", "get into", "explore",
    "find new", "taste", "loop", "adventurous",
    # broadened for real store reviews (short, less-jargon language than reddit):
    "repetitive", "boring", "variety", "diverse", "artist", "same", "shuffle",
    "genre", "old song", "predictable", "fresh",
)


def anon_author(name: str | None, prefix: str = "u") -> str:
    """Stable, non-reversible pseudonym. Never store a real handle."""
    if not name:
        return f"{prefix}/anon"
    return f"{prefix}/" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


# --------------------------------------------------------------- cleaning ---

# Emoji / pictographs / dingbats / arrows / regional-indicator + variation
# selectors — stripped so quotes read as plain prose.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoji & pictographs (incl. supplemental)
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U00002190-\U000021FF"   # arrows
    "\U00002B00-\U00002BFF"   # misc symbols & arrows
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U00002000-\U0000206F"   # general punctuation (incl. zero-width joiners)
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"\s+")
# leading forum-reply / subject prefixes ("Re: ", "RE: ...")
_REPLY_PREFIX_RE = re.compile(r"^(re|fw|fwd)\s*:\s*", re.IGNORECASE)
# social / promo boilerplate that slips past the keyword relevance filter
_GREETING_RE = re.compile(
    r"(welcome to (the|our)|kia ora|good luck with|happy to have you|"
    r"welcome aboard|nice to meet you|let'?s introduce ourselves|"
    r"artists wanted|let'?s go exploring|welcome!)",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    """Normalise raw review text for display + analysis.

    Decodes HTML entities (``&nbsp;``, ``&amp;`` …), strips emoji, raw URLs, and
    collapses whitespace. Safe to call on already-clean text (idempotent).
    """
    if not text:
        return ""
    t = html.unescape(text)          # &nbsp; -> \xa0, &amp; -> &, &#39; -> '
    t = t.replace("\xa0", " ")        # non-breaking space -> plain space
    t = _URL_RE.sub("", t)            # drop raw links
    t = _EMOJI_RE.sub("", t)          # drop emoji / pictographs
    t = _REPLY_PREFIX_RE.sub("", t.strip())  # drop leading "Re:" forum prefix
    return _WS_RE.sub(" ", t).strip()


def is_quality_text(text: str, min_len: int = 20) -> bool:
    """Keep only clean, English-dominant, non-boilerplate prose.

    Drops fragments that are too short, predominantly non-Latin script (so a
    largely non-English post doesn't become a 'representative quote'), or social
    welcome/greeting chatter. Assumes ``clean_text`` has already run.
    """
    t = (text or "").strip()
    if len(t) < min_len:
        return False
    letters = [c for c in t if c.isalpha()]
    if letters:
        non_latin = sum(1 for c in letters if ord(c) > 0x024F)  # beyond Latin Ext-B
        if non_latin / len(letters) > 0.3:
            return False
    if _GREETING_RE.search(t):
        return False
    return True


def is_relevant(text: str) -> bool:
    t = (text or "").lower()
    return any(kw in t for kw in RELEVANCE)


def load_fixture_docs(
    path: Path, source: str, default_channel: str, default_kind: str, prefix: str = "u",
) -> list[RawDoc]:
    """Load a bundled JSON sample into RawDocs (authors re-anonymised on the way in)."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        RawDoc(
            id=d["id"], source=source, channel=d.get("channel", default_channel),
            kind=d.get("kind", default_kind), author=anon_author(d.get("author", ""), prefix),
            created_utc=float(d.get("created_utc", 0)), url=d.get("url", ""), text=d["text"],
        )
        for d in raw
    ]
