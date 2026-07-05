"""Resolve a 30-second audio preview for a catalog track.

The seed catalog carries no `preview_url` (it's Spotify-API-swappable), so we
look previews up on Apple's keyless iTunes Search API and cache them in-process.
Everything is best-effort: any failure returns None and the UI falls back to its
signal-only Play button rather than erroring.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from . import db

logger = logging.getLogger("crate.previews")

ITUNES_SEARCH = "https://itunes.apple.com/search"

# track_id -> preview url (or None if we looked and found nothing). None is cached
# too, so we don't re-hit iTunes for tracks that have no preview.
_cache: dict[str, Optional[str]] = {}


def _lookup_itunes(artist: str, title: str) -> Optional[str]:
    term = f"{artist} {title}".strip()
    if not term:
        return None
    try:
        r = httpx.get(
            ITUNES_SEARCH,
            params={"term": term, "entity": "song", "limit": 1},
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if results:
            return results[0].get("previewUrl") or None
    except Exception as exc:  # network / parse / rate-limit — degrade gracefully
        logger.warning("iTunes preview lookup failed for %r (%s)", term, exc)
    return None


def preview_url(track_id: str) -> Optional[str]:
    """Return a 30s preview URL for the track, or None. Cached per track."""
    if track_id in _cache:
        return _cache[track_id]
    track = db.get_track(track_id)
    if not track:
        return None
    # honour a preview already on the track (future real catalogs may carry one)
    url = track.get("preview_url") or _lookup_itunes(
        track.get("artist", ""), track.get("title", "")
    )
    _cache[track_id] = url
    return url
