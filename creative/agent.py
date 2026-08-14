"""The creative agent for the AI Greenlight Committee.

Reads the slate from the pre-release database, asks Claude to evaluate each
film on creative merit alone, and records one vote per film.

Run from the repo root so `db` resolves as a package:

    python -m creative.agent

Needs two values in `.env.local` at the repo root:

    ANTHROPIC_API_KEY
    PRERELEASE_DATABASE_URL

The agent's persona lives in `.claude/agents/creative.md` -- this module reads
that file and uses its body as the system prompt, so tuning the character
means editing the markdown, not this code.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import anthropic

from db.env import load_env_file
from db.prerelease import get_slate, record_vote

ROLE = "creative"
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_SESSION_ID = 1

REPO_ROOT = Path(__file__).resolve().parents[1]
PERSONA_PATH = REPO_ROOT / ".claude" / "agents" / "creative.md"

# The API guarantees the response matches this, so no defensive parsing below.
VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "enum": [ROLE]},
        "argument": {
            "type": "string",
            "description": (
                "The full evaluation, in the CCO's voice, covering all four "
                "criteria and ending with the [Predicted Reception Score: "
                "XX/100] line."
            ),
        },
        "vote": {"type": "string", "enum": ["greenlight", "pass"]},
    },
    "required": ["role", "argument", "vote"],
    "additionalProperties": False,
}

# Appended to the persona. This is the part that must hold even if the persona
# file is rewritten, so it says "overrides anything above" and repeats the
# boundaries rather than assuming the markdown still covers them.
FRAMING = """
---

## Committee framing (overrides anything above)

You are voting as the CREATIVE member of a four-person greenlight committee.
Finance, Marketing, and Distribution are separate agents with their own lenses.

**Judge on creative merit only** -- story quality, director and cast pedigree,
originality vs. franchise fatigue, and artistic risk. Budget, break-even math,
audience appeal, positioning, and release windows belong to the other three.
The payload includes a `budget` figure; it is context, not your argument.

**You see pre-release information only.** The payload contains everything that
would have been known before this film opened, and nothing else. You must never
use or reason from how the film under evaluation was actually received -- its
reviews, box office, ratings, or awards -- even if you recognize the title and
remember them. That information does not exist yet. If you notice yourself
reaching for it, stop and argue from the payload instead.

The *other* films in the payload are a different matter: `comparableFilms`,
`franchiseEntries`, `directorFilmography`, and `castFilmography` are all films
that had already been released, so their history is fair evidence. Each carries
a `rating` on a 0-100 scale -- note that it is a public audience score, not a
critics' score.

Where the data is thin or a comparables list looks nonsensical, handle it the
way the persona above tells you to: stay in voice, lean on what you do have,
and move on. Never invent a rating, an award, or a review you were not given.

**Return your evaluation as JSON** matching the schema you were given:
`role` is always "creative"; `argument` is the full evaluation in your voice,
covering all four criteria and ending with the
`[Predicted Reception Score: XX/100]` line; `vote` is exactly "greenlight" or
"pass" -- there is no conditional verdict.
"""


def load_system_prompt(path: Path = PERSONA_PATH) -> str:
    """Read the persona markdown, drop its YAML frontmatter, add the framing."""
    if not path.exists():
        raise FileNotFoundError(
            f"Persona file not found at {path}. The creative agent's character "
            f"is defined there, not in this script."
        )
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _, after = text.partition("---")
        frontmatter, sep, body = after.partition("---")
        if sep:
            text = body
    return text.strip() + "\n" + FRAMING


def build_user_message(film: dict) -> str:
    payload = json.dumps(film["payload"], indent=2, ensure_ascii=False)
    return (
        f"Evaluate this project for the committee.\n\n"
        f"Pre-release information:\n```json\n{payload}\n```"
    )


def evaluate_film(
    client: anthropic.Anthropic, system_prompt: str, film: dict, model: str
) -> dict:
    """Ask Claude for one creative verdict. Returns {role, argument, vote}."""
    with client.beta.messages.stream(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # The persona is identical on every film, so cache it.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": VOTE_SCHEMA},
        },
        messages=[{"role": "user", "content": build_user_message(film)}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError(
            f"Claude declined to evaluate {film['title']!r} "
            f"(category: {getattr(message.stop_details, 'category', None)})."
        )

    text = next(b.text for b in message.content if b.type == "text")
    return json.loads(text)


def run(
    session_id: int = DEFAULT_SESSION_ID,
    slate: str = "default",
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> int:
    load_env_file(".env.local")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the env
    system_prompt = load_system_prompt()

    films = get_slate(slate=slate)
    if not films:
        print(f"No films in slate {slate!r}. Nothing to vote on.", file=sys.stderr)
        return 1

    print(f"{len(films)} film(s) in slate {slate!r}; session {session_id}\n")

    failures = 0
    for film in films:
        print(f"--- {film['title']} (film_id={film['id']}) ---")
        try:
            verdict = evaluate_film(client, system_prompt, film, model)
        except Exception as exc:  # keep going; one bad film shouldn't end the run
            failures += 1
            print(f"  FAILED: {exc}\n", file=sys.stderr)
            continue

        print(f"  vote: {verdict['vote']}")
        print(f"\n{verdict['argument']}\n")

        if dry_run:
            print("  (dry run -- not recorded)\n")
            continue

        record_vote(
            session_id=session_id,
            film_id=film["id"],
            role=ROLE,
            vote=verdict["vote"],
            argument=verdict["argument"],
        )
        print(f"  recorded for session {session_id}\n")

    if failures:
        print(f"{failures} of {len(films)} film(s) failed.", file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", type=int, default=DEFAULT_SESSION_ID)
    parser.add_argument("--slate", default="default")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate and print, but don't write votes to the database.",
    )
    args = parser.parse_args()
    return run(
        session_id=args.session_id,
        slate=args.slate,
        model=args.model,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
