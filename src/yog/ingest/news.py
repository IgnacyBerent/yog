from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yog.ingest.readers import (
    _float_or_none,
    canonicalize_url,
    parse_news_time,
    read_news_json,
    url_hash,
)


@dataclass(slots=True)
class NewsFileResult:
    path: str
    articles: list[tuple] = field(default_factory=list)
    topics: list[tuple] = field(default_factory=list)
    tickers: list[tuple] = field(default_factory=list)
    count: int = 0
    error: str | None = None


def parse_news_file(args: tuple[str, str]) -> NewsFileResult:
    """Parse one news JSON file. Runs inside a process pool."""
    absolute_path, relative_path = args
    result = NewsFileResult(path=relative_path)
    try:
        feed = read_news_json(Path(absolute_path))
        articles: dict[bytes, tuple] = {}
        topics: dict[tuple[bytes, str], float | None] = {}
        tickers: dict[tuple[bytes, str], tuple] = {}

        for item in feed:
            url = (item.get("url") or "").strip()
            published_raw = (item.get("time_published") or "").strip()
            if not url or not published_raw:
                continue
            canonical = canonicalize_url(url)
            digest = url_hash(canonical)
            try:
                published_at = parse_news_time(published_raw)
            except ValueError:
                continue

            title = (item.get("title") or "").strip() or "(untitled)"
            articles.setdefault(
                digest,
                (
                    url,
                    canonical,
                    digest,
                    title,
                    item.get("summary") or None,
                    published_at,
                    item.get("source") or None,
                    item.get("source_domain") or None,
                    item.get("category_within_source") or None,
                    item.get("banner_image") or None,
                    _float_or_none(item.get("overall_sentiment_score")),
                    item.get("overall_sentiment_label") or None,
                ),
            )

            for topic in item.get("topics") or []:
                name = (topic.get("topic") or "").strip()
                if name:
                    topics[(digest, name)] = _float_or_none(topic.get("relevance_score"))

            for sentiment in item.get("ticker_sentiment") or []:
                ticker = (sentiment.get("ticker") or "").strip()
                if ticker:
                    tickers[(digest, ticker)] = (
                        digest,
                        ticker,
                        _float_or_none(sentiment.get("relevance_score")),
                        _float_or_none(sentiment.get("ticker_sentiment_score")),
                        sentiment.get("ticker_sentiment_label") or None,
                    )

        result.articles = list(articles.values())
        result.topics = [(digest, topic, score) for (digest, topic), score in topics.items()]
        result.tickers = list(tickers.values())
        result.count = len(result.articles)
    except Exception as exc:  # noqa: BLE001 - surfaced on the manifest row
        result.error = f"{type(exc).__name__}: {exc}"
    return result
