from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection

TABLE_COUNTS = {
    "instruments": "SELECT count(*) FROM instruments",
    "series": "SELECT count(*) FROM series",
    "observations": "SELECT count(*) FROM observations",
    "daily_bars": "SELECT count(*) FROM daily_bars",
    "bars": "SELECT count(*) FROM bars",
    "put_call_summaries": "SELECT count(*) FROM put_call_summaries",
    "put_call_expirations": "SELECT count(*) FROM put_call_expirations",
    "news_articles": "SELECT count(*) FROM news_articles",
    "news_article_topics": "SELECT count(*) FROM news_article_topics",
    "news_article_tickers": "SELECT count(*) FROM news_article_tickers",
    "ingest_files": "SELECT count(*) FROM ingest_files",
}

EXPECTED = {
    "instruments": 9,
    "series": 29,
    "observations": 198_466,
    "daily_bars": 6_786,
    "bars": 5_832_513,
    "put_call_summaries": 42_587,
    "put_call_expirations": 535_325,
    "ingest_files": 58_093,
}


@dataclass
class Check:
    name: str
    value: object
    expected: object
    ok: bool


def table_counts(conn: Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for name, query in TABLE_COUNTS.items():
            cur.execute(query)
            counts[name] = int(cur.fetchone()[0])
    return counts


def _scalar(conn: Connection, query: str) -> int:
    with conn.cursor() as cur:
        cur.execute(query)
        return int(cur.fetchone()[0])


def validate(conn: Connection, *, full: bool = True) -> tuple[list[Check], bool]:
    counts = table_counts(conn)
    checks: list[Check] = []
    for name, expected in EXPECTED.items():
        actual = counts.get(name)
        checks.append(Check(f"count:{name}", actual, expected, actual == expected))

    # News is deduplicated across topic folders, so exact equality depends on
    # URL canonicalisation. The source contains 1,471,269 distinct raw URLs.
    news_actual = counts["news_articles"]
    checks.append(
        Check(
            "count:news_articles",
            news_actual,
            "<= 1,471,269 and > 1,000,000",
            1_000_000 < news_actual <= 1_471_269,
        )
    )

    quality_queries = {
        "bars:ohlc_invalid": """
            SELECT count(*) FROM bars
            WHERE high < low OR high < open OR high < close
               OR low > open OR low > close OR volume < 0
        """,
        "daily_bars:ohlc_invalid": """
            SELECT count(*) FROM daily_bars
            WHERE high < low OR high < open OR high < close
               OR low > open OR low > close OR volume < 0
        """,
        "put_call_summaries:null_ratios": """
            SELECT count(*) FROM put_call_summaries
            WHERE full_chain_ratio IS NULL
        """,
        "put_call_expirations:negative": """
            SELECT count(*) FROM put_call_expirations WHERE ratio < 0
        """,
        "news_articles:duplicate_hashes": """
            SELECT count(*) - count(DISTINCT url_hash) FROM news_articles
        """,
        "observations:null_values": """
            SELECT count(*) FROM observations WHERE value IS NULL
        """,
        "ingest_files:stuck_loading": """
            SELECT count(*) FROM ingest_files WHERE status = 'loading'
        """,
        "ingest_files:failed": """
            SELECT count(*) FROM ingest_files WHERE status = 'failed'
        """,
    }
    quality_expected = {
        "bars:ohlc_invalid": 0,
        "daily_bars:ohlc_invalid": 0,
        "put_call_summaries:null_ratios": 30,
        "put_call_expirations:negative": 0,
        "news_articles:duplicate_hashes": 0,
        "observations:null_values": 9_589,
        "ingest_files:stuck_loading": 0,
        "ingest_files:failed": 0,
    }
    for name, query in quality_queries.items():
        actual = _scalar(conn, query)
        expected = quality_expected[name]
        checks.append(Check(name, actual, expected, actual == expected))

    if full:
        ok = all(check.ok for check in checks)
    else:
        ok = all(
            check.ok
            for check in checks
            if check.name.startswith("count:") and check.name not in {"count:news_articles"}
        )
    return checks, ok


def print_checks(checks: list[Check]) -> None:
    from rich.table import Table

    table = Table(title="yog validation")
    table.add_column("check")
    table.add_column("actual", justify="right")
    table.add_column("expected", justify="right")
    table.add_column("status")
    for check in checks:
        table.add_row(
            check.name,
            str(check.value),
            str(check.expected),
            "[green]PASS[/green]" if check.ok else "[red]FAIL[/red]",
        )
    from rich.console import Console

    Console().print(table)
