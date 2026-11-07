from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from yog.db.base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    exchange_tz: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'America/New_York'")
    )


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    release_lag_days: Mapped[int | None] = mapped_column(SmallInteger)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict
    )

    __table_args__ = (UniqueConstraint("provider", "code", name="uq_series_provider_code"),)


class Observation(Base):
    __tablename__ = "observations"

    series_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("series.id", ondelete="CASCADE"), primary_key=True
    )
    obs_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_observations_obs_date", "obs_date"),)


class DailyBar(Base):
    __tablename__ = "daily_bars"

    instrument_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_daily_bars_trade_date", "trade_date"),)


class Bar(Base):
    __tablename__ = "bars"

    instrument_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        CheckConstraint("timeframe IN ('1m', '5m')", name="timeframe_valid"),
        Index("ix_bars_ts_brin", "ts", postgresql_using="brin"),
    )


class PutCallSummary(Base):
    __tablename__ = "put_call_summaries"

    instrument_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    full_chain_ratio: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_put_call_summaries_trade_date", "trade_date"),)


class PutCallExpiration(Base):
    __tablename__ = "put_call_expirations"

    instrument_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    expiration_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ratio: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (Index("ix_put_call_expirations_trade_date", "trade_date"),)


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    source_domain: Mapped[str | None] = mapped_column(Text)
    category_within_source: Mapped[str | None] = mapped_column(Text)
    banner_image: Mapped[str | None] = mapped_column(Text)
    overall_sentiment_score: Mapped[float | None] = mapped_column(Float)
    overall_sentiment_label: Mapped[str | None] = mapped_column(String(32))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_news_articles_url_hash"),
        Index("ix_news_articles_published_at", "published_at"),
    )


class NewsArticleTopic(Base):
    __tablename__ = "news_article_topics"

    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic: Mapped[str] = mapped_column(String(64), primary_key=True)
    relevance_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_news_article_topics_topic", "topic", "article_id"),)


class NewsArticleTicker(Base):
    __tablename__ = "news_article_tickers"

    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    sentiment_label: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (Index("ix_news_article_tickers_ticker", "ticker", "article_id"),)


class IngestFile(Base):
    __tablename__ = "ingest_files"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    dataset: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    rows_loaded: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'loading', 'done', 'failed', 'skipped')",
            name="status_valid",
        ),
        Index("ix_ingest_files_status", "status"),
        Index("ix_ingest_files_kind_status", "kind", "status"),
    )


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    args: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict
    )
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict
    )
