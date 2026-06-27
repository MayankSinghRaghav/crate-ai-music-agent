"""Adoption — the North Star.

A win is not "played once" but **a newly-discovered artist entering long-term
rotation**: played on >= ADOPT_DAYS distinct days across >= ADOPT_WEEKS weeks,
*unprompted* (not via a dig click). This module recomputes that from the
listening log and exposes the metrics the dashboard reads.
"""
from __future__ import annotations

from datetime import datetime

from . import db
from .config import settings
from .models import AdoptionMetrics, ArtistAdoption


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _artist_adoption(user_id: str, artist_id: str) -> ArtistAdoption:
    plays = db.unprompted_plays_for_artist(user_id, artist_id)
    name = db.get_artist_name(artist_id)
    if plays:
        dts = sorted(_parse(p) for p in plays)
        distinct_days = len({d.date() for d in dts})
        span_weeks = (dts[-1] - dts[0]).days / 7.0
    else:
        distinct_days, span_weeks = 0, 0.0
    adopted = distinct_days >= settings.adopt_days and span_weeks >= settings.adopt_weeks
    return ArtistAdoption(
        artist_id=artist_id, artist=name,
        status="adopted" if adopted else "candidate",
        distinct_days=distinct_days, span_weeks=round(span_weeks, 2),
    )


def recompute(user_id: str) -> list[ArtistAdoption]:
    """Recompute adoption for every artist Crate surfaced; persist adoption_events."""
    out: list[ArtistAdoption] = []
    now = db.now_iso()
    for artist_id in db.discovery_artist_ids(user_id):
        a = _artist_adoption(user_id, artist_id)
        db.upsert_adoption(
            user_id, artist_id, a.status, a.distinct_days, a.span_weeks,
            first_seen=now, adopted_at=now if a.status == "adopted" else None,
        )
        out.append(a)
    return out


def skip_rate(user_id: str) -> float:
    counts = db.action_counts(user_id)
    decisions = counts.get("played", 0) + counts.get("saved", 0) + counts.get("skipped", 0)
    if decisions == 0:
        return 0.0
    return round(counts.get("skipped", 0) / decisions, 3)


def metrics(user_id: str) -> AdoptionMetrics:
    rows = recompute(user_id)
    # reflect adopted_at persisted across calls
    persisted = {r["artist_id"]: r for r in db.get_adoptions(user_id)}
    for a in rows:
        p = persisted.get(a.artist_id)
        if p and p.get("adopted_at"):
            a.adopted_at = p["adopted_at"]
    adopted = [a for a in rows if a.status == "adopted"]
    candidates = [a for a in rows if a.status != "adopted"]
    rate = round(len(adopted) / len(rows), 3) if rows else 0.0
    user = db.get_user(user_id)

    # discovery funnel: surfaced -> tried -> adopted
    surfaced_ids = {a.artist_id for a in rows}
    tried = len(surfaced_ids & db.played_artist_ids(user_id))
    sr = skip_rate(user_id)
    return AdoptionMetrics(
        user_id=user_id,
        adoption_rate=rate,
        adopted=adopted,
        candidates=sorted(candidates, key=lambda a: a.distinct_days, reverse=True),
        skip_rate=sr,
        comfort_pref=user["comfort_pref"] if user else 0.5,
        surfaced_artists=len(surfaced_ids),
        tried_artists=tried,
        guardrail_active=sr > settings.skip_guardrail,
        skip_guardrail_threshold=settings.skip_guardrail,
    )
