"""Local data layer (SQLite).

Zero-setup default. Mirrors the Postgres schema in supabase/migrations/0001_init.sql
with type translations (uuid/jsonb/vector/timestamptz -> text). Swapping to the
documented Postgres+pgvector path means re-pointing these helpers; the rest of the
app talks only to the functions below.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Optional

from .config import settings

# ---------------------------------------------------------------- connection ---


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _row(r: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(r) if r is not None else None


# -------------------------------------------------------------------- schema ---

SCHEMA = """
create table if not exists users (
  id text primary key,
  display_name text not null,
  comfort_pref real not null default 0.5,
  persona text,
  mission_seed_genre text,
  created_at text
);

create table if not exists taste_profile (
  user_id text primary key references users(id),
  summary text,
  taste_vector text,            -- json array
  top_artists text default '[]',
  top_genres text default '[]',
  top_moods text default '[]',
  updated_at text
);

create table if not exists catalog_tracks (
  id text primary key,
  title text, artist text, artist_id text,
  genres text,                  -- json array
  era text,
  moods text,                   -- json array
  audio_features text,          -- json object
  preview_url text,
  embedding text                -- json array
);

create table if not exists discovery_events (
  id text primary key,
  user_id text references users(id),
  track_id text references catalog_tracks(id),
  surface text,
  bridge_text text,
  shared text default '[]',
  served_at text,
  action text default 'served'
);

create table if not exists listening_log (
  id text primary key,
  user_id text references users(id),
  track_id text references catalog_tracks(id),
  artist_id text,
  played_at text,
  prompted integer default 0,
  source text default 'runtime' -- seed | runtime | sim
);

create table if not exists adoption_events (
  id text primary key,
  user_id text references users(id),
  artist_id text,
  status text default 'candidate',
  distinct_days integer default 0,
  span_weeks real default 0,
  first_seen text,
  adopted_at text
);

create table if not exists missions (
  id text primary key,
  user_id text references users(id),
  goal text, target_genre text,
  start_at text, end_at text,
  status text default 'active',
  plan text, progress text default '{}'
);

create table if not exists feedback (
  id text primary key,
  user_id text references users(id),
  track_id text references catalog_tracks(id),
  sentiment text,
  reason_text text,
  created_at text
);

create table if not exists bridge_cache (
  user_id text,
  track_id text,
  bridge_text text,
  shared text,
  primary key (user_id, track_id)
);

create index if not exists idx_listening_user_artist on listening_log (user_id, artist_id);
create index if not exists idx_discovery_user on discovery_events (user_id);
create index if not exists idx_adoption_user_artist on adoption_events (user_id, artist_id);
create unique index if not exists uq_adoption_user_artist on adoption_events (user_id, artist_id);
create index if not exists idx_feedback_user on feedback (user_id);
create index if not exists idx_missions_user on missions (user_id, status);
"""

# Additive column migrations for DBs created before a column existed. Each is
# idempotent: a duplicate-column error just means the migration already ran.
_MIGRATIONS = [
    "alter table users add column mission_seed_genre text",
]


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already present


# -------------------------------------------------------------------- tracks ---


def upsert_track(track: dict, embedding: list[float]) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into catalog_tracks
               (id,title,artist,artist_id,genres,era,moods,audio_features,preview_url,embedding)
               values(?,?,?,?,?,?,?,?,?,?)
               on conflict(id) do update set
                 title=excluded.title, artist=excluded.artist, artist_id=excluded.artist_id,
                 genres=excluded.genres, era=excluded.era, moods=excluded.moods,
                 audio_features=excluded.audio_features, preview_url=excluded.preview_url,
                 embedding=excluded.embedding""",
            (
                track["id"], track.get("title"), track.get("artist"), track.get("artist_id"),
                _j(track.get("genres") or []), track.get("era"), _j(track.get("moods") or []),
                _j(track.get("audio_features") or {}), track.get("preview_url"), _j(embedding),
            ),
        )


def _parse_track(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["genres"] = json.loads(d.get("genres") or "[]")
    d["moods"] = json.loads(d.get("moods") or "[]")
    d["audio_features"] = json.loads(d.get("audio_features") or "{}")
    if "embedding" in d and d["embedding"] is not None:
        d["embedding"] = json.loads(d["embedding"])
    return d


def get_track(track_id: str) -> Optional[dict]:
    with _connect() as conn:
        r = conn.execute("select * from catalog_tracks where id=?", (track_id,)).fetchone()
    return _parse_track(r) if r else None


def get_artist_name(artist_id: str) -> str:
    with _connect() as conn:
        r = conn.execute(
            "select artist from catalog_tracks where artist_id=? limit 1", (artist_id,)
        ).fetchone()
    return r["artist"] if r else artist_id


def all_tracks(with_embeddings: bool = True) -> list[dict]:
    cols = "*" if with_embeddings else (
        "id,title,artist,artist_id,genres,era,moods,audio_features,preview_url"
    )
    with _connect() as conn:
        rows = conn.execute(f"select {cols} from catalog_tracks").fetchall()
    return [_parse_track(r) for r in rows]


def tracks_by_genre(genre: str, with_embeddings: bool = False) -> list[dict]:
    """All catalog tracks tagged with `genre` (genres are JSON arrays in SQLite)."""
    return [t for t in all_tracks(with_embeddings=with_embeddings) if genre in (t.get("genres") or [])]


def genre_counts() -> list[dict]:
    """Distinct catalog genres with track + artist counts — powers mission setup."""
    tracks = all_tracks(with_embeddings=False)
    by_genre: dict[str, dict] = {}
    for t in tracks:
        for g in t.get("genres") or []:
            e = by_genre.setdefault(g, {"genre": g, "tracks": 0, "artists": set()})
            e["tracks"] += 1
            e["artists"].add(t.get("artist_id"))
    out = [{"genre": e["genre"], "tracks": e["tracks"], "artists": len(e["artists"])}
           for e in by_genre.values()]
    out.sort(key=lambda e: (-e["tracks"], e["genre"]))
    return out


_TABLES = frozenset({
    "meta", "users", "taste_profile", "catalog_tracks", "discovery_events",
    "listening_log", "adoption_events", "missions", "feedback", "bridge_cache",
})


def count(table: str) -> int:
    if table not in _TABLES:  # the f-string below must never see foreign input
        raise ValueError(f"unknown table: {table!r}")
    with _connect() as conn:
        return conn.execute(f"select count(*) c from {table}").fetchone()["c"]


# --------------------------------------------------------------------- users ---


def upsert_user(
    user_id: str, display_name: str, comfort_pref: float, persona: str | None,
    mission_seed_genre: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into users(id,display_name,comfort_pref,persona,mission_seed_genre,created_at)
               values(?,?,?,?,?,?)
               on conflict(id) do update set
                 display_name=excluded.display_name, comfort_pref=excluded.comfort_pref,
                 persona=excluded.persona, mission_seed_genre=excluded.mission_seed_genre""",
            (user_id, display_name, comfort_pref, persona, mission_seed_genre, now_iso()),
        )


def get_users() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "select id,display_name,comfort_pref,persona,mission_seed_genre from users order by created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_user(user_id: str) -> Optional[dict]:
    with _connect() as conn:
        r = conn.execute(
            "select id,display_name,comfort_pref,persona,mission_seed_genre from users where id=?",
            (user_id,),
        ).fetchone()
    return _row(r)


def set_comfort_pref(user_id: str, comfort: float) -> None:
    with _connect() as conn:
        conn.execute("update users set comfort_pref=? where id=?", (float(comfort), user_id))


# ------------------------------------------------------------- taste profile ---


def upsert_taste_profile(
    user_id: str, summary: str, taste_vector: list[float],
    top_artists: list[str], top_genres: list[str], top_moods: list[str],
) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into taste_profile(user_id,summary,taste_vector,top_artists,top_genres,top_moods,updated_at)
               values(?,?,?,?,?,?,?)
               on conflict(user_id) do update set
                 summary=excluded.summary, taste_vector=excluded.taste_vector,
                 top_artists=excluded.top_artists, top_genres=excluded.top_genres,
                 top_moods=excluded.top_moods, updated_at=excluded.updated_at""",
            (user_id, summary, _j(taste_vector), _j(top_artists), _j(top_genres),
             _j(top_moods), now_iso()),
        )


def get_taste_profile(user_id: str) -> Optional[dict]:
    with _connect() as conn:
        r = conn.execute("select * from taste_profile where user_id=?", (user_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["taste_vector"] = json.loads(d.get("taste_vector") or "[]")
    d["top_artists"] = json.loads(d.get("top_artists") or "[]")
    d["top_genres"] = json.loads(d.get("top_genres") or "[]")
    d["top_moods"] = json.loads(d.get("top_moods") or "[]")
    return d


def get_taste_vector(user_id: str) -> list[float]:
    p = get_taste_profile(user_id)
    return p["taste_vector"] if p else []


def update_taste_vector(user_id: str, vector: list[float]) -> None:
    with _connect() as conn:
        conn.execute(
            "update taste_profile set taste_vector=?, updated_at=? where user_id=?",
            (_j(vector), now_iso(), user_id),
        )


# ------------------------------------------------------------ listening_log ---


def clear_seed_history(user_id: str) -> None:
    with _connect() as conn:
        conn.execute("delete from listening_log where user_id=? and source='seed'", (user_id,))


def insert_listening(
    user_id: str, track_id: str, artist_id: str, *,
    prompted: bool = False, source: str = "runtime", played_at: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into listening_log(id,user_id,track_id,artist_id,played_at,prompted,source)
               values(?,?,?,?,?,?,?)""",
            (new_id(), user_id, track_id, artist_id, played_at or now_iso(), 1 if prompted else 0, source),
        )


def user_exemplars(user_id: str) -> dict:
    """Map each genre/mood the listener actually plays to a representative artist
    (the one they play most in it). Used to anchor bridges to the *right* artist."""
    with _connect() as conn:
        rows = conn.execute(
            """select t.artist, t.genres, t.moods, count(*) c
               from listening_log l join catalog_tracks t on t.id = l.track_id
               where l.user_id=? group by t.artist_id""",
            (user_id,),
        ).fetchall()
    by_genre: dict[str, tuple[str, int]] = {}
    by_mood: dict[str, tuple[str, int]] = {}
    for r in rows:
        artist, c = r["artist"], r["c"]
        for g in json.loads(r["genres"] or "[]"):
            if c > by_genre.get(g, ("", 0))[1]:
                by_genre[g] = (artist, c)
        for m in json.loads(r["moods"] or "[]"):
            if c > by_mood.get(m, ("", 0))[1]:
                by_mood[m] = (artist, c)
    return {
        "by_genre": {g: a for g, (a, _) in by_genre.items()},
        "by_mood": {m: a for m, (a, _) in by_mood.items()},
    }


def known_artist_ids(user_id: str) -> set[str]:
    """Artists already in the user's rotation (any listening) or top_artists."""
    with _connect() as conn:
        rows = conn.execute(
            "select distinct artist_id from listening_log where user_id=?", (user_id,)
        ).fetchall()
    ids = {r["artist_id"] for r in rows if r["artist_id"]}
    prof = get_taste_profile(user_id)
    if prof:
        ids.update(prof.get("top_artists") or [])
    return ids


def played_artist_ids(user_id: str, include_seed: bool = False) -> set[str]:
    """Artists the user has actually played (runtime/sim, and optionally seed).
    Used for mission 'tried' progress — distinct from adoption."""
    sql = "select distinct artist_id from listening_log where user_id=?"
    if not include_seed:
        sql += " and source != 'seed'"
    with _connect() as conn:
        rows = conn.execute(sql, (user_id,)).fetchall()
    return {r["artist_id"] for r in rows if r["artist_id"]}


def unprompted_plays_for_artist(user_id: str, artist_id: str) -> list[str]:
    """played_at timestamps of unprompted plays (the adoption signal)."""
    with _connect() as conn:
        rows = conn.execute(
            "select played_at from listening_log where user_id=? and artist_id=? and prompted=0",
            (user_id, artist_id),
        ).fetchall()
    return [r["played_at"] for r in rows]


# --------------------------------------------------------- discovery_events ---


def insert_discovery_event(
    user_id: str, track_id: str, surface: str, bridge_text: str, shared: list[str],
) -> str:
    eid = new_id()
    with _connect() as conn:
        conn.execute(
            """insert into discovery_events(id,user_id,track_id,surface,bridge_text,shared,served_at,action)
               values(?,?,?,?,?,?,?, 'served')""",
            (eid, user_id, track_id, surface, bridge_text, _j(shared), now_iso()),
        )
    return eid


def set_discovery_action(user_id: str, track_id: str, action: str) -> None:
    """Mark the most recent served event for this (user,track) with an action."""
    with _connect() as conn:
        conn.execute(
            """update discovery_events set action=?
               where id = (select id from discovery_events
                           where user_id=? and track_id=? order by served_at desc limit 1)""",
            (action, user_id, track_id),
        )


def discovery_artist_ids(user_id: str) -> list[str]:
    """Distinct artists Crate has surfaced to this user (adoption candidates)."""
    with _connect() as conn:
        rows = conn.execute(
            """select distinct t.artist_id from discovery_events d
               join catalog_tracks t on t.id = d.track_id where d.user_id=?""",
            (user_id,),
        ).fetchall()
    return [r["artist_id"] for r in rows if r["artist_id"]]


def engaged_discovery_tracks(user_id: str, actions=("played", "saved")) -> list[dict]:
    """Tracks the user played/saved from a dig — candidates for re-serve & simulate."""
    qs = ",".join("?" for _ in actions)
    with _connect() as conn:
        rows = conn.execute(
            f"""select distinct d.track_id, t.artist_id from discovery_events d
                join catalog_tracks t on t.id=d.track_id
                where d.user_id=? and d.action in ({qs})""",
            (user_id, *actions),
        ).fetchall()
    return [dict(r) for r in rows]


def served_discovery_tracks(user_id: str, limit: int = 8) -> list[dict]:
    """Most-recently served dig tracks — simulate's fallback when nothing's engaged yet."""
    with _connect() as conn:
        rows = conn.execute(
            """select d.track_id, t.artist_id from discovery_events d
               join catalog_tracks t on t.id=d.track_id
               where d.user_id=? order by d.served_at desc limit ?""",
            (user_id, limit),
        ).fetchall()
    seen, out = set(), []
    for r in rows:
        if r["track_id"] in seen:
            continue
        seen.add(r["track_id"])
        out.append(dict(r))
    return out


def action_counts(user_id: str) -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "select action, count(*) c from discovery_events where user_id=? group by action",
            (user_id,),
        ).fetchall()
    return {r["action"]: r["c"] for r in rows}


# ------------------------------------------------------------------ feedback ---


def insert_feedback(user_id: str, track_id: str, sentiment: str, reason: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into feedback(id,user_id,track_id,sentiment,reason_text,created_at)
               values(?,?,?,?,?,?)""",
            (new_id(), user_id, track_id, sentiment, reason, now_iso()),
        )


def rejected_artist_ids(user_id: str) -> set[str]:
    """Artists down-voted by the user (excluded from future digs)."""
    with _connect() as conn:
        rows = conn.execute(
            """select distinct t.artist_id from feedback f
               join catalog_tracks t on t.id=f.track_id
               where f.user_id=? and f.sentiment='down'""",
            (user_id,),
        ).fetchall()
    return {r["artist_id"] for r in rows if r["artist_id"]}


# ------------------------------------------------------------ bridge cache ---


def get_cached_bridge(user_id: str, track_id: str) -> Optional[dict]:
    with _connect() as conn:
        r = conn.execute(
            "select bridge_text, shared from bridge_cache where user_id=? and track_id=?",
            (user_id, track_id),
        ).fetchone()
    if not r:
        return None
    return {"bridge_text": r["bridge_text"], "shared": json.loads(r["shared"] or "[]")}


def clear_bridge_cache(user_id: str) -> None:
    """Invalidate cached bridges after the taste vector moves (EMA update) —
    otherwise a bridge can reference a stale anchor artist forever."""
    with _connect() as conn:
        conn.execute("delete from bridge_cache where user_id=?", (user_id,))


def set_cached_bridge(user_id: str, track_id: str, bridge_text: str, shared: list[str]) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into bridge_cache(user_id,track_id,bridge_text,shared) values(?,?,?,?)
               on conflict(user_id,track_id) do update set
                 bridge_text=excluded.bridge_text, shared=excluded.shared""",
            (user_id, track_id, bridge_text, _j(shared)),
        )


# ----------------------------------------------------------- adoption_events ---


def upsert_adoption(
    user_id: str, artist_id: str, status: str, distinct_days: int, span_weeks: float,
    first_seen: str | None, adopted_at: str | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """insert into adoption_events(id,user_id,artist_id,status,distinct_days,span_weeks,first_seen,adopted_at)
               values(?,?,?,?,?,?,?,?)
               on conflict(user_id,artist_id) do update set
                 status=excluded.status, distinct_days=excluded.distinct_days,
                 span_weeks=excluded.span_weeks,
                 adopted_at=coalesce(adoption_events.adopted_at, excluded.adopted_at)""",
            (new_id(), user_id, artist_id, status, distinct_days, span_weeks, first_seen, adopted_at),
        )


def get_adoptions(user_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "select * from adoption_events where user_id=? order by distinct_days desc", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------- missions ---


def _parse_mission(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["plan"] = json.loads(d.get("plan") or "{}")
    d["progress"] = json.loads(d.get("progress") or "{}")
    return d


def create_mission(
    user_id: str, goal: str, target_genre: str, plan: dict, end_at: str | None,
) -> str:
    """Persist a new mission. Supersedes any prior active/completed mission so a
    user always has exactly one current mission."""
    mid = new_id()
    with _connect() as conn:
        conn.execute(
            "update missions set status='archived' where user_id=? and status in ('active','completed')",
            (user_id,),
        )
        conn.execute(
            """insert into missions(id,user_id,goal,target_genre,start_at,end_at,status,plan,progress)
               values(?,?,?,?,?,?, 'active', ?, '{}')""",
            (mid, user_id, goal, target_genre, now_iso(), end_at, _j(plan)),
        )
    return mid


def get_active_mission(user_id: str) -> Optional[dict]:
    """The user's current mission (active or just-completed), if any."""
    with _connect() as conn:
        r = conn.execute(
            """select * from missions where user_id=? and status in ('active','completed')
               order by start_at desc limit 1""",
            (user_id,),
        ).fetchone()
    return _parse_mission(r) if r else None


def set_mission_status(mission_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute("update missions set status=? where id=?", (status, mission_id))


def update_mission_progress(mission_id: str, progress: dict) -> None:
    with _connect() as conn:
        conn.execute("update missions set progress=? where id=?", (_j(progress), mission_id))


def end_active_mission(user_id: str) -> bool:
    """Abandon the user's current mission. Returns True if one was active."""
    with _connect() as conn:
        cur = conn.execute(
            "update missions set status='abandoned' where user_id=? and status in ('active','completed')",
            (user_id,),
        )
        return cur.rowcount > 0


# --------------------------------------------------------------- demo reset ---


def reset_runtime(user_id: str) -> None:
    """Wipe a user's runtime state (events/plays/feedback/adoptions) for a clean demo.
    Leaves catalog, users, taste profiles, and seed history intact."""
    with _connect() as conn:
        conn.execute("delete from discovery_events where user_id=?", (user_id,))
        conn.execute("delete from listening_log where user_id=? and source!='seed'", (user_id,))
        conn.execute("delete from feedback where user_id=?", (user_id,))
        conn.execute("delete from adoption_events where user_id=?", (user_id,))
        conn.execute("delete from bridge_cache where user_id=?", (user_id,))
        conn.execute("delete from missions where user_id=?", (user_id,))
