"""Minimal OpenAI Responses API client using the Python standard library."""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict

from db.env import load_env_file


class MarketingAPIError(RuntimeError):
    """Raised when the model request cannot produce a usable assessment."""


class OpenAIResponsesClient:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required in the repo-root .env.local")
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_environment(cls) -> "OpenAIResponsesClient":
        load_env_file(".env.local")
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        )

    def create_assessment(
        self, instructions: str, film_payload: Dict[str, Any], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        request_body = {
            "model": self.model,
            "instructions": instructions,
            "input": "PRE-RELEASE FILM PAYLOAD:\n" + json.dumps(film_payload, indent=2),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "marketing_vote",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MarketingAPIError(
                f"OpenAI request failed ({exc.code}): {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MarketingAPIError(f"OpenAI request failed: {exc}") from exc

        text = self._output_text(payload)
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MarketingAPIError("OpenAI returned invalid structured JSON") from exc
        if not isinstance(result, dict):
            raise MarketingAPIError("OpenAI returned a non-object assessment")
        return result

    @staticmethod
    def _output_text(payload: Dict[str, Any]) -> str:
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    raise MarketingAPIError(
                        content.get("refusal", "OpenAI refused the request")
                    )
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        raise MarketingAPIError("OpenAI response contained no output text")
