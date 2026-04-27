"""
CBP Translator - Phase 2 pipeline orchestrator.

Runs the full daily batch:
    1. Scrape CBP news index for recent articles.
    2. Skip URLs already in the dedupe store.
    3. Classify each article.
    4. Translate qualifying articles to Hebrew.
    5. Save to state/articles.json (persistent store).
    6. Regenerate output/cbp_hebrew_reviews.html and .docx.

Usage:
    python pipeline.py
    python pipeline.py --verbose
    python pipeline.py --dry-run       # classify + translate, do NOT save/write outputs
    python pipeline.py --limit 5       # stop after 5 qualifying articles
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from anthropic import Anthropic, RateLimitError, APIStatusError

import config
import dedupe
import html_writer
import pptx_writer
from quarter import quarter_key
from scraper import Article, fetch_article, list_new
from classifier import classify
from translator import translate

logger = logging.getLogger(__name__)

ARTICLES_PATH = config.STATE_DIR / "articles.json"
APPROVED_URLS_PATH = config.APPROVED_URLS_PATH


# ---------------------------------------------------------------------------
# Articles store (persistent JSON)
# ---------------------------------------------------------------------------

def _load_approved_urls() -> set:
    """Load the set of admin-approved article URLs."""
    if not APPROVED_URLS_PATH.exists():
        return set()
    try:
        return set(json.loads(APPROVED_URLS_PATH.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _update_article_approvals(articles: list[dict], approved_urls: set) -> list[dict]:
    """
    Set admin_approved on each article based on approved_urls.
    Articles missing the field default to True (backward compat for old data).
    """
    for art in articles:
        if "admin_approved" not in art:
            art["admin_approved"] = True  # existing articles stay visible
        else:
            art["admin_approved"] = art["url"] in approved_urls
    return articles


def _load_articles() -> list[dict]:
    if not ARTICLES_PATH.exists():
        return []
    try:
        arts = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load articles store: %s", exc)
        return []
    # Auto-deduplicate by URL on every load (keeps first/newest occurrence)
    seen: set[str] = set()
    unique: list[dict] = []
    for a in arts:
        u = a.get("url", "")
        if u not in seen:
            seen.add(u)
            unique.append(a)
    if len(unique) < len(arts):
        logger.warning("Auto-removed %d duplicate articles on load", len(arts) - len(unique))
    return unique


def _save_articles(articles: list[dict]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ARTICLES_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ARTICLES_PATH)


def _article_to_dict(
    article: Article,
    title: str,
    location: str,
    crossing_type: str,
    body: str,
    quarter: str,
    run_date: str,
    status: str = "needs-review",
) -> dict:
    return {
        "run_date": run_date,
        "article_date": article.article_date.isoformat(),
        "url": article.url,
        "title": title,
        "location": location,
        "crossing_type": crossing_type,
        "body": body,
        "image_url": article.image_url or "",
        "image_urls": article.image_urls or ([article.image_url] if article.image_url else []),
        "quarter": quarter,
        "status": status,
        "admin_approved": False,  # new articles require admin approval before going live
        "editor_notes": "",
    }


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def _with_retry(fn, *args, max_attempts: int = 3, base_delay: float = 5.0, **kwargs):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except RateLimitError:
            if attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("Rate limit hit (attempt %d/%d). Retrying in %.0fs...", attempt, max_attempts, delay)
            time.sleep(delay)
        except APIStatusError as exc:
            if attempt == max_attempts or exc.status_code < 500:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("API error %d (attempt %d/%d). Retrying in %.0fs...", exc.status_code, attempt, max_attempts, delay)
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class RunStats:
    def __init__(self) -> None:
        self.total_fetched: int = 0
        self.skipped_dedupe: int = 0
        self.skipped_classifier: int = 0
        self.translated: int = 0
        self.errors: int = 0
        self.start_time = datetime.now(tz=timezone.utc)

    def summary(self) -> str:
        elapsed = (datetime.now(tz=timezone.utc) - self.start_time).seconds
        return (
            f"Run complete in {elapsed}s | "
            f"fetched={self.total_fetched} "
            f"dedupe_skip={self.skipped_dedupe} "
            f"classifier_skip={self.skipped_classifier} "
            f"translated={self.translated} "
            f"errors={self.errors}"
        )

    def to_dict(self) -> dict:
        return {
            "run_date": self.start_time.isoformat(timespec="seconds"),
            "total_fetched": self.total_fetched,
            "skipped_dedupe": self.skipped_dedupe,
            "skipped_classifier": self.skipped_classifier,
            "translated": self.translated,
            "errors": self.errors,
        }


def _save_last_run(stats: RunStats) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        config.LAST_RUN_PATH.write_text(
            json.dumps(stats.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not save last_run.json: %s", exc)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _parse_month(month_str: str):
    """Parse 'YYYY-MM' into (since_date, until_date) tuple."""
    from datetime import date
    import calendar
    try:
        year, mon = int(month_str[:4]), int(month_str[5:7])
    except (ValueError, IndexError):
        raise ValueError(f"Invalid --month format '{month_str}'. Use YYYY-MM, e.g. 2026-04")
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


def run(
    dry_run: bool = False,
    limit: int | None = None,
    month: str | None = None,
    last_week: bool = False,
    since_date: "date | None" = None,
    until_date: "date | None" = None,
    reprocess: bool = False,
    use_sitemap: bool = False,
) -> RunStats:
    from datetime import timedelta
    api_key = config.anthropic_api_key()
    client = Anthropic(api_key=api_key)
    stats = RunStats()
    run_date = stats.start_time.strftime("%Y-%m-%d %H:%M UTC")

    # Resolve date window
    since: "date | None" = None
    until: "date | None" = None
    if last_week:
        until = date.today() - timedelta(days=1)          # yesterday
        since = until - timedelta(days=6)                 # 7 days back
        logger.info("Last-week filter: %s → %s", since, until)
    elif month:
        since, until = _parse_month(month)
        logger.info("Month filter: %s → %s", since, until)
    elif since_date or until_date:
        since, until = since_date, until_date
        logger.info("Date filter: %s → %s", since, until)

    # Load existing articles store
    all_articles = _load_articles()
    existing_urls: set[str] = {a.get("url", "") for a in all_articles}
    new_articles: list[dict] = []

    logger.info("=== Pipeline start | existing articles: %d ===", len(all_articles))

    # Step 1: Scrape index.
    # Use the XML sitemap only when:
    #   (a) explicitly requested via --use-sitemap, OR
    #   (b) the date range is historical (since > 30 days ago) — CBP's index
    #       pagination beyond page 0 is JS-rendered, making deep scans unreliable.
    # For recent scans (last-week / current month) page 0 of the index is sufficient
    # and far more efficient than fetching the full sitemap (~1,360 URLs).
    _auto_sitemap = False
    if not use_sitemap and since is not None:
        _auto_sitemap = (date.today() - since).days > 30
    articles = list_new(since=since, until=until, use_sitemap=use_sitemap or _auto_sitemap)
    stats.total_fetched = len(articles)

    for article in articles:
        if limit is not None and stats.translated >= limit:
            logger.info("Hit --limit %d. Stopping.", limit)
            break

        url = article.url

        # Step 2: Dedupe check (skip if --reprocess is set)
        if not reprocess and dedupe.seen(url):
            logger.info("SKIP (dedupe store): %s", url)
            stats.skipped_dedupe += 1
            continue

        # Belt-and-suspenders: also skip if URL already in articles.json
        if url in existing_urls:
            logger.info("SKIP (already in articles.json): %s", url)
            if not dry_run:
                dedupe.mark(url, "skipped", reason="already in articles.json")
            stats.skipped_dedupe += 1
            continue

        # Step 3: Fetch full article
        try:
            article = fetch_article(url)
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            dedupe.mark(url, "error", reason=f"fetch failed: {exc}")
            stats.errors += 1
            continue

        # Step 3b: Date-window check using the article's confirmed date.
        # The index scraper may not have found the date; fetch_article() always does.
        if since and article.article_date < since:
            logger.info("SKIP (before window %s): %s | %s", since, url, article.article_date)
            if not dry_run:
                dedupe.mark(url, "skipped", reason=f"date {article.article_date} before {since}")
            stats.skipped_classifier += 1
            continue
        if until and article.article_date > until:
            logger.info("SKIP (after window %s): %s | %s", until, url, article.article_date)
            if not dry_run:
                dedupe.mark(url, "skipped", reason=f"date {article.article_date} after {until}")
            stats.skipped_classifier += 1
            continue

        # Step 4: Classify
        try:
            qualifies, reason = _with_retry(classify, article, client)
        except Exception as exc:
            logger.error("Classifier failed for %s: %s", url, exc)
            dedupe.mark(url, "error", reason=f"classify failed: {exc}")
            stats.errors += 1
            continue

        if not qualifies:
            logger.info("SKIP (classifier): %s | %s", url, reason)
            if not dry_run:
                dedupe.mark(url, "skipped", reason=reason)
            stats.skipped_classifier += 1
            continue

        # Step 5: Translate
        try:
            review = _with_retry(translate, article, client)
        except Exception as exc:
            logger.error("Translation failed for %s: %s", url, exc)
            dedupe.mark(url, "error", reason=f"translate failed: {exc}")
            stats.errors += 1
            continue

        # Step 6: Quarter
        qkey = quarter_key(article.article_date)

        art_dict = _article_to_dict(
            article=article,
            title=review.title,
            location=review.location,
            crossing_type=review.crossing_type,
            body=review.body,
            quarter=qkey,
            run_date=run_date,
        )

        if dry_run:
            logger.info("[DRY RUN] Would save to %s:", qkey)
            print("\n" + "=" * 70)
            print(review.as_text())
            print("=" * 70)
        else:
            new_articles.append(art_dict)
            dedupe.mark(url, "added", quarter=qkey)
            logger.info("SAVED: %s -> %s | %s", url, qkey, review.title[:60])

        stats.translated += 1

    # Step 7: Persist + regenerate outputs
    approved_urls = _load_approved_urls()

    if not dry_run and new_articles:
        all_articles = new_articles + all_articles  # newest first
        all_articles = _update_article_approvals(all_articles, approved_urls)
        _save_articles(all_articles)
        logger.info("Saved %d new articles. Total: %d", len(new_articles), len(all_articles))
    elif not dry_run:
        all_articles = _update_article_approvals(all_articles, approved_urls)
        logger.info("No new articles this run.")

    if not dry_run:
        logger.info("Generating HTML digest...")
        html_path = html_writer.generate(all_articles)
        print(f"\n✓ Website:       {html_path}")

        logger.info("Generating PowerPoint...")
        try:
            pptx_path = pptx_writer.generate(all_articles)
            print(f"✓ PowerPoint:    {pptx_path}")
        except Exception as exc:
            logger.warning("Skipping PowerPoint: %s", exc)

    logger.info(stats.summary())
    _save_last_run(stats)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stdout,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def regenerate_html_only() -> int:
    """Load existing articles, sync approvals, regenerate HTML. No scraping or translation."""
    all_articles = _load_articles()
    approved_urls = _load_approved_urls()
    all_articles = _update_article_approvals(all_articles, approved_urls)
    _save_articles(all_articles)
    html_path = html_writer.generate(all_articles)
    print(f"\n✓ HTML regenerated: {html_path} ({len(all_articles)} articles)")
    try:
        pptx_path = pptx_writer.generate(all_articles)
        print(f"✓ PowerPoint:       {pptx_path}")
    except Exception as exc:
        logger.warning("Skipping PowerPoint: %s", exc)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CBP → Hebrew translator pipeline.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging.")
    parser.add_argument("--dry-run", action="store_true", help="Classify + translate but do NOT save outputs.")
    parser.add_argument("--limit", type=int, default=None, metavar="N", help="Stop after N qualifying articles.")
    parser.add_argument("--month", type=str, default=None, metavar="YYYY-MM",
                        help="Scan all articles from a specific month, e.g. 2026-04.")
    parser.add_argument("--last-week", action="store_true",
                        help="Scan articles from the previous 7 days. Used by the weekly automation.")
    parser.add_argument("--since", type=str, default=None, metavar="YYYY-MM-DD",
                        help="Start date (inclusive), e.g. 2026-04-01.")
    parser.add_argument("--until", type=str, default=None, metavar="YYYY-MM-DD",
                        help="End date (inclusive), e.g. 2026-04-07.")
    parser.add_argument("--reprocess", action="store_true",
                        help="Ignore the dedupe store and re-translate already-seen URLs.")
    parser.add_argument("--use-sitemap", action="store_true",
                        help="Use CBP XML sitemap instead of index pagination. Recommended for queries older than 30 days.")
    parser.add_argument("--regenerate-only", action="store_true",
                        help="Skip scraping/translation. Reload articles, sync approvals, regenerate HTML only.")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if args.regenerate_only:
        return regenerate_html_only()

    from datetime import date
    since_date = date.fromisoformat(args.since) if args.since else None
    until_date = date.fromisoformat(args.until) if args.until else None
    stats = run(
        dry_run=args.dry_run,
        limit=args.limit,
        month=args.month,
        last_week=args.last_week,
        since_date=since_date,
        until_date=until_date,
        reprocess=args.reprocess,
        use_sitemap=args.use_sitemap,
    )
    return 0 if stats.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
