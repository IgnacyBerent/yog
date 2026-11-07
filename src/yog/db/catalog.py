from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.types.json import Jsonb

from yog.catalog import INSTRUMENTS, SERIES
from yog.enums import Provider, SeriesCode, Symbol

if TYPE_CHECKING:
    from psycopg import Connection


def seed_catalog(conn: Connection) -> tuple[int, int]:
    """Insert or update the static instrument and series catalogue."""
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO instruments (symbol, name, asset_class, currency, exchange_tz)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                name = EXCLUDED.name,
                asset_class = EXCLUDED.asset_class,
                currency = EXCLUDED.currency,
                exchange_tz = EXCLUDED.exchange_tz
            """,
            [
                (
                    spec.symbol.value,
                    spec.name,
                    spec.asset_class.value,
                    spec.currency,
                    spec.exchange_tz,
                )
                for spec in INSTRUMENTS
            ],
        )
        cur.executemany(
            """
            INSERT INTO series
                (provider, code, name, description, frequency, unit, kind,
                 source_url, release_lag_days, extra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider, code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                frequency = EXCLUDED.frequency,
                unit = EXCLUDED.unit,
                kind = EXCLUDED.kind,
                source_url = EXCLUDED.source_url,
                release_lag_days = EXCLUDED.release_lag_days,
                extra = EXCLUDED.extra
            """,
            [
                (
                    spec.provider.value,
                    spec.code.value,
                    spec.name,
                    spec.description or None,
                    spec.frequency.value,
                    spec.unit,
                    spec.kind.value,
                    spec.source_url,
                    spec.release_lag_days,
                    Jsonb(spec.extra),
                )
                for spec in SERIES
            ],
        )
    conn.commit()
    return len(INSTRUMENTS), len(SERIES)


def load_series_ids(conn: Connection) -> dict[tuple[Provider, SeriesCode], int]:
    with conn.cursor() as cur:
        cur.execute("SELECT provider, code, id FROM series")
        return {
            (Provider(provider), SeriesCode(code)): series_id for provider, code, series_id in cur
        }


def load_instrument_ids(conn: Connection) -> dict[Symbol, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, id FROM instruments")
        return {Symbol(symbol): instrument_id for symbol, instrument_id in cur}
