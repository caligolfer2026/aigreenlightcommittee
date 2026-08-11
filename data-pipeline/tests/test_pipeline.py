"""Offline tests: no network, no API keys. Run with:
    python3 -m unittest discover -s tests
"""
import unittest

from src.pipeline import build_actual_results_payload, build_pre_release_payload

TMDB_DETAILS = {
    "title": "Example Movie",
    "release_date": "2025-11-07",
    "genres": [{"id": 1, "name": "Science Fiction"}, {"id": 2, "name": "Adventure"}],
    "production_companies": [{"name": "Example Studios"}],
    "budget": 190000000,
    "revenue": 711800000,
    "overview": "A hero saves the day.",
    "vote_average": 7.8,
    "belongs_to_collection": {"name": "Example Collection"},
    "credits": {
        "crew": [{"name": "Jane Director", "job": "Director"}],
        "cast": [{"name": "Star One"}, {"name": "Star Two"}],
    },
    "similar": {"results": [{"title": "Similar Movie One"}, {"title": "Similar Movie Two"}]},
    "external_ids": {"imdb_id": "tt0000000"},
}

OMDB_DATA = {
    "Response": "True",
    "imdbRating": "8.1",
    "Metascore": "74",
    "BoxOffice": "$300,000,000",
    "Ratings": [
        {"Source": "Internet Movie Database", "Value": "8.1/10"},
        {"Source": "Rotten Tomatoes", "Value": "88%"},
        {"Source": "Metacritic", "Value": "74/100"},
    ],
}


class PreReleasePayloadTests(unittest.TestCase):
    def test_shape_matches_contract(self):
        payload = build_pre_release_payload(TMDB_DETAILS)
        self.assertEqual(payload["title"], "Example Movie")
        self.assertEqual(payload["director"], "Jane Director")
        self.assertEqual(payload["cast"], ["Star One", "Star Two"])
        self.assertEqual(payload["studio"], "Example Studios")
        self.assertEqual(payload["franchise"], "Example Collection")
        self.assertEqual(payload["budget"], 190000000)
        self.assertIn("Similar Movie One", payload["comparableFilms"])

    def test_never_leaks_actual_results_fields(self):
        payload = build_pre_release_payload(TMDB_DETAILS)
        for leaky_key in ("revenue", "vote_average", "boxOffice", "audienceScore"):
            self.assertNotIn(leaky_key, payload)


class ActualResultsPayloadTests(unittest.TestCase):
    def test_shape_matches_contract(self):
        payload = build_actual_results_payload(TMDB_DETAILS, OMDB_DATA)
        self.assertEqual(payload["boxOfficeDomestic"], 300000000)
        self.assertEqual(payload["boxOfficeWorldwide"], 711800000)
        self.assertEqual(payload["imdbRating"], 8.1)
        self.assertEqual(payload["audienceScore"], 78.0)
        self.assertEqual(payload["criticScore"], 88.0)

    def test_handles_missing_omdb_data(self):
        payload = build_actual_results_payload(TMDB_DETAILS, None)
        self.assertIsNone(payload["boxOfficeDomestic"])
        self.assertIsNone(payload["imdbRating"])
        self.assertEqual(payload["boxOfficeWorldwide"], 711800000)
        self.assertEqual(payload["audienceScore"], 78.0)


if __name__ == "__main__":
    unittest.main()
