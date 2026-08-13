"""Connections to the two central Postgres databases.

There are deliberately two separate databases, not one database with two
tables:

- PRERELEASE_DATABASE_URL -- what creative/finance/marketing/distribution
  (and the data-pipeline loader) connect to. Holds films, pre-release
  payloads, sessions, and votes.
- RESULTS_DATABASE_URL -- what only the scoring branch (and the
  data-pipeline loader) connect to. Holds actual results and scores.

Only ever ask for the connection you actually need. If your agent doesn't
need RESULTS_DATABASE_URL, don't put it in your .env.local -- the point of
the split is that the committee agents have no way to reach the results
database at all, not just that they choose not to query it.

Requires psycopg (see requirements.txt): `pip install -r db/requirements.txt`
"""
import os

import psycopg

from .env import load_env_file

_loaded = False


def _ensure_env_loaded() -> None:
    global _loaded
    if not _loaded:
        load_env_file(".env.local")
        _loaded = True


def _connect(env_var: str):
    _ensure_env_loaded()
    url = os.environ.get(env_var)
    if not url:
        raise RuntimeError(
            f"Missing {env_var}. Copy db/.env.example to .env.local in your "
            f"branch folder and fill in the connection string your team lead "
            f"gave you."
        )
    return psycopg.connect(url)


def get_prerelease_connection():
    """Connection to the pre-release database. This is the one every
    committee agent branch (creative, finance, marketing, distribution)
    should use."""
    return _connect("PRERELEASE_DATABASE_URL")


def get_results_connection():
    """Connection to the results database. Only the scoring branch (and the
    data-pipeline loader) should ever need this one."""
    return _connect("RESULTS_DATABASE_URL")
