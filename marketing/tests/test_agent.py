import unittest

from marketing.agent import evaluate_marketing


FILM = {
    "title": "Starlight Academy",
    "releaseDate": "2027-11-24",
    "genres": ["Family", "Fantasy", "Adventure"],
    "director": "Jordan Example",
    "cast": ["Alex Star", "Sam Performer"],
    "studio": "Walt Disney Studios",
    "budget": 120000000,
    "logline": "A shy teenager enters a magical school hidden among the stars.",
    "franchise": None,
    "franchiseEntries": [],
    "comparableFilms": [],
    "directorFilmography": [],
    "castFilmography": [],
}


class FakeClient:
    def __init__(self, response=None):
        self.response = response or {
            "role": "marketing",
            "argument": "Families and teens have a clear wish-fulfillment hook, with a visual world suited to a campaign. The unknown talent profile and lack of audience research create risk, but the consumer promise is legible.",
            "vote": "greenlight",
            "awarenessTier": "Medium",
        }
        self.film = None

    def create_assessment(self, instructions, film_payload, schema):
        self.film = film_payload
        return dict(self.response)


class MarketingAgentTests(unittest.TestCase):
    def test_returns_exact_shared_contract_and_awareness_marker(self):
        result = evaluate_marketing(FILM, client=FakeClient())
        self.assertEqual(set(result), {"role", "argument", "vote"})
        self.assertEqual(result["role"], "marketing")
        self.assertEqual(result["vote"], "greenlight")
        self.assertIn("[Predicted Awareness Tier: Medium]", result["argument"])

    def test_pass_vote_is_supported(self):
        client = FakeClient(
            {
                "role": "marketing",
                "argument": "The audience and proposition are unclear.",
                "vote": "pass",
                "awarenessTier": "Low",
            }
        )
        self.assertEqual(evaluate_marketing(FILM, client=client)["vote"], "pass")

    def test_rejects_evaluated_film_result_data(self):
        with self.assertRaisesRegex(ValueError, "result fields are forbidden"):
            evaluate_marketing({**FILM, "boxOfficeWorldwide": 500000000}, FakeClient())

        with self.assertRaisesRegex(ValueError, "result fields are forbidden"):
            evaluate_marketing({**FILM, "tmdbPopularity": 100.0}, FakeClient())

    def test_rejects_invalid_tier(self):
        client = FakeClient(
            {
                "role": "marketing",
                "argument": "Argument",
                "vote": "greenlight",
                "awarenessTier": "Enormous",
            }
        )
        with self.assertRaisesRegex(ValueError, "Low, Medium, or High"):
            evaluate_marketing(FILM, client=client)


if __name__ == "__main__":
    unittest.main()
