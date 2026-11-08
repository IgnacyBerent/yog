from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class Provider(StrEnum):
    """Data provider and raw-dataset root name."""

    ALPHA_VANTAGE = "alpha_vantage"
    FRED = "fred"


class Symbol(StrEnum):
    """ETF symbols covered by the price and put/call datasets."""

    SPY = "SPY"
    XLB = "XLB"
    XLE = "XLE"
    XLF = "XLF"
    XLI = "XLI"
    XLP = "XLP"
    XLU = "XLU"
    XLV = "XLV"
    XLY = "XLY"


class SeriesCode(StrEnum):
    """Scalar series codes tracked in the catalogue."""

    CPI = "CPI"
    FEDERAL_FUNDS_RATE = "FEDERAL_FUNDS_RATE"
    REAL_GDP = "REAL_GDP"
    DURABLES = "DURABLES"
    INFLATION = "INFLATION"
    RETAIL_SALES = "RETAIL_SALES"
    NONFARM_PAYROLL = "NONFARM_PAYROLL"
    UNEMPLOYMENT = "UNEMPLOYMENT"
    TREASURY_YIELD_3MONTH = "TREASURY_YIELD_3MONTH"
    TREASURY_YIELD_2YEAR = "TREASURY_YIELD_2YEAR"
    TREASURY_YIELD_5YEAR = "TREASURY_YIELD_5YEAR"
    TREASURY_YIELD_7YEAR = "TREASURY_YIELD_7YEAR"
    TREASURY_YIELD_10YEAR = "TREASURY_YIELD_10YEAR"
    TREASURY_YIELD_30YEAR = "TREASURY_YIELD_30YEAR"
    BRENT = "BRENT"
    WTI = "WTI"
    NATURAL_GAS = "NATURAL_GAS"
    COPPER = "COPPER"
    XAUUSD = "XAUUSD"
    XAGUSD = "XAGUSD"
    BAA10Y = "BAA10Y"
    DTWEXBGS = "DTWEXBGS"
    HOUST = "HOUST"
    ICSA = "ICSA"
    INDPRO = "INDPRO"
    NFCI = "NFCI"
    T5YIE = "T5YIE"
    UMCSENT = "UMCSENT"
    VIXCLS = "VIXCLS"


class Frequency(StrEnum):
    """Observation frequency of a scalar series."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SeriesKind(StrEnum):
    """Broad economic category of a scalar series."""

    MACRO = "macro"
    RATE = "rate"
    INDEX = "index"
    COMMODITY = "commodity"
    METAL = "metal"


class AssetClass(StrEnum):
    """Asset class of an instrument."""

    ETF = "etf"


class FileKind(StrEnum):
    """How a raw source file is ingested."""

    OBSERVATION = "observation"
    DAILY_BAR = "daily_bar"
    PUT_CALL = "put_call"
    BAR = "bar"
    NEWS = "news"
    SKIPPED = "skipped"


class IngestStatus(StrEnum):
    """Lifecycle state of a file in the ingest manifest."""

    PENDING = "pending"
    LOADING = "loading"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class Timeframe(StrEnum):
    """Bar interval stored in the database."""

    M1 = "1m"
    M5 = "5m"


class BarInterval(StrEnum):
    """Bar interval available from the client, derived if necessary."""

    M5 = "5m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class PutCallLevel(StrEnum):
    """Granularity of put/call data returned by the client."""

    SUMMARY = "summary"
    EXPIRATION = "expiration"


class NewsFrequency(StrEnum):
    """Aggregation frequency for news sentiment."""

    DAILY = "1D"
    WEEKLY = "1W"
    MONTHLY = "1M"

    @property
    def sql_unit(self) -> str:
        return _NEWS_SQL_UNITS[self]


class AvEndpoint(StrEnum):
    """Alpha Vantage folder names that are not scalar-series codes."""

    TIME_SERIES_INTRADAY = "TIME_SERIES_INTRADAY"
    TIME_SERIES_DAILY = "TIME_SERIES_DAILY"
    HISTORICAL_PUT_CALL_RATIO = "HISTORICAL_PUT_CALL_RATIO"
    NEWS_SENTIMENT = "NEWS_SENTIMENT"
    GOLD_SILVER_HISTORY = "GOLD_SILVER_HISTORY"
    TREASURY_YIELD = "TREASURY_YIELD"


class SeriesExtra(TypedDict, total=False):
    """Provider-specific metadata stored in ``series.extra``."""

    endpoint: str
    maturity: str
    nominal: str
    unit_note: str


_NEWS_SQL_UNITS: dict[NewsFrequency, str] = {
    NewsFrequency.DAILY: "day",
    NewsFrequency.WEEKLY: "week",
    NewsFrequency.MONTHLY: "month",
}

EASTERN_TZ = "America/New_York"
NEWS_TIME_FORMAT = "%Y%m%dT%H%M%S"
FALLBACK_NEWS_TITLE = "(untitled)"
CSV_SUFFIX = ".csv"
JSON_SUFFIX = ".json"
MISSING_VALUES: frozenset[str] = frozenset({"na", "n/a", "null", "none", "."})
