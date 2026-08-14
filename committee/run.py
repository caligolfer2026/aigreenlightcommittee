#!/usr/bin/env python3
"""Run a full committee session end to end: four agents vote, then scoring
grades them against actual results. Prints the combined transcript.

Usage (from the repo root):
    python3 -m committee.run --slate default
"""
import argparse

from db.prerelease import create_session, get_slate, get_votes, record_vote
from db.results import get_actual_results, record_score

from .aggregation import aggregate_votes
from .agents import run_agent
from .scoring import run_scoring

ROLES = ["creative", "finance", "marketing", "distribution"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slate", default="default", help="Slate name (default: 'default')")
    args = parser.parse_args()

    films = get_slate(slate=args.slate)
    if not films:
        raise SystemExit(f"No films in slate {args.slate!r}. Run data-pipeline/load_slate.py first.")

    session_id = create_session(slate=args.slate)
    print(f"=== Session {session_id} (slate: {args.slate!r}) ===\n")

    for film in films:
        print(f"--- {film['title']} ---")
        for role in ROLES:
            result = run_agent(role, film["payload"])
            record_vote(
                session_id=session_id,
                film_id=film["id"],
                role=result["role"],
                vote=result["vote"],
                argument=result["argument"],
                confidence=result.get("confidence"),
            )
            print(f"[{role}] {result['vote'].upper()} ({result.get('confidence')}% confident): {result['argument']}\n")

    votes_by_tmdb_id: dict[int, list[dict]] = {}
    for vote in get_votes(session_id):
        votes_by_tmdb_id.setdefault(vote["tmdb_id"], []).append(vote)

    for film in films:
        film_votes = votes_by_tmdb_id.get(film["tmdb_id"], [])
        decision = aggregate_votes(film_votes)
        print(
            f"=== COMMITTEE DECISION: {film['title']} — {decision['outcome'].upper()} "
            f"(confidence-weighted score {decision['confidenceWeightedScore']}/100, "
            f"{decision['greenlightCount']} greenlight / {decision['passCount']} pass) ===\n"
        )

    for film in films:
        film_votes = votes_by_tmdb_id.get(film["tmdb_id"], [])
        actual = get_actual_results(film["tmdb_id"])
        if actual is None:
            print(f"--- {film['title']}: no actual results loaded yet, skipping scoring ---\n")
            continue

        budget = (film["payload"] or {}).get("budget")
        score = run_scoring(film["title"], film_votes, actual["payload"], budget)
        record_score(
            session_id=session_id,
            tmdb_id=film["tmdb_id"],
            grade=score["grade"],
            rationale=score["rationale"],
        )
        print(f"=== SCORE: {film['title']} — {score['grade']} ===")
        print(f"{score['rationale']}\n")


if __name__ == "__main__":
    main()
