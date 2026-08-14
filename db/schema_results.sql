-- Schema for the RESULTS database.
--
-- This is a *separate* Postgres instance from the pre-release database.
-- Only the scoring branch (and the data-pipeline loader) ever gets a
-- connection string to this one. That physical separation -- not just an
-- app-level check -- is what stops a bug or a stray query from leaking
-- actual box office / audience numbers to the committee agents before they
-- vote.

create table if not exists actual_results (
    id                     serial primary key,
    tmdb_id                integer not null unique,  -- matches films.tmdb_id in the pre-release db
    title                  text not null,
    -- Exact ActualResults JSON shape from data-pipeline/src/schema.py. Awareness
    -- scoring uses tmdbPopularity, tmdbVoteCount, and imdbVotes from this payload.
    actual_results_payload jsonb not null,
    revealed_at            timestamptz not null default now()
);

create table if not exists scores (
    id           serial primary key,
    session_id   integer not null,  -- matches committee_sessions.id in the pre-release db (cross-db, not a real FK)
    tmdb_id      integer not null,
    grade        text,
    rationale    text not null,
    per_role     jsonb,  -- optional per-agent breakdown, e.g. {"creative": {...}, "finance": {...}}
    created_at   timestamptz not null default now()
);

create index if not exists scores_session_idx on scores (session_id);
