#!/usr/bin/env python3
"""Fetch a list of films and load them into the two central databases.

Usage:
    python3 load_slate.py --slate 2026-spring "Dune: Part Two" "Wicked"

Run this from inside data-pipeline/ (same as cli.py). It needs
TMDB_API_KEY, OMDB_API_KEY, PRERELEASE_DATABASE_URL, and
RESULTS_DATABASE_URL in data-pipeline/.env.local -- see .env.example.

Only the data-pipeline branch needs RESULTS_DATABASE_URL. This script is
the one place in the whole project where both the pre-release and the
actual-results payload exist side by side; everywhere else they're kept in
separate databases on purpose.
"""
import argparse
import os
import sys
from pathlib import Path

# Make the repo-root `db` package importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.prerelease import upsert_film
from db.results import upsert_actual_results
from src.env import load_env_file
from src.pipeline import find_movie, fetch_film


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("titles", nargs="+", help="Film titles to fetch and load")
    parser.add_argument("--slate", default="default", help="Slate name (default: 'default')")
    args = parser.parse_args()

    load_env_file(".env.local")
    tmdb_key = os.environ.get("TMDB_API_KEY")
    omdb_key = os.environ.get("OMDB_API_KEY")
    if not tmdb_key or not omdb_key:
        print("Missing TMDB_API_KEY and/or OMDB_API_KEY in .env.local.", file=sys.stderr)
        return 1

    for title in args.titles:
        match = find_movie(title, tmdb_key)
        if not match:
            print(f"Skipping {title!r}: no TMDB match found.", file=sys.stderr)
            continue

        pre_release, actual_results = fetch_film(title, tmdb_key, omdb_key)

        film_id = upsert_film(
            tmdb_id=match["id"],
            title=pre_release["title"],
            release_date=pre_release["releaseDate"],
            payload=pre_release,
            slate=args.slate,
        )
        upsert_actual_results(
            tmdb_id=match["id"],
            title=pre_release["title"],
            payload=actual_results,
        )
        print(f"Loaded {pre_release['title']!r} (film id {film_id}, tmdb id {match['id']}) into slate {args.slate!r}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
