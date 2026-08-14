"""Fetches a film from TMDB/OMDb and splits it into the two payloads the rest
of the app relies on: PreReleaseFilm (what the committee agents see) and
ActualResults (what only the scoring agent sees).
"""
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from . import omdb_client, tmdb_client
from .schema import (
    ActualResults,
    CastMemberFilmography,
    ComparableFilm,
    FranchiseEntry,
    PastFilm,
    PreReleaseFilm,
)

# Cap on extra /movie/{id} detail calls made to backfill budget/revenue for
# comparable and franchise films, and on genre-historical-performance comps.
FINANCIALS_LIMIT = 5

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


def _release_window(release_date: Optional[str]) -> Optional[str]:
    """Rough marketing-relevant release window label (e.g. "Summer 2024",
    "Holiday 2024", "Awards Season 2024") from a YYYY-MM-DD date."""
    if not release_date:
        return None
    try:
        year, month_str, _ = release_date.split("-")
        month = int(month_str)
    except (ValueError, AttributeError):
        return None
    if month == 12:
        season = "Holiday"
    elif month in (1, 2):
        season = "Winter"
    elif month in (3, 4):
        season = "Spring"
    elif month in (5, 6, 7, 8):
        season = "Summer"
    elif month in (9, 10):
        season = "Fall"
    else:  # November
        season = "Awards Season"
    return f"{season} {year}"


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
    comparable_financials: Optional[Dict[int, dict]] = None,
    franchise_financials: Optional[Dict[int, dict]] = None,
    genre_historical: Optional[List[dict]] = None,
) -> PreReleaseFilm:
    """Build the pre-release payload from a movie's TMDB details, plus
    optional extra lookups (collection, director/cast credits) used to fill
    in franchiseEntries / directorFilmography / castFilmography. All three
    are optional so callers that only have the base movie record still get a
    valid payload (with those lists empty).

    `comparable_financials` / `franchise_financials` are optional
    {tmdb_id: {"budget": int|None, "revenue": int|None}} maps -- backfilling
    these requires an extra /movie/{id} call per film (the lightweight
    "similar"/"collection" list entries don't carry budget/revenue), so
    that I/O happens in fetch_film and the results are passed in here,
    keeping this function itself pure/offline. `genre_historical` is a
    pre-built list of already-released same-genre films (also fetched by
    fetch_film via TMDB's Discover endpoint, independent of the "similar"
    algorithm) -- also pure pass-through here.
    """
    comparable_financials = comparable_financials or {}
    franchise_financials = franchise_financials or {}

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
            budget=comparable_financials.get(m.get("id"), {}).get("budget"),
            boxOfficeWorldwide=comparable_financials.get(m.get("id"), {}).get("revenue"),
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
                budget=franchise_financials.get(p.get("id"), {}).get("budget"),
                boxOfficeWorldwide=franchise_financials.get(p.get("id"), {}).get("revenue"),
            )
            for p in parts
        ]

    genre_historical_performance = [
        ComparableFilm(
            title=g.get("title") or g.get("original_title"),
            releaseDate=g.get("release_date") or None,
            rating=_normalize_rating(g.get("vote_average")),
            budget=g.get("budget"),
            boxOfficeWorldwide=g.get("revenue"),
        )
        for g in (genre_historical or [])
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
        marketingHook=tmdb_details.get("tagline") or None,
        targetDemo=None,  # not available from TMDB; agents infer this themselves
        releaseWindow=_release_window(tmdb_details.get("release_date")),
        franchise=collection["name"] if collection else None,
        franchiseEntries=franchise_entries,
        comparableFilms=comparable_films,
        directorFilmography=director_filmography,
        castFilmography=cast_filmography,
        genreHistoricalPerformance=genre_historical_performance,
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


def _dedupe_exclude(entries: list, exclude_id: Optional[int], limit: int) -> List[dict]:
    """Like _other_films, but preserves the input order instead of
    re-sorting by release date -- used for genre-historical-performance
    results, which arrive pre-sorted by box office from TMDB's Discover
    endpoint and should stay that way."""
    seen = set()
    out = []
    for entry in entries:
        movie_id = entry.get("id")
        if movie_id is None or movie_id == exclude_id or movie_id in seen:
            continue
        if not entry.get("release_date"):
            continue
        seen.add(movie_id)
        out.append(entry)
        if len(out) >= limit:
            break
    return out


def _fetch_financials(movie_ids: List[int], tmdb_api_key: str) -> Dict[int, dict]:
    """{tmdb_id: {"budget": int|None, "revenue": int|None}} for each id,
    skipping any that fail to fetch. One extra /movie/{id} call per id --
    the lightweight list entries these ids come from don't carry
    budget/revenue, only the full details endpoint does."""
    financials: Dict[int, dict] = {}
    for movie_id in movie_ids:
        try:
            details = tmdb_client.get_movie_details(movie_id, tmdb_api_key)
        except tmdb_client.TMDBError:
            continue
        financials[movie_id] = {
            "budget": details.get("budget") or None,
            "revenue": details.get("revenue") or None,
        }
    return financials


def fetch_genre_historical_performance(
    genre_name: str,
    before_date: str,
    tmdb_api_key: str,
    exclude_id: Optional[int] = None,
    sort_by: str = "revenue.desc",
    limit: int = FINANCIALS_LIMIT,
) -> List[dict]:
    """Already-released films in `genre_name`, sorted by `sort_by` (default:
    highest-grossing first; pass "primary_release_date.desc" for
    most-recently-released first), with budget/revenue backfilled --
    independent of TMDB's "similar movies" algorithm, which optimizes for
    topical/cast similarity rather than genre + financial performance. See
    schema.py's genreHistoricalPerformance docstring. Used both for a real
    film (genre taken from its own TMDB record) and for a hypothetical
    pitch with no TMDB match of its own (see build_pitch_payload)."""
    genre_id = tmdb_client.GENRE_NAME_TO_ID.get(genre_name)
    if genre_id is None:
        return []

    try:
        results = tmdb_client.discover_movies_by_genre(genre_id, before_date, tmdb_api_key, sort_by=sort_by)
    except tmdb_client.TMDBError:
        return []

    candidates = _dedupe_exclude(results, exclude_id, limit=limit)
    financials = _fetch_financials([c["id"] for c in candidates], tmdb_api_key)

    return [
        {**c, "budget": financials.get(c["id"], {}).get("budget"),
         "revenue": financials.get(c["id"], {}).get("revenue")}
        for c in candidates
    ]


def _fetch_genre_historical_performance(tmdb_details: dict, tmdb_api_key: str) -> List[dict]:
    """Wrapper for the real-film call site in fetch_film: pulls genre and
    release date off the film's own TMDB record."""
    genres = tmdb_details.get("genres", [])
    release_date = tmdb_details.get("release_date")
    movie_id = tmdb_details.get("id")
    if not genres or not release_date:
        return []
    return fetch_genre_historical_performance(genres[0]["name"], release_date, tmdb_api_key, exclude_id=movie_id)


def build_pitch_payload(
    title: str,
    genre: str,
    logline: str,
    reference_title: Optional[str],
    tmdb_api_key: str,
    marketing_hook: Optional[str] = None,
    target_demo: Optional[str] = None,
    budget: Optional[int] = None,
) -> PreReleaseFilm:
    """Build a synthetic pre-release payload for a hypothetical pitch that
    doesn't exist as a real film -- no TMDB match, no cast/director of its
    own (budget may be given if the pitch stated one). The only real data
    in here is genreHistoricalPerformance (the last N *already-released*
    films in this genre, sorted by most recent) and, if the pitch named a
    specific comp film, that one comp's real numbers as a single
    comparableFilms entry."""
    today = date.today().isoformat()
    genre_historical = fetch_genre_historical_performance(
        genre, today, tmdb_api_key, sort_by="primary_release_date.desc"
    )
    genre_historical_performance = [
        ComparableFilm(
            title=g.get("title") or g.get("original_title"),
            releaseDate=g.get("release_date") or None,
            rating=_normalize_rating(g.get("vote_average")),
            budget=g.get("budget"),
            boxOfficeWorldwide=g.get("revenue"),
        )
        for g in genre_historical
    ]

    comparable_films: List[ComparableFilm] = []
    if reference_title:
        match = find_movie(reference_title, tmdb_api_key)
        if match:
            try:
                details = tmdb_client.get_movie_details(match["id"], tmdb_api_key)
            except tmdb_client.TMDBError:
                details = {}
            comparable_films = [
                ComparableFilm(
                    title=details.get("title") or match.get("title") or reference_title,
                    releaseDate=details.get("release_date") or match.get("release_date") or None,
                    rating=_normalize_rating(details.get("vote_average") or match.get("vote_average")),
                    budget=details.get("budget") or None,
                    boxOfficeWorldwide=details.get("revenue") or None,
                )
            ]

    return PreReleaseFilm(
        title=title,
        releaseDate=None,
        genres=[genre],
        director=None,
        cast=[],
        studio=None,
        budget=budget,
        logline=logline,
        marketingHook=marketing_hook,
        targetDemo=target_demo,
        releaseWindow=None,
        franchise=None,
        franchiseEntries=[],
        comparableFilms=comparable_films,
        directorFilmography=[],
        castFilmography=[],
        genreHistoricalPerformance=genre_historical_performance,
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

    movie_id = tmdb_details.get("id")
    similar = tmdb_details.get("similar", {}).get("results", [])
    comparable_financials = _fetch_financials(
        [f["id"] for f in _other_films(similar, movie_id, limit=5)], tmdb_api_key
    )

    franchise_financials: Dict[int, dict] = {}
    if collection_data:
        parts = _other_films(collection_data.get("parts", []), movie_id)
        franchise_financials = _fetch_financials(
            [p["id"] for p in parts[:FINANCIALS_LIMIT]], tmdb_api_key
        )

    genre_historical = _fetch_genre_historical_performance(tmdb_details, tmdb_api_key)

    pre_release = build_pre_release_payload(
        tmdb_details,
        collection_data=collection_data,
        director_credits=director_credits,
        cast_credits=cast_credits,
        comparable_financials=comparable_financials,
        franchise_financials=franchise_financials,
        genre_historical=genre_historical,
    )
    actual_results = build_actual_results_payload(tmdb_details, omdb_data)
    return pre_release, actual_results
