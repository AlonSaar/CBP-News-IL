# CBP → Hebrew Translator - Setup Guide

## What you're building

An automation that:
1. Pulls articles from cbp.gov/newsroom
2. Keeps only those with (a) a seizure photo and (b) drugs/plants/animals content
3. Translates to Hebrew using your strict template
4. Writes the result to Google Sheets for review/edit

Built in 3 phases so you can verify each step before layering complexity.

---

## Phase 0 - Install the tools (one-time, ~30 min)

### 1. Install Python
- Windows: download from python.org, check "Add Python to PATH" during install.
- macOS: `brew install python` (install Homebrew first from brew.sh).
- Verify: open a terminal and run `python --version`. Should print 3.10 or higher.

### 2. Install Node.js (needed for Claude Code)
- Download LTS from nodejs.org.
- Verify: `node --version` prints v20+.

### 3. Install Claude Code
```
npm install -g @anthropic-ai/claude-code
```
- Verify: `claude --version`.
- To use it: `cd` into your project folder and run `claude`. You chat with it in the terminal, and it can read, write, and run code in that folder.

### 4. Get an Anthropic API key
- Go to console.anthropic.com → API keys → create key.
- Copy it. Starts with `sk-ant-...`.
- Add $5-10 credit to your account to start. This project will cost pennies per day once running.

### 5. Set the API key as an environment variable
- **macOS/Linux** (add to `~/.zshrc` or `~/.bashrc`):
  ```
  export ANTHROPIC_API_KEY="sk-ant-..."
  ```
  Then run `source ~/.zshrc`.
- **Windows** (PowerShell, one-time for the session):
  ```
  $env:ANTHROPIC_API_KEY="sk-ant-..."
  ```
  For permanent: System Properties → Environment Variables.

### 6. Install project dependencies
From inside this folder, run:
```
pip install -r requirements.txt
```

---

## Phase 1 - Manual translator (what you have now)

Test the core logic on a single known article:
```
python translate_cbp.py https://www.cbp.gov/newsroom/local-media-release/<some-article-slug>
```

What it does:
- Fetches the article HTML.
- Extracts title, body text, and hero image URL.
- Asks Claude to classify whether it's a qualifying seizure article with a real seizure image.
- If yes, translates to Hebrew following your strict template.
- Prints the result to the terminal.

**Your job at this phase:** run it on 5-10 different CBP articles. Some should qualify, some shouldn't. Verify:
- The classifier correctly rejects non-seizure articles (personnel news, policy updates).
- The Hebrew output matches your template exactly.
- Iterate on the `HEBREW_RULES` constant in the script until the output is consistent.

Do NOT move to Phase 2 until Phase 1 output is reliable. Garbage in, garbage out.

---

## Phase 2 - Batch mode + Google Sheets (next step)

Once Phase 1 is solid, we add:
- A scraper that lists all new articles from the CBP news index.
- A dedup store (simple JSON file) so we don't re-translate articles.
- Google Sheets output with columns: Date | Source URL | Hebrew Title | Hebrew Review | Image URL | Status (auto/needs-review) | Your Edits.

Google Sheets setup (~15 min):
1. Create a Google Cloud project.
2. Enable the Sheets API.
3. Create a service account, download the JSON key.
4. Share your target sheet with the service account email.
5. Install `gspread`: `pip install gspread`.

I'll write that code when you're ready for Phase 2.

---

## Phase 3 - Daily automation via GitHub Actions

Once Phase 2 runs reliably on your machine:
1. Push this project to a **private** GitHub repo (private because your API key and service account JSON live in GitHub Secrets, not in code).
2. Add a `.github/workflows/daily.yml` that runs the script every morning.
3. GitHub Actions has 2,000 free minutes/month. This job uses maybe 30 seconds/day.

I'll write the workflow file when you're ready.

---

## How to use Claude Code for this project

Once Claude Code is installed, from inside this project folder run:
```
claude
```
Then you can say things like:
- "Run translate_cbp.py against this URL and tell me if the Hebrew output matches the template."
- "The crossing type wording is wrong for air cargo. Fix the prompt and re-run."
- "Write the Phase 2 scraper."

Claude Code will read your files, edit them, and run the scripts directly. Much faster loop than copy/pasting code between a chat and your editor.

---

## Common pitfalls - read this before you start

- **CBP HTML changes.** If the scraper breaks, it's almost always because they changed a CSS class. The `fetch_article` function has a fallback but you may need to tune selectors.
- **Translation drift.** LLMs drift from strict templates over many calls. Keep `max_tokens` tight, review outputs weekly, and treat the Hebrew output as a draft - always give yourself an edit column in the sheet.
- **Image classification costs more than text.** The vision call per article costs ~5x a text call. Filter out articles by title/body first (no photo → skip), only use vision as the final gate.
- **Don't scrape aggressively.** One run/day, respect robots.txt. CBP is a US government site, so public scraping is legal, but hammering the server is rude and will get you IP-blocked.
