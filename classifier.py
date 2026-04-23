"""
Article classifier - decides whether a CBP article qualifies for Hebrew translation.

Returns (qualifies: bool, reason: str).
Loads its prompt from prompts/classifier.md via config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from anthropic import Anthropic

import config
from scraper import Article

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache the prompt so we only read the file once per process.
_CLASSIFIER_PROMPT: str | None = None


def _get_prompt() -> str:
    global _CLASSIFIER_PROMPT
    if _CLASSIFIER_PROMPT is None:
        _CLASSIFIER_PROMPT = config.load_prompt(config.CLASSIFIER_PROMPT_PATH)
    return _CLASSIFIER_PROMPT


def classify(article: Article, client: Anthropic) -> tuple[bool, str]:
    """
    Classify an article as qualifying or not.

    Returns:
        (True, "YES")                          if it qualifies.
        (False, "NO:<reason>")                 if it does not.
    """
    prompt_template = _get_prompt()

    # Compose the user message - append the article fields at the end.
    user_msg = (
        f"{prompt_template}\n\n"
        f"---\n"
        f"Title: {article.title}\n\n"
        f"Body (truncated to 3 000 chars):\n{article.body[:3000]}\n\n"
        f"Has image URL: {article.has_image}\n"
        f"Image URL: {article.image_url or '(none)'}\n"
    )

    logger.debug("Classifying: %s", article.url)

    try:
        msg = client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS_CLASSIFIER,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as exc:
        logger.error("Classifier API call failed for %s: %s", article.url, exc)
        raise

    answer = msg.content[0].text.strip()
    qualifies = answer.upper().startswith("YES")

    logger.info(
        "Classified %s -> %s | %s",
        article.url,
        "QUALIFY" if qualifies else "SKIP",
        answer,
    )
    return qualifies, answer
