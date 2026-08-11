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
