# Instructions for Claude Code

You are working in the `cbp-translator` repo. Read `PROJECT.md` before making any non-trivial change - it is the single source of truth.

## Ground rules

1. **Do not modify `prompts/hebrew_rules.md` without explicit user confirmation.** This file is Alon's editorial spec. If translation output is wrong, first try fixing the rendering code, not the rules. Only edit the rules when Alon specifically says to.

2. **Phase discipline.** Work one phase at a time. Do not jump ahead. Phases defined in `PROJECT.md` section 7. Before starting a phase, confirm the previous phase's gate was passed.

3. **No invented facts in Hebrew output.** The translator must never hallucinate weights, values, or concealment locations that aren't in the source article. If tests catch hallucination, fix the prompt, not the test.

4. **Quarter keys are `Q{n}-{YYYY}`** (e.g. `Q2-2026`). Use `quarter.py` - do not reinvent this anywhere else.

5. **Secrets never in code.** Only via env vars loaded through `config.py`. `.env` is gitignored.

6. **Tests before commit.** Run `pytest tests/` before telling Alon a feature is done. Quarter boundary tests (Dec 31 vs Jan 1, Mar 31 vs Apr 1) are non-negotiable.

## When Alon opens this repo

Ask Alon which of these they want to do:
- "Run Phase 1 translator on a URL" - use `translate_cbp.py`.
- "Build Phase 2 (scraper + Sheets)" - create the Phase 2 modules per `PROJECT.md` section 6.
- "Set up Phase 3 (daily automation)" - scaffold `.github/workflows/daily.yml`.
- "Edit the Hebrew rules" - open `prompts/hebrew_rules.md` and confirm each change.
- "Fix a failing translation" - inspect the last run's log, find the source URL, reproduce with `translate_cbp.py`, diagnose.

## Conventions

- Python 3.10+. Type hints on all public functions.
- Use `dataclasses` for structured data (e.g. `HebrewReview`, `Article`).
- Use `logging` module, not `print`, in Phase 2+ code. Log level INFO by default, DEBUG via `--verbose`.
- Google Sheets writes are always batched per article (one append call), never per cell.
- Dedupe check happens BEFORE the classifier call to save API cost.

## How to test without hitting live CBP

Use `tests/fixtures/sample_article.html` for offline parser tests. When adding new fixtures, save the raw HTML with `curl -o tests/fixtures/<slug>.html <url>`.
