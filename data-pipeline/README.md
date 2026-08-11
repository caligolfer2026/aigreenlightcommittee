# data-pipeline

Fetches film data from TMDB and OMDb (an IMDB data proxy — there's no free
official IMDB API) and splits it into the two payloads the rest of the app
depends on. See the root [README.md](../README.md) for how this fits into
the overall project.

No third-party dependencies — this is plain Python 3 stdlib (`urllib`) so
anyone on the team can run it without a `pip install` step.

## Setup

1. Get a free TMDB API key: https://www.themoviedb.org/settings/api
2. Get a free OMDb API key: https://www.omdbapi.com/apikey.aspx (emailed to
   you, and you have to click an activation link in the email before it
   works)
3. Copy `.env.example` to `.env.local` and fill in both keys:

```bash
cp .env.example .env.local
```

`.env.local` is gitignored — never commit real API keys.

## Usage

```bash
python3 cli.py "Dune: Part Two"
```

Prints JSON with `preRelease` and `actualResults` payloads for the best TMDB
match on that title.

## Tests

Offline, no API keys or network needed — they run against fixture data:

```bash
python3 -m unittest discover -s tests
```

## Layout

- `src/tmdb_client.py` — search + fetch a movie's full TMDB record (details,
  credits, external IDs, similar titles) in one call
- `src/omdb_client.py` — fetch OMDb's IMDB-sourced rating/box office data by
  IMDB id
- `src/pipeline.py` — shapes raw TMDB/OMDb responses into the two contract
  payloads (`build_pre_release_payload`, `build_actual_results_payload`,
  `fetch_film`)
- `src/schema.py` — the payload shapes (`PreReleaseFilm`, `ActualResults`),
  matching the root README's data contract exactly
- `cli.py` — command-line entry point for trying it out / smoke-testing

## The one rule that matters here

`build_pre_release_payload` must never include anything that only exists
after a film comes out (ratings, box office, revenue, vote counts). That's
the whole premise of the app — if this leaks, the committee agents are
cheating. `test_never_leaks_actual_results_fields` in
`tests/test_pipeline.py` guards this; keep it passing.

## Using this from the rest of the app

Whatever the agent branches end up being built in, they can either:

- shell out to `cli.py` and parse its JSON output, or
- if the final app is also Python, import `fetch_film` from
  `src/pipeline.py` directly

Either way, treat the JSON shape in `src/schema.py` as the interface — don't
change field names without updating the root README's contract and telling
the other branch owners.
