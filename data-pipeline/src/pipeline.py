"""Fetches a film from TMDB/OMDb and splits it into the two payloads the rest
of the app relies on: PreReleaseFilm (what the committee agents see) and
ActualResults (what only the scoring agent sees).
"""
import re
from typing import Optional, Tuple

from . import omdb_client, tmdb_client
from .schema import ActualResults, PreReleaseFilm

MONEY_RE = re.compile(r"[\d,]+")


def _parse_money(value: Optional[str]) -> Optional[int]:
    if not value or value == "N/A":
        return None
    match = MONEY_RE.search(value)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _rating_from_source(omdb_data: dict, source: str) -> Optional[float]:
    for rating in omdb_data.get("Ratings", []):
        if rating.get("Source") == source:
            value = rating["Value"]
            if value.endswith("%"):
                return float(value.rstrip("%"))
            if "/" in value:
                numerator, _, denominator = value.partition("/")
                return round(float(numerator) / float(denominator) * 100, 1)
    return None


def find_movie(title: str, tmdb_api_key: str) -> Optional[dict]:
    """Return the best-guess TMDB search result for a title, or None."""
    results = tmdb_client.search_movie(title, tmdb_api_key)
    return results[0] if results else None


def build_pre_release_payload(tmdb_details: dict) -> PreReleaseFilm:
    credits = tmdb_details.get("credits", {})
    director = next(
        (c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"),
        None,
    )
    cast = [c["name"] for c in credits.get("cast", [])[:8]]
    studios = [c["name"] for c in tmdb_details.get("production_companies", [])]
    collection = tmdb_details.get("belongs_to_collection")
    similar = tmdb_details.get("similar", {}).get("results", [])

    return PreReleaseFilm(
        title=tmdb_details.get("title") or tmdb_details.get("original_title"),
        releaseDate=tmdb_details.get("release_date") or None,
        genres=[g["name"] for g in tmdb_details.get("genres", [])],
        director=director,
        cast=cast,
        studio=studios[0] if studios else None,
        budget=tmdb_details.get("budget") or None,
        logline=tmdb_details.get("overview") or None,
        franchise=collection["name"] if collection else None,
        comparableFilms=[m["title"] for m in similar[:5]],
    )


def build_actual_results_payload(
    tmdb_details: dict, omdb_data: Optional[dict]
) -> ActualResults:
    omdb_data = omdb_data or {}
    imdb_rating = omdb_data.get("imdbRating")
    metascore = omdb_data.get("Metascore")

    return ActualResults(
        boxOfficeDomestic=_parse_money(omdb_data.get("BoxOffice")),
        boxOfficeWorldwide=tmdb_details.get("revenue") or None,
        imdbRating=float(imdb_rating) if imdb_rating and imdb_rating != "N/A" else None,
        # TMDB's vote_average is a 0-10 user (audience) score; normalize to 0-100
        # to sit alongside the other percentage-based scores.
        audienceScore=round(tmdb_details["vote_average"] * 10, 1)
        if tmdb_details.get("vote_average")
        else None,
        criticScore=_rating_from_source(omdb_data, "Rotten Tomatoes")
        or (float(metascore) if metascore and metascore != "N/A" else None),
    )


def fetch_film(
    title: str, tmdb_api_key: str, omdb_api_key: str
) -> Tuple[PreReleaseFilm, ActualResults]:
    """Look up a film by title and return (pre_release, actual_results)."""
    match = find_movie(title, tmdb_api_key)
    if not match:
        raise ValueError(f"No TMDB match found for {title!r}")

    tmdb_details = tmdb_client.get_movie_full(match["id"], tmdb_api_key)

    omdb_data = None
    imdb_id = tmdb_details.get("external_ids", {}).get("imdb_id")
    if imdb_id:
        try:
            omdb_data = omdb_client.get_by_imdb_id(imdb_id, omdb_api_key)
        except omdb_client.OMDbError:
            omdb_data = None

    pre_release = build_pre_release_payload(tmdb_details)
    actual_results = build_actual_results_payload(tmdb_details, omdb_data)
    return pre_release, actual_results
