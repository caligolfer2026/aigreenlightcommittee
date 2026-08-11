"""Thin client for the OMDb API (wraps IMDB data — there's no free official
IMDB API). Get a free key at https://www.omdbapi.com/apikey.aspx
"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://www.omdbapi.com/"


class OMDbError(RuntimeError):
    pass


def get_by_imdb_id(imdb_id: str, api_key: str) -> dict:
    query = {"apikey": api_key, "i": imdb_id}
    url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OMDbError(f"OMDb request failed ({exc.code}): {body}") from exc

    if data.get("Response") == "False":
        raise OMDbError(data.get("Error", "unknown OMDb error"))
    return data
