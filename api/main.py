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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from db.prerelease import create_session, get_slate, get_votes
from db.results import get_actual_results, get_scores

app = FastAPI(title="AI Greenlight Committee")


@app.get("/api/slate")
def slate(slate: str = "default"):
    return get_slate(slate=slate)


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


@app.get("/api/results/{tmdb_id}")
def results(tmdb_id: int):
    result = get_actual_results(tmdb_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Not released or not loaded yet")
    return result


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
