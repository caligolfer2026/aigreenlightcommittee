"""Run the Marketing Agent across a database slate and record session votes."""

import argparse
import json
from typing import Callable, Iterable, Optional

from db.prerelease import get_slate, record_vote

from .agent import evaluate_marketing


def run_slate(
    session_id: int = 1,
    slate: str = "default",
    dry_run: bool = False,
    films: Optional[Iterable[dict]] = None,
    evaluator: Callable[[dict], dict] = evaluate_marketing,
    recorder: Callable[..., None] = record_vote,
) -> list:
    """Evaluate every film and optionally write votes to the shared database."""
    selected_films = list(films) if films is not None else get_slate(slate=slate)
    results = []
    for film in selected_films:
        result = evaluator(film["payload"])
        if not dry_run:
            recorder(
                session_id=session_id,
                film_id=film["id"],
                role=result["role"],
                vote=result["vote"],
                argument=result["argument"],
            )
        results.append({"film_id": film["id"], "title": film["title"], **result})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", type=int, default=1)
    parser.add_argument("--slate", default="default")
    parser.add_argument(
        "--dry-run", action="store_true", help="Evaluate without recording votes"
    )
    args = parser.parse_args()
    results = run_slate(args.session_id, args.slate, args.dry_run)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
