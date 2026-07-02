# Deploying Crate

Crate is two deployable pieces plus a database. They go to two different kinds of host:

```
  Browser
     │  https
     ▼
┌───────────────────────┐      https / fetch      ┌────────────────────────────┐
│  Web — Next.js        │ ──────────────────────► │  API — FastAPI             │
│  host: Vercel         │  NEXT_PUBLIC_API_BASE   │  host: Render / Railway /  │
│  apps/web/            │      = API URL          │        Fly / Cloud Run     │
└───────────────────────┘                         │  (built from the Dockerfile)│
                                                  └──────────────┬─────────────┘
                                                                 │
                                       SQLite inside the image (demo, re-seeds on boot)
                                                  └──or──► managed Postgres + pgvector (scale)
```

The API is the source of truth; the web app is a static/SSR client that calls it. Deploy the **API first**, then point the **web app** at its URL.

---

## 1. API → a container host (Render shown; Railway/Fly/Cloud Run are equivalent)

The API ships a [`services/api/Dockerfile`](services/api/Dockerfile) that installs deps, copies the app + seed data, **seeds on boot**, and serves uvicorn on `$PORT`. Any container host can build and run it.

**Render (free tier works) — one click:** New + → **Blueprint** → connect this repo. [`render.yaml`](render.yaml) defines the service (Docker, health check, env vars); you only fill in `GROQ_API_KEY` and `ALLOWED_ORIGINS` in the dashboard.

**Or manually:**
1. New → **Web Service** → connect this GitHub repo.
2. **Runtime: Docker**. **Dockerfile path:** `services/api/Dockerfile`. **Docker build context:** the **repo root** (`.`) — the Dockerfile copies `data/`, which lives at the root.
3. **Environment variables:**
   | Key | Value | Why |
   |---|---|---|
   | `GROQ_API_KEY` | your Groq key | live LLM bridges/summaries (omit → runs in stub mode, still works) |
   | `ALLOWED_ORIGINS` | `https://<your-web-app>.vercel.app` | lets the browser call the API (CORS) |
   | `SEED_ON_START` | `1` (default) | seed the demo data on first boot; set `0` to skip |
4. Deploy. Render runs `docker build` for you and gives you `https://<api>.onrender.com`.
5. Verify: open `https://<api>.onrender.com/health` → `{"status":"ok"}` and `/docs` for the API explorer.

> **Persistence note:** SQLite lives inside the container, and most free PaaS filesystems are **ephemeral** — data resets on redeploy/restart. That's fine for a demo (it re-seeds on boot). For durable data, attach a managed Postgres and set `DB_BACKEND=postgres`, `VECTOR_BACKEND=pgvector`, `DATABASE_URL=...` (the `supabase/migrations/0001_init.sql` schema + `docker-compose.yml` pgvector image are the documented path).

## 2. Web → Vercel

1. Vercel → **Add New Project** → import this repo.
2. **Root Directory = `apps/web`** ([`apps/web/vercel.json`](apps/web/vercel.json) pins the Next.js build).
3. **Environment variable:**
   ```
   NEXT_PUBLIC_API_BASE = https://<your-api-host>     # the Render URL from step 1
   ```
4. Deploy → you get `https://<web>.vercel.app`.
5. Go back to the API host and make sure `ALLOWED_ORIGINS` contains that exact Vercel URL, then redeploy the API.

## 3. Smoke-test the live deployment

```bash
curl https://<api-host>/health
curl -X POST "https://<api-host>/dev/seed"
# open the Vercel URL, switch personas, drag the dial, run a mission, Simulate 3 weeks
```

---

## Optional: build the image locally first (closes the deploy-risk gap)

The hosts above run `docker build` on the Dockerfile for you. Building it **locally first** proves that exact image assembles before you push — catching deploy-only failures (`pip` resolution on Linux, `COPY` paths, the boot seed) that the unit tests can't, since tests run in your already-working venv.

```bash
# from the repo root (Docker Desktop must be running)
docker build -f services/api/Dockerfile -t crate-api .
docker run --rm -p 8000:8000 crate-api
# in another shell:
curl localhost:8000/health      # {"status":"ok"}  → image is deploy-sound
```

A green local build ≈ a green build on the host. It does **not** prove TLS, host env vars, or the public URL — only that the artifact is sound, which is the bulk of deploy risk.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push: API `pytest` + the one-command adoption demo, the ingest suite + a multi-source smoke run, and the web `lint` + `build`. A green CI badge means the same commands a host runs have already passed.

## Scheduled daily data ingest

[`.github/workflows/ingest-daily.yml`](.github/workflows/ingest-daily.yml) runs the **AI Review Discovery Engine** on a cron (06:17 UTC daily) — and on-demand via the *Actions → Run workflow* button. It pulls live public discussion from every source that has credentials, clusters + tags it, then (a) uploads the ranked backlog + raw corpus as a 90-day **artifact** and (b) commits the refreshed `ingest/snapshots/opportunities-latest.{csv,json}` back to the repo when it changed.

**It never hard-fails:** any source missing its secret falls back to bundled offline fixtures.

**Setup (one-time):** push to GitHub, then add the secrets you have under **Settings → Secrets and variables → Actions**. All optional:

| Secret | Enables | Where to get it |
|---|---|---|
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | live Reddit (PRAW) | reddit.com/prefs/apps |
| `X_BEARER_TOKEN` | live X / Twitter (API v2) | developer.x.com |
| `YOUTUBE_API_KEY`, `YOUTUBE_VIDEO_IDS` | live YouTube comments | Google Cloud (Data API v3) |
| `PRODUCT_HUNT_TOKEN` | live Product Hunt | producthunt.com/v2/oauth |
| `GROQ_API_KEY` | live LLM tagging (else stub) | console.groq.com/keys |

App Store, Google Play and Spotify Community are **keyless** — already enabled in the workflow via `LIVE_SOURCES`; no secret needed.

**Caveats to know:**
- Scheduled workflows run **only from the default branch**, and GitHub auto-disables the schedule after ~60 days of repo inactivity (a push re-enables it).
- `play_store` uses the unofficial `google-play-scraper` and `x` the free API tier — both can rate-limit or break; on any error that source simply falls back to fixtures for the day.
- The job needs the repo's Actions permission set to **Read and write** (Settings → Actions → General → Workflow permissions) so it can commit the snapshot.

## What never gets deployed

`.env` is gitignored and excluded from the image via [`.dockerignore`](.dockerignore); `.env.example` is the committed template and must stay key-free. Set real secrets only as host environment variables.
