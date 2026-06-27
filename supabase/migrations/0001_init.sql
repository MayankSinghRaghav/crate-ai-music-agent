-- Crate — initial schema (Postgres / Supabase, production-fidelity path).
-- Local dev uses an equivalent SQLite schema created by services/api/app/db.py.
-- pgvector dimension matches OpenAI text-embedding-3-large (3072).

create extension if not exists vector;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  display_name text not null,
  comfort_pref real not null default 0.5,         -- 0=comfort, 1=curiosity
  created_at timestamptz default now()
);

create table if not exists taste_profile (
  user_id uuid primary key references users(id),
  summary text,                                   -- LLM-written taste summary
  taste_vector vector(3072),                      -- weighted avg of liked/played embeddings
  top_artists jsonb default '[]',
  trajectory jsonb default '[]',                  -- [{week, tried[], adopted[], rejected[]}]
  updated_at timestamptz default now()
);

create table if not exists catalog_tracks (
  id text primary key,
  title text, artist text, artist_id text,
  genres text[], era text, moods text[],
  audio_features jsonb,                           -- {energy,valence,acousticness,tempo}
  preview_url text,
  embedding vector(3072)
);

create table if not exists discovery_events (     -- something Crate served
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  track_id text references catalog_tracks(id),
  surface text,                                   -- 'dig' | 're-serve' | 'mission'
  bridge_text text,
  served_at timestamptz default now(),
  action text default 'served'                    -- served|played|skipped|saved
);

create table if not exists listening_log (        -- plays used to compute adoption
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  track_id text references catalog_tracks(id),
  artist_id text,
  played_at timestamptz default now(),
  prompted boolean default false                  -- true if play came from clicking a dig
);

create table if not exists adoption_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  artist_id text,
  status text default 'candidate',                -- candidate|adopted
  distinct_days int default 0,
  span_weeks real default 0,
  first_seen timestamptz,
  adopted_at timestamptz
);

create table if not exists missions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  goal text, target_genre text,
  start_at timestamptz default now(), end_at timestamptz,
  status text default 'active',                   -- active|completed
  plan jsonb, progress jsonb default '{}'
);

create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  track_id text references catalog_tracks(id),
  sentiment text,                                 -- 'up' | 'down'
  reason_text text, created_at timestamptz default now()
);

create index if not exists idx_listening_user_artist on listening_log (user_id, artist_id);
create index if not exists idx_discovery_user on discovery_events (user_id);
create index if not exists idx_adoption_user_artist on adoption_events (user_id, artist_id);
create index if not exists idx_feedback_user on feedback (user_id);
