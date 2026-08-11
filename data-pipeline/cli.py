#!/usr/bin/env python3
"""Look up a film and print its pre-release and actual-results payloads.

Usage:
    python3 cli.py "Dune: Part Two"
"""
import argparse
import json
import os
import sys

from src.env import load_env_file
from src.pipeline import fetch_film


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", help="Film title to look up")
    args = parser.parse_args()

    load_env_file(".env.local")
    tmdb_key = os.environ.get("TMDB_API_KEY")
    omdb_key = os.environ.get("OMDB_API_KEY")
    if not tmdb_key or not omdb_key:
        print(
            "Missing TMDB_API_KEY and/or OMDB_API_KEY. Copy .env.example to "
            ".env.local and fill in your keys.",
            file=sys.stderr,
        )
        return 1

    pre_release, actual_results = fetch_film(args.title, tmdb_key, omdb_key)
    print(json.dumps({"preRelease": pre_release, "actualResults": actual_results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
