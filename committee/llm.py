"""Shared Claude API call used by every committee agent and the scoring agent."""
import json
import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.env import load_env_file

MODEL = "claude-opus-5"

_client = None
_env_loaded = False


def _ensure_env_loaded() -> None:
    global _env_loaded
    if not _env_loaded:
        load_env_file(".env.local")
        _env_loaded = True


def has_api_key() -> bool:
    """False when no ANTHROPIC_API_KEY is set -- callers should fall back to
    a mock response instead of hitting the API, so people testing the
    pipeline (DB writes, UI, orchestration) don't burn tokens."""
    _ensure_env_loaded()
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _ensure_env_loaded()
        _client = anthropic.Anthropic()
    return _client


def call_structured(system_prompt: str, user_content: str, schema: dict) -> dict:
    """Call Claude with a system prompt + user content, forcing the response
    to validate against `schema` via structured outputs."""
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user_content}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
