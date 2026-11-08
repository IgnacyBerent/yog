from __future__ import annotations

from yog.catalog import INSTRUMENTS, SERIES
from yog.enums import (
    BarInterval,
    FileKind,
    Frequency,
    IngestStatus,
    NewsFrequency,
    Provider,
    SeriesCode,
    SeriesKind,
    Symbol,
    Timeframe,
)


def test_series_enum_matches_catalogue() -> None:
    assert set(SeriesCode) == {spec.code for spec in SERIES}


def test_symbol_enum_matches_catalogue() -> None:
    assert set(Symbol) == {spec.symbol for spec in INSTRUMENTS}


def test_catalogue_uses_enum_types() -> None:
    assert all(isinstance(spec.provider, Provider) for spec in SERIES)
    assert all(isinstance(spec.code, SeriesCode) for spec in SERIES)
    assert all(isinstance(spec.frequency, Frequency) for spec in SERIES)
    assert all(isinstance(spec.kind, SeriesKind) for spec in SERIES)
    assert all(isinstance(spec.symbol, Symbol) for spec in INSTRUMENTS)


def test_timeframe_values_match_schema_constraint() -> None:
    assert {timeframe.value for timeframe in Timeframe} == {"1m", "5m"}


def test_bar_interval_values_are_stable() -> None:
    assert {interval.value for interval in BarInterval} == {
        "5m",
        "1h",
        "4h",
        "1d",
    }


def test_ingest_status_values_match_schema_constraint() -> None:
    assert {status.value for status in IngestStatus} == {
        "pending",
        "loading",
        "done",
        "failed",
        "skipped",
    }


def test_file_kind_values_are_stable() -> None:
    assert {kind.value for kind in FileKind} == {
        "observation",
        "daily_bar",
        "put_call",
        "bar",
        "news",
        "skipped",
    }


def test_news_frequency_sql_units() -> None:
    assert NewsFrequency.DAILY.sql_unit == "day"
    assert NewsFrequency.WEEKLY.sql_unit == "week"
    assert NewsFrequency.MONTHLY.sql_unit == "month"
