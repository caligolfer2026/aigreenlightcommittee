"""Thin wrapper around the Anthropic API. The model only ever writes the
rationale text -- it never decides the grade (see calibration.py). If no
ANTHROPIC_API_KEY is available, falls back to a templated rationale built
straight from the computed numbers, so the agent still works offline.
"""
import json
import os
from typing import List, Optional

DEFAULT_MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are the Scoring agent in a studio greenlight committee simulation.
You have no opinion of your own about whether a film should have been made.
Your only job is to write a short, objective rationale (2-4 sentences)
explaining how well the committee's votes matched what actually happened.
You are given an already-computed grade and the facts behind it -- do not
change the grade and do not invent facts beyond what's provided. Reference
specific agents' arguments where it's illuminating. Respond with strict JSON
of the shape {"rationale": string} and nothing else."""


def fallback_rationale(title: str, computed: dict) -> str:
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


def build_rationale(
    title: str,
    votes: List[dict],
    actual_results: dict,
    computed: dict,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback_rationale(title, computed)

    import anthropic  # imported lazily so this module loads even without the SDK installed

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "film": title,
                        "committeeVotes": votes,
                        "actualResults": actual_results,
                        "computed": computed,
                    }
                ),
            }
        ],
    )
    content = response.content[0].text if response.content else ""
    try:
        parsed = json.loads(content)
        rationale = (parsed.get("rationale") or "").strip()
        if rationale:
            return rationale
    except (json.JSONDecodeError, AttributeError):
        pass
    return content.strip() or fallback_rationale(title, computed)
