#!/usr/bin/env python3
"""One-off diagnostic: what's actually in the pre-release database right now?
Doesn't write anything -- just reports sessions, vote counts, and loaded
films so we know why get_votes(1) came back empty.

Run from the repo root:
    python3 scoring/diagnose.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.env import load_env_file
from db.prerelease import get_prerelease_connection


def main() -> int:
    load_env_file(".env.local")
    conn = get_prerelease_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("select id, slate, notes, started_at from committee_sessions order by id")
            sessions = cur.fetchall()

            cur.execute("select session_id, count(*) from votes group by session_id order by session_id")
            vote_counts = cur.fetchall()

            cur.execute("select id, tmdb_id, title, slate from films order by id")
            films = cur.fetchall()
    finally:
        conn.close()

    print("=== committee_sessions ===")
    if not sessions:
        print("  (none -- no session has ever been created)")
    for s in sessions:
        print(f"  id={s[0]} slate={s[1]!r} notes={s[2]!r} created_at={s[3]}")

    print("\n=== votes, grouped by session_id ===")
    if not vote_counts:
        print("  (none -- zero votes recorded anywhere, for any session)")
    for session_id, count in vote_counts:
        print(f"  session_id={session_id}: {count} votes")

    print("\n=== films ===")
    if not films:
        print("  (none -- no films loaded)")
    for f in films:
        print(f"  id={f[0]} tmdb_id={f[1]} title={f[2]!r} slate={f[3]!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
