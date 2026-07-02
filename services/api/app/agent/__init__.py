"""The agent loop — Plan -> Act -> Observe -> Adapt.

A recommender returns a list. Crate runs a closed loop that *optimises for
adoption*: it re-serves high-potential tracks to convert a first play into a
habit, recomputes the North Star from real listens, and adapts taste + comfort.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np

from .. import adoption, db, mission
from ..config import settings
from ..embeddings import l2_normalize
from ..llm import generate_bridge
from ..models import ArtistAdoption, DigItem, LoopResult
from ..recommender import recommend

logger = logging.getLogger("crate.agent")

EMA_ALPHA = 0.12
SKIP_GUARDRAIL = settings.skip_guardrail


# ----------------------------------------------------------------- PLAN ---


def plan(user_id: str, comfort: float, k: int = 5) -> list[dict]:
    return recommend(user_id, comfort, k=k)


# ------------------------------------------------------------------ ACT ---


def reserve_items(user_id: str, profile: dict, limit: int = 2) -> list[DigItem]:
    """High-potential tracks: played before, artist not yet adopted -> bring them
    back (familiarity converts a first play into a habit)."""
    adopted = {a["artist_id"] for a in db.get_adoptions(user_id) if a["status"] == "adopted"}
    items: list[DigItem] = []
    for row in db.engaged_discovery_tracks(user_id, actions=("played",)):
        if row["artist_id"] in adopted:
            continue
        track = db.get_track(row["track_id"])
        if not track:
            continue
        bridge = generate_bridge(user_id, profile, track, surface="re-serve")
        if not bridge:
            continue
        items.append(
            DigItem(track=track, bridge_text=bridge["bridge_text"],
                    shared=bridge["shared"], surface="re-serve")
        )
        if len(items) >= limit:
            break
    return items


# -------------------------------------------------------------- OBSERVE ---


def observe(user_id: str) -> list[ArtistAdoption]:
    return adoption.recompute(user_id)


# ---------------------------------------------------------------- ADAPT ---


def adapt(user_id: str) -> float:
    """EMA the taste vector toward newly engaged tracks; apply the engagement
    guardrail (pull comfort back when skip-rate is high). Returns comfort_pref."""
    profile = db.get_taste_profile(user_id)
    user = db.get_user(user_id)
    if not profile or not user:
        return 0.5

    # EMA taste update toward played/saved tracks
    engaged = db.engaged_discovery_tracks(user_id, actions=("played", "saved"))
    vecs = [db.get_track(r["track_id"]).get("embedding") for r in engaged]
    vecs = [v for v in vecs if v]
    taste = profile.get("taste_vector")
    if vecs and taste:
        mean = np.mean(np.asarray(vecs, dtype=np.float32), axis=0)
        updated = (1 - EMA_ALPHA) * np.asarray(taste, dtype=np.float32) + EMA_ALPHA * mean
        db.update_taste_vector(user_id, l2_normalize(updated).tolist())
        db.clear_bridge_cache(user_id)  # taste moved — cached bridges may be stale

    # engagement guardrail
    comfort = float(user["comfort_pref"])
    if adoption.skip_rate(user_id) > SKIP_GUARDRAIL:
        comfort = max(0.0, round(comfort - 0.1, 2))
        db.set_comfort_pref(user_id, comfort)
        logger.info("guardrail: high skip-rate -> comfort nudged to %.2f for %s", comfort, user_id)
    return comfort


# ----------------------------------------------------------------- TICK ---


def _adopted_ids(user_id: str) -> set[str]:
    return {a["artist_id"] for a in db.get_adoptions(user_id) if a["status"] == "adopted"}


def tick(user_id: str) -> LoopResult:
    before = _adopted_ids(user_id)
    rows = observe(user_id)
    comfort = adapt(user_id)
    after = {a.artist_id: a for a in rows if a.status == "adopted"}
    newly = [after[aid] for aid in (set(after) - before)]
    celebration = None
    if newly:
        names = ", ".join(a.artist for a in newly)
        celebration = f"🎉 {names} just entered your long-term rotation."
    # a mission celebration (goal progress / completion) takes priority when relevant
    mission_msg = mission.on_adoptions(user_id, newly)
    if mission_msg:
        celebration = mission_msg
    return LoopResult(
        user_id=user_id, newly_adopted=newly, comfort_pref=comfort, celebration=celebration
    )


# ------------------------------------------------------- TIME SIMULATION ---


def simulate(user_id: str, days: int, plays: int) -> LoopResult:
    """Advance a demo clock: insert *unprompted* listens for tracks the user has
    shown interest in, spread across `days` distinct days over >= ADOPT_WEEKS
    weeks — so adoption can cross its threshold live (no waiting 3 real weeks)."""
    days = max(1, days)
    plays = max(1, plays)
    targets = db.engaged_discovery_tracks(user_id, actions=("played", "saved"))
    if not targets:
        targets = db.served_discovery_tracks(user_id, limit=6)

    span_days = max(days, settings.adopt_weeks * 7 + 1)  # guarantee the week-span crosses
    base = datetime.now(timezone.utc)
    for row in targets:
        for i in range(days):
            # spread dates from (base - span_days) up to base
            frac = i / (days - 1) if days > 1 else 1.0
            played_at = (base - timedelta(days=span_days * (1 - frac))).isoformat()
            for _ in range(plays):
                db.insert_listening(
                    user_id, row["track_id"], row["artist_id"],
                    prompted=False, source="sim", played_at=played_at,
                )
    logger.info("simulate: %d targets x %d days x %d plays for %s", len(targets), days, plays, user_id)
    return tick(user_id)
