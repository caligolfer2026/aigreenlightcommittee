"""The scoring agent: reveals actual results and grades the committee.

Ported from the `scoring` branch: the grade is always computed
deterministically by calibration.py (financial hit/flop + reception vs. the
committee's vote majority) -- the LLM never invents the grade, it only
writes the rationale explaining it. Falls back to a templated rationale
when no ANTHROPIC_API_KEY is set, same as everything else in this package.
"""
import json
from typing import Optional

from .aggregation import aggregate_votes
from .calibration import compute_calibration, score_to_grade
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
        try:
            result = call_structured(SYSTEM_PROMPT, user_content, RATIONALE_SCHEMA)
            rationale = result["rationale"]
        except Exception:
            # A present-but-unusable key (no credit balance, rate limited,
            # network hiccup) shouldn't 500 the whole request.
            rationale = _fallback_rationale(title, computed)

    return {"grade": computed["grade"], "rationale": rationale}


# ---------------------------------------------------------------------------
# Pitch scoring: a hypothetical pitch (synthetic negative tmdb_id, no real
# release) has no actual results to reveal. Per spec, the fifth agent grades
# it purely on the four committee members' own votes/confidence/reasoning --
# aggregate_votes() is the deterministic backbone here instead of
# compute_calibration(), and the grade comes from mapping its
# confidenceWeightedScore onto the same A-F scale via score_to_grade().
PITCH_SYSTEM_PROMPT = """You are the Scoring agent in a studio greenlight committee simulation.
This film is a hypothetical pitch, not a real release -- there is no box
office or audience data to reveal. Your only job is to write a short,
objective rationale (2-4 sentences) explaining whether the committee's own
votes and reasoning add up to a defensible greenlight call. You are given
an already-computed outcome and grade -- do not change them and do not
invent facts beyond what's provided. Reference specific agents' arguments
where it's illuminating, and note any real disagreement between roles."""


def _pitch_fallback_rationale(title: str, decision: dict, grade: str) -> str:
    vote_line = (
        f'The committee voted {decision["greenlightCount"]}-{decision["passCount"]} '
        f'(outcome: {decision["outcome"]}) on "{title}", a hypothetical pitch with no '
        "real outcome to reveal."
    )
    confidence_line = (
        f'Confidence-weighted score: {decision["confidenceWeightedScore"]}/100 '
        f'(avg confidence {decision["averageConfidence"]}%).'
    )
    grade_line = f"Grade: {grade}."
    return " ".join([vote_line, confidence_line, grade_line])


def run_pitch_scoring(title: str, votes: list[dict]) -> dict:
    """Grade a hypothetical pitch's committee votes -- no real outcome data
    exists to compare against, so the grade is derived from how strongly and
    consistently the four members backed the pitch (see aggregate_votes)."""
    decision = aggregate_votes(votes)
    grade = score_to_grade(int(decision["confidenceWeightedScore"]))

    if not has_api_key():
        rationale = _pitch_fallback_rationale(title, decision, grade)
    else:
        user_content = json.dumps(
            {
                "film": title,
                "committeeVotes": votes,
                "aggregatedDecision": decision,
                "grade": grade,
            }
        )
        try:
            result = call_structured(PITCH_SYSTEM_PROMPT, user_content, RATIONALE_SCHEMA)
            rationale = result["rationale"]
        except Exception:
            # A present-but-unusable key (no credit balance, rate limited,
            # network hiccup) shouldn't 500 the whole request.
            rationale = _pitch_fallback_rationale(title, decision, grade)

    return {"grade": grade, "outcome": decision["outcome"], "rationale": rationale}
