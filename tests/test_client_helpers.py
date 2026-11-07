from __future__ import annotations

from datetime import UTC, date, datetime

from yog.client import _as_date, _as_datetime


def test_as_date_accepts_strings_dates_and_datetimes() -> None:
    assert _as_date("2024-01-02") == date(2024, 1, 2)
    assert _as_date(date(2024, 1, 2)) == date(2024, 1, 2)
    assert _as_date(datetime(2024, 1, 2, 15, 30, tzinfo=UTC)) == date(2024, 1, 2)
    assert _as_date(None) is None


def test_as_datetime_treats_date_only_as_start_of_day() -> None:
    assert _as_datetime("2024-01-02") == datetime(2024, 1, 2, tzinfo=UTC)
    assert _as_datetime(date(2024, 1, 2)) == datetime(2024, 1, 2, tzinfo=UTC)


def test_as_datetime_end_of_day_expands_date_only_values() -> None:
    assert _as_datetime("2024-01-02", end_of_day=True) == datetime(
        2024, 1, 2, 23, 59, 59, 999999, tzinfo=UTC
    )
    assert _as_datetime(date(2024, 1, 2), end_of_day=True) == datetime(
        2024, 1, 2, 23, 59, 59, 999999, tzinfo=UTC
    )


def test_as_datetime_keeps_explicit_timestamps() -> None:
    # Explicit times are never expanded even when end_of_day is requested.
    value = datetime(2024, 1, 2, 16, 0, tzinfo=UTC)
    assert _as_datetime(value, end_of_day=True) == value
    assert _as_datetime("2024-01-02T16:00:00", end_of_day=True) == value


def test_as_datetime_normalises_to_utc() -> None:
    assert _as_datetime("2024-01-02T16:00:00+01:00") == datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
