"""App Store source — Apple's public customer-reviews RSS feed.

Official Apple endpoint, public data, no key required. Kept OFF by default (the
engine stays deterministic/offline); opt in with `LIVE_SOURCES=app_store`.

Guardrails: official RSS only, public reviews only, rate-limited (a few pages —
Apple exposes ~10 pages of recent reviews), authors anonymised.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.app_store")


class AppStoreSource:
    name = "app_store"

    def __init__(self) -> None:
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        import httpx  # lazy

        docs: list[RawDoc] = []
        pages = max(1, min(10, limit // 25 + 1))
        for page in range(1, pages + 1):
            url = (
                f"https://itunes.apple.com/{settings.app_store_country}/rss/customerreviews/"
                f"page={page}/id={settings.app_store_app_id}/sortby=mostrecent/json"
            )
            r = httpx.get(url, timeout=30)
            r.raise_for_status()
            entries = r.json().get("feed", {}).get("entry") or []
            for e in entries:
                if "im:rating" not in e:  # first entry is app metadata, not a review
                    continue
                title = e.get("title", {}).get("label", "")
                body = e.get("content", {}).get("label", "")
                text = f"{title}. {body}".strip()
                if not is_relevant(text):
                    continue
                docs.append(RawDoc(
                    id=f"as_{e.get('id', {}).get('label', '')[-12:]}", source="app_store",
                    channel=f"App Store ({settings.app_store_country.upper()})", kind="review",
                    author=anon_author(e.get("author", {}).get("name", {}).get("label", ""), "as"),
                    created_utc=0.0,
                    url=e.get("author", {}).get("uri", {}).get("label", ""), text=text,
                ))
                if len(docs) >= limit:
                    break
            if len(docs) >= limit:
                break
        logger.info("App Store live: %d relevant reviews", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "app_store_spotify.json",
            "app_store", "App Store (US)", "review", "as",
        )
        logger.info("App Store fixtures: loaded %d sample reviews (offline)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.app_store_live:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("App Store live returned nothing; using fixtures.")
            except Exception as exc:  # network / parse / rate-limit
                logger.warning("App Store live failed (%s); using fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
