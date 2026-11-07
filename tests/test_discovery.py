from __future__ import annotations

from collections import Counter

import pytest

from yog.config import get_settings
from yog.enums import FileKind, Provider, SeriesCode, Symbol, Timeframe
from yog.ingest.discovery import classify, discover_files


def test_classify_intraday_bar() -> None:
    spec = classify("alpha_vantage/TIME_SERIES_INTRADAY/5min/SPY/2024-01.csv")

    assert spec is not None
    assert spec.kind is FileKind.BAR
    assert spec.dataset is Provider.ALPHA_VANTAGE
    assert spec.symbol is Symbol.SPY
    assert spec.timeframe is Timeframe.M5


def test_classify_one_minute_is_skipped() -> None:
    spec = classify("alpha_vantage/TIME_SERIES_INTRADAY/1min/SPY/2024-01.csv")

    assert spec is not None
    assert spec.kind is FileKind.SKIPPED
    assert spec.timeframe is Timeframe.M1


def test_classify_treasury_csv() -> None:
    spec = classify("alpha_vantage/TREASURY_YIELD/daily/10year.csv")

    assert spec is not None
    assert spec.kind is FileKind.OBSERVATION
    assert spec.code is SeriesCode.TREASURY_YIELD_10YEAR


def test_classify_unknown_symbol_is_ignored() -> None:
    assert classify("alpha_vantage/TIME_SERIES_INTRADAY/5min/UNKNOWN/2024-01.csv") is None


def test_discover_files_counts_match_snapshot() -> None:
    data_root = get_settings().data_root
    if not data_root.exists():
        pytest.skip("raw dataset is not available")

    specs = discover_files(data_root)
    counts = Counter((spec.kind, spec.dataset) for spec in specs)

    assert len(specs) == 58_093
    assert counts == {
        (FileKind.BAR, Provider.ALPHA_VANTAGE): 2_898,
        (FileKind.DAILY_BAR, Provider.ALPHA_VANTAGE): 1,
        (FileKind.NEWS, Provider.ALPHA_VANTAGE): 9_679,
        (FileKind.OBSERVATION, Provider.ALPHA_VANTAGE): 20,
        (FileKind.OBSERVATION, Provider.FRED): 9,
        (FileKind.PUT_CALL, Provider.ALPHA_VANTAGE): 42_588,
        (FileKind.SKIPPED, Provider.ALPHA_VANTAGE): 2_898,
    }
