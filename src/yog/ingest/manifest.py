from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from psycopg import Connection

from yog.ingest.discovery import FileSpec

KIND_PRIORITY = {
    "observation": 0,
    "daily_bar": 1,
    "put_call": 2,
    "bar": 3,
    "news": 4,
    "skipped": 99,
}


@dataclass(frozen=True, slots=True)
class PendingFile:
    path: str
    dataset: str
    kind: str


def sync_manifest(conn: Connection, specs: Iterable[FileSpec]) -> None:
    rows = [
        (
            spec.path,
            spec.dataset,
            spec.kind,
            spec.size_bytes,
            spec.mtime,
            "skipped" if spec.kind == "skipped" else "pending",
        )
        for spec in specs
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO ingest_files
                (path, dataset, kind, size_bytes, mtime, status)
            VALUES (%s, %s, %s, %s, to_timestamp(%s), %s)
            ON CONFLICT (path) DO UPDATE SET
                dataset = EXCLUDED.dataset,
                kind = EXCLUDED.kind,
                size_bytes = EXCLUDED.size_bytes,
                mtime = EXCLUDED.mtime,
                status = CASE
                    WHEN EXCLUDED.status = 'skipped' THEN 'skipped'
                    WHEN ingest_files.status = 'skipped' THEN EXCLUDED.status
                    ELSE ingest_files.status
                END,
                updated_at = now()
            """,
            rows,
        )
    conn.commit()


def reset_stale_loading(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE ingest_files SET status = 'pending' WHERE status = 'loading'")
    conn.commit()


def pending_files(
    conn: Connection,
    *,
    datasets: Sequence[str] | None = None,
    kinds: Sequence[str] | None = None,
    force: bool = False,
    limit: int | None = None,
) -> list[PendingFile]:
    clauses = ["kind <> 'skipped'"]
    params: list[object] = []
    if datasets:
        clauses.append("dataset = ANY(%s)")
        params.append(list(datasets))
    if kinds:
        clauses.append("kind = ANY(%s)")
        params.append(list(kinds))
    if force:
        clauses.append("status <> 'skipped'")
    else:
        clauses.append("status IN ('pending', 'failed')")
    sql = (
        "SELECT path, dataset, kind FROM ingest_files WHERE "
        + " AND ".join(clauses)
        + " ORDER BY path"
    )
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    files = [PendingFile(path=row[0], dataset=row[1], kind=row[2]) for row in rows]
    files.sort(key=lambda item: (KIND_PRIORITY.get(item.kind, 50), item.path))
    return files


def mark_loading(conn: Connection, path: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_files
            SET status = 'loading', started_at = now(), error = NULL
            WHERE path = %s
            """,
            (path,),
        )
    conn.commit()


def mark_done(conn: Connection, path: str, rows_loaded: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_files
            SET status = 'done', rows_loaded = %s, finished_at = now(),
                error = NULL, updated_at = now()
            WHERE path = %s
            """,
            (rows_loaded, path),
        )
    conn.commit()


def mark_failed(conn: Connection, path: str, error: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_files
            SET status = 'failed', error = %s, finished_at = now(),
                updated_at = now()
            WHERE path = %s
            """,
            (error[:4_000], path),
        )
    conn.commit()


def status_counts(conn: Connection) -> list[tuple[str, str, str, int]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dataset, kind, status, count(*)
            FROM ingest_files
            GROUP BY dataset, kind, status
            ORDER BY dataset, kind, status
            """
        )
        return list(cur.fetchall())
