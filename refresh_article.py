"""
Re-fetches a single article and updates its image_url in articles.json.
Also regenerates the HTML output.

Usage:
    python refresh_article.py <CBP_article_URL>

Example:
    python refresh_article.py https://www.cbp.gov/newsroom/national-media-release/monkey-and-125-pounds-prohibited-meat-intercepted-agriculture
"""

import sys
import json
import logging
from pathlib import Path

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

import config
import html_writer
from scraper import fetch_article

ARTICLES_PATH = config.STATE_DIR / "articles.json"


def load_articles():
    if not ARTICLES_PATH.exists():
        return []
    return json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))


def save_articles(articles):
    tmp = ARTICLES_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ARTICLES_PATH)


def main():
    if len(sys.argv) < 2:
        print("Usage: python refresh_article.py <CBP_article_URL>")
        sys.exit(1)

    url = sys.argv[1].strip().rstrip("/")

    logger.info("Re-fetching: %s", url)
    try:
        article = fetch_article(url)
    except Exception as e:
        logger.error("Failed to fetch article: %s", e)
        sys.exit(1)

    logger.info("Image found: %s", article.image_url or "(none)")

    articles = load_articles()

    # Find matching article by URL (normalize trailing slash)
    matched = False
    for art in articles:
        stored_url = art.get("url", "").rstrip("/")
        if stored_url == url:
            old_img = art.get("image_url", "")
            art["image_url"] = article.image_url or ""
            logger.info("Updated image_url: %s → %s", old_img or "(none)", art["image_url"] or "(none)")
            matched = True
            break

    if not matched:
        logger.warning("URL not found in articles.json. Nothing updated.")
        logger.warning("Stored URLs are:")
        for art in articles:
            logger.warning("  %s", art.get("url", ""))
        sys.exit(1)

    save_articles(articles)
    logger.info("articles.json saved.")

    logger.info("Regenerating HTML...")
    html_path = html_writer.generate(articles)
    logger.info("Done: %s", html_path)


if __name__ == "__main__":
    main()
