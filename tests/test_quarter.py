"""Tests for quarter.py - boundary dates are non-negotiable."""

from datetime import date

import pytest

from quarter import (
    Quarter,
    current_quarter,
    next_quarter,
    previous_quarter,
    quarter_for,
    quarter_key,
)


class TestQuarterBoundaries:
    """Every month must map to the correct quarter."""

    @pytest.mark.parametrize(
        "month,expected_q",
        [
            (1, 1), (2, 1), (3, 1),
            (4, 2), (5, 2), (6, 2),
            (7, 3), (8, 3), (9, 3),
            (10, 4), (11, 4), (12, 4),
        ],
    )
    def test_month_to_quarter(self, month: int, expected_q: int) -> None:
        q = quarter_for(date(2026, month, 15))
        assert q.n == expected_q
        assert q.year == 2026

    def test_boundary_dec_31_q4(self) -> None:
        assert quarter_key(date(2026, 12, 31)) == "Q4-2026"

    def test_boundary_jan_1_next_year_q1(self) -> None:
        assert quarter_key(date(2027, 1, 1)) == "Q1-2027"

    def test_boundary_mar_31_q1(self) -> None:
        assert quarter_key(date(2026, 3, 31)) == "Q1-2026"

    def test_boundary_apr_1_q2(self) -> None:
        assert quarter_key(date(2026, 4, 1)) == "Q2-2026"

    def test_boundary_jun_30_q2(self) -> None:
        assert quarter_key(date(2026, 6, 30)) == "Q2-2026"

    def test_boundary_jul_1_q3(self) -> None:
        assert quarter_key(date(2026, 7, 1)) == "Q3-2026"

    def test_boundary_sep_30_q3(self) -> None:
        assert quarter_key(date(2026, 9, 30)) == "Q3-2026"

    def test_boundary_oct_1_q4(self) -> None:
        assert quarter_key(date(2026, 10, 1)) == "Q4-2026"


class TestQuarterMetadata:
    def test_q1_start_end(self) -> None:
        q = Quarter(n=1, year=2026)
        assert q.start == date(2026, 1, 1)
        assert q.end == date(2026, 3, 31)

    def test_q2_start_end(self) -> None:
        q = Quarter(n=2, year=2026)
        assert q.start == date(2026, 4, 1)
        assert q.end == date(2026, 6, 30)

    def test_q3_start_end(self) -> None:
        q = Quarter(n=3, year=2026)
        assert q.start == date(2026, 7, 1)
        assert q.end == date(2026, 9, 30)

    def test_q4_start_end(self) -> None:
        q = Quarter(n=4, year=2026)
        assert q.start == date(2026, 10, 1)
        assert q.end == date(2026, 12, 31)

    def test_key_format(self) -> None:
        assert Quarter(n=3, year=2026).key == "Q3-2026"

    def test_label_format(self) -> None:
        assert "Jul-Sep" in Quarter(n=3, year=2026).label


class TestQuarterNavigation:
    def test_next_same_year(self) -> None:
        assert next_quarter(Quarter(n=2, year=2026)) == Quarter(n=3, year=2026)

    def test_next_wraps_year(self) -> None:
        assert next_quarter(Quarter(n=4, year=2026)) == Quarter(n=1, year=2027)

    def test_prev_same_year(self) -> None:
        assert previous_quarter(Quarter(n=3, year=2026)) == Quarter(n=2, year=2026)

    def test_prev_wraps_year(self) -> None:
        assert previous_quarter(Quarter(n=1, year=2027)) == Quarter(n=4, year=2026)


class TestInputTypes:
    def test_accepts_iso_string(self) -> None:
        assert quarter_key("2026-08-15") == "Q3-2026"

    def test_accepts_iso_datetime_string(self) -> None:
        assert quarter_key("2026-11-20T14:30:00") == "Q4-2026"

    def test_rejects_invalid_type(self) -> None:
        with pytest.raises(TypeError):
            quarter_for(12345)  # type: ignore[arg-type]


def test_current_quarter_is_valid() -> None:
    q = current_quarter()
    assert 1 <= q.n <= 4
    assert q.year >= 2025
