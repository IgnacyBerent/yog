from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Self

import pandas as pd
from sqlalchemy import Engine, create_engine, select, text

from yog.aggregation import bucket_minutes, early_close_dates
from yog.config import get_settings
from yog.db.models import (
    Bar,
    DailyBar,
    Instrument,
    Observation,
    PutCallExpiration,
    PutCallSummary,
    Series,
)
from yog.enums import (
    BarInterval,
    NewsFrequency,
    Provider,
    PutCallLevel,
    Timeframe,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from sqlalchemy.engine import Connection as SaConnection
    from sqlalchemy.sql import Selectable

    SqlParam = str | bytes | date | datetime | float | int | Sequence[str] | None
    SqlParamValue = (
        str | bytes | date | datetime | float | int | Sequence[str] | Sequence[date] | None
    )


def _as_list(value: str | Sequence[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def _as_date(value: str | date | datetime | None) -> date | None:
    """Coerce a boundary into a real ``date`` for typed SQL comparisons."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


def _as_datetime(
    value: str | date | datetime | None, *, end_of_day: bool = False
) -> datetime | None:
    """Coerce a boundary into a UTC-aware ``datetime``.

    Date-only strings and ``date`` objects are expanded to the start of the day,
    or to the final microsecond of the day when ``end_of_day`` is set.
    """
    if value is None:
        return None
    date_only = isinstance(value, date) and not isinstance(value, datetime)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        date_only = len(text) <= 10
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = datetime.combine(date.fromisoformat(text), time.min)
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    if end_of_day and date_only:
        parsed = datetime.combine(parsed.date(), time.max, tzinfo=UTC)
    return parsed


class Client:
    """Synchronous read client for the PostgreSQL dataset.

    All methods return a ``pandas.DataFrame``.
    """

    def __init__(
        self,
        database_url: str | None = None,
        *,
        engine: Engine | None = None,
    ) -> None:
        self.engine = engine or create_engine(
            database_url or get_settings().database_url,
            pool_pre_ping=True,
            future=True,
        )

    def close(self) -> None:
        self.engine.dispose()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _read(stmt: Selectable, conn: SaConnection) -> pd.DataFrame:
        return pd.read_sql(stmt, conn)

    # ------------------------------------------------------------------ catalogue
    def catalog(self) -> pd.DataFrame:
        """Return the series catalogue."""
        stmt = select(
            Series.provider,
            Series.code,
            Series.name,
            Series.description,
            Series.frequency,
            Series.unit,
            Series.kind,
            Series.source_url,
            Series.release_lag_days,
        ).order_by(Series.provider, Series.code)
        with self.engine.connect() as conn:
            return self._read(stmt, conn)

    def instruments(self) -> pd.DataFrame:
        """Return the instrument catalogue."""
        stmt = select(
            Instrument.symbol,
            Instrument.name,
            Instrument.asset_class,
            Instrument.currency,
            Instrument.exchange_tz,
        ).order_by(Instrument.symbol)
        with self.engine.connect() as conn:
            return self._read(stmt, conn)

    # --------------------------------------------------------------- observations
    def series(
        self,
        codes: str | Sequence[str],
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        *,
        provider: Provider | str | None = None,
        wide: bool = False,
    ) -> pd.DataFrame:
        """Return scalar observations for one or more series codes.

        With ``wide=True`` the result is indexed by observation date and has one
        column per series code.
        """
        wanted = _as_list(codes)
        if not wanted:
            raise ValueError("at least one series code is required")
        stmt = (
            select(
                Series.provider,
                Series.code,
                Observation.obs_date,
                Observation.value,
            )
            .join(Observation, Observation.series_id == Series.id)
            .where(Series.code.in_(wanted))
            .order_by(Observation.obs_date, Series.code)
        )
        if provider is not None:
            stmt = stmt.where(Series.provider == Provider(provider).value)
        start_date = _as_date(start)
        end_date = _as_date(end)
        if start_date is not None:
            stmt = stmt.where(Observation.obs_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(Observation.obs_date <= end_date)
        with self.engine.connect() as conn:
            df = self._read(stmt, conn)
        if df.empty:
            df = pd.DataFrame(columns=["provider", "code", "obs_date", "value"])
        else:
            df["obs_date"] = pd.to_datetime(df["obs_date"])
        if wide:
            wide_df = df.pivot_table(
                index="obs_date", columns="code", values="value", aggfunc="last"
            ).sort_index()
            wide_df.columns.name = None
            return wide_df
        return df

    # ------------------------------------------------------------------ prices
    def daily_bars(
        self,
        symbols: str | Sequence[str],
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
    ) -> pd.DataFrame:
        wanted = _as_list(symbols)
        if not wanted:
            raise ValueError("at least one symbol is required")
        stmt = (
            select(
                Instrument.symbol,
                DailyBar.trade_date,
                DailyBar.open,
                DailyBar.high,
                DailyBar.low,
                DailyBar.close,
                DailyBar.volume,
            )
            .join(DailyBar, DailyBar.instrument_id == Instrument.id)
            .where(Instrument.symbol.in_(wanted))
            .order_by(DailyBar.trade_date, Instrument.symbol)
        )
        if start is not None:
            stmt = stmt.where(DailyBar.trade_date >= _as_date(start))
        if end is not None:
            stmt = stmt.where(DailyBar.trade_date <= _as_date(end))
        with self.engine.connect() as conn:
            df = self._read(stmt, conn)
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        present = set(df["symbol"].unique()) if not df.empty else set()
        missing = [symbol for symbol in wanted if symbol not in present]
        if missing:
            derived = self._derived_daily_bars(missing, start, end)
            df = pd.concat([df, derived], ignore_index=True)
        return df.sort_values(["trade_date", "symbol"]).reset_index(drop=True)

    def bars(
        self,
        symbols: str | Sequence[str],
        *,
        timeframe: Timeframe | str = Timeframe.M5,
        start: str | date | datetime,
        end: str | date | datetime,
        max_rows: int = 2_000_000,
    ) -> pd.DataFrame:
        """Return intraday bars.

        A start and end are required to prevent accidentally loading millions of
        rows into memory.
        """
        interval = Timeframe(timeframe)
        wanted = _as_list(symbols)
        if not wanted:
            raise ValueError("at least one symbol is required")
        start_ts = _as_datetime(start)
        end_ts = _as_datetime(end, end_of_day=True)
        stmt = (
            select(
                Instrument.symbol,
                Bar.timeframe,
                Bar.ts,
                Bar.open,
                Bar.high,
                Bar.low,
                Bar.close,
                Bar.volume,
            )
            .join(Bar, Bar.instrument_id == Instrument.id)
            .where(
                Instrument.symbol.in_(wanted),
                Bar.timeframe == interval.value,
                Bar.ts >= start_ts,
                Bar.ts <= end_ts,
            )
            .order_by(Bar.ts, Instrument.symbol)
            .limit(max_rows + 1)
        )
        with self.engine.connect() as conn:
            df = self._read(stmt, conn)
        if len(df) > max_rows:
            raise ValueError(f"query returned more than max_rows={max_rows}; narrow the date range")
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df

    def aggregated_bars(
        self,
        symbols: str | Sequence[str],
        *,
        interval: BarInterval | str,
        start: str | date | datetime,
        end: str | date | datetime,
    ) -> pd.DataFrame:
        """Return bars aggregated to a derived interval."""
        resolved = BarInterval(interval)
        wanted = _as_list(symbols)
        if not wanted:
            raise ValueError("at least one symbol is required")
        if resolved is BarInterval.M5:
            return self.bars(
                wanted,
                timeframe=Timeframe.M5,
                start=start,
                end=end,
            )
        if resolved is BarInterval.D1:
            daily = self.daily_bars(wanted, start, end)
            daily["timeframe"] = resolved.value
            daily["ts"] = pd.to_datetime(daily["trade_date"], utc=True)
            return daily[
                [
                    "symbol",
                    "timeframe",
                    "ts",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ]
        start_ts = _as_datetime(start)
        end_ts = _as_datetime(end, end_of_day=True)
        if start_ts is None or end_ts is None:
            raise ValueError("start and end are required")
        early = early_close_dates(
            start_ts.date() - timedelta(days=1),
            end_ts.date() + timedelta(days=1),
        )
        params: dict[str, SqlParamValue] = {
            "symbols": wanted,
            "timeframe": Timeframe.M5.value,
            "interval": resolved.value,
            "bucket_minutes": bucket_minutes(resolved),
            "start_ts": start_ts,
            "end_ts": end_ts,
        }
        early_clause = "FALSE"
        if early:
            early_clause = "local_ts::date = ANY(:early_close_dates)"
            params["early_close_dates"] = list(early)
        sql = f"""
        WITH filtered AS (
            SELECT i.symbol,
                   (b.ts AT TIME ZONE 'America/New_York') AS local_ts,
                   b.open, b.high, b.low, b.close, b.volume
            FROM bars b
            JOIN instruments i ON i.id = b.instrument_id
            WHERE i.symbol = ANY(:symbols)
              AND b.timeframe = :timeframe
              AND b.ts >= :start_ts
              AND b.ts <= :end_ts
        ),
        session_bars AS (
            SELECT *,
                   local_ts::date AS trade_date,
                   FLOOR(
                       EXTRACT(EPOCH FROM (local_ts::time - TIME '09:30'))
                       / (:bucket_minutes * 60.0)
                   )::int AS bucket_index
            FROM filtered
            WHERE local_ts::time >= TIME '09:30'
              AND local_ts::time < CASE
                  WHEN {early_clause} THEN TIME '13:00'
                  ELSE TIME '16:00'
              END
        ),
        bucketed AS (
            SELECT *,
                   trade_date + TIME '09:30'
                   + (bucket_index * :bucket_minutes) * INTERVAL '1 minute'
                   AS bucket_start
            FROM session_bars
        )
        SELECT symbol,
               :interval AS timeframe,
               bucket_start AT TIME ZONE 'America/New_York' AS ts,
               (ARRAY_AGG(open ORDER BY local_ts))[1] AS open,
               MAX(high) AS high,
               MIN(low) AS low,
               (ARRAY_AGG(close ORDER BY local_ts DESC))[1] AS close,
               SUM(volume) AS volume
        FROM bucketed
        GROUP BY symbol, bucket_start
        ORDER BY ts, symbol
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params=params)
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df

    def _derived_daily_bars(
        self,
        symbols: Sequence[str],
        start: str | date | datetime | None,
        end: str | date | datetime | None,
    ) -> pd.DataFrame:
        params: dict[str, SqlParamValue] = {
            "symbols": list(symbols),
            "timeframe": Timeframe.M5.value,
        }
        start_clause = ""
        end_clause = ""
        if start is not None:
            start_clause = "AND b.ts >= :start_ts"
            params["start_ts"] = _as_datetime(start)
        if end is not None:
            end_clause = "AND b.ts <= :end_ts"
            params["end_ts"] = _as_datetime(end, end_of_day=True)
        early = early_close_dates(date(2006, 1, 1), date(2100, 1, 1))
        early_clause = "FALSE"
        if early:
            early_clause = "local_ts::date = ANY(:early_close_dates)"
            params["early_close_dates"] = list(early)
        sql = f"""
        WITH filtered AS (
            SELECT i.symbol,
                   (b.ts AT TIME ZONE 'America/New_York') AS local_ts,
                   b.open, b.high, b.low, b.close, b.volume
            FROM bars b
            JOIN instruments i ON i.id = b.instrument_id
            WHERE i.symbol = ANY(:symbols)
              AND b.timeframe = :timeframe
              {start_clause}
              {end_clause}
        ),
        session_bars AS (
            SELECT *,
                   local_ts::date AS trade_date
            FROM filtered
            WHERE local_ts::time >= TIME '09:30'
              AND local_ts::time < CASE
                  WHEN {early_clause} THEN TIME '13:00'
                  ELSE TIME '16:00'
              END
        )
        SELECT symbol,
               trade_date,
               (ARRAY_AGG(open ORDER BY local_ts))[1] AS open,
               MAX(high) AS high,
               MIN(low) AS low,
               (ARRAY_AGG(close ORDER BY local_ts DESC))[1] AS close,
               SUM(volume) AS volume
        FROM session_bars
        GROUP BY symbol, trade_date
        ORDER BY trade_date, symbol
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params=params)
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df

    def iter_bars(
        self,
        symbols: str | Sequence[str],
        *,
        timeframe: Timeframe | str = Timeframe.M5,
        start: str | date | datetime,
        end: str | date | datetime,
        batch_size: int = 100_000,
    ) -> Iterator[pd.DataFrame]:
        """Stream intraday bars in batches."""
        interval = Timeframe(timeframe)
        wanted = _as_list(symbols)
        if not wanted:
            raise ValueError("at least one symbol is required")
        start_ts = _as_datetime(start)
        end_ts = _as_datetime(end, end_of_day=True)
        stmt = (
            select(
                Instrument.symbol,
                Bar.timeframe,
                Bar.ts,
                Bar.open,
                Bar.high,
                Bar.low,
                Bar.close,
                Bar.volume,
            )
            .join(Bar, Bar.instrument_id == Instrument.id)
            .where(
                Instrument.symbol.in_(wanted),
                Bar.timeframe == interval.value,
                Bar.ts >= start_ts,
                Bar.ts <= end_ts,
            )
            .order_by(Bar.ts, Instrument.symbol)
            .execution_options(yield_per=batch_size)
        )
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            for partition in result.mappings().partitions():
                df = pd.DataFrame(partition, columns=list(result.keys()))
                if not df.empty:
                    df["ts"] = pd.to_datetime(df["ts"], utc=True)
                yield df

    def _put_call_summary(
        self,
        wanted: list[str],
        start: str | date | datetime | None,
        end: str | date | datetime | None,
    ) -> pd.DataFrame:
        stmt = (
            select(
                Instrument.symbol,
                PutCallSummary.trade_date,
                PutCallSummary.full_chain_ratio,
            )
            .join(
                PutCallSummary,
                PutCallSummary.instrument_id == Instrument.id,
            )
            .where(Instrument.symbol.in_(wanted))
            .order_by(PutCallSummary.trade_date, Instrument.symbol)
        )
        if start is not None:
            stmt = stmt.where(PutCallSummary.trade_date >= _as_date(start))
        if end is not None:
            stmt = stmt.where(PutCallSummary.trade_date <= _as_date(end))
        with self.engine.connect() as conn:
            df = self._read(stmt, conn)
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df

    def _put_call_expiration(
        self,
        wanted: list[str],
        start: str | date | datetime | None,
        end: str | date | datetime | None,
    ) -> pd.DataFrame:
        stmt = (
            select(
                Instrument.symbol,
                PutCallExpiration.trade_date,
                PutCallExpiration.expiration_date,
                PutCallExpiration.ratio,
            )
            .join(
                PutCallExpiration,
                PutCallExpiration.instrument_id == Instrument.id,
            )
            .where(Instrument.symbol.in_(wanted))
            .order_by(
                PutCallExpiration.trade_date,
                PutCallExpiration.expiration_date,
                Instrument.symbol,
            )
        )
        if start is not None:
            stmt = stmt.where(PutCallExpiration.trade_date >= _as_date(start))
        if end is not None:
            stmt = stmt.where(PutCallExpiration.trade_date <= _as_date(end))
        with self.engine.connect() as conn:
            df = self._read(stmt, conn)
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df["expiration_date"] = pd.to_datetime(df["expiration_date"])
        return df

    def put_call(
        self,
        symbols: str | Sequence[str],
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        *,
        level: PutCallLevel | str = PutCallLevel.SUMMARY,
    ) -> pd.DataFrame:
        """Return put/call ratios at summary or per-expiration granularity."""
        granularity = PutCallLevel(level)
        wanted = _as_list(symbols)
        if not wanted:
            raise ValueError("at least one symbol is required")
        if granularity is PutCallLevel.SUMMARY:
            return self._put_call_summary(wanted, start, end)
        return self._put_call_expiration(wanted, start, end)

    # -------------------------------------------------------------------- news
    def news(
        self,
        *,
        topics: str | Sequence[str] | None = None,
        tickers: str | Sequence[str] | None = None,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        min_relevance: float = 0.0,
        limit: int = 10_000,
    ) -> pd.DataFrame:
        topic_list = _as_list(topics)
        ticker_list = _as_list(tickers)
        conditions = []
        params: dict[str, SqlParam] = {"limit": limit}
        if start is not None:
            conditions.append("a.published_at >= :start")
            params["start"] = _as_datetime(start)
        if end is not None:
            conditions.append("a.published_at <= :end")
            params["end"] = _as_datetime(end, end_of_day=True)
        if topic_list:
            conditions.append(
                """
                EXISTS (
                    SELECT 1 FROM news_article_topics t
                    WHERE t.article_id = a.id
                      AND t.topic = ANY(:topics)
                      AND coalesce(t.relevance_score, 0) >= :min_relevance
                )
                """
            )
            params["topics"] = topic_list
        if ticker_list:
            conditions.append(
                """
                EXISTS (
                    SELECT 1 FROM news_article_tickers ts
                    WHERE ts.article_id = a.id
                      AND ts.ticker = ANY(:tickers)
                      AND coalesce(ts.relevance_score, 0) >= :min_relevance
                )
                """
            )
            params["tickers"] = ticker_list
        if topic_list or ticker_list:
            params["min_relevance"] = min_relevance
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = text(
            f"""
            SELECT a.id, a.published_at, a.title, a.url, a.canonical_url,
                   a.source, a.source_domain, a.overall_sentiment_score,
                   a.overall_sentiment_label
            FROM news_articles a
            {where}
            ORDER BY a.published_at DESC
            LIMIT :limit
            """
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
        if not df.empty:
            df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
        return df

    def news_sentiment(
        self,
        tickers: str | Sequence[str],
        *,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        frequency: NewsFrequency | str = NewsFrequency.DAILY,
        min_relevance: float = 0.0,
    ) -> pd.DataFrame:
        wanted = _as_list(tickers)
        if not wanted:
            raise ValueError("at least one ticker is required")
        freq = NewsFrequency(frequency)
        conditions = ["ts.ticker = ANY(:tickers)"]
        params: dict[str, SqlParam] = {
            "tickers": wanted,
            "unit": freq.sql_unit,
            "min_relevance": min_relevance,
        }
        if start is not None:
            conditions.append("a.published_at >= :start")
            params["start"] = _as_datetime(start)
        if end is not None:
            conditions.append("a.published_at <= :end")
            params["end"] = _as_datetime(end, end_of_day=True)
        query = text(
            f"""
            SELECT ts.ticker,
                   date_trunc(:unit, a.published_at)::date AS bucket,
                   count(*) AS article_count,
                   avg(ts.sentiment_score) AS avg_sentiment,
                   avg(ts.relevance_score) AS avg_relevance
            FROM news_articles a
            JOIN news_article_tickers ts ON ts.article_id = a.id
            WHERE {" AND ".join(conditions)}
              AND coalesce(ts.relevance_score, 0) >= :min_relevance
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
        if not df.empty:
            df["bucket"] = pd.to_datetime(df["bucket"])
        return df

    # ------------------------------------------------------------------- panels
    def panel(
        self,
        symbols: str | Sequence[str],
        *,
        start: str | date | datetime,
        end: str | date | datetime,
        macro: Sequence[str] | None = None,
        news_tickers: Sequence[str] | None = None,
        frequency: NewsFrequency | str = NewsFrequency.DAILY,
    ) -> pd.DataFrame:
        """Build a daily feature panel from daily bars, macro series and news.

        Macro observations are joined with a backward ``merge_asof``, so a row
        only sees observations dated on or before that day. This does *not*
        correct for data revisions: the snapshot stores observation dates, not
        real-time release vintages.
        """
        freq = NewsFrequency(frequency)
        if freq is not NewsFrequency.DAILY:
            raise ValueError("panel currently supports frequency='1D' only")
        symbols_list = _as_list(symbols) or []
        bars_df = self.daily_bars(symbols_list, start, end)
        if bars_df.empty:
            raise ValueError("no daily bars found for the requested symbols")

        if len(symbols_list) == 1:
            base = bars_df.drop(columns=["symbol"]).rename(columns={"trade_date": "date"})
        else:
            close = bars_df.pivot(index="trade_date", columns="symbol", values="close")
            close.columns = [f"{symbol}_close" for symbol in close.columns]
            volume = bars_df.pivot(index="trade_date", columns="symbol", values="volume")
            volume.columns = [f"{symbol}_volume" for symbol in volume.columns]
            base = close.join(volume).reset_index().rename(columns={"trade_date": "date"})
        base = base.sort_values("date").reset_index(drop=True)

        if macro:
            macro_df = self.series(macro, start, end, wide=True)
            macro_df = macro_df.reset_index().rename(columns={"obs_date": "date"})
            macro_df = macro_df.sort_values("date")
            base = pd.merge_asof(
                base,
                macro_df,
                on="date",
                direction="backward",
                allow_exact_matches=True,
            )

        if news_tickers:
            sentiment = self.news_sentiment(news_tickers, start=start, end=end, frequency=freq)
            if not sentiment.empty:
                sentiment = sentiment.rename(columns={"bucket": "date"})
                sentiment["date"] = pd.to_datetime(sentiment["date"])
                pivot = sentiment.pivot(index="date", columns="ticker", values="avg_sentiment")
                pivot.columns = [f"news_{ticker}_sentiment" for ticker in pivot.columns]
                counts = sentiment.pivot(index="date", columns="ticker", values="article_count")
                counts.columns = [f"news_{ticker}_count" for ticker in counts.columns]
                base = base.merge(pivot.join(counts).reset_index(), on="date", how="left")
        return base
