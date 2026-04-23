"""Tests for scraper.py - use local fixture, no live network."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from scraper import _parse_date, _extract_hero_image, Article


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_article.html"


class TestParseDate:
    def test_long_month(self) -> None:
        assert _parse_date("April 18, 2026") == date(2026, 4, 18)

    def test_short_month(self) -> None:
        assert _parse_date("Apr 18, 2026") == date(2026, 4, 18)

    def test_iso(self) -> None:
        assert _parse_date("2026-04-18") == date(2026, 4, 18)

    def test_slash(self) -> None:
        assert _parse_date("04/18/2026") == date(2026, 4, 18)

    def test_invalid_returns_none(self) -> None:
        assert _parse_date("not a date") is None

    def test_whitespace_stripped(self) -> None:
        assert _parse_date("  April 18, 2026  ") == date(2026, 4, 18)


class TestExtractHeroImage:
    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def test_og_image_fallback(self) -> None:
        html = '<html><head><meta property="og:image" content="https://cbp.gov/img.jpg"/></head><body></body></html>'
        soup = self._soup(html)
        assert _extract_hero_image(soup, None) == "https://cbp.gov/img.jpg"

    def test_body_img_preferred(self) -> None:
        html = (
            '<html><head><meta property="og:image" content="https://cbp.gov/og.jpg"/></head>'
            '<body><div class="field--name-body"><img src="https://cbp.gov/body.jpg"/></div></body></html>'
        )
        soup = self._soup(html)
        body_el = soup.find("div", class_="field--name-body")
        assert _extract_hero_image(soup, body_el) == "https://cbp.gov/body.jpg"

    def test_relative_url_resolved(self) -> None:
        html = '<body><div id="body"><img src="/sites/img.jpg"/></div></body>'
        soup = self._soup(html)
        body_el = soup.find("div", id="body")
        result = _extract_hero_image(soup, body_el)
        assert result == "https://www.cbp.gov/sites/img.jpg"

    def test_no_image_returns_none(self) -> None:
        soup = self._soup("<html><body><p>no image here</p></body></html>")
        assert _extract_hero_image(soup, None) is None


class TestFetchArticleWithFixture:
    """Parse the sample fixture through the same logic fetch_article uses."""

    def test_fixture_parses_title(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.find("h1")
        assert title_el is not None
        title = title_el.get_text(strip=True)
        assert "Methamphetamine" in title

    def test_fixture_parses_image(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        body_el = soup.find("div", class_="field--name-body")
        image_url = _extract_hero_image(soup, body_el)
        assert image_url is not None
        assert "meth-seizure-laredo" in image_url

    def test_fixture_parses_date(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        date_el = soup.find(class_="field--name-created")
        assert date_el is not None
        parsed = _parse_date(date_el.get_text(strip=True))
        assert parsed == date(2026, 4, 18)

    def test_fixture_body_contains_key_facts(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        body_el = soup.find("div", class_="field--name-body")
        body = body_el.get_text(" ", strip=True)
        assert "45 pounds" in body
        assert "door panels" in body
        assert "HSI" in body
