"""Phase 10 — multi-source ingestion.

Verifies the source registry, that every channel loads its bundled fixtures
through the shared guardrails (relevance filter + author anonymisation), and that
the pipeline produces a clustered, tagged backlog from more than one source.
"""
import pytest

from ingest.sources import (
    ALL_SOURCE_NAMES, SOURCE_CLASSES, build_sources, resolve_source_names,
)
from ingest.sources.base import is_relevant

EXPECTED = {
    "reddit", "app_store", "play_store", "twitter", "youtube", "product_hunt",
    "spotify_community",
}


def test_registry_has_all_sources():
    assert set(SOURCE_CLASSES) == EXPECTED
    assert set(ALL_SOURCE_NAMES) == EXPECTED


def test_resolve_names_all_single_and_dedupe():
    assert set(resolve_source_names(["all"])) == EXPECTED
    assert resolve_source_names(["reddit"]) == ["reddit"]
    # duplicates and 'all' collapse, order preserved
    assert resolve_source_names(["reddit", "reddit", "app_store"]) == ["reddit", "app_store"]
    assert resolve_source_names(None) == list(ALL_SOURCE_NAMES)  # default = everything


def test_unknown_source_raises():
    with pytest.raises(ValueError):
        resolve_source_names(["myspace"])


@pytest.mark.parametrize("name", sorted(EXPECTED - {"reddit"}))
def test_each_new_source_loads_relevant_anonymised_fixtures(name):
    src = SOURCE_CLASSES[name]()
    docs = src.fetch(limit=200)
    assert src.last_mode == "fixtures"   # no creds in tests -> offline
    assert len(docs) >= 5
    for d in docs:
        assert d.source == name
        assert d.text and is_relevant(d.text)        # on-topic only
        assert d.author and "/" in d.author          # anonymised pseudonym
        assert "@" not in d.author                   # never a raw handle


def test_build_sources_returns_instances_in_order():
    sources = build_sources(["app_store", "reddit"])
    assert [s.name for s in sources] == ["app_store", "reddit"]


def test_pipeline_multi_source_backlog():
    from ingest.pipeline import run_pipeline

    s = run_pipeline(limit=200, source_names=["reddit", "app_store", "twitter"])
    assert {x["name"] for x in s["sources"]} == {"reddit", "app_store", "twitter"}
    assert s["raw_docs"] >= s["after_dedupe"]        # dedupe never adds docs
    assert s["clusters"] >= 1
    assert s["opportunities"], "a multi-source run must yield ranked opportunities"
    top = s["opportunities"][0]
    for key in ("rank", "topic", "sentiment", "segment", "unmet_need", "opportunity_score"):
        assert key in top                            # documented output schema
