"""Source registry — resolve names to adapter instances so the pipeline (and CLI)
can pull from one channel or many. Every adapter implements the same `Source`
shape; add a new channel by dropping a module here and registering it below.
"""
from .app_store import AppStoreSource
from .base import RawDoc, Source, anon_author, is_relevant, load_fixture_docs
from .play_store import PlayStoreSource
from .product_hunt import ProductHuntSource
from .reddit import RedditSource
from .spotify_community import SpotifyCommunitySource
from .twitter import TwitterSource
from .youtube import YouTubeSource

SOURCE_CLASSES = {
    "reddit": RedditSource,
    "app_store": AppStoreSource,
    "play_store": PlayStoreSource,
    "twitter": TwitterSource,
    "youtube": YouTubeSource,
    "product_hunt": ProductHuntSource,
    "spotify_community": SpotifyCommunitySource,
}
ALL_SOURCE_NAMES = tuple(SOURCE_CLASSES)
DEFAULT_SOURCES = ALL_SOURCE_NAMES  # `ingest.run` with no --sources mines everything


def resolve_source_names(names: list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalise a list of names (supporting the alias 'all') to a deduped list."""
    if not names:
        return list(DEFAULT_SOURCES)
    out: list[str] = []
    for n in names:
        key = n.strip().lower()
        if key == "all":
            out.extend(ALL_SOURCE_NAMES)
        elif key in SOURCE_CLASSES:
            out.append(key)
        else:
            raise ValueError(
                f"unknown source '{n}'. choices: {', '.join(ALL_SOURCE_NAMES)}, all"
            )
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def build_sources(names: list[str] | tuple[str, ...] | None = None) -> list[Source]:
    return [SOURCE_CLASSES[n]() for n in resolve_source_names(names)]


__all__ = [
    "RawDoc", "Source", "anon_author", "is_relevant", "load_fixture_docs",
    "RedditSource", "AppStoreSource", "PlayStoreSource", "TwitterSource",
    "YouTubeSource", "ProductHuntSource", "SpotifyCommunitySource",
    "SOURCE_CLASSES", "ALL_SOURCE_NAMES", "DEFAULT_SOURCES",
    "resolve_source_names", "build_sources",
]
