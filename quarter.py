"""
Quarter logic. Pure date math, no I/O.

Quarters:
    Q1 = Jan, Feb, Mar
    Q2 = Apr, May, Jun
    Q3 = Jul, Aug, Sep
    Q4 = Oct, Nov, Dec

Quarter key format: "Q{n}-{YYYY}" e.g. "Q2-2026".
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Union


DateLike = Union[date, datetime, str]


@dataclass(frozen=True)
class Quarter:
    n: int   # 1..4
    year: int

    @property
    def key(self) -> str:
        return f"Q{self.n}-{self.year}"

    @property
    def start(self) -> date:
        return date(self.year, (self.n - 1) * 3 + 1, 1)

    @property
    def end(self) -> date:
        end_month = self.n * 3
        if end_month == 12:
            return date(self.year, 12, 31)
        return date(self.year, end_month + 1, 1) - timedelta(days=1)

    @property
    def label(self) -> str:
        names = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}
        return f"{self.key} ({names[self.n]})"

    def __str__(self) -> str:
        return self.key


def _to_date(d: DateLike) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        # Accept ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        return datetime.fromisoformat(d).date()
    raise TypeError(f"Unsupported date type: {type(d).__name__}")


def quarter_for(d: DateLike) -> Quarter:
    """Return the Quarter containing the given date."""
    dt = _to_date(d)
    n = (dt.month - 1) // 3 + 1
    return Quarter(n=n, year=dt.year)


def quarter_key(d: DateLike) -> str:
    """Shortcut: return the quarter key string, e.g. 'Q2-2026'."""
    return quarter_for(d).key


def current_quarter() -> Quarter:
    return quarter_for(date.today())


def next_quarter(q: Quarter) -> Quarter:
    if q.n == 4:
        return Quarter(n=1, year=q.year + 1)
    return Quarter(n=q.n + 1, year=q.year)


def previous_quarter(q: Quarter) -> Quarter:
    if q.n == 1:
        return Quarter(n=4, year=q.year - 1)
    return Quarter(n=q.n - 1, year=q.year)


if __name__ == "__main__":
    # Quick smoke test - run: python quarter.py
    today = current_quarter()
    print(f"Today: {today.label}")
    print(f"  Starts: {today.start}")
    print(f"  Ends:   {today.end}")
    print(f"  Next:   {next_quarter(today).key}")
    print(f"  Prev:   {previous_quarter(today).key}")
    print()
    for sample in ["2026-01-01", "2026-03-31", "2026-04-01", "2026-12-31"]:
        print(f"  {sample} -> {quarter_key(sample)}")
