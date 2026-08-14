"""The scoring agent: reveals actual results and grades the committee.

Ported from the `scoring` branch: the grade is always computed
deterministically by calibration.py (financial hit/flop + reception vs. the
committee's vote majority) -- the LLM never invents the grade, it only
writes the rationale explaining it. Falls back to a templated rationale
when no ANTHROPIC_API_KEY is set, same as everything else in this package.
"""
import json
from typing import Optional

from .calibration import compute_calibration
from .llm import call_structured, has_api_key

RATIONALE_SCHEMA = {
    "type": "object",
    "properties": {"rationale": {"type": "string"}},
    "required": ["rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the Scoring agent in a studio greenlight committee simulation.
You have no opinion of your own about whether a film should have been made.
Your only job is to write a short, objective rationale (2-4 sentences)
explaining how well the committee's votes matched what actually happened.
You are given an already-computed grade and the facts behind it -- do not
change the grade and do not invent facts beyond what's provided. Reference
specific agents' arguments where it's illuminating."""


def _fallback_rationale(title: str, computed: dict) -> str:
    tally = computed["tally"]
    financial = computed["financial"]
    reception = computed["reception"]

    vote_line = (
        f'The committee voted {tally["greenlight"]}-{tally["pass"]} '
        f'(majority: {tally["majority"]}) on "{title}".'
    )
    if financial["label"] == "unknown":
        money_line = "Box office or budget data wasn't available to judge the financial outcome."
    else:
        money_line = f'It grossed {financial["multiple"]:.2f}x its budget, a financial {financial["label"]}.'
    if reception["label"] == "unknown":
        reception_line = "No audience or critic scores were available."
    else:
        reception_line = (
            f'Average audience/critic reception was {reception["average"]:.1f}/100 '
            f'({reception["label"]}).'
        )
    outcome_line = (
        f'Overall outcome: {computed["overall"]}. '
        f'Calibration score: {computed["score"]}/100 ({computed["grade"]}).'
    )
    return " ".join([vote_line, money_line, reception_line, outcome_line])


def run_scoring(
    title: str, votes: list[dict], actual_results: dict, budget: Optional[int] = None
) -> dict:
    """Grade one film's committee votes against its actual results."""
    computed = compute_calibration(votes, actual_results, budget)

    if not has_api_key():
        rationale = _fallback_rationale(title, computed)
    else:
        user_content = json.dumps(
            {
                "film": title,
                "committeeVotes": votes,
                "actualResults": actual_results,
                "computed": computed,
            }
        )
        result = call_structured(SYSTEM_PROMPT, user_content, RATIONALE_SCHEMA)
        rationale = result["rationale"]

    return {"grade": computed["grade"], "rationale": rationale}
