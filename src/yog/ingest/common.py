from __future__ import annotations

import psycopg
from psycopg import Connection

from yog.config import get_settings


def connect(*, autocommit: bool = False) -> Connection:
    settings = get_settings()
    conn = psycopg.connect(settings.libpq_url, autocommit=autocommit)
    if not autocommit:
        with conn.cursor() as cur:
            cur.execute("SET synchronous_commit = off")
        conn.commit()
    return conn
