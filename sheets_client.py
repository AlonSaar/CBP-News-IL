"""
Google Sheets wrapper for the CBP translator pipeline.

Manages quarterly tabs and appends Hebrew reviews.

Auth: Google Service Account JSON loaded from GOOGLE_SERVICE_ACCOUNT_JSON env var
      (the full JSON string, not a file path).

Key methods:
    ensure_quarter_tab(quarter_key)                     -> None
    append_review(quarter_key, review, article)         -> None
    url_exists(url)                                     -> bool
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

import config
from quarter import Quarter
from scraper import Article
from translator import HebrewReview

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Row 1 of every tab is the header.
_HEADER_ROW = config.SHEET_COLUMNS  # list of 11 column names from config


class SheetsClient:
    def __init__(
        self,
        spreadsheet_id: Optional[str] = None,
        service_account_json: Optional[str] = None,
    ) -> None:
        sid = spreadsheet_id or config.GOOGLE_SHEETS_ID
        sa_json = service_account_json or config.GOOGLE_SERVICE_ACCOUNT_JSON

        if not sid:
            raise RuntimeError(
                "GOOGLE_SHEETS_ID is not set. Add it to your .env file."
            )
        if not sa_json:
            raise RuntimeError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is not set. Add it to your .env file."
            )

        creds_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(creds_info, scopes=_SCOPES)
        gc = gspread.authorize(creds)

        self._spreadsheet = gc.open_by_key(sid)
        logger.info("Connected to spreadsheet: %s", self._spreadsheet.title)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def ensure_quarter_tab(self, quarter_key: str) -> gspread.Worksheet:
        """
        Return the worksheet for `quarter_key`, creating it (with header row)
        if it does not exist yet.
        """
        try:
            ws = self._spreadsheet.worksheet(quarter_key)
            logger.debug("Tab '%s' already exists", quarter_key)
            return ws
        except gspread.WorksheetNotFound:
            logger.info("Creating new tab: %s", quarter_key)
            ws = self._spreadsheet.add_worksheet(
                title=quarter_key, rows=1000, cols=len(_HEADER_ROW)
            )
            ws.append_row(_HEADER_ROW, value_input_option="RAW")
            # Freeze the header row
            ws.freeze(rows=1)
            logger.info("Created tab '%s' with header row", quarter_key)
            return ws

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def url_exists(self, url: str) -> bool:
        """
        Check all existing tabs for a row with this source URL (column C).
        Used as a cross-tab safety net on top of dedupe.py.
        """
        for ws in self._spreadsheet.worksheets():
            # Column C (index 2) = Source URL
            urls_in_tab = ws.col_values(3)  # 1-indexed, col 3 = C
            if url in urls_in_tab:
                logger.debug("URL already in sheet (tab '%s'): %s", ws.title, url)
                return True
        return False

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append_review(
        self,
        quarter_key: str,
        review: HebrewReview,
        article: Article,
        status: str = "needs-review",
    ) -> None:
        """
        Append one row to the quarter tab.

        Columns (A-K):
            A: Run Date (UTC ISO)
            B: Article Date (YYYY-MM-DD)
            C: Source URL
            D: Hebrew Title
            E: Hebrew Location Line
            F: Crossing Type
            G: Hebrew Review Body
            H: Image URL
            I: Status
            J: Editor Notes  (empty)
            K: Last Modified (left empty; can be set via a Sheet formula)
        """
        ws = self.ensure_quarter_tab(quarter_key)

        run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        article_date_str = article.article_date.isoformat()

        # Strip the "סוג מעבר: " prefix from crossing_type for the column value
        crossing_value = review.crossing_type
        prefix = "סוג מעבר: "
        if crossing_value.startswith(prefix):
            crossing_value = crossing_value[len(prefix):]

        row = [
            run_date,                          # A: Run Date
            article_date_str,                  # B: Article Date
            article.url,                       # C: Source URL
            review.title,                      # D: Hebrew Title
            review.location,                   # E: Hebrew Location Line
            crossing_value,                    # F: Crossing Type
            review.body,                       # G: Hebrew Review Body
            article.image_url or "",           # H: Image URL
            status,                            # I: Status
            "",                                # J: Editor Notes
            "",                                # K: Last Modified (formula-managed)
        ]

        ws.append_row(row, value_input_option="RAW")
        logger.info(
            "Appended to tab '%s': %s | %s",
            quarter_key,
            article_date_str,
            review.title[:60],
        )
