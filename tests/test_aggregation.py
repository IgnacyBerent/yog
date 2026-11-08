"""Derived aggregation helpers."""

from __future__ import annotations

from datetime import date

import pytest

from yog.aggregation import bucket_minutes, early_close_dates
from yog.enums import BarInterval


def test_bucket_minutes_for_intraday_intervals() -> None:
    assert bucket_minutes(BarInterval.H1) == 60
    assert bucket_minutes(BarInterval.H4) == 240


def test_bucket_minutes_rejects_non_intraday_intervals() -> None:
    with pytest.raises(ValueError, match="not an intraday"):
        bucket_minutes(BarInterval.D1)
    with pytest.raises(ValueError, match="not an intraday"):
        bucket_minutes(BarInterval.M5)


def test_early_close_dates_include_thanksgiving_half_day() -> None:
    closes = early_close_dates(date(2024, 11, 25), date(2024, 12, 2))
    assert date(2024, 11, 29) in closes


def test_early_close_dates_are_empty_outside_the_range() -> None:
    assert early_close_dates(date(2024, 10, 1), date(2024, 10, 31)) == ()
