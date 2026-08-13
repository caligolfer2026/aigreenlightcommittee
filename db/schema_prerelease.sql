-- Schema for the PRE-RELEASE database.
--
-- This database is the one every committee agent (creative, finance,
-- marketing, distribution) gets a connection string to. It must never
-- contain a film's own post-release reception (ratings, box office). See
-- the root README's "Data contract" section and data-pipeline/src/schema.py
-- for the payload shape this mirrors.

create table if not exists films (
    id                   serial primary key,
    tmdb_id              integer not null unique,
    title                text not null,
    release_date         date,
    slate                text not null default 'default',
    pre_release_payload  jsonb not null,  -- exact PreReleaseFilm shape from data-pipeline/src/schema.py
    created_at           timestamptz not null default now()
);

create index if not exists films_slate_idx on films (slate);

create table if not exists committee_sessions (
    id          serial primary key,
    slate       text not null,
    started_at  timestamptz not null default now(),
    notes       text
);

create table if not exists votes (
    id           serial primary key,
    session_id   integer not null references committee_sessions(id) on delete cascade,
    film_id      integer not null references films(id) on delete cascade,
    role         text not null check (role in ('creative', 'finance', 'marketing', 'distribution')),
    vote         text not null check (vote in ('greenlight', 'pass')),
    argument     text not null,
    created_at   timestamptz not null default now(),
    unique (session_id, film_id, role)
);

create index if not exists votes_session_idx on votes (session_id);
