# CBP → Hebrew Translator

Daily automation that translates qualifying CBP Newsroom seizure articles into structured Hebrew reviews and writes them to a Google Sheet organized by calendar quarter.

## Docs

- `PROJECT.md` - full project brief. **Read this first.**
- `SETUP.md` - install and onboarding instructions.
- `CLAUDE.md` - instructions for Claude Code when working in this repo.
- `prompts/hebrew_rules.md` - the Hebrew translation rules (editorial spec).

## Quick start (after Phase 0 setup)

```bash
# Copy env template and fill in your API key
cp .env.example .env

# Install deps
pip install -r requirements.txt

# Phase 1 - translate a single article
python translate_cbp.py https://www.cbp.gov/newsroom/local-media-release/<slug>
```

## Phase status

- Phase 1 - Single URL CLI translator - **done**
- Phase 2 - Scraper + Google Sheets with quarterly tabs - not started
- Phase 3 - GitHub Actions daily scheduler - not started

## Quarter convention

- Q1 = Jan-Mar
- Q2 = Apr-Jun
- Q3 = Jul-Sep
- Q4 = Oct-Dec

Key format: `Q{n}-{YYYY}` (e.g. `Q2-2026`).
