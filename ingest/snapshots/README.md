# Discovery backlog snapshots

`opportunities-latest.{csv,json}` here is the most recent ranked opportunity
backlog produced by the **AI Review Discovery Engine**. It is refreshed
automatically every day by [`.github/workflows/ingest-daily.yml`](../../.github/workflows/ingest-daily.yml),
which pulls fresh public discussion from every source that has credentials
(Reddit, X, YouTube, Product Hunt, App Store, Google Play, Spotify Community),
clusters + tags it, and commits the result back here when it changes.

- **Latest, browsable in-repo:** the two `-latest` files (overwritten daily).
- **Dated history:** each daily run also uploads `opportunities.{csv,json}` + the
  raw corpus (`raw.jsonl`) as a workflow **artifact** (90-day retention) — see the
  run under the repo's *Actions* tab.

Regenerate locally any time:

```bash
python -m ingest.run --sources all --limit 200   # writes ingest/out/, then copy here
```
