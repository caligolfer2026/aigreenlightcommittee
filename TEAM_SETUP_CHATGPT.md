# Team Setup Guide — ChatGPT / OpenAI Team

This is for the team using ChatGPT instead of Claude. (If your team is
using Claude, use [TEAM_SETUP_CLAUDE.md](TEAM_SETUP_CLAUDE.md) instead.)

This guide covers getting GitHub set up and getting your OpenAI API key
connected. If you get stuck on any step, ask Corey.

See the main [README.md](README.md) for the overall project concept and
the data contract every agent has to follow.

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
2. Pick your team's branch from the list

## Part 3 — Get an OpenAI API key

1. Go to https://platform.openai.com and sign up (or log in)
2. Click **API Keys** in the left sidebar
3. Click **Create new secret key**, give it any name, copy the key it
   shows you (you won't be able to see it again after you close the
   window, so copy it somewhere safe right away)

Note: OpenAI API usage isn't covered by a free ChatGPT Plus subscription —
you may need to add a small amount of billing credit (a few dollars) to
your OpenAI account at https://platform.openai.com/settings/organization/billing
to actually make API calls.

Keep this key private — don't share it, don't post it anywhere, don't put
it in a file that gets pushed to GitHub (see Part 4).

## Part 4 — Save your key safely

1. Open **Finder**, go to the cloned repo folder, then into your team's
   folder
2. Right-click inside → **New Document → New Text File** (or open TextEdit
   and save a new file there)
3. Name it exactly: `.env.local`
4. Type one line inside it:
   ```
   OPENAI_API_KEY=pasteyourkeyhere
   ```
5. Save it

This file is set up to be ignored by GitHub on purpose — your key should
never get pushed or shared. If you ever see `.env.local` show up as a
change in GitHub Desktop, do not include it in a commit.

## Part 5 — Save and share your work

Once you have files to add (from building your agent), do this all inside
GitHub Desktop, no Terminal needed:

1. Your new files will show up automatically in the left sidebar under
   "Changes" — **but not `.env.local`**, since that has your secret key.
   If `.env.local` shows up in that list, leave its checkbox unchecked.
2. In the bottom left, type a short summary of what you changed, then
   click **Commit to [your branch name]**
3. Click **Push origin** (top right)
4. Go to github.com, you'll see a banner "Compare & pull request" — click
   it, then **Create pull request**

Someone else on the team should review your pull request before it gets
merged into `main`.
