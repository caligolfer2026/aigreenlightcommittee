"""Shapes match the data contract in the root README.md.

Keep these two payloads strictly separate: PreReleaseFilm may only contain
information that would have been known before the film opened, and must
never include the evaluated film's own post-release reception. Other films
referenced within PreReleaseFilm (comparable titles, franchise entries, past
filmography) are already-released movies, so their own historical reception
data is fair game and included directly. ActualResults holds everything that
only exists after the evaluated film's release, and is only ever handed to
the scoring agent.
"""
from typing import List, Optional, TypedDict


class ComparableFilm(TypedDict):
    title: str
    releaseDate: Optional[str]
    rating: Optional[float]
    budget: Optional[int]
    boxOfficeWorldwide: Optional[int]


class FranchiseEntry(TypedDict):
    title: str
    releaseDate: Optional[str]
    rating: Optional[float]
    budget: Optional[int]
    boxOfficeWorldwide: Optional[int]


class PastFilm(TypedDict):
    title: str
    releaseDate: Optional[str]
    rating: Optional[float]


class CastMemberFilmography(TypedDict):
    name: str
    pastFilms: List[PastFilm]


class PreReleaseFilm(TypedDict):
    title: str
    releaseDate: Optional[str]
    genres: List[str]
    director: Optional[str]
    cast: List[str]
    studio: Optional[str]
    budget: Optional[int]
    logline: Optional[str]
    franchise: Optional[str]
    franchiseEntries: List[FranchiseEntry]
    comparableFilms: List[ComparableFilm]
    directorFilmography: List[PastFilm]
    castFilmography: List[CastMemberFilmography]
    # Historical financial performance of already-released films in this
    # film's primary genre, sourced independently of TMDB's "similar movies"
    # algorithm (which optimizes for topical/cast similarity, not genre +
    # box office) -- this is what agents should actually reason from for
    # "how do films like this typically perform" questions.
    genreHistoricalPerformance: List[ComparableFilm]


class ActualResults(TypedDict):
    boxOfficeDomestic: Optional[int]
    boxOfficeWorldwide: Optional[int]
    imdbRating: Optional[float]
    audienceScore: Optional[float]
    criticScore: Optional[float]
