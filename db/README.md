# db

The central, shared database layer. Instead of every branch calling TMDB/OMDb
itself (and everyone getting slightly different data), `data-pipeline`
populates two central Postgres databases once, and every agent branch reads
from them.

## Why two databases, not one

The whole premise of this project is that the committee agents (`creative`,
`finance`, `marketing`, `distribution`) only ever see information that would
have existed *before* a film's release, and the `scoring` agent is the only
one who reveals what actually happened. A single database with a
"don't query this column" convention is one bug away from an agent seeing
the answer before it votes. So instead there are two separate hosted
Postgres instances:

- **pre-release database** — films, their pre-release payload, committee
  sessions, and votes. `creative`, `finance`, `marketing`, and
  `distribution` all get a connection string to this one.
- **results database** — actual box office / audience data, and the
  scoring agent's grades. Only `scoring` (and the data-pipeline loader) get
  a connection string to this one.

If your branch's `.env.local` doesn't have `RESULTS_DATABASE_URL` in it,
your code has no way to reach that data at all — not just a rule you're
trusting yourself to follow.

## Setup (one-time, per person)

1. Get `PRERELEASE_DATABASE_URL` (and `RESULTS_DATABASE_URL`, if you're on
   `scoring`) from your team lead — these come from two free
   [Neon](https://neon.tech) Postgres projects. Never commit these values.
2. From the repo root:
   ```bash
   pip install -r db/requirements.txt
   ```
3. Copy `db/.env.example` to `.env.local` in your branch's own folder and
   fill in the connection string(s) you were given.
4. (Team lead only, one time per database) Apply the schema:
   ```bash
   python3 -m db.init_db --prerelease
   python3 -m db.init_db --results
   ```

## Usage

**Committee agents** (`creative`, `finance`, `marketing`, `distribution`)
only ever import from `db.prerelease`:

```python
from db.prerelease import get_slate, record_vote

films = get_slate()  # list of films with their pre-release payload
for film in films:
    # ... build your argument from film["payload"] (PreReleaseFilm shape) ...
    record_vote(session_id, film["id"], role="creative", vote="greenlight", argument="...")
```

**Scoring** imports from both:

```python
from db.prerelease import get_votes
from db.results import get_actual_results, record_score

votes = get_votes(session_id)
for v in votes:
    actual = get_actual_results(v["tmdb_id"])  # None if the film hasn't released yet
    # ... compare v["vote"] to actual, compute a grade ...
    record_score(session_id, v["tmdb_id"], grade=..., rationale="...")
```

Run agent scripts from the repo root (or make sure the repo root is on
`sys.path`) so `db` resolves as a package.

## Layout

- `schema_prerelease.sql` / `schema_results.sql` — table definitions for
  each database
- `connection.py` — reads `PRERELEASE_DATABASE_URL` / `RESULTS_DATABASE_URL`
  from `.env.local` and opens a connection
- `prerelease.py` — `upsert_film`, `get_slate`, `create_session`,
  `record_vote`, `get_votes`
- `results.py` — `upsert_actual_results`, `get_actual_results`,
  `record_score`, `get_scores`
- `init_db.py` — one-time schema setup, run with `python3 -m db.init_db`
- `tests/` — offline tests (mocked connections, no live database needed)

See `data-pipeline/load_slate.py` for how the pipeline's `fetch_film`
output gets loaded into these two databases in the first place.
