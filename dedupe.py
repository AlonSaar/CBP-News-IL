"""
Deduplication store - tracks which URLs have been processed.

Backed by a JSON file at config.PROCESSED_URLS_PATH.
Thread safety: single-process only (file lock not required for this use case).

Schema of each entry:
{
    "<url>": {
        "status": "added" | "skipped" | "error",
        "quarter": "Q2-2026",      # only for status=added
        "reason": "...",           # only for status=skipped
        "timestamp": "2026-04-22T08:00:00"
    }
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"added", "skipped", "error"}


class DedupeStore:
    def __init__(self, path: Path = config.PROCESSED_URLS_PATH) -> None:
        self._path = path
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def seen(self, url: str) -> bool:
        """Return True if this URL is already in the store (any status)."""
        return url in self._data

    def mark(
        self,
        url: str,
        status: str,
        *,
        quarter: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Record that a URL has been processed.

        Args:
            url:     The article URL.
            status:  One of "added", "skipped", "error".
            quarter: Quarter key (e.g. "Q2-2026"). Required when status="added".
            reason:  Short reason string. Used for status="skipped"/"error".
        """
        if status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {_VALID_STATUSES}.")
        if status == "added" and not quarter:
            raise ValueError("quarter is required when status='added'.")

        entry: dict[str, Any] = {
            "status": status,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        }
        if quarter:
            entry["quarter"] = quarter
        if reason:
            entry["reason"] = reason

        self._data[url] = entry
        self._save()
        logger.debug("Marked %s as %s", url, status)

    def get(self, url: str) -> Optional[dict[str, Any]]:
        """Return the stored entry for a URL, or None if not found."""
        return self._data.get(url)

    def all_added(self) -> dict[str, dict[str, Any]]:
        """Return all entries with status='added'."""
        return {u: e for u, e in self._data.items() if e.get("status") == "added"}

    def stats(self) -> dict[str, int]:
        """Return counts by status."""
        counts: dict[str, int] = {}
        for entry in self._data.values():
            s = entry.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            logger.debug("Dedupe store not found at %s; starting fresh", self._path)
            self._data = {}
            return
        try:
            with self._path.open(encoding="utf-8") as fh:
                self._data = json.load(fh)
            logger.debug("Loaded %d entries from dedupe store", len(self._data))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load dedupe store: %s; starting fresh", exc)
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
            tmp.replace(self._path)
        except OSError as exc:
            logger.error("Failed to save dedupe store: %s", exc)
            raise


# Module-level singleton - instantiated on first import.
_store: Optional[DedupeStore] = None


def _get_store() -> DedupeStore:
    global _store
    if _store is None:
        _store = DedupeStore()
    return _store


# Convenience module-level functions that mirror the class API.

def seen(url: str) -> bool:
    return _get_store().seen(url)


def mark(url: str, status: str, *, quarter: Optional[str] = None, reason: Optional[str] = None) -> None:
    _get_store().mark(url, status, quarter=quarter, reason=reason)


def get(url: str) -> Optional[dict[str, Any]]:
    return _get_store().get(url)


def stats() -> dict[str, int]:
    return _get_store().stats()
