"""Slate intake: parse a free-text film pitch ("a new horror film like The
Conjuring") into the structured fields data-pipeline needs to build a
synthetic pre-release package -- no real film exists yet, so there's
nothing to look up by title. Genre, logline, and (if named) a comp film
are extracted from the text; data-pipeline/src/pipeline.py's
build_pitch_payload then fetches real historical data for that genre.
"""
import hashlib
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


# An explicit title beats everything else -- "called X" / "titled X" /
# "named X", or a quoted phrase anywhere in the pitch.
_TITLE_NAMED_RE = re.compile(
    r"\b(?:called|titled|named)\s+[\"“]?([A-Z][\w:'\-]*(?:\s+[A-Z0-9][\w:'\-]*)*)",
    re.IGNORECASE,
)
_TITLE_QUOTED_RE = re.compile(r"[\"“]([^\"”]{2,60})[\"”]")


def _detect_explicit_title(text: str) -> "str | None":
    match = _TITLE_NAMED_RE.search(text)
    if match:
        return match.group(1).strip().rstrip(".,!?\"”")
    match = _TITLE_QUOTED_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


# Deterministic working-title generator for when the pitch doesn't name one
# itself -- picks an adjective + a genre-flavored noun, hash-seeded on the
# pitch text so the same pitch always gets the same title. Much more
# film-like than a literal "Untitled X Pitch" placeholder, and it keeps the
# mock agent arguments (which interpolate {title}) from reading as fake.
_TITLE_ADJECTIVES = [
    "Midnight", "Hollow", "Silent", "Last", "Broken", "Crimson", "Shattered",
    "Distant", "Final", "Wild", "Golden", "Restless", "Quiet", "Long",
]

_TITLE_NOUNS_BY_GENRE = {
    "Horror": ["House", "Hour", "Chapel", "Woods", "Bloodline", "Hollow"],
    "Action": ["Protocol", "Directive", "Strike", "Legacy", "Reckoning"],
    "Comedy": ["Disaster", "Wedding", "Plan", "Reunion", "Getaway"],
    "Science Fiction": ["Signal", "Horizon", "Genesis", "Frequency", "Descent"],
    "Romance": ["Letter", "Summer", "Promise", "Season", "Reunion"],
    "Thriller": ["Contract", "Silence", "Trigger", "Witness", "Exchange"],
    "Drama": ["Reckoning", "Inheritance", "Reunion", "Harvest", "Departure"],
    "Crime": ["Heist", "Ledger", "Alibi", "Syndicate"],
    "Mystery": ["Cipher", "Vanishing", "Inquiry"],
    "Fantasy": ["Kingdom", "Prophecy", "Realm"],
    "Adventure": ["Expedition", "Passage", "Frontier"],
    "Animation": ["Kingdom", "Voyage", "Wonder"],
    "Family": ["Adventure", "Summer", "Reunion"],
    "War": ["Front", "Siege", "Company"],
    "History": ["Reckoning", "Empire", "Reign"],
    "Music": ["Encore", "Refrain", "Chorus"],
}

_DEFAULT_TITLE_NOUNS = ["Project", "Story", "Reckoning"]


def _generate_title(pitch_text: str, genre: "str | None") -> str:
    seed = int(hashlib.sha256(pitch_text.encode()).hexdigest(), 16)
    nouns = _TITLE_NOUNS_BY_GENRE.get(genre, _DEFAULT_TITLE_NOUNS)
    adjective = _TITLE_ADJECTIVES[seed % len(_TITLE_ADJECTIVES)]
    noun = nouns[(seed // 7) % len(nouns)]
    return f"{adjective} {noun}"


def _mock_parse(pitch_text: str) -> dict:
    """No ANTHROPIC_API_KEY -- heuristic genre/title/reference-title
    extraction instead of an LLM call, so pitch intake still works for
    free. Less precise than the real thing, but deterministic and good
    enough to exercise the rest of the pipeline."""
    genre = _detect_genre(pitch_text)
    reference_title = _detect_reference_title(pitch_text)
    title = _detect_explicit_title(pitch_text) or _generate_title(pitch_text, genre)
    return {
        "title": title,
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

    try:
        return call_structured(PITCH_SYSTEM_PROMPT, pitch_text, PITCH_SCHEMA)
    except Exception:
        # A present-but-unusable key (no credit balance, rate limited,
        # network hiccup) shouldn't 500 the whole request -- fall back to
        # the same heuristic parse used when no key is set at all.
        return _mock_parse(pitch_text)
