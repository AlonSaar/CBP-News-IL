"""
fix_articles.py — one-time batch fix for existing articles.

Applies:
  1. Weight conversion: adds (כ-Y ק"ג) after every "X פאונד" that is missing it.
  2. Date removal: strips date phrases from the start of sentences.
  3. Hebrew grammar & phrasing check via Claude (fixes awkward phrasing, not translation).

Usage:
    python fix_articles.py                  # dry-run (print diffs, save nothing)
    python fix_articles.py --apply          # save changes to articles.json
    python fix_articles.py --apply --grammar  # also run Claude grammar pass (slow, costs API calls)
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

import config

ARTICLES_PATH = config.STATE_DIR / "articles.json"

# ── Weight conversion ─────────────────────────────────────────────────────────
# Matches: "350 פאונד" or "350.5 פאונד" (with or without comma in number)
_POUND_RE = re.compile(r'([\d,]+(?:\.\d+)?)\s*פאונד(?!\s*\()', re.UNICODE)

def _add_kg(m: re.Match) -> str:
    raw = m.group(1).replace(',', '')
    try:
        lbs = float(raw)
        kg  = round(lbs * 0.4536)
        return f'{m.group(1)} פאונד (כ-{kg} ק"ג)'
    except ValueError:
        return m.group(0)  # leave untouched if parse fails

def fix_weights(text: str) -> str:
    return _POUND_RE.sub(_add_kg, text)

# ── Date removal ──────────────────────────────────────────────────────────────
# Matches Hebrew/English date patterns at start of sentence or standalone:
# "ב-10 במרץ 2026" / "On March 10, 2026" / "ב-10.3.2026"
_MONTHS_HE = r'(?:ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)'
_DAYS_HE   = r'(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)'

_DATE_PATTERNS = [
    # "ביום רביעי, 11 במרץ 2026," or "ביום ראשון, ה-8 במרץ 2026,"
    re.compile(
        r'ביום\s+' + _DAYS_HE + r'[,،]\s+ה?-?\d{1,2}\s+ב' + _MONTHS_HE + r'\s+\d{4}[,.]?\s*',
        re.UNICODE
    ),
    # "ב-DD בחודש YYYY," at sentence start
    re.compile(
        r'ב-?\d{1,2}\s+ב' + _MONTHS_HE + r'\s+\d{4}[,.]?\s*',
        re.UNICODE
    ),
    # "ביום DD בחודש YYYY,"
    re.compile(
        r'ביום\s+\d{1,2}\s+ב' + _MONTHS_HE + r'\s+\d{4}[,.]?\s*',
        re.UNICODE
    ),
    # English date: "On March 10, 2026,"
    re.compile(
        r'On\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}[,.]?\s*',
        re.IGNORECASE
    ),
    # Numeric Hebrew date: "ב-10.3.2026"
    re.compile(r'ב-?\d{1,2}\.\d{1,2}\.\d{4}[,.]?\s*', re.UNICODE),
]

def fix_dates(text: str) -> str:
    for pat in _DATE_PATTERNS:
        text = pat.sub('', text)
    return text.strip()

# ── Claude grammar pass ───────────────────────────────────────────────────────
_GRAMMAR_SYSTEM = """You are a professional Hebrew editor. You receive the body text of a CBP seizure review written in Hebrew.
Your task: fix ONLY phrasing, grammar, and naturalness issues.
Do NOT change facts, numbers, proper names, or English terms.
Do NOT translate or restructure paragraphs.
Do NOT add or remove information.
Return ONLY the corrected Hebrew text — no explanations, no preamble."""

def grammar_fix(body: str, client) -> str:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=_GRAMMAR_SYSTEM,
        messages=[{"role": "user", "content": body}],
    )
    return resp.content[0].text.strip()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Batch-fix existing articles.")
    parser.add_argument("--apply",   action="store_true", help="Save changes (default: dry-run).")
    parser.add_argument("--grammar", action="store_true", help="Also run Claude Hebrew grammar pass.")
    args = parser.parse_args()

    arts = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    changed = 0

    client = None
    if args.grammar:
        from anthropic import Anthropic
        client = Anthropic(api_key=config.anthropic_api_key())

    for art in arts:
        original_body  = art.get("body", "")
        original_title = art.get("title", "")

        body = original_body

        # 1. Weight conversion
        body = fix_weights(body)

        # 2. Date removal
        body = fix_dates(body)

        # 3. Grammar pass (optional, expensive)
        if args.grammar and client and body.strip():
            try:
                body = grammar_fix(body, client)
            except Exception as exc:
                print(f"  ⚠ Grammar pass failed for {art.get('url','')[-50:]}: {exc}")

        if body != original_body:
            changed += 1
            url_short = art.get("url", "")[-55:]
            print(f"\n{'─'*70}")
            print(f"URL: ...{url_short}")
            if args.apply:
                art["body"] = body
                print("  ✓ Applied")
            else:
                # Show first difference
                for i, (old, new) in enumerate(zip(original_body.split('. '), body.split('. '))):
                    if old != new:
                        print(f"  OLD: {old[:120]}")
                        print(f"  NEW: {new[:120]}")
                        if i > 2:
                            print("  ... (more changes)")
                        break

    print(f"\n{'='*70}")
    if args.apply:
        tmp = ARTICLES_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(arts, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(ARTICLES_PATH)
        print(f"✓ Saved {changed} changed articles to articles.json")
        print("Next: git add state/articles.json && git commit -m 'fix: batch article corrections' && git push")
    else:
        print(f"Dry-run complete. {changed} articles would change.")
        print("Run with --apply to save changes.")

if __name__ == "__main__":
    main()
