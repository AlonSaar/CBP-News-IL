"""
Translates a qualifying CBP article into a structured Hebrew review.

Output is a HebrewReview dataclass with four fields:
    title        - line 1  (Hebrew title)
    location     - line 2  (Hebrew - English location line)
    crossing_type - line 3 (סוג מעבר: ...)
    body         - paragraph (the single-paragraph Hebrew review)

Loads its system prompt from prompts/hebrew_rules.md via config.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from anthropic import Anthropic

import config
from scraper import Article

logger = logging.getLogger(__name__)

# Cache the prompt so we only read the file once per process.
_HEBREW_RULES: str | None = None


def _get_rules() -> str:
    global _HEBREW_RULES
    if _HEBREW_RULES is None:
        _HEBREW_RULES = config.load_prompt(config.HEBREW_RULES_PATH)
    return _HEBREW_RULES


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class HebrewReview:
    title: str
    location: str
    crossing_type: str
    body: str

    def as_text(self) -> str:
        """Reconstruct the raw 4-block review text."""
        return f"{self.title}\n{self.location}\n{self.crossing_type}\n\n{self.body}"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_CROSSING_PREFIX = "סוג מעבר:"


def _parse_review(raw: str) -> HebrewReview:
    """
    Parse the 4-block Hebrew output into HebrewReview fields.

    Expected structure:
        Line 1: title
        Line 2: location
        Line 3: סוג מעבר: <...>
        Line 4: blank
        Line 5+: paragraph body
    """
    lines = raw.strip().splitlines()

    title = ""
    location = ""
    crossing_type = ""
    body_lines: list[str] = []

    # Walk the lines assigning fields
    state = "title"
    for line in lines:
        stripped = line.strip()

        if state == "title":
            title = stripped
            state = "location"
            continue

        if state == "location":
            location = stripped
            state = "crossing"
            continue

        if state == "crossing":
            crossing_type = stripped
            state = "blank"
            continue

        if state == "blank":
            # Expect a blank line then body; tolerate missing blank
            if stripped == "":
                state = "body"
            else:
                # No blank line - treat as body start
                body_lines.append(stripped)
                state = "body"
            continue

        if state == "body":
            body_lines.append(line)

    body = " ".join(l.strip() for l in body_lines if l.strip())

    # Sanity: if crossing_type is missing the prefix, add it
    if crossing_type and not crossing_type.startswith(_CROSSING_PREFIX):
        crossing_type = f"{_CROSSING_PREFIX} {crossing_type}"

    return HebrewReview(
        title=title,
        location=location,
        crossing_type=crossing_type,
        body=body,
    )


def _validate(review: HebrewReview, url: str) -> None:
    """Log warnings for structural issues without raising."""
    if not review.title:
        logger.warning("Empty title in review for %s", url)
    if not review.location:
        logger.warning("Empty location in review for %s", url)
    if not review.crossing_type.startswith(_CROSSING_PREFIX):
        logger.warning(
            "crossing_type missing prefix '%s' in review for %s",
            _CROSSING_PREFIX,
            url,
        )
    if not review.body:
        logger.warning("Empty body in review for %s", url)


# ---------------------------------------------------------------------------
# Main translate function
# ---------------------------------------------------------------------------

def translate(article: Article, client: Anthropic) -> HebrewReview:
    """
    Translate a qualifying article to a structured Hebrew review.

    Retries once on parse failure (empty title or body) with a stricter prompt.
    Raises on API errors.
    """
    rules = _get_rules()

    user_msg = (
        f"Source CBP article (URL: {article.url})\n\n"
        f"TITLE: {article.title}\n\n"
        f"BODY:\n{article.body}\n\n"
        "Produce the Hebrew review now, following every rule in the system prompt."
    )

    logger.debug("Translating: %s", article.url)

    for attempt in (1, 2):
        try:
            msg = client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_TOKENS_TRANSLATION,
                system=rules,
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as exc:
            logger.error(
                "Translation API call failed (attempt %d) for %s: %s",
                attempt,
                article.url,
                exc,
            )
            raise

        raw = msg.content[0].text.strip()
        review = _parse_review(raw)

        if review.title and review.body:
            break

        if attempt == 1:
            logger.warning(
                "Parse produced empty fields on attempt 1 for %s; retrying",
                article.url,
            )
            # Second attempt: remind model of exact format
            user_msg += (
                "\n\nIMPORTANT: Follow the 4-block structure exactly.\n"
                "Line 1: Hebrew title\n"
                "Line 2: Hebrew location - English location, state\n"
                "Line 3: סוג מעבר: ...\n"
                "Line 4: blank\n"
                "Line 5: single Hebrew paragraph\n"
                "No extra lines, no markdown."
            )

    _validate(review, article.url)
    logger.info("Translated: %s -> title='%s'", article.url, review.title[:60])
    return review
