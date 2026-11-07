from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from yog.ingest.readers import (
    canonicalize_url,
    parse_news_time,
    read_news_json,
    read_ohlcv_csv,
    read_put_call_json,
    read_value_csv,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_read_value_csv_preserves_missing_values(tmp_path: Path) -> None:
    path = tmp_path / "series.csv"
    path.write_text(
        "observation_date,VALUE\n2024-01-01,1.5\n2024-01-02,\n2024-01-03,.\n",
        encoding="utf-8",
    )

    assert read_value_csv(path) == [
        (date(2024, 1, 1), 1.5),
        (date(2024, 1, 2), None),
        (date(2024, 1, 3), None),
    ]


def test_read_ohlcv_csv_daily(tmp_path: Path) -> None:
    path = tmp_path / "daily.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n2024-01-03,100,110,90,105,1000\n",
        encoding="utf-8",
    )

    assert read_ohlcv_csv(path, intraday=False) == [
        (date(2024, 1, 3), 100.0, 110.0, 90.0, 105.0, 1000)
    ]


def test_read_ohlcv_csv_intraday_converts_eastern_to_utc(tmp_path: Path) -> None:
    path = tmp_path / "intraday.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-01-15 09:30:00,1,2,0.5,1.5,10\n"
        "2024-07-15 09:30:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    rows = read_ohlcv_csv(path, intraday=True)

    # Standard time (UTC-5) and daylight time (UTC-4).
    assert rows[0][0] == datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
    assert rows[1][0] == datetime(2024, 7, 15, 13, 30, tzinfo=UTC)


def test_read_put_call_json_empty_payload_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")

    assert read_put_call_json(path) is None


def test_read_put_call_json_skips_null_expiration_values(tmp_path: Path) -> None:
    path = tmp_path / "pc.json"
    path.write_text(
        """
        {
          "symbol": "SPY",
          "date": "2024-01-03",
          "put_call_ratio_full_chain": "0.87",
          "put_call_ratio_by_expiration": [
            {"date": "2024-01-05", "value": "0.82"},
            {"date": "2024-01-12", "value": null}
          ]
        }
        """,
        encoding="utf-8",
    )

    record = read_put_call_json(path)

    assert record is not None
    assert record["trade_date"] == date(2024, 1, 3)
    assert record["full_chain_ratio"] == pytest.approx(0.87)
    assert record["expirations"] == [(date(2024, 1, 5), 0.82)]


def test_read_news_json_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "feed.json"
    path.write_text("[]", encoding="utf-8")

    assert read_news_json(path) == []


def test_canonicalize_url_strips_tracking_and_fragment() -> None:
    url = "HTTPS://Example.COM/story?id=7&utm_source=x&utm_medium=y&fbclid=abc&b=2&a=1#section"

    assert canonicalize_url(url) == "https://example.com/story?a=1&b=2&id=7"


def test_parse_news_time_is_eastern() -> None:
    assert parse_news_time("20240115T093000") == datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
    assert parse_news_time("20240715T093000") == datetime(2024, 7, 15, 13, 30, tzinfo=UTC)
