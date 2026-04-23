"""
Scrapes the CBP Newsroom index and individual article pages.

list_new()       -> list[Article]   # recent articles from the index
fetch_article()  -> Article         # full body + image for one URL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

_CBP_BASE = "https://www.cbp.gov"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Article:
    url: str
    title: str
    article_date: date
    has_image: bool
    image_url: Optional[str] = None   # first image (backward compat)
    image_urls: list = field(default_factory=list)  # all images found
    body: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.CBP_USER_AGENT})
    return s


def _get(url: str, session: requests.Session) -> BeautifulSoup:
    resp = session.get(url, timeout=config.HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parse_date(text: str) -> Optional[date]:
    """Parse a date string into a date object. Returns None on failure."""
    text = text.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(_CBP_BASE, href)


def _extract_hero_image(soup: BeautifulSoup, body_el) -> Optional[str]:
    """
    Extract article-specific hero image URL.
    Priority: figure/body img > CBP media URL scan > og:image > twitter:image.
    og:image on CBP pages often points to a generic CBP banner rather than the
    article photo, so we try the article content area first.
    """
    import re

    def _is_meaningful(img_tag) -> bool:
        """Return False for tiny icons, spacers, logos."""
        src = img_tag.get("src", "")
        if any(kw in src.lower() for kw in ("logo", "icon", "spacer", "seal", "badge")):
            return False
        try:
            w = int(img_tag.get("width", 0))
            h = int(img_tag.get("height", 0))
            if w and h and (w < 100 or h < 100):
                return False
        except (ValueError, TypeError):
            pass
        return True

    # 1. First <img> inside a <figure> (typically the article photo)
    for figure in soup.find_all("figure"):
        img = figure.find("img")
        if img and img.get("src") and _is_meaningful(img):
            return _resolve_url(img["src"])

    # 2. First meaningful <img> inside the article body element
    if body_el:
        for img in body_el.find_all("img"):
            if img.get("src") and _is_meaningful(img):
                return _resolve_url(img["src"])

    # 3. Scan raw HTML for any CBP media image under /sites/default/files/
    #    Covers both /assets/images/ and bare date-stamped filenames like /20260408_125920_copy.jpg
    page_text = str(soup)
    _GENERIC = ("seal", "logo", "icon", "badge", "twitter-card", "placeholder")
    for m in re.findall(
        r'(https?://www\.cbp\.gov/sites/default/files/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))',
        page_text,
        re.IGNORECASE,
    ):
        if not any(kw in m.lower() for kw in _GENERIC):
            return m

    # 4. og:image — fallback (may be a generic CBP banner)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        content = og["content"]
        if not any(kw in content.lower() for kw in ("seal", "logo", "cbp-logo")):
            return content

    # 5. twitter:image (same generic-image filter)
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        content = tw["content"]
        if not any(kw in content.lower() for kw in ("seal", "logo", "cbp-logo")):
            return content

    return None


def _extract_all_images(soup: BeautifulSoup, body_el, max_images: int = 5) -> list:
    """
    Return all meaningful article-specific image URLs found on the page.
    Deduplicates, filters generic CBP images, caps at max_images.
    """
    import re
    seen: set = set()
    results: list = []
    _GENERIC = ("seal", "logo", "icon", "badge", "twitter-card", "placeholder", "spacer")

    def _add(url: str) -> None:
        url = url.strip()
        if not url or url in seen:
            return
        if any(kw in url.lower() for kw in _GENERIC):
            return
        seen.add(url)
        results.append(url)

    def _ok(img_tag) -> bool:
        src = img_tag.get("src", "")
        if not src or any(kw in src.lower() for kw in _GENERIC):
            return False
        try:
            w, h = int(img_tag.get("width", 0)), int(img_tag.get("height", 0))
            if w and h and (w < 100 or h < 100):
                return False
        except (ValueError, TypeError):
            pass
        return True

    # 1. <figure> images (most reliable article photos)
    for figure in soup.find_all("figure"):
        for img in figure.find_all("img"):
            if _ok(img):
                _add(_resolve_url(img["src"]))
        if len(results) >= max_images:
            return results

    # 2. Meaningful images inside article body
    if body_el:
        for img in body_el.find_all("img"):
            if _ok(img):
                _add(_resolve_url(img["src"]))
        if len(results) >= max_images:
            return results

    # 3. All CBP /sites/default/files/ image URLs in raw HTML
    page_text = str(soup)
    for m in re.findall(
        r'(https?://www\.cbp\.gov/sites/default/files/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))',
        page_text, re.IGNORECASE,
    ):
        _add(m)
        if len(results) >= max_images:
            return results

    # 4. og:image / twitter:image as last resort
    for meta_tag in [
        soup.find("meta", property="og:image"),
        soup.find("meta", attrs={"name": "twitter:image"}),
    ]:
        if meta_tag and meta_tag.get("content"):
            _add(meta_tag["content"])

    return results[:max_images]


# ---------------------------------------------------------------------------
# Index scraper
# ---------------------------------------------------------------------------

def _scrape_index_page(
    page: int,
    session,
    seen_urls: set,
    since: Optional[date] = None,
    until: Optional[date] = None,
) -> tuple[list[Article], bool]:
    """
    Scrape one page of the CBP news index.
    Returns (articles_found, should_stop).
    should_stop=True when all remaining articles are older than `since`.
    """
    _INDEX_PATH = "/newsroom/national-media-release"
    url = config.CBP_NEWS_INDEX_URL + (f"?page={page}" if page > 0 else "")
    logger.info("Fetching index page %d: %s", page, url)

    try:
        soup = _get(url, session)
    except Exception as exc:
        logger.error("Failed to fetch index page %d: %s", page, exc)
        return [], True

    all_anchors = soup.find_all(
        "a",
        href=lambda h: h and h.startswith(_INDEX_PATH + "/") and len(h) > len(_INDEX_PATH) + 1,
    )

    if not all_anchors:
        return [], True  # No more pages

    articles: list[Article] = []

    for anchor in all_anchors:
        href = anchor.get("href", "")
        url = _resolve_url(href)

        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = anchor.get_text(strip=True)
        if not title:
            parent = anchor.find_parent(["h2", "h3", "h4", "li", "div"])
            if parent:
                title = parent.get_text(strip=True)
        if not title:
            continue

        # Date: walk up the DOM
        article_date: Optional[date] = None
        container = anchor.find_parent(["li", "div", "article", "tr"])
        if container:
            time_el = container.find("time")
            if time_el:
                dt = time_el.get("datetime", "")
                article_date = _parse_date(dt[:10]) or _parse_date(time_el.get_text(strip=True))

            if not article_date:
                for cls in ("date-display-single", "field--name-created",
                            "field-name-post-date", "views-field-created",
                            "views-field-field-date"):
                    el = container.find(class_=cls)
                    if el:
                        article_date = _parse_date(el.get_text(strip=True))
                        if article_date:
                            break

        if not article_date:
            logger.warning("No date found for %s; using today", url)
            article_date = date.today()

        # If article is older than `since`, everything below will be too — stop paging
        if since and article_date < since:
            return articles, True

        # Skip if outside target window
        if since and article_date < since:
            continue
        if until and article_date > until:
            continue

        has_image = bool(container and container.find("img")) if container else False
        articles.append(Article(url=url, title=title, article_date=article_date, has_image=has_image))

    return articles, False


def list_new(
    max_articles: int = config.SCRAPE_MAX_ARTICLES_PER_RUN,
    since: Optional[date] = None,
    until: Optional[date] = None,
) -> list[Article]:
    """
    Fetch the CBP Newsroom index and return Articles.

    - max_articles: upper cap (ignored when since/until are set — we scan until
      the date window is exhausted or no more pages).
    - since / until: inclusive date bounds. When set, pagination continues
      automatically across as many index pages as needed.
    """
    session = _session()
    articles: list[Article] = []
    seen_urls: set[str] = set()
    paginate = since is not None or until is not None
    max_pages = 20 if paginate else 1  # safety cap

    for page in range(max_pages):
        page_articles, stop = _scrape_index_page(page, session, seen_urls, since, until)
        articles.extend(page_articles)
        logger.info("Page %d: +%d articles (total so far: %d)", page, len(page_articles), len(articles))

        if stop:
            break
        if not paginate and len(articles) >= max_articles:
            break

    if not paginate:
        articles = articles[:max_articles]

    logger.info("Index scan complete: %d articles found", len(articles))
    return articles


def list_new_legacy(max_articles: int = config.SCRAPE_MAX_ARTICLES_PER_RUN) -> list[Article]:
    """Legacy single-page scraper kept for reference."""
    session = _session()
    articles: list[Article] = []
    seen_urls: set[str] = set()

    logger.info("Fetching CBP news index: %s", config.CBP_NEWS_INDEX_URL)

    try:
        soup = _get(config.CBP_NEWS_INDEX_URL, session)
    except Exception as exc:
        logger.error("Failed to fetch news index: %s", exc)
        return []

    _INDEX_PATH = "/newsroom/national-media-release"

    all_anchors = soup.find_all(
        "a",
        href=lambda h: h and h.startswith(_INDEX_PATH + "/") and len(h) > len(_INDEX_PATH) + 1,
    )

    logger.debug("Found %d raw anchor candidates", len(all_anchors))

    for anchor in all_anchors:
        if len(articles) >= max_articles:
            break

        href = anchor.get("href", "")
        url = _resolve_url(href)

        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = anchor.get_text(strip=True)
        if not title:
            parent = anchor.find_parent(["h2", "h3", "h4", "li", "div"])
            if parent:
                title = parent.get_text(strip=True)
        if not title:
            continue

        article_date: Optional[date] = None
        container = anchor.find_parent(["li", "div", "article", "tr"])
        if container:
            time_el = container.find("time")
            if time_el:
                dt = time_el.get("datetime", "")
                article_date = _parse_date(dt[:10]) or _parse_date(time_el.get_text(strip=True))

            if not article_date:
                for cls in ("date-display-single", "field--name-created",
                            "field-name-post-date", "views-field-created",
                            "views-field-field-date"):
                    el = container.find(class_=cls)
                    if el:
                        article_date = _parse_date(el.get_text(strip=True))
                        if article_date:
                            break

        if not article_date:
            logger.warning("No date found for %s; using today", url)
            article_date = date.today()

        has_image = bool(container and container.find("img")) if container else False

        articles.append(Article(
            url=url,
            title=title,
            article_date=article_date,
            has_image=has_image,
        ))

    logger.info("Found %d articles on index page", len(articles))
    return articles


# ---------------------------------------------------------------------------
# Full article fetcher
# ---------------------------------------------------------------------------

def fetch_article(url: str, session: Optional[requests.Session] = None) -> Article:
    """
    Fetch a single CBP article page and return a fully populated Article.
    Raises requests.HTTPError on network failures.
    """
    if session is None:
        session = _session()

    logger.debug("Fetching article: %s", url)
    soup = _get(url, session)

    # Title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Publication date
    article_date: Optional[date] = None
    for cls in ("field--name-created", "field-name-post-date", "date-display-single"):
        el = soup.find(class_=cls)
        if el:
            article_date = _parse_date(el.get_text(strip=True))
            if article_date:
                break
    if not article_date:
        time_el = soup.find("time")
        if time_el:
            dt_attr = time_el.get("datetime", "")
            article_date = _parse_date(dt_attr[:10]) or _parse_date(time_el.get_text(strip=True))
    if not article_date:
        article_date = date.today()

    # Body text - try multiple selectors for CBP's Drupal structure
    body_el = (
        soup.find("div", class_="field--name-body")
        or soup.find("div", class_="field-name-body")
        or soup.find("div", class_="field--name-field-description")
        or soup.find("div", attrs={"data-block-plugin-id": "field_block:node:news_release:body"})
        or soup.find("div", class_="layout__region--content")
        or soup.find("div", class_="node__content")
        or soup.find("article")
        or soup.find("main")
    )
    for tag in soup.find_all(["nav", "script", "style", "footer", "header", "noscript"]):
        tag.decompose()

    body = body_el.get_text(" ", strip=True) if body_el else ""

    if len(body) < 300:
        full_text = soup.get_text(" ", strip=True)
        title_pos = full_text.find(title) if title else -1
        if title_pos >= 0:
            body = full_text[title_pos:]
        else:
            body = full_text

    # All article images
    image_urls = _extract_all_images(soup, body_el)
    image_url = image_urls[0] if image_urls else None
    has_image = bool(image_urls)

    if not title:
        logger.warning("Could not parse title from %s — CBP HTML may have changed", url)

    return Article(
        url=url,
        title=title,
        article_date=article_date,
        has_image=has_image,
        image_url=image_url,
        image_urls=image_urls,
        body=body,
    )
