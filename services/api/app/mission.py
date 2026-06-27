"""Discovery Missions — the Goal layer.

A mission is an *intentful* on-ramp: "get me into {genre} over 3 weeks." The agent
plans a staged set of digs (accessible -> deep), injects them into Today's Dig as
`surface='mission'`, tracks progress from real listens, and celebrates when a
mission artist crosses the adoption threshold.

Progress is computed *live* from the listening log and adoption events (the single
source of truth) rather than trusted from a stored counter — so it can never drift
from what actually happened.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import db, llm
from .config import settings
from .models import (
    Mission, MissionProgress, MissionTrack, MissionWeek, Track,
)

logger = logging.getLogger("crate.mission")

MIN_ARTISTS = 3          # a genre needs at least this many distinct artists to plan
COMPLETION_TARGET = 3    # adopt this many distinct mission artists -> "you're into it"


# --------------------------------------------------------------- planning ---


def _candidates(user_id: str, genre: str) -> list[dict]:
    """Tracks in `genre` eligible for a mission: never a down-voted artist, and —
    when possible — artists the listener doesn't already play (a mission is about
    *new* discoveries). Falls back to all non-rejected if that's too thin."""
    rejected = db.rejected_artist_ids(user_id)
    known = db.known_artist_ids(user_id)
    pool = [t for t in db.tracks_by_genre(genre) if t.get("artist_id") not in rejected]
    fresh = [t for t in pool if t.get("artist_id") not in known]
    if len({t["artist_id"] for t in fresh}) >= MIN_ARTISTS:
        return fresh
    return pool


def can_plan(user_id: str, genre: str) -> bool:
    return len({t["artist_id"] for t in _candidates(user_id, genre)}) >= MIN_ARTISTS


def create(user_id: str, target_genre: str) -> Optional[Mission]:
    """Plan + persist a mission. Returns the Mission, or None if the genre can't
    sustain one (too few distinct artists)."""
    genre = target_genre.strip().lower()
    profile = db.get_taste_profile(user_id) or {}
    candidates = _candidates(user_id, genre)
    if len({t["artist_id"] for t in candidates}) < MIN_ARTISTS:
        return None

    plan = llm.plan_mission_weeks(genre, profile, candidates)
    end_at = (datetime.now(timezone.utc) + timedelta(weeks=settings.adopt_weeks)).isoformat()
    db.create_mission(user_id, goal=f"Get into {genre}", target_genre=genre,
                      plan=plan, end_at=end_at)
    logger.info("mission created: %s -> %s (%d weeks planned)", user_id, genre, len(plan.get("weeks", [])))
    return get(user_id)


# --------------------------------------------------------------- read/progress ---


def _plan_rows(mission: dict) -> list[dict]:
    """Flatten the plan to ordered rows: {week, theme, track}. Skips ids that no
    longer resolve (defensive)."""
    rows: list[dict] = []
    for w in mission.get("plan", {}).get("weeks", []):
        for tid in w.get("track_ids", []):
            t = db.get_track(tid)
            if t:
                rows.append({"week": int(w.get("week", 0)), "theme": w.get("theme", ""), "track": t})
    return rows


def _progress(user_id: str, rows: list[dict]) -> MissionProgress:
    artist_ids = {r["track"]["artist_id"] for r in rows}
    tried = artist_ids & db.played_artist_ids(user_id)
    adopted = {a["artist_id"] for a in db.get_adoptions(user_id)
               if a["status"] == "adopted" and a["artist_id"] in artist_ids}
    target = min(COMPLETION_TARGET, len(artist_ids)) or 1
    percent = min(100, round(100 * len(adopted) / target))
    return MissionProgress(
        total_artists=len(artist_ids),
        tried_artists=len(tried),
        adopted_artists=len(adopted),
        target_artists=target,
        percent=percent,
        status="completed" if len(adopted) >= target else "active",
    )


def get(user_id: str) -> Optional[Mission]:
    """The user's current mission with live progress, or None."""
    m = db.get_active_mission(user_id)
    if not m:
        return None
    rows = _plan_rows(m)
    tried = db.played_artist_ids(user_id)
    adopted = {a["artist_id"] for a in db.get_adoptions(user_id) if a["status"] == "adopted"}

    weeks: dict[int, MissionWeek] = {}
    for r in rows:
        t = r["track"]
        wk = weeks.setdefault(r["week"], MissionWeek(week=r["week"], theme=r["theme"], tracks=[]))
        wk.tracks.append(MissionTrack(
            id=t["id"], title=t["title"], artist=t["artist"], artist_id=t["artist_id"],
            tried=t["artist_id"] in tried, adopted=t["artist_id"] in adopted,
        ))

    prog = _progress(user_id, rows)
    return Mission(
        id=m["id"], user_id=user_id, goal=m["goal"], target_genre=m["target_genre"],
        status=m["status"], weeks=[weeks[k] for k in sorted(weeks)],
        progress=prog, start_at=m.get("start_at"), end_at=m.get("end_at"),
    )


def end(user_id: str) -> bool:
    return db.end_active_mission(user_id)


# --------------------------------------------------------------- dig injection ---


def dig_items(user_id: str, profile: dict, limit: int = 2):
    """Mission tracks to weave into Today's Dig (surface='mission'). Surfaces the
    earliest un-adopted week first, one track per artist, so the on-ramp advances
    in order. Imported lazily by main.dig to keep import graph flat."""
    from .models import DigItem  # local import avoids a heavy top-level cycle

    m = db.get_active_mission(user_id)
    if not m or m["status"] != "active":
        return []

    adopted = {a["artist_id"] for a in db.get_adoptions(user_id) if a["status"] == "adopted"}
    items: list[DigItem] = []
    used_artists: set[str] = set()
    for r in _plan_rows(m):  # already week-ordered
        t = r["track"]
        aid = t["artist_id"]
        if aid in adopted or aid in used_artists:
            continue
        used_artists.add(aid)
        bridge = llm.mission_bridge(user_id, profile, t, r["week"], r["theme"], m["target_genre"])
        items.append(DigItem(
            track=Track(**{k: t[k] for k in (
                "id", "title", "artist", "artist_id", "genres", "era", "moods",
                "audio_features", "preview_url") if k in t}),
            bridge_text=bridge["bridge_text"], shared=bridge["shared"], surface="mission",
        ))
        if len(items) >= limit:
            break
    return items


# --------------------------------------------------------------- adoption hook ---


def on_adoptions(user_id: str, newly_adopted: list) -> Optional[str]:
    """Called from the agent loop after adoption recompute. Updates mission status
    and returns a mission-flavoured celebration string when relevant."""
    m = db.get_active_mission(user_id)
    if not m:
        return None
    rows = _plan_rows(m)
    artist_ids = {r["track"]["artist_id"] for r in rows}
    prog = _progress(user_id, rows)
    db.update_mission_progress(m["id"], prog.model_dump())

    genre = m["target_genre"]
    mission_new = [a for a in newly_adopted if a.artist_id in artist_ids]

    if prog.status == "completed" and m["status"] != "completed":
        db.set_mission_status(m["id"], "completed")
        return (f"🎉 Mission complete — you're officially into {genre}! "
                f"{prog.adopted_artists} artists now in long-term rotation.")
    if mission_new and m["status"] == "active":
        names = ", ".join(a.artist for a in mission_new)
        return f"🎉 {names} adopted — your {genre} mission is {prog.percent}% there."
    return None
