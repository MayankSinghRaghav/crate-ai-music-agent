"""Product Hunt source — GraphQL API v2 (comments on a product). Needs
`PRODUCT_HUNT_TOKEN` (developer token from producthunt.com/v2/oauth/applications).

Guardrails: official GraphQL API only, public comments only, a single bounded
query, author ids anonymised.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import RawDoc, anon_author, is_relevant, load_fixture_docs

logger = logging.getLogger("ingest.product_hunt")

_QUERY = """
query($slug: String!) {
  post(slug: $slug) {
    name
    comments(first: 50) { edges { node { id body user { id } } } }
  }
}
"""


class ProductHuntSource:
    name = "product_hunt"

    def __init__(self) -> None:
        self.last_mode = "fixtures"

    # ---------------------------------------------------------------- live ---
    def _fetch_live(self, limit: int) -> list[RawDoc]:
        import httpx  # lazy

        r = httpx.post(
            "https://api.producthunt.com/v2/api/graphql",
            headers={"Authorization": f"Bearer {settings.product_hunt_token}"},
            json={"query": _QUERY, "variables": {"slug": settings.product_hunt_slug}},
            timeout=30,
        )
        r.raise_for_status()
        post = (r.json().get("data") or {}).get("post") or {}
        edges = (post.get("comments") or {}).get("edges") or []
        docs: list[RawDoc] = []
        for e in edges:
            node = e.get("node", {})
            text = (node.get("body") or "").strip()
            if not is_relevant(text):
                continue
            docs.append(RawDoc(
                id=f"ph_{node.get('id', '')}", source="product_hunt", channel="Product Hunt",
                kind="comment", author=anon_author(str((node.get("user") or {}).get("id", "")), "ph"),
                created_utc=0.0,
                url=f"https://www.producthunt.com/posts/{settings.product_hunt_slug}", text=text,
            ))
            if len(docs) >= limit:
                break
        logger.info("Product Hunt live: %d relevant comments", len(docs))
        return docs[:limit]

    # ------------------------------------------------------------ fixtures ---
    def _fetch_fixtures(self, limit: int) -> list[RawDoc]:
        docs = load_fixture_docs(
            settings.fixtures_dir / "product_hunt_spotify.json",
            "product_hunt", "Product Hunt", "comment", "ph",
        )
        logger.info("Product Hunt fixtures: loaded %d sample comments (offline)", len(docs))
        return docs[:limit]

    def fetch(self, limit: int = 200) -> list[RawDoc]:
        if settings.product_hunt_live:
            try:
                docs = self._fetch_live(limit)
                if docs:
                    self.last_mode = "live"
                    return docs
                logger.warning("Product Hunt live returned nothing; using fixtures.")
            except Exception as exc:  # network / auth / rate-limit
                logger.warning("Product Hunt live failed (%s); using fixtures.", exc)
        self.last_mode = "fixtures"
        return self._fetch_fixtures(limit)
