#!/usr/bin/env python3
"""Read-only-plus-session-creation API over the two shared committee databases.

This does NOT run any agent -- it only creates sessions and reads whatever
votes/scores have been written to the databases by whichever agent code
(committee/, or the per-person branches once merged) populated them. That
split is deliberate: the UI works the same regardless of which agent
implementation ends up wired in.

Run from the repo root:
    pip install -r api/requirements.txt
    uvicorn api.main:app --reload
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "data-pipeline"))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from committee.agents import run_agent
from committee.scoring import run_scoring
from db.env import load_env_file
from db.prerelease import create_session, get_slate, get_votes, record_vote, upsert_film
from db.results import get_actual_results, get_scores, record_score, upsert_actual_results
from src.pipeline import fetch_film, find_movie

app = FastAPI(title="AI Greenlight Committee")


def _find_film(slate_name: str, film_id: int) -> dict:
    for film in get_slate(slate=slate_name):
        if film["id"] == film_id:
            return film
    raise HTTPException(status_code=404, detail=f"Film {film_id} not in slate {slate_name!r}")


@app.get("/api/slate")
def slate(slate: str = "default"):
    return get_slate(slate=slate)


@app.post("/api/slate/add-film")
def add_film(title: str, slate: str = "default"):
    """Fetch a film by title from TMDB/OMDb (live) and load it into both
    databases under the given slate, same as data-pipeline/load_slate.py."""
    load_env_file(".env.local")
    tmdb_key = os.environ.get("TMDB_API_KEY")
    omdb_key = os.environ.get("OMDB_API_KEY")
    if not tmdb_key or not omdb_key:
        raise HTTPException(status_code=500, detail="TMDB_API_KEY / OMDB_API_KEY not set in .env.local")

    match = find_movie(title, tmdb_key)
    if not match:
        raise HTTPException(status_code=404, detail=f"No TMDB match found for {title!r}")

    pre_release, actual_results = fetch_film(title, tmdb_key, omdb_key)

    film_id = upsert_film(
        tmdb_id=match["id"],
        title=pre_release["title"],
        release_date=pre_release["releaseDate"],
        payload=pre_release,
        slate=slate,
    )
    upsert_actual_results(tmdb_id=match["id"], title=pre_release["title"], payload=actual_results)

    return {
        "id": film_id,
        "tmdb_id": match["id"],
        "title": pre_release["title"],
        "release_date": pre_release["releaseDate"],
        "payload": pre_release,
    }


@app.post("/api/session")
def new_session(slate: str = "default"):
    session_id = create_session(slate=slate)
    return {"session_id": session_id}


@app.get("/api/session/{session_id}/votes")
def session_votes(session_id: int):
    return get_votes(session_id)


@app.get("/api/session/{session_id}/scores")
def session_scores(session_id: int):
    return get_scores(session_id)


@app.post("/api/session/{session_id}/agent-run")
def agent_run(session_id: int, film_id: int, role: str, slate: str = "default"):
    """Actually run one committee agent (real Claude call, or a free mock
    response if ANTHROPIC_API_KEY isn't set) and record its vote."""
    film = _find_film(slate, film_id)
    result = run_agent(role, film["payload"])
    record_vote(
        session_id=session_id,
        film_id=film_id,
        role=result["role"],
        vote=result["vote"],
        argument=result["argument"],
    )
    return result


@app.post("/api/session/{session_id}/score-run")
def score_run(session_id: int, tmdb_id: int, slate: str = "default"):
    """Actually run the scoring agent (real Claude call, or a free mock
    response) for one film and record its grade. The grade itself is always
    computed deterministically (see committee/calibration.py) -- only the
    rationale text depends on ANTHROPIC_API_KEY."""
    votes = [v for v in get_votes(session_id) if v["tmdb_id"] == tmdb_id]
    if not votes:
        raise HTTPException(status_code=400, detail="No votes recorded for this film yet")

    actual = get_actual_results(tmdb_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="No actual results loaded for this film yet")

    title = votes[0]["title"]
    budget = None
    for film in get_slate(slate=slate):
        if film["tmdb_id"] == tmdb_id:
            budget = (film["payload"] or {}).get("budget")
            break

    result = run_scoring(title, votes, actual["payload"], budget)
    record_score(
        session_id=session_id,
        tmdb_id=tmdb_id,
        grade=result["grade"],
        rationale=result["rationale"],
    )
    return result


@app.get("/api/results/{tmdb_id}")
def results(tmdb_id: int):
    result = get_actual_results(tmdb_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Not released or not loaded yet")
    return result


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
