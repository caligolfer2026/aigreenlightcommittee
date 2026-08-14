import unittest
from unittest.mock import patch

from committee.agents import run_agent


class CommitteeIntegrationTests(unittest.TestCase):
    @patch("committee.agents.evaluate_marketing")
    def test_shared_runner_delegates_marketing_to_specialized_agent(self, evaluate):
        expected = {
            "role": "marketing",
            "argument": "Audience-first marketing case.",
            "vote": "greenlight",
        }
        evaluate.return_value = expected
        payload = {"title": "Film One"}

        result = run_agent("marketing", payload)

        evaluate.assert_called_once_with(payload)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
