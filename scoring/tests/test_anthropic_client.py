"""Offline tests for scoring/anthropic_client.py. Only covers the no-API-key
fallback path -- no network or real credentials needed. The live-API path
isn't unit tested here (would need mocking the anthropic SDK's response
shape); it's exercised by actually running scoring/agent.py against a film.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anthropic_client import build_rationale
from calibration import compute_calibration


class TestFallbackRationale(unittest.TestCase):
    VOTES = [
        {"role": "creative", "argument": "Strong director.", "vote": "greenlight"},
        {"role": "finance", "argument": "Budget is fine.", "vote": "greenlight"},
        {"role": "marketing", "argument": "Good trailer-ability.", "vote": "pass"},
        {"role": "distribution", "argument": "Crowded window.", "vote": "pass"},
    ]
    ACTUAL = {"boxOfficeWorldwide": 90_000_000, "audienceScore": 55, "criticScore": 45}

    def test_writes_a_templated_rationale_when_no_api_key_is_available(self):
        computed = compute_calibration(self.VOTES, self.ACTUAL, budget=150_000_000)
        rationale = build_rationale("Test Film", self.VOTES, self.ACTUAL, computed, api_key="")

        self.assertIn("Test Film", rationale)
        self.assertIn(f'Calibration score: {computed["score"]}/100 ({computed["grade"]})', rationale)
        self.assertIn("2-2", rationale)  # split vote


if __name__ == "__main__":
    unittest.main()
