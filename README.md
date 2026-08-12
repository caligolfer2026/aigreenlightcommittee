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
office numbers and audience/critic response — and grades the committee on how
well their pre-release judgment matched reality.

Data comes from TMDB and IMDB (via a data-pipeline module, since there's no
free official IMDB API — OMDb is the usual proxy for IMDB ratings).

## Team & Branches

| Branch | Owner | Role |
|---|---|---|
| `data-pipeline` | Corey | Pulls and cleans film data from TMDB/IMDB |
| `creative` | Allyson | Creative agent |
| `finance` | Olga | Finance agent |
| `marketing` | Joe | Marketing agent |
| `distribution` | Nic, Jenn | Distribution agent |
| `scoring` | Angel | Reveal + scoring agent |

Each person should work primarily on their own branch and open a PR into
`main` when ready.

## New to GitHub or coding? Start here

If you've never used GitHub or written code before, don't read the rest of
this file first — go straight to one of these instead:

- [TEAM_SETUP_CLAUDE.md](TEAM_SETUP_CLAUDE.md) — for teams using Claude
- [TEAM_SETUP_CHATGPT.md](TEAM_SETUP_CHATGPT.md) — for the team using ChatGPT

Both walk through installing GitHub Desktop, cloning the repo, switching to
your branch, getting your API key, and pushing your work — no Terminal
required.

## How the pieces fit together

```
            ┌────────────────┐
            │  data-pipeline │  fetches TMDB/IMDB data, splits it into:
            └───────┬────────┘   - PRE-release payload (for the debate)
                    │            - ACTUAL-results payload (for scoring)
                    ▼
   ┌───────────┬───────────┬───────────┬──────────────┐
   │ creative  │  finance  │ marketing │ distribution │   each agent reads the
   └─────┬─────┴─────┬─────┴─────┬─────┴──────┬───────┘   PRE-release payload
         └───────────┴───────────┴────────────┘            only, and outputs:
                          │                                 { argument, vote }
                          ▼
                   committee transcript + votes
                          │
                          ▼
                 ┌─────────────────┐
                 │     scoring      │  reveals the ACTUAL-results payload,
                 └─────────────────┘  compares it to the committee's votes,
                                       and produces a grade + rationale
```

`main` is the integration branch. Nobody pushes directly to `main` — every
branch merges in via a reviewed pull request.

## Data contract (agree on this before writing agent code)

So the branches can be built independently and still plug together cleanly,
every agent should be written against these two shapes:

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
should expose one function that takes the pre-release payload (and optionally
the other agents' arguments, if you want cross-talk) and returns:

```json
{ "role": "creative", "argument": "string", "vote": "greenlight | pass" }
```

**The scoring agent** takes the committee's transcript + votes plus the
actual-results payload and returns:

```json
{ "grade": "string | number", "rationale": "string" }
```

## Getting started on your branch

1. `git checkout <your-branch>` (e.g. `git checkout creative`)
2. `git pull origin <your-branch>` to make sure you're up to date
3. `git pull origin main` (or rebase) periodically so you're not building on
   stale code
4. Build your piece against the data contract above so it can be swapped into
   the full app without changes to anyone else's code
5. Commit and push to your branch, then open a PR into `main` for review —
   don't merge your own PR without at least one reviewer

## Agents

Every agent is an LLM API call with a distinct system prompt that locks it
into its one perspective. Most branches use Claude; one team is using
ChatGPT instead — that's fine, the API/provider doesn't matter as long as
every agent's input and output match the data contract above. See
[TEAM_SETUP_CLAUDE.md](TEAM_SETUP_CLAUDE.md) or
[TEAM_SETUP_CHATGPT.md](TEAM_SETUP_CHATGPT.md) depending on which one your
team is using. Suggested framing for each agent:

- **Creative** — story quality, director/cast pedigree, originality vs.
  franchise fatigue, artistic risk
- **Finance** — budget vs. plausible return, comparable films' performance,
  break-even math, financial risk
- **Marketing** — audience appeal, positioning, trailer-ability, cultural
  moment/timing
- **Distribution** — release window competition, platform strategy (theatrical
  vs. streaming), international rollout potential
- **Scoring** — no opinion of its own; its job is to reveal the actual
  results and objectively grade how well the committee's reasoning and vote
  held up against reality

Each committee agent's system prompt should explicitly forbid it from using
any post-release information (reviews, box office, audience scores) — it only
gets the pre-release payload above.

## Environment variables

`data-pipeline` is already built (see `data-pipeline/README.md`) and only
needs:

- `TMDB_API_KEY` — film metadata
- `OMDB_API_KEY` — IMDb rating / box office data (OMDb wraps IMDB data; there's
  no free official IMDB API)

Each agent branch needs its own key for whichever LLM it calls:

- `ANTHROPIC_API_KEY` — for branches using Claude
- `OPENAI_API_KEY` — for branches using ChatGPT

Never commit real API keys — every branch keeps its keys in its own
`.env.local` (gitignored), never in a file that gets pushed to GitHub.
