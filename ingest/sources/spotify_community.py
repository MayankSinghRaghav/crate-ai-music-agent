"""Spotify Community source — the official support forum (community.spotify.com).

Runs on Khoros (Lithium), which exposes a public **Community API v2** with a
SQL-like query language (LiQL). Public boards are readable without a session key,
so — like the other keyless sources — this stays OFF by default for determinism;
opt in with `LIVE_SOURCES=spotify_community`.

Guardrails: official Community API v2 only, public messages only, a single bounded
query (no crawling), HTML stripped, authors anonymised, on-topic filter applied.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.spotify_community")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    """Khoros returns post bodies as HTML; reduce to clean text."""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


class SpotifyCommunitySource:
    name = "spotify_community"

    def __init__(self) -> None:
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        import httpx  # lazy

        # LiQL: bounded, newest-first search over public forum messages.
        q = (
            "SELECT subject, body, author.login, post_time, view_href "
            "FROM messages "
            f"WHERE body MATCHES '{settings.spotify_community_query}' "
            f"ORDER BY post_time DESC LIMIT {max(1, min(limit, 100))}"
        )
        url = f"{settings.spotify_community_base}/api/2.0/search?q={quote(q)}"
        r = httpx.get(url, headers={"Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        items = (r.json().get("data") or {}).get("items") or []

        docs: list[RawDoc] = []
        for it in items:
            subject = it.get("subject") or ""
            body = _strip_html(it.get("body") or "")
            text = f"{subject}. {body}".strip(". ").strip()
            if not is_relevant(text):
                continue
            author = ((it.get("author") or {}).get("login")) or ""
            docs.append(RawDoc(
                id=f"sc_{str(it.get('id', subject))[:16]}", source="spotify_community",
                channel="Spotify Community", kind="post",
                author=anon_author(author, "sc"),
                created_utc=0.0, url=it.get("view_href", "") or "", text=text,
            ))
            if len(docs) >= limit:
                break
        logger.info("Spotify Community live: %d relevant posts", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "spotify_community_spotify.json",
            "spotify_community", "Spotify Community", "post", "sc",
        )
        logger.info("Spotify Community fixtures: loaded %d sample posts (offline)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.spotify_community_live:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("Spotify Community live returned nothing; using fixtures.")
            except Exception as exc:  # network / parse / rate-limit
                logger.warning("Spotify Community live failed (%s); using fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
