"""Aggregation: turns the four committee members' individual votes (each
with a confidence score) into one committee-level decision. Pure and
deterministic -- no LLM call, and it never touches actual-results data.
This is the step between Vote and Reveal: by the time this runs, the
committee has an outcome of its own, before anyone finds out what really
happened.
"""
from typing import List, Optional, TypedDict


class PerVote(TypedDict):
    role: str
    vote: str
    confidence: Optional[int]


class AggregatedDecision(TypedDict):
    outcome: str  # "greenlight" | "pass" | "split"
    confidenceWeightedScore: float  # 0-100; >55 leans greenlight, <45 leans pass
    greenlightCount: int
    passCount: int
    averageConfidence: float
    perVote: List[PerVote]


# A vote with no recorded confidence (older data, or a source that doesn't
# supply one) is treated as neutral rather than excluded.
_DEFAULT_CONFIDENCE = 50


def _signed_confidence(vote: dict) -> float:
    confidence = vote.get("confidence")
    confidence = _DEFAULT_CONFIDENCE if confidence is None else confidence
    # -100..+100 scale: a greenlight at confidence C contributes +C, a pass
    # at confidence C contributes -C. A unanimous, low-confidence committee
    # nets out near zero, same as a confident committee split down the middle.
    return confidence if vote.get("vote") == "greenlight" else -confidence


def aggregate_votes(votes: List[dict]) -> AggregatedDecision:
    """`votes` is a list of {role, vote, confidence, ...} dicts for one
    film -- typically all four committee roles' votes from one session, as
    returned by db.prerelease.get_votes filtered to one tmdb_id. Missing
    votes (fewer than four) are aggregated as-is; the caller decides
    whether that's meaningful."""
    if not votes:
        return AggregatedDecision(
            outcome="split",
            confidenceWeightedScore=50.0,
            greenlightCount=0,
            passCount=0,
            averageConfidence=0.0,
            perVote=[],
        )

    greenlight_count = sum(1 for v in votes if v.get("vote") == "greenlight")
    pass_count = sum(1 for v in votes if v.get("vote") == "pass")

    n = len(votes)
    total_signed = sum(_signed_confidence(v) for v in votes)
    # Rescale the per-vote -100..+100 average back onto a 0..100 scale,
    # where 50 is dead-neutral (an even, low-confidence split).
    confidence_weighted_score = round(((total_signed / n) + 100) / 2, 1)

    confidences = [
        v.get("confidence") if v.get("confidence") is not None else _DEFAULT_CONFIDENCE for v in votes
    ]
    average_confidence = round(sum(confidences) / n, 1)

    if confidence_weighted_score > 55:
        outcome = "greenlight"
    elif confidence_weighted_score < 45:
        outcome = "pass"
    else:
        outcome = "split"

    return AggregatedDecision(
        outcome=outcome,
        confidenceWeightedScore=confidence_weighted_score,
        greenlightCount=greenlight_count,
        passCount=pass_count,
        averageConfidence=average_confidence,
        perVote=[
            PerVote(role=v.get("role"), vote=v.get("vote"), confidence=v.get("confidence"))
            for v in votes
        ],
    )
