"""
Central config - loads env vars and exposes constants.

All modules should import from here, not read os.environ directly.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT: Path = Path(__file__).resolve().parent
PROMPTS_DIR: Path = ROOT / "prompts"
STATE_DIR: Path = ROOT / "state"
LOGS_DIR: Path = ROOT / "logs"

HEBREW_RULES_PATH: Path = PROMPTS_DIR / "hebrew_rules.md"
CLASSIFIER_PROMPT_PATH: Path = PROMPTS_DIR / "classifier.md"
PROCESSED_URLS_PATH: Path = STATE_DIR / "processed_urls.json"
LAST_RUN_PATH: Path = STATE_DIR / "last_run.json"


# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
MODEL: str = os.environ.get("CBP_MODEL", "claude-sonnet-4-6")
MAX_TOKENS_CLASSIFIER: int = 60
MAX_TOKENS_TRANSLATION: int = 1500


# ---------------------------------------------------------------------------
# CBP scraping
# ---------------------------------------------------------------------------
CBP_NEWS_INDEX_URL: str = "https://www.cbp.gov/newsroom/national-media-release"
CBP_USER_AGENT: str = "Mozilla/5.0 (compatible; CBP-Translator/0.1)"
HTTP_TIMEOUT_SECONDS: int = 20
SCRAPE_MAX_ARTICLES_PER_RUN: int = 30


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------
GOOGLE_SHEETS_ID: Optional[str] = os.environ.get("GOOGLE_SHEETS_ID")
GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_JSON"
)

SHEET_COLUMNS: list[str] = [
    "Run Date",
    "Article Date",
    "Source URL",
    "Hebrew Title",
    "Hebrew Location Line",
    "Crossing Type",
    "Hebrew Review Body",
    "Image URL",
    "Status",
    "Editor Notes",
    "Last Modified",
]


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
def anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or .env file."
        )
    return key


def load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
