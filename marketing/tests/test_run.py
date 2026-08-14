import unittest

from marketing.run import run_slate


FILMS = [
    {"id": 1, "title": "Film One", "payload": {"title": "Film One"}},
    {"id": 2, "title": "Film Two", "payload": {"title": "Film Two"}},
]


def evaluator(film):
    return {
        "role": "marketing",
        "argument": f"Marketing case for {film['title']}",
        "vote": "greenlight",
    }


class MarketingRunTests(unittest.TestCase):
    def test_dry_run_never_records_votes(self):
        recorded = []
        results = run_slate(
            films=FILMS,
            dry_run=True,
            evaluator=evaluator,
            recorder=lambda **kwargs: recorded.append(kwargs),
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(recorded, [])

    def test_records_session_one_contract(self):
        recorded = []
        run_slate(
            session_id=1,
            films=FILMS,
            evaluator=evaluator,
            recorder=lambda **kwargs: recorded.append(kwargs),
        )
        self.assertEqual(len(recorded), 2)
        self.assertEqual(recorded[0]["session_id"], 1)
        self.assertEqual(recorded[0]["role"], "marketing")
        self.assertEqual(recorded[0]["vote"], "greenlight")


if __name__ == "__main__":
    unittest.main()
