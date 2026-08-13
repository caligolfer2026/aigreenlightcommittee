#!/usr/bin/env python3
"""Apply the schema to one of the two central databases.

Usage (run from the repo root, so `db` resolves as a package):
    python3 -m db.init_db --prerelease
    python3 -m db.init_db --results

Run each of these once, after your team lead has created the two Neon
projects and shared the connection strings. Safe to re-run -- every
statement is `create table if not exists`.
"""
import argparse
from pathlib import Path

from .connection import get_prerelease_connection, get_results_connection

HERE = Path(__file__).parent


def apply_schema(conn, sql_file: Path) -> None:
    sql = sql_file.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prerelease", action="store_true", help="Apply schema_prerelease.sql")
    group.add_argument("--results", action="store_true", help="Apply schema_results.sql")
    args = parser.parse_args()

    if args.prerelease:
        conn = get_prerelease_connection()
        apply_schema(conn, HERE / "schema_prerelease.sql")
        print("Pre-release schema applied.")
    else:
        conn = get_results_connection()
        apply_schema(conn, HERE / "schema_results.sql")
        print("Results schema applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
