"""Read/write helpers for the pre-release database.

This is the module every committee agent branch (creative, finance,
marketing, distribution) should import from. It never touches the results
database -- there's no function here that could return post-release data,
because this module has no connection to that database at all.
"""
import json
from typing import List, Optional, TypedDict

from .connection import get_prerelease_connection


class Film(TypedDict):
    id: int
    tmdb_id: int
    title: str
    release_date: Optional[str]
    payload: dict  # PreReleaseFilm shape, see data-pipeline/src/schema.py


def upsert_film(
    tmdb_id: int, title: str, release_date: Optional[str], payload: dict, slate: str = "default"
) -> int:
    """Insert or update a film's pre-release payload. Returns the film's id.
    Used by the data-pipeline loader, not by the committee agents."""
    conn = get_prerelease_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into films (tmdb_id, title, release_date, slate, pre_release_payload)
                values (%s, %s, %s, %s, %s)
                on conflict (tmdb_id) do update set
                    title = excluded.title,
                    release_date = excluded.release_date,
                    slate = excluded.slate,
                    pre_release_payload = excluded.pre_release_payload
                returning id
                """,
                (tmdb_id, title, release_date, slate, json.dumps(payload)),
            )
            film_id = cur.fetchone()[0]
        conn.commit()
        return film_id
    finally:
        conn.close()


def get_slate(slate: str = "default") -> List[Film]:
    """Return every film in a slate, with its pre-release payload. This is
    what a committee agent calls to get the films it's voting on."""
    conn = get_prerelease_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, tmdb_id, title, release_date, pre_release_payload
                from films
                where slate = %s
                order by id
                """,
                (slate,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        Film(id=r[0], tmdb_id=r[1], title=r[2], release_date=str(r[3]) if r[3] else None, payload=r[4])
        for r in rows
    ]


def create_session(slate: str = "default", notes: Optional[str] = None) -> int:
    """Start a new committee session for a slate. Returns the session id --
    every agent voting in this round should pass the same session id."""
    conn = get_prerelease_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into committee_sessions (slate, notes) values (%s, %s) returning id",
                (slate, notes),
            )
            session_id = cur.fetchone()[0]
        conn.commit()
        return session_id
    finally:
        conn.close()


def record_vote(
    session_id: int,
    film_id: int,
    role: str,
    vote: str,
    argument: str,
    confidence: Optional[int] = None,
) -> None:
    """Record one agent's vote + argument for one film in a session. `role`
    must be one of creative/finance/marketing/distribution; `vote` must be
    greenlight/pass -- matches the data contract in the root README.
    `confidence` (0-100) is optional so older callers still work."""
    conn = get_prerelease_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into votes (session_id, film_id, role, vote, confidence, argument)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (session_id, film_id, role) do update set
                    vote = excluded.vote,
                    confidence = excluded.confidence,
                    argument = excluded.argument
                """,
                (session_id, film_id, role, vote, confidence, argument),
            )
        conn.commit()
    finally:
        conn.close()


def get_votes(session_id: int) -> List[dict]:
    """All votes cast in a session, across all four roles. The scoring
    agent uses this (joined with results.get_actual_results) to grade the
    committee."""
    conn = get_prerelease_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select v.film_id, f.tmdb_id, f.title, v.role, v.vote, v.confidence, v.argument, v.created_at
                from votes v
                join films f on f.id = v.film_id
                where v.session_id = %s
                order by v.film_id, v.role
                """,
                (session_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "film_id": r[0],
            "tmdb_id": r[1],
            "title": r[2],
            "role": r[3],
            "vote": r[4],
            "confidence": r[5],
            "argument": r[6],
            "created_at": r[7].isoformat(),
        }
        for r in rows
    ]
