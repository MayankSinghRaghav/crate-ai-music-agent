"""Reddit source — official API via PRAW when credentials are present, otherwise
a bundled, clearly-labelled sample of representative r/spotify discussion so the
pipeline runs end-to-end offline.

Guardrails (per the build plan): official API only, public data only, rate-limited
by PRAW, authors anonymised (PII stripped). The fixtures are synthetic,
representative examples — not scraped real users' content.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.reddit")

# kept as module-local aliases so the rest of the file reads unchanged
_anon = anon_author
_relevant = is_relevant


class RedditSource:
    name = "reddit"

    def __init__(self, subreddits: tuple[str, ...] | None = None):
        self.subreddits = subreddits or settings.subreddits
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        import praw  # lazy — only when creds exist

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            check_for_async=False,
        )
        reddit.read_only = True

        docs: list[RawDoc] = []
        per_sub = max(5, limit // max(1, len(self.subreddits)))
        query = "discovery OR recommendations OR 'discover weekly' OR 'same songs'"
        for sub in self.subreddits:
            for sub_post in reddit.subreddit(sub).search(query, sort="relevance", limit=per_sub):
                body = f"{sub_post.title}\n\n{sub_post.selftext or ''}".strip()
                if _relevant(body):
                    docs.append(RawDoc(
                        id=f"reddit_{sub_post.id}", source="reddit", channel=f"r/{sub}",
                        kind="post", author=_anon(str(sub_post.author)),
                        created_utc=float(sub_post.created_utc),
                        url=f"https://reddit.com{sub_post.permalink}", text=body,
                    ))
                sub_post.comments.replace_more(limit=0)
                for c in sub_post.comments[:5]:
                    if c.body and _relevant(c.body) and len(c.body) > 40:
                        docs.append(RawDoc(
                            id=f"reddit_{c.id}", source="reddit", channel=f"r/{sub}",
                            kind="comment", author=_anon(str(c.author)),
                            created_utc=float(c.created_utc),
                            url=f"https://reddit.com{c.permalink}", text=c.body.strip(),
                        ))
                if len(docs) >= limit:
                    break
        logger.info("Reddit live: pulled %d relevant docs", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "reddit_spotify.json", "reddit", "r/spotify", "comment"
        )
        logger.info("Reddit fixtures: loaded %d sample docs (offline mode)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.reddit_live:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("Reddit live returned nothing; falling back to fixtures.")
            except Exception as exc:  # network / auth / rate-limit
                logger.warning("Reddit live failed (%s); falling back to fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
