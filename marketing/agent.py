"""Public Marketing Agent interface compatible with the shared committee contract."""

from typing import Any, Dict, Optional

from .openai_client import OpenAIResponsesClient
from .prompt import RESPONSE_SCHEMA, SYSTEM_PROMPT

ROLE = "marketing"
VOTES = {"greenlight", "pass"}
AWARENESS_TIERS = {"Low", "Medium", "High"}
FORBIDDEN_FILM_FIELDS = {
    "actualResults",
    "boxOfficeDomestic",
    "boxOfficeWorldwide",
    "criticScore",
    "imdbRating",
    "revenue",
    "vote_average",
    "vote_count",
}


def _validate_film(film: Dict[str, Any]) -> None:
    if not isinstance(film, dict):
        raise ValueError("film must be a pre-release payload object")
    if not isinstance(film.get("title"), str) or not film["title"].strip():
        raise ValueError("film.title must be a non-empty string")
    forbidden = FORBIDDEN_FILM_FIELDS.intersection(film)
    if forbidden:
        raise ValueError(
            "Evaluated-film result fields are forbidden: " + ", ".join(sorted(forbidden))
        )


def evaluate_marketing(
    film: Dict[str, Any], client: Optional[Any] = None
) -> Dict[str, str]:
    """Evaluate one PreReleaseFilm and return the exact committee contract.

    The predicted awareness tier is appended to the argument so the current
    database schema can store it without changing the shared contract.
    """
    _validate_film(film)
    model_client = client or OpenAIResponsesClient.from_environment()
    raw = model_client.create_assessment(SYSTEM_PROMPT, film, RESPONSE_SCHEMA)

    if raw.get("role") != ROLE:
        raise ValueError("Model response role must be marketing")
    vote = raw.get("vote")
    if vote not in VOTES:
        raise ValueError("Model response vote must be greenlight or pass")
    tier = raw.get("awarenessTier")
    if tier not in AWARENESS_TIERS:
        raise ValueError("Model response awarenessTier must be Low, Medium, or High")
    argument = raw.get("argument")
    if not isinstance(argument, str) or not argument.strip():
        raise ValueError("Model response argument must be a non-empty string")

    marker = f"[Predicted Awareness Tier: {tier}]"
    clean_argument = argument.strip()
    if marker not in clean_argument:
        clean_argument = f"{clean_argument}\n\n{marker}"
    return {"role": ROLE, "argument": clean_argument, "vote": vote}
