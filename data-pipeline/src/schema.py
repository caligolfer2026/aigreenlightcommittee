"""Shapes match the data contract in the root README.md.

Keep these two payloads strictly separate: PreReleaseFilm may only contain
information that would have been known before the film opened. ActualResults
holds everything that only exists after release, and is only ever handed to
the scoring agent.
"""
from typing import List, Optional, TypedDict


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
    comparableFilms: List[str]


class ActualResults(TypedDict):
    boxOfficeDomestic: Optional[int]
    boxOfficeWorldwide: Optional[int]
    imdbRating: Optional[float]
    audienceScore: Optional[float]
    criticScore: Optional[float]
