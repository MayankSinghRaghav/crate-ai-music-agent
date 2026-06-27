"""YouTube source — Data API v3 `commentThreads` on configured video ids.

Needs `YOUTUBE_API_KEY` and `YOUTUBE_VIDEO_IDS` (comma-separated, e.g. reviews of
Spotify's discovery features). Guardrails: official API only, public comments only,
rate-limited (one page per video), author channel ids anonymised.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.youtube")


class YouTubeSource:
    name = "youtube"

    def __init__(self) -> None:
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        import httpx  # lazy

        docs: list[RawDoc] = []
        for vid in settings.youtube_video_ids:
            params = {
                "part": "snippet", "videoId": vid, "maxResults": "100",
                "order": "relevance", "textFormat": "plainText", "key": settings.youtube_api_key,
            }
            r = httpx.get(
                "https://www.googleapis.com/youtube/v3/commentThreads", params=params, timeout=30
            )
            r.raise_for_status()
            for item in r.json().get("items") or []:
                sn = item["snippet"]["topLevelComment"]["snippet"]
                text = (sn.get("textDisplay") or "").strip()
                if not is_relevant(text):
                    continue
                docs.append(RawDoc(
                    id=f"yt_{item['id'][:16]}", source="youtube", channel="YouTube comments",
                    kind="comment",
                    author=anon_author(sn.get("authorChannelId", {}).get("value", ""), "yt"),
                    created_utc=0.0, url=f"https://youtube.com/watch?v={vid}", text=text,
                ))
                if len(docs) >= limit:
                    break
            if len(docs) >= limit:
                break
        logger.info("YouTube live: %d relevant comments", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "youtube_spotify.json",
            "youtube", "YouTube comments", "comment", "yt",
        )
        logger.info("YouTube fixtures: loaded %d sample comments (offline)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.youtube_live and settings.youtube_video_ids:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("YouTube live returned nothing; using fixtures.")
            except Exception as exc:  # network / auth / quota
                logger.warning("YouTube live failed (%s); using fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
