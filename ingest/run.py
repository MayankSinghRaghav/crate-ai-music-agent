"""CLI: python -m ingest.run [--limit N]

Runs the discovery engine and prints the ranked opportunity backlog.
"""
from __future__ import annotations

import argparse
import logging


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Crate — AI Review Discovery Engine")
    parser.add_argument("--limit", type=int, default=200, help="max docs per source")
    parser.add_argument(
        "--sources", default="all",
        help="comma-separated: reddit,app_store,play_store,twitter,youtube,product_hunt,"
             "spotify_community | all (default: all)",
    )
    args = parser.parse_args()

    from .pipeline import run_pipeline

    source_names = [x.strip() for x in args.sources.split(",") if x.strip()]
    try:
        s = run_pipeline(args.limit, source_names)
    except ValueError as exc:  # unknown --sources name
        parser.error(str(exc))

    print("\n" + "=" * 78)
    print("  CRATE — AI REVIEW DISCOVERY ENGINE")
    print("=" * 78)
    print(f"  sources: {s['source_mode']}")
    print("  per-source: " + " | ".join(f"{x['name']}={x['docs']}" for x in s["sources"]))
    print(f"  embed={s['embed_mode']}  tag={s['tag_mode']}")
    print(f"  {s['raw_docs']} raw -> {s['after_dedupe']} after dedupe "
          f"({s['duplicates_dropped']} dupes) -> {s['clusters']} themes")
    print("-" * 78)
    print("  RANKED OPPORTUNITY BACKLOG")
    print("-" * 78)
    for o in s["opportunities"]:
        print(f"\n  #{o['rank']}  [{o['opportunity_score']:>4}]  {o['topic']}")
        print(f"       size {o['size']} ({int(o['share']*100)}%) · {o['sentiment']} · "
              f"segment: {o['segment']}")
        print(f"       unmet need: {o['unmet_need']}")
        if o.get("research_question"):
            print(f"       maps to: {o['research_question']}")
        if o["example_quotes"]:
            q = o["example_quotes"][0]
            print(f"       e.g. “{q[:96]}{'…' if len(q) > 96 else ''}”")
    print("\n" + "-" * 78)
    print(f"  written: {s['out_csv']}")
    print(f"           {s['out_json']}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
