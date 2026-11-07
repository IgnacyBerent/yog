# yog

PostgreSQL loader and data client for a market/macro dataset used for machine
learning experiments. The package ingests the raw snapshot under `dataset/raw/`
into a normalised PostgreSQL schema and exposes a synchronous, pandas-first
client for reading it back.

The raw dataset itself is **not committed**; see [`dataset.md`](dataset.md) for
its full description and source attribution.

## What gets loaded

| Source | Table | Rows (expected) |
| --- | --- | ---: |
| Alpha Vantage + FRED scalar series | `observations` | 198,466 |
| Alpha Vantage daily OHLCV (SPY) | `daily_bars` | 6,786 |
| Alpha Vantage 5-minute OHLCV (9 ETFs) | `bars` | 5,835,411 |
| Put/call ratio summaries | `put_call_summaries` | 42,587 |
| Put/call ratios by expiration | `put_call_expirations` | 535,325 |
| News sentiment articles | `news_articles` | 1,447,580 (after URL dedup) |
| File manifest | `ingest_files` | 58,093 |

Design choices:

- **PostgreSQL only.** No TimescaleDB or other extensions; the schema uses plain
  tables, composite primary keys and a BRIN index on `bars.ts`.
- **5-minute intraday only.** The 2,898 one-minute files are recorded in the
  manifest as `skipped` and never parsed.
- **`NULL` is meaningful.** FRED missing values and missing put/call ratios are
  preserved as `NULL` rather than dropped or forward-filled.
- **Deduplication by canonical URL.** News URLs are lower-cased, stripped of
  tracking parameters and fragment identifiers, then hashed. The hash is the
  uniqueness key, so articles repeated across topic folders are loaded once
  (2,598,671 feed entries collapse to 1,447,580 distinct articles).
- **Resumable ingestion.** Every discovered file has an `ingest_files` row with a
  status (`pending`, `loading`, `done`, `failed`, `skipped`). Re-running an
  ingest skips completed files and retries failures.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Provide configuration (defaults match compose.yaml)
cp .env.example .env

# 3. Start PostgreSQL 18
docker compose up -d

# 4. Create the schema
uv run yog db upgrade

# 5. Seed the instrument and series catalogue
uv run yog catalog seed

# 6. Discover raw files and build the manifest
uv run yog scan
```

`DATA_ROOT` defaults to `dataset/raw`. Place the raw snapshot there, or point
`DATA_ROOT` at its location before running `scan`/`ingest`.

## Ingestion

Load everything that is still pending:

```bash
uv run yog ingest
```

Load specific stages (useful for a first run or to retry one kind):

```bash
uv run yog ingest --kind observation --kind daily_bar
uv run yog ingest --kind put_call
uv run yog ingest --kind bar       # 5-minute OHLCV (the large table)
uv run yog ingest --kind news      # parsed in a process pool
```

Other options:

```bash
uv run yog ingest --kind bar --workers 8   # override worker count
uv run yog ingest --kind bar --limit 10    # smoke test
uv run yog ingest --kind bar --dry-run     # show the selection only
uv run yog ingest --force                  # re-process completed files
uv run yog ingest --fail-fast              # stop at the first failure
```

Inspect progress and table sizes:

```bash
uv run yog status
```

Validate row counts and data quality:

```bash
uv run yog validate
```

## Client

`yog.Client` is synchronous and returns a `pandas.DataFrame` by default. Pass
`format="polars"` to receive Polars frames instead.

```python
import yog

with yog.Client() as client:              # reads DATABASE_URL from the environment
    catalog = client.catalog()
    instruments = client.instruments()

    # Scalar series (long format)
    macro = client.series(["CPI", "UNEMPLOYMENT"], start="2015-01-01")

    # Wide format: one column per series code, indexed by observation date
    macro_wide = client.series(["CPI", "UNEMPLOYMENT"], wide=True)

    # Daily bars
    spy = client.daily_bars("SPY", start="2024-01-01", end="2024-12-31")

    # Intraday bars: start and end are required
    intraday = client.bars(
        ["SPY", "XLE"],
        timeframe="5m",
        start="2024-01-02",
        end="2024-01-03",
    )

    # Stream a large range in batches
    for chunk in client.iter_bars(
        "SPY", start="2024-01-01", end="2024-12-31", batch_size=100_000
    ):
        ...

    # Put/call data, either daily summary or per-expiration detail
    pc = client.put_call(["SPY"], level="summary")
    pc_exp = client.put_call(["SPY"], level="expiration")

    # News filtered by topic and/or ticker
    news = client.news(topics=["technology"], start="2024-01-01")

    # Daily sentiment aggregation per ticker
    sentiment = client.news_sentiment("SPY", start="2024-01-01")

    # Daily feature panel: prices + macro + news sentiment
    panel = client.panel(
        ["SPY", "XLE"],
        start="2020-01-01",
        end="2024-12-31",
        macro=["CPI", "UNEMPLOYMENT", "FEDERAL_FUNDS_RATE"],
        news_tickers=["SPY"],
    )
```

Pass an explicit connection string when needed:

```python
client = yog.Client("postgresql+psycopg://yog:yog@localhost:5432/yog")
```

Polars output:

```python
client = yog.Client(format="polars")
df = client.daily_bars("SPY", start="2024-01-01")
```

## Schema overview

- `instruments` — the 9 ETFs (`SPY` plus 8 SPDR sector funds).
- `series` — catalogue of the 29 scalar series (provider, code, units,
  frequency, release lag).
- `observations` — `(series_id, obs_date) → value`, with `value` nullable.
- `daily_bars` — `(instrument_id, trade_date) → OHLCV`.
- `bars` — `(instrument_id, timeframe, ts) → OHLCV`; `ts` is UTC and
  `timeframe` is constrained to `1m`/`5m`. Only `5m` is populated.
- `put_call_summaries` — daily full-chain put/call ratio per instrument.
- `put_call_expirations` — ratio per `(trade_date, expiration_date)`.
- `news_articles` — one row per canonical URL (unique `url_hash`), with UTC
  `published_at`.
- `news_article_topics`, `news_article_tickers` — article topics and per-ticker
  sentiment.
- `ingest_files`, `ingest_runs` — ingestion manifest and run bookkeeping.

Timestamps are stored as `timestamptz` in UTC. Alpha Vantage intraday bars are
interpreted as `America/New_York` and converted; news timestamps use the same
US Eastern assumption.

## Development

```bash
uv run ruff check src tests migrations
uv run ruff format src tests migrations
uv run pytest
```

Create a new migration after changing `src/yog/db/models.py`:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run yog db upgrade
```

## Configuration

Environment variables (or `.env`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://yog:yog@localhost:5432/yog` | SQLAlchemy URL used by the client, Alembic and the loader |
| `DATA_ROOT` | `dataset/raw` | Root of the raw snapshot |
| `INGEST_WORKERS` | `8` | Worker threads (or processes for news) |
| `COPY_BATCH_SIZE` | `100000` | Reserved for batched COPY operations |
| `NEWS_BATCH_SIZE` | `50` | Files parsed and inserted per news batch |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT` | `yog` | Docker PostgreSQL credentials and port |

The Compose service uses the `postgres:18-alpine` image and mounts the volume at
`/var/lib/postgresql` (the layout required by PostgreSQL 18 images).

## Notes and limitations

- The snapshot stores observation dates, not real-time release vintages.
  `panel()` joins macro data with a backward `merge_asof`, but it cannot correct
  for later revisions.
- `SERIES` may contain codes that are not present in the snapshot; validation
  asserts the measured counts, not catalogue size.
- News ingestion deduplicates on canonical URL, so `news_articles` can be lower
  than the number of raw feed entries.
- `client.bars()` requires `start` and `end` and refuses to return more than
  `max_rows` (default 2,000,000) to avoid accidental full-table loads.

## Attribution

The data is provided by Alpha Vantage and FRED. See
[`dataset.md`](dataset.md#attribution-and-terms) for source links, terms and
citation requirements.
