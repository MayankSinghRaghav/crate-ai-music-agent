"""Google Play source — `google-play-scraper` (public review data, no key).

Off by default; opt in with `LIVE_SOURCES=play_store` (requires
`pip install google-play-scraper`). Guardrails: public reviews only, newest-first
page, authors anonymised.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.play_store")


class PlayStoreSource:
    name = "play_store"

    def __init__(self) -> None:
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        from google_play_scraper import Sort, reviews  # lazy

        result, _ = reviews(
            settings.play_store_app_id, lang=settings.play_store_lang, country="us",
            sort=Sort.NEWEST, count=max(limit, 100),
        )
        docs: list[RawDoc] = []
        for r in result:
            text = (r.get("content") or "").strip()
            if not is_relevant(text):
                continue
            at = r.get("at")
            docs.append(RawDoc(
                id=f"gp_{str(r.get('reviewId', ''))[:16]}", source="play_store",
                channel="Google Play", kind="review",
                author=anon_author(r.get("userName", ""), "gp"),
                created_utc=float(at.timestamp()) if at else 0.0, url="", text=text,
            ))
            if len(docs) >= limit:
                break
        logger.info("Play Store live: %d relevant reviews", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "play_store_spotify.json",
            "play_store", "Google Play", "review", "gp",
        )
        logger.info("Play Store fixtures: loaded %d sample reviews (offline)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.play_store_live:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("Play Store live returned nothing; using fixtures.")
            except Exception as exc:  # import / network / rate-limit
                logger.warning("Play Store live failed (%s); using fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
