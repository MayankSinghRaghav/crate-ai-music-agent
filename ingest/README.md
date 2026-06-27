# AI Review Discovery Engine

The insight pipeline that justifies Crate. It mines public review/forum data,
removes near-duplicates, clusters it into themes, and tags each theme with
**topic · sentiment · unmet-need · segment** to produce a **ranked opportunity
backlog** — the evidence behind "users don't lack discovery, they lack adoption."

Separate from the runtime app (`services/api`). **Six sources** are implemented
behind one `Source` interface — Reddit, App Store, Google Play, X (Twitter),
YouTube, and Product Hunt — each with a live path and a bundled offline sample, so
the whole engine runs end-to-end with no keys.

```
sources ─▶ raw store ─▶ dedupe (cosine>0.92) ─▶ embed ─▶ cluster ─▶ tag ─▶ backlog
 6 channels             near-dupes out          TF-IDF/  KMeans/   Groq/   CSV+JSON
 (live / fixtures)      (incl. cross-source)    OpenAI   BERTopic  stub
```

## Run it (offline, no keys)

Runs on bundled, **representative samples** across all six channels (synthetic,
PII-free — not scraped real users) using TF-IDF + KMeans + a keyword tagger.

```bash
cd ingest
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install numpy scikit-learn python-dotenv      # offline core
cd .. && python -m ingest.run                      # all sources, run from repo root
python -m ingest.run --sources reddit              # or a single channel
python -m ingest.run --sources app_store,twitter   # or a subset
```

Outputs land in `ingest/out/`:
- `opportunities.csv` / `opportunities.json` — the ranked backlog
- `raw.jsonl` — the raw store (every fetched doc, tagged with its `source`)

Tests: `python -m pytest ingest/tests` (offline, deterministic).

### Sample output (all six sources)

```
per-source: reddit=47 | app_store=10 | play_store=10 | twitter=8 | youtube=8 | product_hunt=8
91 raw -> 89 after dedupe (2 dupes) -> 8 themes

#1 [18.0] Recommendations recycle the familiar (echo chamber)    negative · 20%
          unmet need: genuinely novel recommendations that expand taste   (Q2)
#2 [17.0] Recommendations lack a 'why'                           negative · 19%
#3 [13.0] Stuck in a listening loop / same songs on repeat       negative · 14%
#4 [11.0] New music never sticks (discovery without adoption)    negative · 12%   (core)
#5 [10.0] No guided on-ramp into a new genre                     negative · 11%
#6 [ 7.8] Discovery is too high-effort / overwhelming            mixed · 14%
#7 [ 1.8] Users want control over adventurousness                positive ·  7%
```

The top opportunity *is* Crate's thesis — and #2→bridges, #3→Discovery Missions,
#4→the Comfort↔Curiosity dial, #5→the re-serve loop. The research engine and the
product line up.

## How it answers the research questions

`opportunity_score = cluster_size × negativity` ranks where the pain is. The
`unmet_need`, `segment`, and `research_question` tags map every theme back to:

| Question | Surfaced as |
| --- | --- |
| Why do users struggle to discover? | "Discovery surfaces don't lead anywhere new" |
| Most common recommendation frustrations | "Echo chamber" + "lack a 'why'" clusters, ranked by volume×negativity |
| What behaviours are users trying to achieve | `segment` + intent themes (genre on-ramp, mood, background) |
| What causes repeat-listening of the same content | "Stuck in a loop" + "never sticks (no adoption)" |
| Which segments face different challenges | `segment` tag (busy parent / power digger / casual / aspirational) |
| Unmet needs that recur | the `unmet_need` column on the ranked backlog |

## Go live (real data + real AI)

Each source has a live adapter that activates the moment its credentials (or
opt-in flag) are present in the repo-root `.env`; otherwise it serves its bundled
sample. The run header prints each source's mode (`live` / `fixtures`).

| Source | Off (default) | On — credential / flag |
| --- | --- | --- |
| **Reddit** | sample fixtures | official API · `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` |
| **App Store** | sample fixtures | Apple RSS (public, no key) · `LIVE_SOURCES=app_store` (+ `APP_STORE_APP_ID`) |
| **Google Play** | sample fixtures | `google-play-scraper` (no key) · `LIVE_SOURCES=play_store` (+ `PLAY_STORE_APP_ID`) |
| **X (Twitter)** | sample fixtures | API v2 recent search · `X_BEARER_TOKEN` (+ `X_QUERY`) |
| **YouTube** | sample fixtures | Data API v3 `commentThreads` · `YOUTUBE_API_KEY` + `YOUTUBE_VIDEO_IDS` |
| **Product Hunt** | sample fixtures | GraphQL API v2 · `PRODUCT_HUNT_TOKEN` (+ `PRODUCT_HUNT_SLUG`) |
| **Tagging** | keyword/lexicon | **`GROQ_API_KEY` → Groq free tier** (or `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`) |
| **Embeddings** | TF-IDF | `OPENAI_API_KEY` → `text-embedding-3-large` (semantic dedupe + clusters) |

`LIVE_SOURCES` is a comma list opting the keyless channels (App Store, Google Play)
into live mode; the token-gated channels (X, YouTube, Product Hunt) go live as soon
as their key is set. Anything not live falls back to fixtures, so a partial-key run
still completes.

```bash
pip install -r requirements.txt     # adds praw, httpx, google-play-scraper, …
# Reddit: https://www.reddit.com/prefs/apps · Groq: https://console.groq.com/keys
LIVE_SOURCES=app_store python -m ingest.run --sources all --limit 300
```

**BERTopic** (the spec's production clusterer) is the documented swap in
`cluster.py` — better topic coherence, but a heavy dependency
(`torch` + `sentence-transformers` + `umap` + `hdbscan`), so it's left out of the
offline-first slice exactly like pgvector/Pinecone in the runtime app.

## Adding a source

Implement the `Source` protocol (`sources/base.py`) — set `name`/`last_mode`, return
`RawDoc`s from `fetch()`, reuse the shared `anon_author` / `is_relevant` /
`load_fixture_docs` helpers — then register the class in `sources/__init__.py`. The
rest of the pipeline is source-agnostic. (Spotify Community is the next drop-in:
Apify actor / web scraper, same shape.)

## Guardrails

Official APIs preferred · public data only · rate-limited (one bounded page/query
per source) · authors anonymised (PII stripped, never raw handles) · keyless
channels opt-in only · respect ToS + `robots.txt`. n8n schedules the sources daily
in the production design.
