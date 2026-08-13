"""Read/write helpers for the results database.

Only the scoring branch (and the data-pipeline loader) should ever import
this module -- everyone else's .env.local shouldn't even have
RESULTS_DATABASE_URL in it. See db/connection.py for why this is a
physically separate database rather than a permissions check.
"""
import json
from typing import List, Optional, TypedDict

from .connection import get_results_connection


class ActualResults(TypedDict):
    tmdb_id: int
    title: str
    payload: dict  # ActualResults shape, see data-pipeline/src/schema.py


def upsert_actual_results(tmdb_id: int, title: str, payload: dict) -> None:
    """Insert or update a film's actual-results payload. Used by the
    data-pipeline loader after the film has released."""
    conn = get_results_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into actual_results (tmdb_id, title, actual_results_payload)
                values (%s, %s, %s)
                on conflict (tmdb_id) do update set
                    title = excluded.title,
                    actual_results_payload = excluded.actual_results_payload,
                    revealed_at = now()
                """,
                (tmdb_id, title, json.dumps(payload)),
            )
        conn.commit()
    finally:
        conn.close()


def get_actual_results(tmdb_id: int) -> Optional[ActualResults]:
    """The one function that reveals real box office / audience data for a
    film. Only ever called from the scoring branch, after voting closes."""
    conn = get_results_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select tmdb_id, title, actual_results_payload from actual_results where tmdb_id = %s",
                (tmdb_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return ActualResults(tmdb_id=row[0], title=row[1], payload=row[2])


def record_score(
    session_id: int,
    tmdb_id: int,
    grade,
    rationale: str,
    per_role: Optional[dict] = None,
) -> None:
    """Save the scoring agent's grade + rationale for one film in a
    session. `grade` can be a number or a short string label."""
    conn = get_results_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into scores (session_id, tmdb_id, grade, rationale, per_role)
                values (%s, %s, %s, %s, %s)
                """,
                (session_id, tmdb_id, str(grade), rationale, json.dumps(per_role) if per_role else None),
            )
        conn.commit()
    finally:
        conn.close()


def get_scores(session_id: int) -> List[dict]:
    """All scores recorded for a session."""
    conn = get_results_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select tmdb_id, grade, rationale, per_role, created_at
                from scores
                where session_id = %s
                order by tmdb_id
                """,
                (session_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "tmdb_id": r[0],
            "grade": r[1],
            "rationale": r[2],
            "per_role": r[3],
            "created_at": r[4].isoformat(),
        }
        for r in rows
    ]
