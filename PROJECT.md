# CBP → Hebrew Translator - Project Brief

Single source of truth for this project. Claude Code should read this first when opening the repo.

---

## 1. What it does

Automates daily translation of qualifying CBP Newsroom articles into structured Hebrew reviews, organized by calendar quarter into a Google Sheet.

**Input:** https://www.cbp.gov/newsroom (press releases published daily)

**Output:** Google Sheet with quarterly tabs. Each row is one Hebrew review + editable status column.

**Qualifying article** = ALL true:
- Describes a CBP seizure of drugs, pills/tablets, plants, or animals/wildlife.
- Has a photo of the seized items or seizure context (not a generic logo or officer portrait).

---

## 2. Non-goals

Things this project will NOT do. If scope creep happens, push back against these:
- Translate non-seizure news (personnel, policy, stats).
- Build a web dashboard. Google Sheets IS the UI.
- Handle currency-only or weapon-only seizures (user scope is drugs/plants/animals).
- Multi-user editing workflows. One user, Alon.
- Support non-Hebrew outputs.

---

## 3. Output structure

One Google Sheet (workbook): **"CBP Hebrew Reviews"**

**Tabs** (auto-created when a new quarter starts):
- Q1-2026  (Jan-Mar)
- Q2-2026  (Apr-Jun)
- Q3-2026  (Jul-Sep)
- Q4-2026  (Oct-Dec)
- ... rolls forward each quarter.

**Columns** (same on every tab):

| Column | Source | Editable |
|---|---|---|
| A: Run Date | Script | No |
| B: Article Date | Parsed from CBP page | No |
| C: Source URL | CBP | No |
| D: Hebrew Title | Claude | Yes |
| E: Hebrew Location Line | Claude | Yes |
| F: Crossing Type | Claude | Yes |
| G: Hebrew Review Body | Claude | Yes |
| H: Image URL | CBP hero image | No |
| I: Status | Script / user | Yes (auto / needs-review / approved / rejected) |
| J: Editor Notes | User | Yes |
| K: Last Modified | Sheet timestamp | No |

Columns D-G are broken out (not one blob) so you can fix just the title or just the crossing-type line without retyping the whole review.

---

## 4. Quarter logic

```
Q1 = Jan, Feb, Mar
Q2 = Apr, May, Jun
Q3 = Jul, Aug, Sep
Q4 = Oct, Nov, Dec
```
Quarter key format: `Q{n}-{YYYY}` (e.g. `Q2-2026`).

Implementation lives in `quarter.py`. When the pipeline runs, it computes the current quarter for each article's **publication date** (not run date - this matters if a run covers articles from late March pushed in early April; they still go to Q1).

---

## 5. Repo layout

```
cbp-translator/
├── PROJECT.md                    # This file. Read first.
├── CLAUDE.md                     # Instructions for Claude Code.
├── SETUP.md                      # Install & onboarding for Alon.
├── README.md                     # Short public summary.
├── requirements.txt
├── .env.example                  # Template for secrets
├── .gitignore
│
├── config.py                     # Central config & env var loading
├── quarter.py                    # Quarter logic (Jan-Mar=Q1, etc.)
│
├── translate_cbp.py              # PHASE 1 - single-URL CLI (working now)
│
├── scraper.py                    # PHASE 2 - list new CBP articles
├── classifier.py                 # PHASE 2 - qualify article yes/no
├── translator.py                 # PHASE 2 - article -> Hebrew review object
├── sheets_client.py              # PHASE 2 - Google Sheets wrapper (quarter tabs)
├── dedupe.py                     # PHASE 2 - track processed URLs
├── pipeline.py                   # PHASE 2 - end-to-end daily runner
│
├── prompts/
│   ├── hebrew_rules.md           # Translation rules (edit this, not Python)
│   └── classifier.md             # Classifier prompt
│
├── state/
│   ├── processed_urls.json       # Dedupe store (URL -> quarter, timestamp)
│   └── last_run.json             # Timestamp + stats of last run
│
├── logs/                         # Run logs (gitignored content, .gitkeep tracked)
│
├── tests/
│   ├── test_quarter.py           # Quarter boundary tests
│   ├── test_dedupe.py
│   └── fixtures/
│       └── sample_article.html   # Saved CBP page for offline testing
│
└── .github/
    └── workflows/
        └── daily.yml             # PHASE 3 - GitHub Actions daily schedule
```

---

## 6. Module responsibilities

- **config.py** - loads `ANTHROPIC_API_KEY`, `GOOGLE_SHEETS_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` from env. Central place to change model name (`claude-sonnet-4-6`).
- **quarter.py** - pure date math. No I/O.
- **scraper.py** - fetches the CBP news index, returns a list of `{url, title, date, has_image}` dicts. Also has `fetch_article(url)` which returns full article text + hero image URL.
- **classifier.py** - given an article dict + the vision-capable model, returns `(qualifies: bool, reason: str)`. In Phase 2 upgrade to actually download the hero image and send it to Claude's vision API.
- **translator.py** - given an article dict, returns a structured `HebrewReview` dataclass (title, location, crossing_type, body). Loads rules from `prompts/hebrew_rules.md`.
- **sheets_client.py** - wraps gspread. Key methods: `ensure_quarter_tab(quarter_key)`, `append_review(quarter_key, review, source_meta)`, `url_exists(url)` (for cross-tab dedupe).
- **dedupe.py** - thin JSON store. Before adding a URL to the sheet, check if we've seen it.
- **pipeline.py** - the orchestrator. Pseudocode:
  ```
  articles = scraper.list_new()
  for a in articles:
      if dedupe.seen(a.url): continue
      qualifies, reason = classifier.classify(a)
      if not qualifies: 
          dedupe.mark(a.url, status='skipped', reason=reason)
          continue
      review = translator.translate(a)
      quarter = quarter_for(a.article_date)
      sheets_client.append_review(quarter, review, a)
      dedupe.mark(a.url, status='added', quarter=quarter)
  ```

---

## 7. Phased delivery

**Phase 1 - Single URL CLI (DONE)**
- `translate_cbp.py <url>` fetches, classifies (text-only), translates, prints.
- Purpose: prove the Hebrew template works before adding complexity.
- Gate to Phase 2: run on 10 articles, output quality is consistent.

**Phase 2 - Batch + Google Sheets (~1 day of work)**
- Build scraper, sheets_client, dedupe, pipeline.
- Add Google Service Account auth.
- Quarter tabs auto-created.
- Still manually triggered: `python pipeline.py`.
- Gate to Phase 3: ran manually for 1 week, output stable.

**Phase 3 - Daily automation (~2 hours)**
- GitHub Actions workflow runs `pipeline.py` once a day at 08:00 UTC.
- Secrets stored in GitHub Secrets (API key, service account JSON).
- Private repo.

**Phase 4 - OPTIONAL, only if Phase 3 pain demands it**
- Vision API for real image classification (vs. current text-only inference about images).
- Email/Slack notification when new rows are added.
- Auto-correction retry when output fails the template regex check.

---

## 8. Hebrew translation rules

Canonical copy lives in `prompts/hebrew_rules.md`. That file is the spec - edit it to tune the output. All translator code reads from it, no duplication.

Short version of the rules (full detail in the prompt file):
- Output in Hebrew only, English inline for proper names.
- 4-block structure: Title / Location line / `סוג מעבר:` line / one paragraph.
- Paragraph must specify: what was inspected, inspection type, what was found, where concealed, weight/value/origin, arrests, receiving agency.
- Replace "X-ray" with "screening" (סריקה).
- Standard crossing-type wording for 5 cases (land MX-US, sea, air, air cargo, air cargo + express mail).
- Do not invent facts. If a detail is absent from the source, omit it.

---

## 9. Cost & scale estimates

- CBP publishes ~5-15 press releases/day, ~1-3 qualify.
- Per qualifying article: 1 classifier call (~500 tokens) + 1 translation call (~3000 tokens).
- Claude Sonnet 4.6 pricing: ~$0.05-0.15 per qualifying article.
- Monthly cost at 3/day × 30 days: under $15.
- Annual rows: ~1,000. Fits comfortably in 4 quarterly tabs.

---

## 10. Failure modes to handle

- **CBP HTML changes** - scraper selectors break. Mitigation: log HTML snapshot on parse failure, fall back to `og:` meta tags.
- **Rate limit from Anthropic** - pipeline retries with exponential backoff, max 3 attempts.
- **Google Sheets quota** - batched writes, one append call per article.
- **Duplicate URLs** - dedupe check before every write, plus Sheet has unique-URL constraint via `url_exists`.
- **Classifier false positives** - Status column defaults to `needs-review` for first month, flip to `auto` once trusted.

---

## 11. Hand-off to Claude Code

When Alon runs `claude` inside this folder, Claude Code should:
1. Read `PROJECT.md` (this file) and `CLAUDE.md`.
2. Check what phase is complete via presence of the Phase 2/3 modules.
3. Ask Alon which phase to work on next.
4. Never modify `prompts/hebrew_rules.md` without explicit user confirmation - that's Alon's editorial spec.
