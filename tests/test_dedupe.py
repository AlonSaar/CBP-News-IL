"""Tests for dedupe.py."""

import json
import pytest
from pathlib import Path
from datetime import date

# We'll use a temp path so tests don't touch the real state file
from dedupe import DedupeStore


@pytest.fixture
def store(tmp_path: Path) -> DedupeStore:
    return DedupeStore(path=tmp_path / "test_processed_urls.json")


class TestSeen:
    def test_new_url_not_seen(self, store: DedupeStore) -> None:
        assert not store.seen("https://cbp.gov/article/1")

    def test_marked_url_is_seen(self, store: DedupeStore) -> None:
        url = "https://cbp.gov/article/1"
        store.mark(url, "skipped", reason="no photo")
        assert store.seen(url)

    def test_different_url_not_seen(self, store: DedupeStore) -> None:
        store.mark("https://cbp.gov/article/1", "skipped", reason="no photo")
        assert not store.seen("https://cbp.gov/article/2")


class TestMark:
    def test_mark_added_requires_quarter(self, store: DedupeStore) -> None:
        with pytest.raises(ValueError, match="quarter is required"):
            store.mark("https://cbp.gov/a", "added")

    def test_mark_added_stores_quarter(self, store: DedupeStore) -> None:
        store.mark("https://cbp.gov/a", "added", quarter="Q2-2026")
        entry = store.get("https://cbp.gov/a")
        assert entry is not None
        assert entry["quarter"] == "Q2-2026"
        assert entry["status"] == "added"

    def test_mark_skipped_stores_reason(self, store: DedupeStore) -> None:
        store.mark("https://cbp.gov/b", "skipped", reason="personnel announcement")
        entry = store.get("https://cbp.gov/b")
        assert entry["reason"] == "personnel announcement"

    def test_invalid_status_raises(self, store: DedupeStore) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            store.mark("https://cbp.gov/c", "unknown_status")

    def test_mark_overwrites_existing(self, store: DedupeStore) -> None:
        url = "https://cbp.gov/d"
        store.mark(url, "error", reason="network fail")
        store.mark(url, "added", quarter="Q2-2026")
        assert store.get(url)["status"] == "added"


class TestPersistence:
    def test_data_survives_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "dedupe.json"
        s1 = DedupeStore(path=path)
        s1.mark("https://cbp.gov/x", "added", quarter="Q1-2026")

        # New instance reads from the same file
        s2 = DedupeStore(path=path)
        assert s2.seen("https://cbp.gov/x")
        assert s2.get("https://cbp.gov/x")["quarter"] == "Q1-2026"

    def test_corrupt_file_starts_fresh(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.json"
        path.write_text("NOT JSON {{{{")
        s = DedupeStore(path=path)
        assert s.stats() == {}


class TestStats:
    def test_stats_empty(self, store: DedupeStore) -> None:
        assert store.stats() == {}

    def test_stats_mixed(self, store: DedupeStore) -> None:
        store.mark("https://cbp.gov/1", "added", quarter="Q2-2026")
        store.mark("https://cbp.gov/2", "added", quarter="Q2-2026")
        store.mark("https://cbp.gov/3", "skipped", reason="no photo")
        s = store.stats()
        assert s["added"] == 2
        assert s["skipped"] == 1
