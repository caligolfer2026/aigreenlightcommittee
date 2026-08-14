"""Thin client for The Movie Database (TMDB) API v3.

Get a free API key at https://www.themoviedb.org/settings/api
"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.themoviedb.org/3"


class TMDBError(RuntimeError):
    pass


def _get(path: str, api_key: str, **params) -> dict:
    query = {"api_key": api_key, **{k: v for k, v in params.items() if v is not None}}
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TMDBError(f"TMDB request failed ({exc.code}) for {path}: {body}") from exc


def search_movie(title: str, api_key: str) -> list:
    """Return TMDB's search results (list of {id, title, release_date, ...})."""
    data = _get("/search/movie", api_key, query=title)
    return data.get("results", [])


def get_movie_full(tmdb_id: int, api_key: str) -> dict:
    """Fetch a movie's details plus credits, external IDs, and similar titles
    in one call via TMDB's append_to_response."""
    return _get(
        f"/movie/{tmdb_id}",
        api_key,
        append_to_response="credits,external_ids,similar",
    )


def get_movie_details(tmdb_id: int, api_key: str) -> dict:
    """Plain /movie/{id} fetch -- no append_to_response. The lightweight
    objects returned by /search, /similar, /collection, and
    /person/movie_credits don't carry budget/revenue, only the full details
    endpoint does; use this to backfill those two fields for a comp film
    without paying for credits/similar data you don't need."""
    return _get(f"/movie/{tmdb_id}", api_key)


# TMDB's fixed movie genre list (https://developer.themoviedb.org/reference/genre-movie-list)
GENRE_NAME_TO_ID = {
    "Action": 28,
    "Adventure": 12,
    "Animation": 16,
    "Comedy": 35,
    "Crime": 80,
    "Documentary": 99,
    "Drama": 18,
    "Family": 10751,
    "Fantasy": 14,
    "History": 36,
    "Horror": 27,
    "Music": 10402,
    "Mystery": 9648,
    "Romance": 10749,
    "Science Fiction": 878,
    "TV Movie": 10770,
    "Thriller": 53,
    "War": 10752,
    "Western": 37,
}


def discover_movies_by_genre(
    genre_id: int, before_date: str, api_key: str, sort_by: str = "revenue.desc"
) -> list:
    """Already-released films in a given genre, sorted by (default) worldwide
    box office. `before_date` (YYYY-MM-DD) excludes films that release on or
    after the film being evaluated, so this stays historical-only data."""
    data = _get(
        "/discover/movie",
        api_key,
        with_genres=genre_id,
        **{
            "primary_release_date.lte": before_date,
            "vote_count.gte": 50,  # filter out obscure/unrated titles
            "sort_by": sort_by,
        },
    )
    return data.get("results", [])


def get_collection(collection_id: int, api_key: str) -> dict:
    """Fetch a franchise/collection's full list of entries (parts)."""
    return _get(f"/collection/{collection_id}", api_key)


def get_person_movie_credits(person_id: int, api_key: str) -> dict:
    """Fetch a person's film credits (cast + crew), for filmography lookups."""
    return _get(f"/person/{person_id}/movie_credits", api_key)
