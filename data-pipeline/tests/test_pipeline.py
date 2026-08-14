"""Offline tests: no network, no API keys. Run with:
    python3 -m unittest discover -s tests
"""
import unittest

from src.pipeline import build_actual_results_payload, build_pre_release_payload

TMDB_DETAILS = {
    "id": 1,
    "title": "Example Movie",
    "release_date": "2025-11-07",
    "genres": [{"id": 1, "name": "Science Fiction"}, {"id": 2, "name": "Adventure"}],
    "production_companies": [{"name": "Example Studios"}],
    "budget": 190000000,
    "revenue": 711800000,
    "overview": "A hero saves the day.",
    "popularity": 123.45,
    "vote_average": 7.8,
    "vote_count": 4567,
    "belongs_to_collection": {"id": 100, "name": "Example Collection"},
    "credits": {
        "crew": [{"id": 10, "name": "Jane Director", "job": "Director"}],
        "cast": [{"id": 20, "name": "Star One"}, {"id": 21, "name": "Star Two"}],
    },
    "similar": {
        "results": [
            {
                "id": 2,
                "title": "Similar Movie One",
                "release_date": "2023-05-01",
                "vote_average": 6.5,
            },
            {
                "id": 3,
                "title": "Similar Movie Two",
                "release_date": "2020-01-01",
                "vote_average": 7.0,
            },
        ]
    },
    "external_ids": {"imdb_id": "tt0000000"},
}

COLLECTION_DATA = {
    "id": 100,
    "parts": [
        {"id": 1, "title": "Example Movie", "release_date": "2025-11-07", "vote_average": 7.8},
        {"id": 4, "title": "Example Movie: Origins", "release_date": "2019-06-01", "vote_average": 6.8},
    ],
}

DIRECTOR_CREDITS = {
    "crew": [
        {"id": 1, "title": "Example Movie", "job": "Director", "release_date": "2025-11-07"},
        {
            "id": 5,
            "title": "Jane's Earlier Film",
            "job": "Director",
            "release_date": "2021-03-01",
            "vote_average": 7.2,
        },
    ]
}

CAST_CREDITS = [
    (
        "Star One",
        {
            "cast": [
                {"id": 1, "title": "Example Movie", "release_date": "2025-11-07"},
                {
                    "id": 6,
                    "title": "Star One's Earlier Role",
                    "release_date": "2022-08-01",
                    "vote_average": 5.9,
                },
            ]
        },
    )
]

OMDB_DATA = {
    "Response": "True",
    "imdbRating": "8.1",
    "imdbVotes": "123,456",
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
        titles = [f["title"] for f in payload["comparableFilms"]]
        self.assertIn("Similar Movie One", titles)

    def test_comparable_films_include_rating_and_release_date(self):
        payload = build_pre_release_payload(TMDB_DETAILS)
        first = payload["comparableFilms"][0]
        self.assertEqual(first["title"], "Similar Movie One")
        self.assertEqual(first["releaseDate"], "2023-05-01")
        self.assertEqual(first["rating"], 65.0)

    def test_franchise_entries_exclude_the_evaluated_film(self):
        payload = build_pre_release_payload(TMDB_DETAILS, collection_data=COLLECTION_DATA)
        titles = [e["title"] for e in payload["franchiseEntries"]]
        self.assertNotIn("Example Movie", titles)
        self.assertIn("Example Movie: Origins", titles)
        self.assertEqual(payload["franchiseEntries"][0]["rating"], 68.0)

    def test_director_filmography_excludes_the_evaluated_film(self):
        payload = build_pre_release_payload(TMDB_DETAILS, director_credits=DIRECTOR_CREDITS)
        titles = [f["title"] for f in payload["directorFilmography"]]
        self.assertNotIn("Example Movie", titles)
        self.assertIn("Jane's Earlier Film", titles)

    def test_cast_filmography_excludes_the_evaluated_film(self):
        payload = build_pre_release_payload(TMDB_DETAILS, cast_credits=CAST_CREDITS)
        self.assertEqual(payload["castFilmography"][0]["name"], "Star One")
        titles = [f["title"] for f in payload["castFilmography"][0]["pastFilms"]]
        self.assertNotIn("Example Movie", titles)
        self.assertIn("Star One's Earlier Role", titles)

    def test_never_leaks_actual_results_fields(self):
        payload = build_pre_release_payload(
            TMDB_DETAILS,
            collection_data=COLLECTION_DATA,
            director_credits=DIRECTOR_CREDITS,
            cast_credits=CAST_CREDITS,
        )
        for leaky_key in ("revenue", "vote_average", "boxOffice", "audienceScore"):
            self.assertNotIn(leaky_key, payload)
        # The evaluated film itself must never appear with reception data
        # anywhere in the payload, even nested inside comparables/franchise/
        # filmography entries.
        for entry in payload["comparableFilms"] + payload["franchiseEntries"]:
            self.assertNotEqual(entry["title"], "Example Movie")
        for entry in payload["directorFilmography"]:
            self.assertNotEqual(entry["title"], "Example Movie")
        for member in payload["castFilmography"]:
            for entry in member["pastFilms"]:
                self.assertNotEqual(entry["title"], "Example Movie")


class ActualResultsPayloadTests(unittest.TestCase):
    def test_shape_matches_contract(self):
        payload = build_actual_results_payload(TMDB_DETAILS, OMDB_DATA)
        self.assertEqual(payload["boxOfficeDomestic"], 300000000)
        self.assertEqual(payload["boxOfficeWorldwide"], 711800000)
        self.assertEqual(payload["imdbRating"], 8.1)
        self.assertEqual(payload["imdbVotes"], 123456)
        self.assertEqual(payload["tmdbPopularity"], 123.45)
        self.assertEqual(payload["tmdbVoteCount"], 4567)
        self.assertEqual(payload["audienceScore"], 78.0)
        self.assertEqual(payload["criticScore"], 88.0)

    def test_handles_missing_omdb_data(self):
        payload = build_actual_results_payload(TMDB_DETAILS, None)
        self.assertIsNone(payload["boxOfficeDomestic"])
        self.assertIsNone(payload["imdbRating"])
        self.assertIsNone(payload["imdbVotes"])
        self.assertEqual(payload["tmdbPopularity"], 123.45)
        self.assertEqual(payload["tmdbVoteCount"], 4567)
        self.assertEqual(payload["boxOfficeWorldwide"], 711800000)
        self.assertEqual(payload["audienceScore"], 78.0)


if __name__ == "__main__":
    unittest.main()
