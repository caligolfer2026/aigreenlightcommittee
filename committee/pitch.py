"""Slate intake: parse a free-text film pitch ("a new horror film like The
Conjuring") into the structured fields data-pipeline needs to build a
synthetic pre-release package -- no real film exists yet, so there's
nothing to look up by title. Genre, logline, and (if named) a comp film
are extracted from the text; data-pipeline/src/pipeline.py's
build_pitch_payload then fetches real historical data for that genre.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data-pipeline"))
from src.tmdb_client import GENRE_NAME_TO_ID  # noqa: E402

from .llm import call_structured, has_api_key

PITCH_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "genre": {"type": "string", "enum": list(GENRE_NAME_TO_ID.keys())},
        "logline": {"type": "string"},
        "marketingHook": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "targetDemo": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "referenceTitle": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "budget": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["title", "genre", "logline", "marketingHook", "targetDemo", "referenceTitle", "budget"],
    "additionalProperties": False,
}

PITCH_SYSTEM_PROMPT = """Extract structured fields from a short film pitch describing a NEW, not-yet-made film. Do not invent facts beyond what's stated or reasonably implied by the pitch text.

- title: a short, punchy working title for the pitch (invent one if none is given).
- genre: the single best-matching genre from the allowed list.
- logline: a one-to-two sentence expanded logline capturing the pitch's premise.
- marketingHook: a short, quotable one-line marketing hook/tagline for this pitch, if one is implied; otherwise null.
- targetDemo: a brief target-audience description (e.g. "adult horror fans, 18-34"), if reasonably inferable from the pitch; otherwise null.
- referenceTitle: if the pitch names a specific existing film as a comp/reference (e.g. "like The Conjuring"), the exact title of that film; otherwise null.
- budget: an approximate production budget in dollars, only if the pitch states or clearly implies one; otherwise null. Do not guess a typical budget for the genre -- leave null unless the pitch itself gives you a number."""


_GENRE_SYNONYMS = {
    "scary": "Horror",
    "slasher": "Horror",
    "supernatural": "Horror",
    "rom-com": "Romance",
    "romantic comedy": "Romance",
    "sci-fi": "Science Fiction",
    "sci fi": "Science Fiction",
    "space opera": "Science Fiction",
    "whodunit": "Mystery",
    "detective": "Mystery",
    "heist": "Crime",
    "gangster": "Crime",
    "musical": "Music",
    "animated": "Animation",
    "kids": "Family",
    "biopic": "History",
}


def _detect_genre(text: str) -> "str | None":
    lowered = text.lower()
    for name in GENRE_NAME_TO_ID:
        if name.lower() in lowered:
            return name
    for keyword, genre in _GENRE_SYNONYMS.items():
        if keyword in lowered:
            return genre
    return None


_REFERENCE_RE = re.compile(r"\blike\s+([A-Z][\w:'\-]*(?:\s+[A-Z0-9][\w:'\-]*)*)")


def _detect_reference_title(text: str) -> "str | None":
    match = _REFERENCE_RE.search(text)
    if not match:
        return None
    return match.group(1).strip().rstrip(".,!?")


def _mock_parse(pitch_text: str) -> dict:
    """No ANTHROPIC_API_KEY -- heuristic genre/reference-title extraction
    instead of an LLM call, so pitch intake still works for free. Less
    precise than the real thing, but deterministic and good enough to
    exercise the rest of the pipeline."""
    genre = _detect_genre(pitch_text)
    reference_title = _detect_reference_title(pitch_text)
    return {
        "title": f"Untitled {genre or 'Film'} Pitch",
        "genre": genre,
        "logline": pitch_text.strip(),
        "marketingHook": None,
        "targetDemo": None,
        "referenceTitle": reference_title,
        "budget": None,
    }


def parse_pitch(pitch_text: str) -> dict:
    """Returns {title, genre, logline, marketingHook, targetDemo,
    referenceTitle, budget}. `genre` is None if it couldn't be determined
    (mock mode only -- the real LLM path is schema-constrained to always
    return one of the valid TMDB genre names) -- callers should treat a
    None genre as "ask the user to be more specific"."""
    if not has_api_key():
        return _mock_parse(pitch_text)

    result = call_structured(PITCH_SYSTEM_PROMPT, pitch_text, PITCH_SCHEMA)
    return result
