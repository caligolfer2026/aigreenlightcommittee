# Team Setup Guide — Claude / Anthropic Teams (No Coding Required)

This is for the **creative**, **finance**, **marketing**, **distribution**,
and **scoring** teams using Claude. (If your team is using ChatGPT instead,
use [TEAM_SETUP_CHATGPT.md](TEAM_SETUP_CHATGPT.md) instead.)

This guide is written for people who have never used GitHub or written
code before. If you get stuck on any step, ask Corey.

See the main [README.md](README.md) first for the overall project concept
and the data contract every agent has to follow.

## Best setup for each team

Each team works only inside their own folder, named after their branch
(`creative/`, `finance/`, `marketing/`, `distribution/`, or `scoring/`) —
same pattern as the existing `data-pipeline/` folder. Since you don't need
to write code, **you'll ask Claude to write the code for you**, using a
prompt template below — then just run it. Nobody edits real code by hand
except to paste in a couple of things.

---

## Part 1 — One-time setup (do this once per person)

1. Go to https://desktop.github.com and click **Download for macOS** (or
   Windows). Install it, then open it.
2. Sign in with a GitHub account (make one at github.com if you don't have
   one — it's free, just needs an email and password).
3. In GitHub Desktop, click **File → Clone Repository**
4. Click the **URL** tab, paste this in:
   `https://github.com/caligolfer2026/aigreenlightcommittee`
5. Pick any folder on your computer, click **Clone**

## Part 2 — Switch to your team's branch

1. At the top of GitHub Desktop there's a button that says **Current
   Branch**. Click it.
2. Pick your team's branch from the list (`creative`, `finance`,
   `marketing`, `distribution`, or `scoring`)

## Part 3 — Get a Claude API key

1. Go to https://console.anthropic.com and sign up (or log in)
2. Click **API Keys** in the left sidebar
3. Click **Create Key**, give it any name, copy the key it shows you

Keep this key private — don't share it, don't post it anywhere, don't put
it in a file that gets pushed to GitHub (see Part 4).

## Part 4 — Save your key safely

1. Open **Finder**, go to the cloned repo folder, then into your team's
   folder (e.g. `creative`)
2. Right-click inside → **New Document → New Text File** (or open TextEdit
   and save a new file there)
3. Name it exactly: `.env.local`
4. Type one line inside it:
   ```
   ANTHROPIC_API_KEY=pasteyourkeyhere
   ```
5. Save it

This file is set up to be ignored by GitHub on purpose — your key should
never get pushed or shared. If you ever see `.env.local` show up as a
change in GitHub Desktop, do not include it in a commit.

## Part 5 — Get your agent written (no coding — Claude writes it)

1. Fill out your agent's "personality worksheet" first:
   - What does your character care about? (e.g. Finance cares about budget
     vs. plausible return, not whether the story is good)
   - What's their tone/personality? (skeptical? bullish? risk-averse?)
   - What are they NOT allowed to know? (only pre-release info — title,
     genre, director, cast, budget, release date, similar films. Never
     reviews, ratings, or box office — that's cheating.)
   - What does a "yes" (greenlight) look like for them vs. a "no" (pass)?
     Give 1-2 concrete example reasons for each.

   (The `scoring` team's worksheet is different — see the note at the
   bottom of this doc.)

2. Open https://claude.ai in a browser
3. Paste this prompt, filling in the `[bracketed]` parts with your
   worksheet answers:

   ```
   Write a single Python file called agent.py that does the following:

   1. Reads an API key from a file called .env.local in the same folder
      (format: ANTHROPIC_API_KEY=xxxx, one line, no quotes)
   2. Reads a movie's pre-release info from a JSON file passed as a
      command-line argument, e.g.: python3 agent.py movie.json
      The JSON has this shape:
      {
        "title": "string", "releaseDate": "string", "genres": ["string"],
        "director": "string", "cast": ["string"], "studio": "string",
        "budget": number or null, "logline": "string",
        "franchise": "string or null", "comparableFilms": ["string"]
      }
   3. Sends that info to Claude (model "claude-sonnet-5") using the
      anthropic Python package, with this system prompt, so the agent
      argues from one specific point of view:

      "[paste your worksheet content here — what this character cares
      about, their tone, and 2-3 example reasons for greenlight vs pass]"

   4. Prints the result as JSON in exactly this shape:
      {"role": "[creative/finance/marketing/distribution]",
       "argument": "one paragraph of reasoning",
       "vote": "greenlight" or "pass"}

   Keep it simple, no error handling beyond the basics.
   ```

4. Claude will output a code file. Copy the whole thing.
5. Back in Finder, in your team folder, create a new text file named
   `agent.py`, paste the code in, and save it.

## Part 6 — Test it

This is the one step that needs Terminal — but it's just copy-paste, no
editing:

1. Get one of the sample movie JSON files from the `shared-data/` folder in
   the repo (ask Corey if it's not there yet)
2. Open Terminal (Cmd+Space, type "Terminal", press Enter), then paste:
   ```bash
   cd ~/path/to/aigreenlightcommittee/creative
   pip3 install anthropic
   python3 agent.py barbie.json
   ```
   (swap `creative` for your team's folder name)
3. If it prints back JSON with an argument and a vote, it worked.

## Part 7 — Save and share your work

All inside GitHub Desktop, no Terminal needed:

1. Your new files (`agent.py`) will show up automatically in the left
   sidebar under "Changes" — **but not `.env.local`**, since that has your
   secret key. If `.env.local` shows up in that list, leave its checkbox
   unchecked.
2. In the bottom left, type a short summary like "Add creative agent",
   then click **Commit to [your branch name]**
3. Click **Push origin** (top right)
4. Go to github.com, you'll see a banner "Compare & pull request" — click
   it, then **Create pull request**

Someone else on the team should review your pull request before it gets
merged into `main`.

---

## Note for the `scoring` team

Your worksheet is different, since your agent doesn't have an opinion of
its own — it grades the other four:

- What counts as the committee "getting it right"? (e.g. they greenlit it
  and it made money / passed and it flopped = good call; greenlit a flop =
  bad call)
- Should reasoning matter, or just the vote outcome? (e.g. right vote for
  the wrong reason — does that count?)
- What does the output look like — a letter grade? a number? a paragraph
  of verdict?

Your agent takes the other four agents' arguments and votes, plus the
**actual-results payload** (box office, IMDb rating, audience/critic
score — see the data contract in the main README), and produces a grade
plus a rationale.
