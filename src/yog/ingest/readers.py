from __future__ import annotations

import csv
import hashlib
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, TypedDict, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import orjson

from yog.enums import EASTERN_TZ, MISSING_VALUES, NEWS_TIME_FORMAT

if TYPE_CHECKING:
    from pathlib import Path

EASTERN = ZoneInfo(EASTERN_TZ)


class PutCallRecord(TypedDict):
    symbol: str | None
    trade_date: date
    full_chain_ratio: float | None
    expirations: list[tuple[date, float]]


class NewsTopic(TypedDict, total=False):
    """A topic tag attached to a news article."""

    topic: str
    relevance_score: str | float


class TickerSentiment(TypedDict, total=False):
    """Per-ticker sentiment attached to a news article."""

    ticker: str
    relevance_score: str | float
    ticker_sentiment_score: str | float
    ticker_sentiment_label: str


class NewsFeedArticle(TypedDict, total=False):
    """One article from an Alpha Vantage ``NEWS_SENTIMENT`` feed."""

    url: str
    time_published: str
    title: str
    summary: str
    source: str
    source_domain: str
    category_within_source: str
    banner_image: str
    overall_sentiment_score: str | float
    overall_sentiment_label: str
    topics: list[NewsTopic]
    ticker_sentiment: list[TickerSentiment]


TRACKING_PREFIXES = ("utm_", "gaa_", "mc_", "_hs", "oly_", "pk_", "mtm_", "hsa_")
TRACKING_PARAMS = {
    "_ga",
    "campaign",
    "campaign_id",
    "cmpid",
    "creative",
    "dclid",
    "fbclid",
    "gclid",
    "igshid",
    "ito",
    "mkt_tok",
    "msclkid",
    "ncid",
    "ns_campaign",
    "ns_fee",
    "ns_linkname",
    "ns_mchannel",
    "ns_source",
    "ocid",
    "rb_clickid",
    "s_cid",
    "scm",
    "si",
    "smid",
    "smtyp",
    "spm",
    "vero_id",
    "yclid",
}


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in MISSING_VALUES:
        return None
    return float(text)


def _int_or_none(value: object) -> int | None:
    number = _float_or_none(value)
    return None if number is None else int(number)


def read_value_csv(path: Path) -> list[tuple[date, float | None]]:
    """Read an Alpha Vantage or FRED ``timestamp,value`` CSV.

    FRED uses empty cells for holidays and other missing observations; those
    are preserved as ``None`` rather than dropped.
    """
    rows: list[tuple[date, float | None]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for line_no, row in enumerate(reader, start=2):
            if not row or not row[0].strip():
                continue
            if len(row) < 2:
                raise ValueError(f"{path}:{line_no}: expected 2 columns, got {row!r}")
            rows.append((date.fromisoformat(row[0].strip()), _float_or_none(row[1])))
    return rows


def read_ohlcv_csv(
    path: Path,
    *,
    intraday: bool,
    exchange_tz: str = EASTERN_TZ,
) -> list[tuple[datetime | date, float, float, float, float, int | None]]:
    """Read an Alpha Vantage OHLCV CSV.

    Intraday timestamps are interpreted in ``exchange_tz`` and converted to UTC.
    Daily rows keep a ``date``.
    """
    zone = ZoneInfo(exchange_tz)
    rows: list[tuple[datetime | date, float, float, float, float, int | None]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for line_no, row in enumerate(reader, start=2):
            if not row or not row[0].strip():
                continue
            if len(row) < 6:
                raise ValueError(f"{path}:{line_no}: expected 6 columns, got {row!r}")
            stamp = row[0].strip()
            if intraday:
                parsed = datetime.fromisoformat(stamp)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=zone)
                ts: datetime | date = parsed.astimezone(UTC)
            else:
                ts = date.fromisoformat(stamp)
            rows.append(
                (
                    ts,
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    _int_or_none(row[5]),
                )
            )
    return rows


def read_put_call_json(path: Path) -> PutCallRecord | None:
    """Parse one put/call ratio payload.

    Some snapshot files are empty objects (for example
    ``HISTORICAL_PUT_CALL_RATIO/SPY/2008-04-14.json``). Those carry no
    observation and are reported as ``None`` instead of failing the run.
    """
    payload = orjson.loads(path.read_bytes())
    if not isinstance(payload, dict) or "date" not in payload:
        return None
    expirations: list[tuple[date, float]] = []
    for item in payload.get("put_call_ratio_by_expiration") or []:
        if not isinstance(item, dict):
            continue
        raw_date = item.get("date")
        ratio = _float_or_none(item.get("value"))
        if raw_date and ratio is not None:
            expirations.append((date.fromisoformat(raw_date), ratio))
    return {
        "symbol": payload.get("symbol"),
        "trade_date": date.fromisoformat(payload["date"]),
        "full_chain_ratio": _float_or_none(payload.get("put_call_ratio_full_chain")),
        "expirations": expirations,
    }


def read_gold_silver_json(path: Path) -> list[tuple[date, float]]:
    payload = orjson.loads(path.read_bytes())
    if not isinstance(payload, dict):
        return []
    rows: list[tuple[date, float]] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        raw_date = item.get("date")
        price = _float_or_none(item.get("price"))
        if raw_date and price is not None:
            rows.append((date.fromisoformat(raw_date), price))
    return rows


def read_news_json(path: Path) -> list[NewsFeedArticle]:
    payload = orjson.loads(path.read_bytes())
    if not isinstance(payload, dict):
        return []
    feed = payload.get("feed")
    if not isinstance(feed, list):
        return []
    return [cast("NewsFeedArticle", item) for item in feed if isinstance(item, dict)]


def canonicalize_url(url: str) -> str:
    """Normalise an article URL and strip common tracking parameters."""
    url = url.strip()
    parts = urlsplit(url)
    query_pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PREFIXES):
            continue
        query_pairs.append((key, value))
    query_pairs.sort()
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            urlencode(query_pairs, doseq=True),
            "",
        )
    )


def url_hash(url: str) -> bytes:
    return hashlib.sha256(url.encode("utf-8")).digest()


def parse_news_time(value: str) -> datetime:
    """Parse Alpha Vantage's ``YYYYMMDDTHHMMSS`` US-Eastern timestamp."""
    parsed = datetime.strptime(value.strip(), NEWS_TIME_FORMAT)  # noqa: DTZ007 - provider timestamp is zone-less Eastern time
    return parsed.replace(tzinfo=EASTERN).astimezone(UTC)
