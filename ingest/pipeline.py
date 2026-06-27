"""Pipeline: source -> raw store -> dedupe -> embed -> cluster -> tag -> backlog.

Produces a ranked opportunity backlog (JSON + CSV) where each row is a theme the
reviews surfaced, tagged with sentiment / unmet-need / segment and scored by
size x negativity (bigger, angrier clusters = bigger opportunities).
"""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict

from .cluster import cluster
from .config import settings
from .dedupe import dedupe
from .embed import embed
from .sources import build_sources
from .tag import tag_cluster

logger = logging.getLogger("ingest.pipeline")

SENTIMENT_WEIGHT = {"negative": 1.0, "mixed": 0.6, "positive": 0.25}


def _representative_quotes(docs, k: int = 3) -> list[str]:
    return [d.text for d in sorted(docs, key=lambda d: len(d.text))[:k]]


def run_pipeline(limit: int = 200, source_names=None) -> dict:
    # pull from one or many channels; dedupe later collapses cross-source repeats
    sources = build_sources(source_names)
    raw = []
    per_source: list[dict] = []
    for src in sources:
        docs = src.fetch(limit)
        per_source.append({"name": src.name, "docs": len(docs), "mode": src.last_mode})
        raw.extend(docs)
    if not raw:
        raise RuntimeError("sources returned no documents")

    # raw store
    raw_path = settings.out_dir / "raw.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for d in raw:
            f.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")

    vectors, embed_mode = embed([d.text for d in raw])
    kept, kvecs, dropped = dedupe(raw, vectors, settings.dedupe_threshold)
    labels, k = cluster(kvecs)

    groups: dict[int, list] = defaultdict(list)
    for d, lab in zip(kept, labels):
        groups[int(lab)].append(d)

    # tag each cluster, then merge clusters that landed on the same topic so the
    # backlog has one row per theme (clustering can over-split a theme).
    sev = {"negative": 0, "mixed": 1, "positive": 2}
    by_topic: dict[str, dict] = {}
    for lab, docs in groups.items():
        tag = tag_cluster([d.text for d in docs])
        topic = tag["topic"]
        if topic not in by_topic:
            by_topic[topic] = {
                "topic": topic, "size": 0, "cluster_ids": [],
                "sentiment": tag.get("sentiment", "mixed"),
                "unmet_need": tag.get("unmet_need"), "segment": tag.get("segment"),
                "research_question": tag.get("research_question", ""),
                "keywords": [], "example_quotes": [],
            }
        m = by_topic[topic]
        m["size"] += len(docs)
        m["cluster_ids"].append(lab)
        m["example_quotes"] = (m["example_quotes"] + _representative_quotes(docs))[:3]
        if sev.get(tag.get("sentiment"), 1) < sev.get(m["sentiment"], 1):
            m["sentiment"] = tag.get("sentiment")  # keep the most negative
        for kw in tag.get("keywords", []):
            if kw not in m["keywords"]:
                m["keywords"].append(kw)
        m["keywords"] = m["keywords"][:6]

    opportunities = []
    for m in by_topic.values():
        m["share"] = round(m["size"] / len(kept), 3)
        m["opportunity_score"] = round(m["size"] * SENTIMENT_WEIGHT.get(m["sentiment"], 0.6), 2)
        opportunities.append(m)

    opportunities.sort(key=lambda o: o["opportunity_score"], reverse=True)
    for i, o in enumerate(opportunities, 1):
        o["rank"] = i

    json_path = settings.out_dir / "opportunities.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(opportunities, f, ensure_ascii=False, indent=2)

    csv_path = settings.out_dir / "opportunities.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "topic", "size", "share", "sentiment", "segment",
                    "unmet_need", "research_question", "opportunity_score",
                    "top_keywords", "example_quote"])
        for o in opportunities:
            w.writerow([o["rank"], o["topic"], o["size"], o["share"], o["sentiment"],
                        o["segment"], o["unmet_need"], o["research_question"],
                        o["opportunity_score"], "; ".join(o["keywords"]),
                        o["example_quotes"][0] if o["example_quotes"] else ""])

    return {
        "sources": per_source,
        "source": "+".join(s["name"] for s in per_source),
        "source_mode": ", ".join(f"{s['name']}:{s['mode']}" for s in per_source),
        "embed_mode": embed_mode,
        "tag_mode": settings.llm_provider,
        "raw_docs": len(raw),
        "after_dedupe": len(kept),
        "duplicates_dropped": dropped,
        "clusters": k,
        "opportunities": opportunities,
        "out_json": str(json_path),
        "out_csv": str(csv_path),
    }
