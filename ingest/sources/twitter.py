"""X (Twitter) source — API v2 recent search. Needs `X_BEARER_TOKEN`.

Guardrails: official API only, public tweets only (`-is:retweet`), rate-limited
(one page), author ids anonymised — we never store handles.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.twitter")


class TwitterSource:
    name = "twitter"

    def __init__(self) -> None:
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        import httpx  # lazy

        params = {
            "query": settings.x_query,
            "max_results": str(min(100, max(10, limit))),
            "tweet.fields": "created_at,author_id,lang",
        }
        r = httpx.get(
            "https://api.twitter.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            params=params, timeout=30,
        )
        r.raise_for_status()
        docs: list[RawDoc] = []
        for t in r.json().get("data") or []:
            text = (t.get("text") or "").strip()
            if not is_relevant(text):
                continue
            docs.append(RawDoc(
                id=f"x_{t['id']}", source="twitter", channel="@mentions", kind="tweet",
                author=anon_author(str(t.get("author_id", "")), "x"), created_utc=0.0,
                url=f"https://twitter.com/i/web/status/{t['id']}", text=text,
            ))
            if len(docs) >= limit:
                break
        logger.info("X live: %d relevant tweets", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "twitter_spotify.json",
            "twitter", "@mentions", "tweet", "x",
        )
        logger.info("X fixtures: loaded %d sample tweets (offline)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.x_live:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("X live returned nothing; using fixtures.")
            except Exception as exc:  # network / auth / rate-limit
                logger.warning("X live failed (%s); using fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
