"""Derived bar aggregation helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol, cast

import exchange_calendars as xcals
import pandas as pd

from yog.enums import BarInterval

if TYPE_CHECKING:
    from datetime import date

CALENDAR_NAME = "XNYS"
SESSION_OPEN = "09:30"
SESSION_CLOSE = "16:00"
EARLY_CLOSE = "13:00"
BUCKET_MINUTES: dict[BarInterval, int] = {
    BarInterval.H1: 60,
    BarInterval.H4: 240,
}


class ExchangeCalendar(Protocol):
    """Minimal exchange-calendar surface used by the aggregator."""

    @property
    def early_closes(self) -> pd.DatetimeIndex: ...


@lru_cache(maxsize=1)
def exchange_calendar() -> ExchangeCalendar:
    """Return the New York exchange calendar."""
    return cast("ExchangeCalendar", xcals.get_calendar(CALENDAR_NAME))


def early_close_dates(start: date, end: date) -> tuple[date, ...]:
    """Return early-close session dates in a date range."""
    closes = exchange_calendar().early_closes
    selected = closes[(closes >= pd.Timestamp(start)) & (closes <= pd.Timestamp(end))]
    return tuple(timestamp.date() for timestamp in selected)


def bucket_minutes(interval: BarInterval) -> int:
    """Return the bucket width in minutes for an intraday interval."""
    if interval not in BUCKET_MINUTES:
        raise ValueError(f"interval {interval} is not an intraday aggregation")
    return BUCKET_MINUTES[interval]
