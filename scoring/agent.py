#!/usr/bin/env python3
"""Scoring agent: reveal actual results and grade the committee's pre-release
votes against them.

Run from the repo root:
    python3 scoring/agent.py
    python3 scoring/agent.py --session 1 --slate default

Needs ANTHROPIC_API_KEY, PRERELEASE_DATABASE_URL, and RESULTS_DATABASE_URL in
.env.local at the repo root -- see db/README.md for how to get these. Without
ANTHROPIC_API_KEY, the agent still runs and records a grade, just with a
templated rationale instead of an LLM-written one.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Make the repo-root `db` package importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.env import load_env_file
from db.prerelease import get_slate, get_votes
from db.results import get_actual_results, record_score

from calibration import compute_calibration
from anthropic_client import build_rationale


def group_votes_by_film(votes: list) -> dict:
    """{tmdb_id: [votes for that film]}, preserving vote order within a film."""
    by_film = defaultdict(list)
    for v in votes:
        by_film[v["tmdb_id"]].append(v)
    return dict(by_film)


def budgets_by_tmdb_id(slate: str) -> dict:
    """Budget lives in the pre-release payload, not in get_votes()'s output
    or get_actual_results()'s payload -- so it's pulled separately here."""
    return {f["tmdb_id"]: (f["payload"] or {}).get("budget") for f in get_slate(slate)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=int, default=1, help="Committee session id (default: 1)")
    parser.add_argument(
        "--slate", default="default", help="Slate name, to look up budgets (default: 'default')"
    )
    args = parser.parse_args()

    load_env_file(".env.local")

    votes = get_votes(args.session)
    if not votes:
        print(f"No votes found for session {args.session}.", file=sys.stderr)
        return 1

    budgets = budgets_by_tmdb_id(args.slate)
    by_film = group_votes_by_film(votes)

    graded_any = False
    for tmdb_id, film_votes in by_film.items():
        title = film_votes[0]["title"]
        actual = get_actual_results(tmdb_id)

        if actual is None:
            print(f"Skipping {title!r} (tmdb_id={tmdb_id}): no actual results loaded yet.")
            continue

        budget = budgets.get(tmdb_id)
        computed = compute_calibration(film_votes, actual["payload"], budget)
        rationale = build_rationale(title, film_votes, actual["payload"], computed)

        record_score(
            session_id=args.session,
            tmdb_id=tmdb_id,
            grade=computed["grade"],
            rationale=rationale,
        )
        graded_any = True

        print(f'{title}: grade={computed["grade"]} score={computed["score"]}/100')
        print(f"  {rationale}")

    if not graded_any:
        print("No films had actual results to grade against.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
