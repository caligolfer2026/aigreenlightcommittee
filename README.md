# AI Greenlight Committee

The project for AI with Holloway.

## Concept

Four AI agents play a studio greenlight committee, each arguing a single
perspective — **Creative**, **Finance**, **Marketing**, and **Distribution** —
about a slate of films using only information that would have been available
*before* the film's release (cast, director, genre, budget, comps, release
date, etc.). The committee debates and votes to greenlight or pass on each
film.

A fifth agent, **Scoring**, then reveals what actually happened — real box
office numbers and audience/critic response, pulled live from TMDB/OMDb —
and grades the committee on how well their pre-release judgment matched
reality.

## Status

A working end-to-end app is built and running on `main` — you can add a
film by title (live TMDB/OMDb lookup), convene the committee, watch all
four agents vote, and see the scoring agent's grade. No `ANTHROPIC_API_KEY`
is required to try it: every agent falls back to a free, deterministic mock
response when no key is set, so the whole pipeline (database writes,
scoring math, the UI) can be exercised at zero cost. Add a real key to get
actual Claude-generated arguments.

Persona status per role — most were built by teammates on their own
branches and ported into the running app (`committee/agents.py`):

| Role | Persona | Ported from |
|---|---|---|
| Creative | ✅ | `creative` branch (`.claude/agents/creative.md`) |
| Finance | ✅ | `finance` branch (`finance/PERSONA.md`) |
| Marketing | ✅ | `marketing` branch (`marketing/prompt.py` — originally built for OpenAI, ported to run on Claude instead so the app stays on one LLM provider) |
| Distribution | ⬜ generic | no branch work yet |
| Scoring | ✅ grade is deterministic | `scoring` branch (`scoring/calibration.py`) — the LLM only writes the rationale, never the grade |

## Project layout

```
data-pipeline/   TMDB/OMDb fetch + pre-release/actual-results payload builder
db/              Shared Postgres layer -- two databases, deliberately separate
committee/       The five agents (creative/finance/marketing/distribution
                 vote; scoring grades) + the Claude call wrapper + mock mode
api/             FastAPI backend -- sessions, votes, scores, add-film-by-title
frontend/        The UI (landing/slate builder -> deliberation -> verdict)
```

## How the pieces fit together

```
                        ┌────────────────┐
                        │  data-pipeline  │  fetches TMDB/OMDb data, loads it
                        └────────┬────────┘  into two central Postgres DBs
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                            ▼
        ┌──────────────────────┐      ┌──────────────────────┐
        │   pre-release db     │      │      results db      │
        │  films + votes       │      │  box office/audience │
        └──────────┬────────────┘      └───────────┬───────────┘
                   │                                │
                   ▼                                │
        ┌──────────────────────────────────────┐    │
        │      committee/agents.py              │    │
        │  creative · finance · marketing ·     │    │
        │  distribution vote (Claude, or mock)  │    │
        └──────────────────┬─────────────────────┘   │
                            │                         │
                            ▼                         ▼
                     ┌────────────────────────────────┐
                     │       committee/scoring.py       │
                     │  grade computed deterministically │
                     │  from real TMDB/OMDb numbers;     │
                     │  Claude (or mock) writes only the │
                     │  rationale text                   │
                     └────────────────┬───────────────┘
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │   api/main.py (FastAPI)         │
                      │  sessions, agent-run, score-run,│
                      │  add-film (live TMDB/OMDb)      │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │    frontend/      │
                              │  landing → deliberation → verdict │
                              └─────────────────┘
```

Two separate central Postgres databases, not one — see
[`db/README.md`](db/README.md) for why. `committee/agents.py`'s four voting
agents only ever read from the pre-release database; only
`committee/scoring.py` (and the data-pipeline loader) can reach the results
database at all.

`main` is the integration branch. Nobody pushes directly to `main` — every
branch merges in via a reviewed pull request.

## Running it locally

```bash
# from the repo root
pip install -r api/requirements.txt -r committee/requirements.txt -r db/requirements.txt
python3 -m uvicorn api.main:app --reload
```

Open `http://localhost:8000`. Add a film by title (or load an existing
slate), click **Convene the Committee**, and watch it run. Works with no
`ANTHROPIC_API_KEY` set — see [Environment variables](#environment-variables).

To run the same flow from the command line instead of the browser:

```bash
python3 -m committee.run --slate default
```

## Environment variables

All of the following live in a single `.env.local` file at the **repo
root** (gitignored — never commit real keys or database URLs):

- `TMDB_API_KEY` / `OMDB_API_KEY` — film metadata and box office/rating data.
  Required for loading films (via the UI's "add film" or
  `data-pipeline/load_slate.py`).
- `PRERELEASE_DATABASE_URL` / `RESULTS_DATABASE_URL` — the two central
  Postgres databases (see [`db/README.md`](db/README.md) for setup).
- `ANTHROPIC_API_KEY` — optional. Without it, every agent (and scoring's
  rationale text) runs in mock mode instead of calling Claude — the app
  still works end-to-end, just with placeholder argument text instead of
  real LLM output. The scoring **grade** is always real regardless, since
  it's computed deterministically from TMDB/OMDb data, not by the LLM.

## Data contract

So the pieces plug together cleanly, every agent is written against these
two shapes:

**Pre-release film payload** (only this is visible to the four committee
agents — no ratings, no box office, nothing that only exists after release,
for *the film being evaluated*. Other, already-released films referenced
here — comparable titles, franchise entries, filmography — are historical
public data, so their own rating/release info is included directly):

```json
{
  "title": "string",
  "releaseDate": "YYYY-MM-DD",
  "genres": ["string"],
  "director": "string",
  "cast": ["string"],
  "studio": "string",
  "budget": "number | null",
  "logline": "string",
  "franchise": "string | null",
  "franchiseEntries": [
    { "title": "string", "releaseDate": "YYYY-MM-DD | null", "rating": "number | null" }
  ],
  "comparableFilms": [
    { "title": "string", "releaseDate": "YYYY-MM-DD | null", "rating": "number | null" }
  ],
  "directorFilmography": [
    { "title": "string", "releaseDate": "YYYY-MM-DD | null", "rating": "number | null" }
  ],
  "castFilmography": [
    {
      "name": "string",
      "pastFilms": [
        { "title": "string", "releaseDate": "YYYY-MM-DD | null", "rating": "number | null" }
      ]
    }
  ]
}
```

`rating` is TMDB's public rating normalized to a 0–100 scale (same scale as
`audienceScore` below). `franchiseEntries` is the full list of other entries
in the film's collection (for franchise-fatigue analysis); `directorFilmography`
is the director's last 5 films; `castFilmography` covers the top 4 billed
cast members, each with their last 5 films. All four lists exclude the film
currently being evaluated — that's still only revealed via the actual-results
payload below, after the vote.

**Actual-results payload** (only revealed by the `scoring` agent, after the
vote):

```json
{
  "boxOfficeDomestic": "number | null",
  "boxOfficeWorldwide": "number | null",
  "imdbRating": "number | null",
  "audienceScore": "number | null",
  "criticScore": "number | null"
}
```

**Each committee agent** (`creative`, `finance`, `marketing`, `distribution`)
returns:

```json
{ "role": "creative", "argument": "string", "vote": "greenlight | pass" }
```

**The scoring agent** takes the committee's votes plus the actual-results
payload and returns:

```json
{ "grade": "string | number", "rationale": "string" }
```

## Agent personas

Suggested framing for each role (see `committee/agents.py` for the actual
ported system prompts):

- **Creative** — story quality, director/cast pedigree, originality vs.
  franchise fatigue, artistic risk
- **Finance** — budget vs. plausible return, comparable films' performance,
  break-even math, financial risk
- **Marketing** — audience clarity, consumer proposition, campaign/trailer
  potential, strategic fit, cultural timing
- **Distribution** — release window competition, platform strategy (theatrical
  vs. streaming), international rollout potential — *not yet built*
- **Scoring** — no opinion of its own; its job is to reveal the actual
  results and objectively grade how well the committee's reasoning and vote
  held up against reality. The grade is computed deterministically (see
  `committee/calibration.py`); only the rationale text comes from an LLM.

Every committee agent's system prompt explicitly forbids using any
post-release information (reviews, box office, audience scores) — it only
gets the pre-release payload above.

## Team & Branches

| Branch | Owner | Role | Status |
|---|---|---|---|
| `data-pipeline` | Corey | Pulls and cleans film data from TMDB/OMDb | ✅ merged |
| `creative` | Allyson | Creative agent persona | ✅ ported to `main` |
| `finance` | Olga | Finance agent persona | ✅ ported to `main` |
| `marketing` | Joe | Marketing agent persona | ✅ ported to `main` |
| `distribution` | Nic, Jenn | Distribution agent | ⬜ not started |
| `scoring` | Angel | Reveal + scoring agent | ✅ ported to `main` |

Branch work still gets merged in via PR — if you push updates to your
branch, they'll get folded into `committee/agents.py` on `main` the same
way the creative/finance/marketing/scoring branches were.

## New to GitHub or coding? Start here

If you've never used GitHub or written code before, don't read the rest of
this file first — go straight to one of these instead:

- [TEAM_SETUP_CLAUDE.md](TEAM_SETUP_CLAUDE.md) — for teams using Claude
- [TEAM_SETUP_CHATGPT.md](TEAM_SETUP_CHATGPT.md) — for the team using ChatGPT

Both walk through installing GitHub Desktop, cloning the repo, switching to
your branch, getting your API key, and pushing your work — no Terminal
required.
