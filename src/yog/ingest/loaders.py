from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from yog.enums import AvEndpoint, FileKind, Frequency, Provider, SeriesCode, Symbol, Timeframe
from yog.ingest.copy import copy_rows
from yog.ingest.readers import (
    read_gold_silver_json,
    read_ohlcv_csv,
    read_put_call_json,
    read_value_csv,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from psycopg import Connection

    from yog.ingest.discovery import FileSpec
    from yog.ingest.news import ArticleRow, NewsFileResult, TickerRow, TopicRow

ObservationRow = tuple[int, date, float | None]
DailyBarRow = tuple[int, date, float, float, float, float, int | None]
BarRow = tuple[int, str, datetime, float, float, float, float, int | None]
PutCallSummaryRow = tuple[int, date, float | None]
PutCallExpirationRow = tuple[int, date, date, float]


@dataclass(frozen=True, slots=True)
class LoaderContext:
    data_root: Path
    series_ids: dict[tuple[Provider, SeriesCode], int]
    instrument_ids: dict[Symbol, int]

    def series_id(self, provider: Provider | None, code: SeriesCode | None) -> int:
        if provider is None or code is None:
            raise ValueError("series file is missing provider or code")
        try:
            return self.series_ids[(provider, code)]
        except KeyError as exc:
            raise KeyError(f"unknown series {provider.value}:{code.value}") from exc

    def instrument_id(self, symbol: Symbol | None) -> int:
        if symbol is None:
            raise ValueError("instrument file is missing a symbol")
        try:
            return self.instrument_ids[symbol]
        except KeyError as exc:
            raise KeyError(f"unknown instrument {symbol.value}") from exc


def _path(ctx: LoaderContext, spec: FileSpec) -> Path:
    return ctx.data_root / spec.path


def load_file(conn: Connection, spec: FileSpec, ctx: LoaderContext) -> int:
    match spec.kind:
        case FileKind.OBSERVATION:
            return _load_observation(conn, spec, ctx)
        case FileKind.DAILY_BAR:
            return _load_daily_bar(conn, spec, ctx)
        case FileKind.BAR:
            return _load_bar(conn, spec, ctx)
        case FileKind.PUT_CALL:
            return _load_put_call(conn, spec, ctx)
    raise ValueError(f"no loader for kind {spec.kind.value!r}")


def _load_observation(conn: Connection, spec: FileSpec, ctx: LoaderContext) -> int:
    series_id = ctx.series_id(spec.provider, spec.code)
    path = _path(ctx, spec)
    rows: Sequence[tuple[date, float | None]]
    if (
        path.parent.name == Frequency.DAILY.value
        and path.parent.parent.name == AvEndpoint.GOLD_SILVER_HISTORY.value
    ):
        rows = read_gold_silver_json(path)
    else:
        rows = read_value_csv(path)
    payload: Iterable[ObservationRow] = ((series_id, obs_date, value) for obs_date, value in rows)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
                CREATE TEMP TABLE stg_observations (
                    series_id integer NOT NULL,
                    obs_date date NOT NULL,
                    value double precision
                ) ON COMMIT DROP
                """
        )
        count = copy_rows(
            cur,
            "stg_observations",
            ("series_id", "obs_date", "value"),
            payload,
        )
        cur.execute(
            """
                INSERT INTO observations (series_id, obs_date, value)
                SELECT series_id, obs_date, value FROM stg_observations
                ON CONFLICT (series_id, obs_date) DO NOTHING
                """
        )
    return count


def _load_daily_bar(conn: Connection, spec: FileSpec, ctx: LoaderContext) -> int:
    instrument_id = ctx.instrument_id(spec.symbol)
    rows = read_ohlcv_csv(_path(ctx, spec), intraday=False)
    payload: Iterable[DailyBarRow] = (
        (instrument_id, trade_date, open_, high, low, close, volume)
        for trade_date, open_, high, low, close, volume in rows
    )
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
                CREATE TEMP TABLE stg_daily_bars (
                    instrument_id smallint NOT NULL,
                    trade_date date NOT NULL,
                    open double precision NOT NULL,
                    high double precision NOT NULL,
                    low double precision NOT NULL,
                    close double precision NOT NULL,
                    volume bigint
                ) ON COMMIT DROP
                """
        )
        count = copy_rows(
            cur,
            "stg_daily_bars",
            (
                "instrument_id",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ),
            payload,
        )
        cur.execute(
            """
                INSERT INTO daily_bars
                    (instrument_id, trade_date, open, high, low, close, volume)
                SELECT instrument_id, trade_date, open, high, low, close, volume
                FROM stg_daily_bars
                ON CONFLICT (instrument_id, trade_date) DO NOTHING
                """
        )
    return count


def _load_bar(conn: Connection, spec: FileSpec, ctx: LoaderContext) -> int:
    instrument_id = ctx.instrument_id(spec.symbol)
    timeframe = spec.timeframe or Timeframe.M5
    rows = read_ohlcv_csv(_path(ctx, spec), intraday=True)
    payload: Iterable[BarRow] = (
        (instrument_id, timeframe.value, ts, open_, high, low, close, volume)
        for ts, open_, high, low, close, volume in rows
        if isinstance(ts, datetime)
    )
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
                CREATE TEMP TABLE stg_bars (
                    instrument_id smallint NOT NULL,
                    timeframe text NOT NULL,
                    ts timestamptz NOT NULL,
                    open double precision NOT NULL,
                    high double precision NOT NULL,
                    low double precision NOT NULL,
                    close double precision NOT NULL,
                    volume bigint
                ) ON COMMIT DROP
                """
        )
        count = copy_rows(
            cur,
            "stg_bars",
            (
                "instrument_id",
                "timeframe",
                "ts",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ),
            payload,
        )
        cur.execute(
            """
                INSERT INTO bars
                    (instrument_id, timeframe, ts, open, high, low, close, volume)
                SELECT instrument_id, timeframe, ts, open, high, low, close, volume
                FROM stg_bars
                ON CONFLICT (instrument_id, timeframe, ts) DO NOTHING
                """
        )
    return count


def _load_put_call(conn: Connection, spec: FileSpec, ctx: LoaderContext) -> int:
    instrument_id = ctx.instrument_id(spec.symbol)
    record = read_put_call_json(_path(ctx, spec))
    if record is None:
        return 0
    summary: PutCallSummaryRow = (
        instrument_id,
        record["trade_date"],
        record["full_chain_ratio"],
    )
    expiration_rows: list[PutCallExpirationRow] = [
        (instrument_id, record["trade_date"], expiration, ratio)
        for expiration, ratio in record["expirations"]
    ]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
                CREATE TEMP TABLE stg_pc_summary (
                    instrument_id smallint NOT NULL,
                    trade_date date NOT NULL,
                    full_chain_ratio double precision
                ) ON COMMIT DROP
                """
        )
        cur.execute(
            """
                CREATE TEMP TABLE stg_pc_expirations (
                    instrument_id smallint NOT NULL,
                    trade_date date NOT NULL,
                    expiration_date date NOT NULL,
                    ratio double precision NOT NULL
                ) ON COMMIT DROP
                """
        )
        copy_rows(
            cur,
            "stg_pc_summary",
            ("instrument_id", "trade_date", "full_chain_ratio"),
            [summary],
        )
        copy_rows(
            cur,
            "stg_pc_expirations",
            ("instrument_id", "trade_date", "expiration_date", "ratio"),
            expiration_rows,
        )
        cur.execute(
            """
                INSERT INTO put_call_summaries
                    (instrument_id, trade_date, full_chain_ratio)
                SELECT instrument_id, trade_date, full_chain_ratio
                FROM stg_pc_summary
                ON CONFLICT (instrument_id, trade_date) DO NOTHING
                """
        )
        cur.execute(
            """
                INSERT INTO put_call_expirations
                    (instrument_id, trade_date, expiration_date, ratio)
                SELECT instrument_id, trade_date, expiration_date, ratio
                FROM stg_pc_expirations
                ON CONFLICT (instrument_id, trade_date, expiration_date)
                DO NOTHING
                """
        )
    return 1 + len(expiration_rows)


def load_news_batch(conn: Connection, results: list[NewsFileResult]) -> int:
    """Insert a batch of parsed news files in one transaction."""
    articles: list[ArticleRow] = []
    topics: list[TopicRow] = []
    tickers: list[TickerRow] = []
    for result in results:
        if result.error:
            continue
        articles.extend(result.articles)
        topics.extend(result.topics)
        tickers.extend(result.tickers)

    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
                CREATE TEMP TABLE stg_news_articles (
                    url text NOT NULL,
                    canonical_url text NOT NULL,
                    url_hash bytea NOT NULL,
                    title text NOT NULL,
                    summary text,
                    published_at timestamptz NOT NULL,
                    source text,
                    source_domain text,
                    category_within_source text,
                    banner_image text,
                    overall_sentiment_score double precision,
                    overall_sentiment_label text
                ) ON COMMIT DROP
                """
        )
        cur.execute(
            """
                CREATE TEMP TABLE stg_news_topics (
                    url_hash bytea NOT NULL,
                    topic text NOT NULL,
                    relevance_score double precision
                ) ON COMMIT DROP
                """
        )
        cur.execute(
            """
                CREATE TEMP TABLE stg_news_tickers (
                    url_hash bytea NOT NULL,
                    ticker text NOT NULL,
                    relevance_score double precision,
                    sentiment_score double precision,
                    sentiment_label text
                ) ON COMMIT DROP
                """
        )
        copy_rows(
            cur,
            "stg_news_articles",
            (
                "url",
                "canonical_url",
                "url_hash",
                "title",
                "summary",
                "published_at",
                "source",
                "source_domain",
                "category_within_source",
                "banner_image",
                "overall_sentiment_score",
                "overall_sentiment_label",
            ),
            articles,
        )
        copy_rows(
            cur,
            "stg_news_topics",
            ("url_hash", "topic", "relevance_score"),
            topics,
        )
        copy_rows(
            cur,
            "stg_news_tickers",
            (
                "url_hash",
                "ticker",
                "relevance_score",
                "sentiment_score",
                "sentiment_label",
            ),
            tickers,
        )
        cur.execute(
            """
                INSERT INTO news_articles
                    (url, canonical_url, url_hash, title, summary, published_at,
                     source, source_domain, category_within_source, banner_image,
                     overall_sentiment_score, overall_sentiment_label)
                SELECT url, canonical_url, url_hash, title, summary, published_at,
                       source, source_domain, category_within_source, banner_image,
                       overall_sentiment_score, overall_sentiment_label
                FROM stg_news_articles
                ON CONFLICT (url_hash) DO NOTHING
                """
        )
        cur.execute(
            """
                INSERT INTO news_article_topics
                    (article_id, topic, relevance_score)
                SELECT a.id, s.topic, s.relevance_score
                FROM stg_news_topics AS s
                JOIN news_articles AS a ON a.url_hash = s.url_hash
                ON CONFLICT (article_id, topic) DO NOTHING
                """
        )
        cur.execute(
            """
                INSERT INTO news_article_tickers
                    (article_id, ticker, relevance_score, sentiment_score,
                     sentiment_label)
                SELECT a.id, s.ticker, s.relevance_score, s.sentiment_score,
                       s.sentiment_label
                FROM stg_news_tickers AS s
                JOIN news_articles AS a ON a.url_hash = s.url_hash
                ON CONFLICT (article_id, ticker) DO NOTHING
                """
        )
    return len(articles)
