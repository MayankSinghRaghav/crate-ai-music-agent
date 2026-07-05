"""Crate API entrypoint — the public API the UI builds against.

Phase 4: dig / events / feedback / taste / users / dev-seed.
Phase 6 adds the agent loop, adoption metrics, and time simulation.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import adoption, agent, db, insights, mission, previews
from .config import log_startup_mode, settings
from .llm import generate_bridge
from .models import (
    AdoptionMetrics, DigItem, DigResponse, EventIn, FeedbackIn, GenreInfo,
    InsightsAnswer, InsightsAskIn, LoopResult, Mission, MissionCreateIn,
    TasteProfile, User,
)
from .recommender import recommend
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Crate API",
    description="An AI music-discovery companion that optimises for adoption, not feed-scroll.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # production: the deployed web origin(s) from ALLOWED_ORIGINS (e.g. Vercel)
    allow_origins=list(settings.allowed_origins),
    # dev convenience: accept the web app on any localhost port
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    db.init_db()
    log_startup_mode()


# ------------------------------------------------------------ rate limit ---

# ponytail: per-IP sliding window, in-process. Enough for one Render instance;
# move to the platform edge / Redis if this ever runs multi-instance.
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    limit = settings.rate_limit_per_min
    if limit > 0 and request.url.path != "/health":
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        q.append(now)
    return await call_next(request)


# ----------------------------------------------------------------- health ---


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {
        "name": "Crate API",
        "status": "ok",
        "mode": "stub" if (settings.llm_stub or settings.embed_stub) else "live",
        "docs": "/docs",
    }


# -------------------------------------------------------------------- dev ---


def _demo_only() -> None:
    """Destructive/simulation endpoints exist only while DEMO_MODE=true.
    Set DEMO_MODE=false in production and they 404."""
    if not settings.demo_mode:
        raise HTTPException(404, "not found")


@app.post("/dev/seed")
def dev_seed() -> dict:
    _demo_only()
    return seed()


@app.post("/dev/reset")
def dev_reset(user_id: str) -> dict:
    _demo_only()
    if not db.get_user(user_id):
        raise HTTPException(404, "unknown user")
    db.reset_runtime(user_id)
    return {"ok": True, "user_id": user_id}


# ------------------------------------------------------------------ users ---


@app.get("/users", response_model=list[User])
def users() -> list[User]:
    return [
        User(
            id=u["id"], display_name=u["display_name"], comfort_pref=u["comfort_pref"],
            persona=u.get("persona"), mission_seed_genre=u.get("mission_seed_genre"),
        )
        for u in db.get_users()
    ]


@app.get("/taste/{user_id}", response_model=TasteProfile)
def taste(user_id: str) -> TasteProfile:
    p = db.get_taste_profile(user_id)
    if not p:
        raise HTTPException(404, "unknown user")
    return TasteProfile(
        user_id=user_id, summary=p.get("summary"),
        top_artists=p.get("top_artists") or [], top_genres=p.get("top_genres") or [],
    )


# -------------------------------------------------------------------- dig ---


def _first_name(display_name: str) -> str:
    return display_name.split(" (")[0].strip()


def _comfort_phrase(comfort: float) -> str:
    if comfort <= 0.33:
        return "close to home"
    if comfort >= 0.66:
        return "for a real stretch"
    return "with a gentle stretch"


def make_greeting(user: dict, profile: dict | None, comfort: float, n: int) -> str:
    name = _first_name(user["display_name"])
    phrase = _comfort_phrase(comfort)
    genres = (profile or {}).get("top_genres") or []
    tail = f" beyond your {genres[0]} comfort zone" if genres else ""
    return f"Hey {name} — {n} fresh picks today, dialed {phrase}{tail}."


@app.get("/dig", response_model=DigResponse)
def dig(user_id: str, comfort: float | None = None) -> DigResponse:
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(404, "unknown user")
    profile = db.get_taste_profile(user_id)
    eff_comfort = float(comfort) if comfort is not None else float(user["comfort_pref"])

    items: list[DigItem] = []

    # ACT (re-serve): bring back 1-2 played-but-not-adopted tracks to convert a
    # first play into a habit. Skipped on a fresh persona (nothing played yet).
    for ri in agent.reserve_items(user_id, profile or {}, limit=2):
        db.insert_discovery_event(user_id, ri.track.id, "re-serve", ri.bridge_text, ri.shared)
        items.append(ri)

    used_artists = {it.track.artist_id for it in items}
    used_tracks = {it.track.id for it in items}

    # GOAL (mission): weave in the active mission's current-week on-ramp picks.
    # No-op when the user has no active mission.
    for mi in mission.dig_items(user_id, profile or {}, limit=2):
        if len(items) >= 5:
            break
        if mi.track.artist_id in used_artists or mi.track.id in used_tracks:
            continue
        db.insert_discovery_event(user_id, mi.track.id, "mission", mi.bridge_text, mi.shared)
        items.append(mi)
        used_artists.add(mi.track.artist_id)
        used_tracks.add(mi.track.id)

    # PLAN + ACT (new picks fill the rest of the dig).
    # Bridges are LLM calls (~0.5s each live) — generate them concurrently so the
    # first dig costs one round-trip, not five. Stub mode is unaffected.
    recs = [
        r for r in recommend(user_id, eff_comfort, k=5)
        if r["track"]["artist_id"] not in used_artists and r["track"]["id"] not in used_tracks
    ]
    with ThreadPoolExecutor(max_workers=5) as pool:
        bridges = list(pool.map(lambda r: generate_bridge(user_id, profile or {}, r["track"]), recs))
    for r, bridge in zip(recs, bridges):
        if len(items) >= 5:
            break
        track = r["track"]
        if not bridge:  # grounding guard — never show an ungrounded card
            continue
        db.insert_discovery_event(user_id, track["id"], "dig", bridge["bridge_text"], bridge["shared"])
        items.append(
            DigItem(
                track=track, bridge_text=bridge["bridge_text"], shared=bridge["shared"],
                surface="dig", similarity=r["similarity"],
            )
        )
        used_artists.add(track["artist_id"])
        used_tracks.add(track["id"])

    return DigResponse(
        greeting=make_greeting(user, profile, eff_comfort, len(items)),
        items=items,
        comfort=eff_comfort,
    )


# ----------------------------------------------- agent loop / metrics ---


@app.post("/loop/tick", response_model=LoopResult)
def loop_tick(body: dict) -> LoopResult:
    user_id = body.get("user_id")
    if not user_id or not db.get_user(user_id):
        raise HTTPException(404, "unknown user")
    return agent.tick(user_id)


@app.get("/metrics/adoption", response_model=AdoptionMetrics)
def metrics_adoption(user_id: str) -> AdoptionMetrics:
    if not db.get_user(user_id):
        raise HTTPException(404, "unknown user")
    return adoption.metrics(user_id)


@app.post("/dev/simulate", response_model=LoopResult)
def dev_simulate(user_id: str, days: int = 4, plays: int = 1) -> LoopResult:
    _demo_only()
    if not db.get_user(user_id):
        raise HTTPException(404, "unknown user")
    return agent.simulate(user_id, days, plays)


# ---------------------------------------------------------------- events ---


@app.post("/events")
def events(body: EventIn) -> dict:
    track = db.get_track(body.track_id)
    if not track:
        raise HTTPException(404, "unknown track")
    db.set_discovery_action(body.user_id, body.track_id, body.action)
    if body.action == "played":
        # a play from a dig click is *prompted* — adoption requires unprompted plays
        db.insert_listening(
            body.user_id, body.track_id, track["artist_id"], prompted=True, source="runtime"
        )
    return {"ok": True}


@app.post("/feedback")
def feedback(body: FeedbackIn) -> dict:
    if not db.get_track(body.track_id):
        raise HTTPException(404, "unknown track")
    db.insert_feedback(body.user_id, body.track_id, body.sentiment, body.reason)
    return {"ok": True}


# -------------------------------------------------------------- missions ---


@app.get("/catalog/genres", response_model=list[GenreInfo])
def catalog_genres() -> list[GenreInfo]:
    """Genres available for a Discovery Mission, with track/artist counts."""
    return [GenreInfo(**g) for g in db.genre_counts()]


@app.get("/catalog/preview/{track_id}")
def catalog_preview(track_id: str) -> dict:
    """A 30s audio preview URL for the track (resolved via iTunes, cached), or
    null when none is available. Best-effort — never errors on lookup failure."""
    if not db.get_track(track_id):
        raise HTTPException(404, "unknown track")
    return {"track_id": track_id, "preview_url": previews.preview_url(track_id)}


@app.post("/missions", response_model=Mission)
def create_mission(body: MissionCreateIn) -> Mission:
    if not db.get_user(body.user_id):
        raise HTTPException(404, "unknown user")
    m = mission.create(body.user_id, body.target_genre)
    if not m:
        raise HTTPException(
            422, f"Not enough distinct artists in '{body.target_genre}' to plan a mission."
        )
    return m


@app.get("/missions/{user_id}", response_model=Optional[Mission])
def get_mission(user_id: str) -> Optional[Mission]:
    """The user's active (or just-completed) mission with live progress, or null."""
    if not db.get_user(user_id):
        raise HTTPException(404, "unknown user")
    return mission.get(user_id)


@app.delete("/missions/{user_id}")
def end_mission(user_id: str) -> dict:
    if not db.get_user(user_id):
        raise HTTPException(404, "unknown user")
    return {"ok": True, "ended": mission.end(user_id)}


# -------------------------------------------------------------- insights ---


@app.post("/insights/ask", response_model=InsightsAnswer)
def insights_ask(body: InsightsAskIn) -> InsightsAnswer:
    """Answer a question grounded only in the discovery-opportunity backlog.

    503 when no live LLM provider is configured or the call fails — the chat has
    no offline template answer, so the UI shows an "assistant unavailable" state
    rather than a fabricated reply.
    """
    result = insights.answer(body.question, [h.model_dump() for h in body.history])
    if result is None:
        raise HTTPException(
            503, "The insights assistant is unavailable right now. Please try again."
        )
    return InsightsAnswer(**result)
