"""Deterministic, LLM-free reading of "what actually happened" and "how well
the committee's vote matched it". This is the objective backbone the agent
hands to the LLM -- the LLM only writes the rationale, it never decides the
grade.

Ported 1:1 from the original JS prototype (same thresholds, same rules),
which had 25 passing tests against this exact logic.
"""
from typing import List, Optional, TypedDict

# Films typically need to gross ~2x budget to cover marketing/distribution
# and break even; that industry rule of thumb is the financial hit/flop line.
BREAK_EVEN_MULTIPLE = 2
FLOP_MULTIPLE = 1

RECEPTION_STRONG_THRESHOLD = 70
RECEPTION_WEAK_THRESHOLD = 40


class Classification(TypedDict):
    label: str
    multiple: Optional[float]


def classify_financial(budget: Optional[int], actual_results: dict) -> dict:
    """`actual_results` is the payload from db.results.get_actual_results
    (boxOfficeDomestic, boxOfficeWorldwide, ...). `budget` isn't in that
    payload -- it lives in the pre-release side, so pass it in separately
    (see agent.py, which pulls it from db.prerelease.get_slate)."""
    gross = actual_results.get("boxOfficeWorldwide") or actual_results.get("boxOfficeDomestic")

    if not budget or budget <= 0 or gross is None:
        return {"label": "unknown", "multiple": None}

    multiple = gross / budget
    if multiple >= BREAK_EVEN_MULTIPLE:
        return {"label": "hit", "multiple": multiple}
    if multiple < FLOP_MULTIPLE:
        return {"label": "flop", "multiple": multiple}
    return {"label": "mixed", "multiple": multiple}


def classify_reception(actual_results: dict) -> dict:
    scores = [
        s for s in (actual_results.get("audienceScore"), actual_results.get("criticScore")) if s is not None
    ]

    if not scores:
        return {"label": "unknown", "average": None}

    average = sum(scores) / len(scores)
    if average >= RECEPTION_STRONG_THRESHOLD:
        return {"label": "strong", "average": average}
    if average < RECEPTION_WEAK_THRESHOLD:
        return {"label": "weak", "average": average}
    return {"label": "mixed", "average": average}


def classify_overall(financial: dict, reception: dict) -> str:
    """Collapses financial + reception into one overall call. Financial
    result carries more weight than reception since "greenlight" is
    fundamentally a financial bet, but a financial "mixed" is broken by
    reception."""
    if financial["label"] == "unknown" and reception["label"] == "unknown":
        return "unknown"
    if financial["label"] in ("hit", "flop"):
        return financial["label"]
    if financial["label"] == "mixed":
        if reception["label"] == "strong":
            return "hit"
        if reception["label"] == "weak":
            return "flop"
        return "mixed"
    # financial unknown (no budget data) -- fall back to reception alone
    if reception["label"] == "strong":
        return "hit"
    if reception["label"] == "weak":
        return "flop"
    return "mixed"


def tally_votes(votes: List[dict]) -> dict:
    """`votes` is a list of this film's votes, as returned by
    db.prerelease.get_votes -- each has a "vote" key of "greenlight" or
    "pass" (V1 keeps verdicts binary, no third "conditional" option)."""
    greenlight = sum(1 for v in votes if v["vote"] == "greenlight")
    passes = sum(1 for v in votes if v["vote"] == "pass")
    if greenlight == passes:
        majority = "split"
    elif greenlight > passes:
        majority = "greenlight"
    else:
        majority = "pass"
    return {"greenlight": greenlight, "pass": passes, "majority": majority}


def calibration_score(majority_vote: str, overall: str) -> int:
    """How well the committee's majority vote matches reality, as 0-100."""
    if overall == "unknown":
        return 50  # no data to judge against -- neutral
    if overall == "mixed":
        return 65  # reality itself was ambiguous -- partial credit either way
    if majority_vote == "split":
        return 45  # committee couldn't agree, reality did

    matched = (majority_vote == "greenlight" and overall == "hit") or (
        majority_vote == "pass" and overall == "flop"
    )
    return 100 if matched else 0


def score_to_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def compute_calibration(votes: List[dict], actual_results: dict, budget: Optional[int] = None) -> dict:
    financial = classify_financial(budget, actual_results)
    reception = classify_reception(actual_results)
    overall = classify_overall(financial, reception)
    tally = tally_votes(votes)
    score = calibration_score(tally["majority"], overall)
    grade = score_to_grade(score)
    return {
        "financial": financial,
        "reception": reception,
        "overall": overall,
        "tally": tally,
        "score": score,
        "grade": grade,
    }
