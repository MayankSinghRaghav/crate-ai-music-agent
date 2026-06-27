"""Source interface — every channel (Reddit, App Store, Play Store, X, YouTube,
Product Hunt) implements this same shape so the pipeline is source-agnostic.

Shared guardrail helpers live here too: author anonymisation (PII stripped), an
on-topic relevance filter (mine discovery/recommendation signal, not chatter), and
a fixtures loader so every source runs end-to-end offline on bundled samples.
"""
from __future__ import annotations

import hashlib
import json
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
)


def anon_author(name: str | None, prefix: str = "u") -> str:
    """Stable, non-reversible pseudonym. Never store a real handle."""
    if not name:
        return f"{prefix}/anon"
    return f"{prefix}/" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


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
