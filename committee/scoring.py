"""The scoring agent: reveals actual results and grades the committee."""
import json

from .llm import call_structured, has_api_key

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "grade": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["grade", "rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are the scoring agent for a studio greenlight committee. You have "
    "no opinion of your own -- your only job is to reveal what actually "
    "happened and objectively grade how well the committee's reasoning and "
    "vote held up against reality. You will be given the four committee "
    "members' votes and arguments for one film, plus that film's actual "
    "results (box office, audience/critic scores). Compare the committee's "
    "greenlight/pass calls and stated reasoning to what actually happened, "
    "then produce a grade (a short label like 'A' or 'well-calibrated', or "
    "a number) and a rationale explaining the comparison."
)


def _mock_score(votes: list[dict], actual_results: dict) -> dict:
    """No ANTHROPIC_API_KEY set -- return a placeholder grade instead of
    calling the API, so the pipeline can be tested for free."""
    greenlights = sum(1 for v in votes if v.get("vote") == "greenlight")
    return {
        "grade": "N/A (mock)",
        "rationale": (
            f"[MOCK -- no ANTHROPIC_API_KEY set] {greenlights}/{len(votes)} "
            "committee members voted greenlight. Set ANTHROPIC_API_KEY in "
            ".env.local to get a real Claude-generated grade + rationale here."
        ),
    }


def run_scoring(votes: list[dict], actual_results: dict) -> dict:
    """Grade one film's committee votes against its actual results."""
    if not has_api_key():
        return _mock_score(votes, actual_results)

    user_content = json.dumps(
        {"votes": votes, "actualResults": actual_results}, indent=2
    )
    return call_structured(SYSTEM_PROMPT, user_content, SCORE_SCHEMA)
