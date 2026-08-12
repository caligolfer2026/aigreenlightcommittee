"""Fetches a film from TMDB/OMDb and splits it into the two payloads the rest
of the app relies on: PreReleaseFilm (what the committee agents see) and
ActualResults (what only the scoring agent sees).
"""
import re
from typing import List, Optional, Tuple

from . import omdb_client, tmdb_client
from .schema import (
    ActualResults,
    CastMemberFilmography,
    ComparableFilm,
    FranchiseEntry,
    PastFilm,
    PreReleaseFilm,
)

MONEY_RE = re.compile(r"[\d,]+")

CAST_FILMOGRAPHY_SIZE = 4
PAST_FILMS_LIMIT = 5


def _parse_money(value: Optional[str]) -> Optional[int]:
    if not value or value == "N/A":
        return None
    match = MONEY_RE.search(value)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _normalize_rating(vote_average: Optional[float]) -> Optional[float]:
    """TMDB's vote_average is 0-10; normalize to 0-100 to match the rest of
    the app's rating scale. Only ever applied to *other, already-released*
    films (comparables, franchise entries, filmography) — never to the film
    currently being evaluated."""
    if not vote_average:
        return None
    return round(vote_average * 10, 1)


def _other_films(
    entries: list, exclude_id: Optional[int], limit: Optional[int] = None
) -> List[dict]:
    """Dedupe a list of TMDB movie entries by id, drop the film currently
    being evaluated, and drop anything without a release date (unreleased /
    not yet comparable)."""
    seen = set()
    films = []
    for entry in entries:
        movie_id = entry.get("id")
        if movie_id is None or movie_id == exclude_id or movie_id in seen:
            continue
        release_date = entry.get("release_date")
        if not release_date:
            continue
        seen.add(movie_id)
        films.append(entry)
    films.sort(key=lambda e: e["release_date"], reverse=True)
    return films[:limit] if limit else films


def _as_past_film(entry: dict) -> PastFilm:
    return PastFilm(
        title=entry.get("title") or entry.get("original_title"),
        releaseDate=entry.get("release_date") or None,
        rating=_normalize_rating(entry.get("vote_average")),
    )


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


def build_pre_release_payload(
    tmdb_details: dict,
    collection_data: Optional[dict] = None,
    director_credits: Optional[dict] = None,
    cast_credits: Optional[List[Tuple[str, dict]]] = None,
) -> PreReleaseFilm:
    """Build the pre-release payload from a movie's TMDB details, plus
    optional extra lookups (collection, director/cast credits) used to fill
    in franchiseEntries / directorFilmography / castFilmography. All three
    are optional so callers that only have the base movie record still get a
    valid payload (with those lists empty).
    """
    credits = tmdb_details.get("credits", {})
    movie_id = tmdb_details.get("id")
    director_entry = next(
        (c for c in credits.get("crew", []) if c.get("job") == "Director"), None
    )
    cast_entries = credits.get("cast", [])[:8]
    cast = [c["name"] for c in cast_entries]
    studios = [c["name"] for c in tmdb_details.get("production_companies", [])]
    collection = tmdb_details.get("belongs_to_collection")
    similar = tmdb_details.get("similar", {}).get("results", [])

    comparable_films = [
        ComparableFilm(
            title=m.get("title") or m.get("original_title"),
            releaseDate=m.get("release_date") or None,
            rating=_normalize_rating(m.get("vote_average")),
        )
        for m in _other_films(similar, movie_id, limit=5)
    ]

    franchise_entries: List[FranchiseEntry] = []
    if collection_data:
        parts = _other_films(collection_data.get("parts", []), movie_id)
        franchise_entries = [
            FranchiseEntry(
                title=p.get("title") or p.get("original_title"),
                releaseDate=p.get("release_date") or None,
                rating=_normalize_rating(p.get("vote_average")),
            )
            for p in parts
        ]

    director_filmography: List[PastFilm] = []
    if director_credits:
        directed = [
            c for c in director_credits.get("crew", []) if c.get("job") == "Director"
        ]
        director_filmography = [
            _as_past_film(f) for f in _other_films(directed, movie_id, limit=PAST_FILMS_LIMIT)
        ]

    cast_filmography: List[CastMemberFilmography] = []
    for name, credits_data in cast_credits or []:
        past = _other_films(
            credits_data.get("cast", []), movie_id, limit=PAST_FILMS_LIMIT
        )
        cast_filmography.append(
            CastMemberFilmography(name=name, pastFilms=[_as_past_film(f) for f in past])
        )

    return PreReleaseFilm(
        title=tmdb_details.get("title") or tmdb_details.get("original_title"),
        releaseDate=tmdb_details.get("release_date") or None,
        genres=[g["name"] for g in tmdb_details.get("genres", [])],
        director=director_entry["name"] if director_entry else None,
        cast=cast,
        studio=studios[0] if studios else None,
        budget=tmdb_details.get("budget") or None,
        logline=tmdb_details.get("overview") or None,
        franchise=collection["name"] if collection else None,
        franchiseEntries=franchise_entries,
        comparableFilms=comparable_films,
        directorFilmography=director_filmography,
        castFilmography=cast_filmography,
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

    collection_data = None
    collection = tmdb_details.get("belongs_to_collection")
    if collection and collection.get("id"):
        try:
            collection_data = tmdb_client.get_collection(collection["id"], tmdb_api_key)
        except tmdb_client.TMDBError:
            collection_data = None

    credits = tmdb_details.get("credits", {})

    director_credits = None
    director_entry = next(
        (c for c in credits.get("crew", []) if c.get("job") == "Director"), None
    )
    if director_entry and director_entry.get("id"):
        try:
            director_credits = tmdb_client.get_person_movie_credits(
                director_entry["id"], tmdb_api_key
            )
        except tmdb_client.TMDBError:
            director_credits = None

    cast_credits: List[Tuple[str, dict]] = []
    for cast_entry in credits.get("cast", [])[:CAST_FILMOGRAPHY_SIZE]:
        if not cast_entry.get("id"):
            continue
        try:
            person_credits = tmdb_client.get_person_movie_credits(
                cast_entry["id"], tmdb_api_key
            )
        except tmdb_client.TMDBError:
            continue
        cast_credits.append((cast_entry["name"], person_credits))

    pre_release = build_pre_release_payload(
        tmdb_details,
        collection_data=collection_data,
        director_credits=director_credits,
        cast_credits=cast_credits,
    )
    actual_results = build_actual_results_payload(tmdb_details, omdb_data)
    return pre_release, actual_results
