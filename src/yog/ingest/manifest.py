from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from yog.enums import FileKind, IngestStatus, Provider

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from psycopg import Connection

    from yog.ingest.discovery import FileSpec

KIND_PRIORITY: dict[FileKind, int] = {
    FileKind.OBSERVATION: 0,
    FileKind.DAILY_BAR: 1,
    FileKind.PUT_CALL: 2,
    FileKind.BAR: 3,
    FileKind.NEWS: 4,
    FileKind.SKIPPED: 99,
}


@dataclass(frozen=True, slots=True)
class PendingFile:
    path: str
    dataset: Provider
    kind: FileKind


def sync_manifest(conn: Connection, specs: Iterable[FileSpec]) -> None:
    rows = [
        (
            spec.path,
            spec.dataset.value,
            spec.kind.value,
            spec.size_bytes,
            spec.mtime,
            IngestStatus.SKIPPED.value
            if spec.kind is FileKind.SKIPPED
            else IngestStatus.PENDING.value,
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
                    WHEN EXCLUDED.status = %s THEN %s
                    WHEN ingest_files.status = %s THEN EXCLUDED.status
                    ELSE ingest_files.status
                END,
                updated_at = now()
            """,
            [
                (
                    *row,
                    IngestStatus.SKIPPED.value,
                    IngestStatus.SKIPPED.value,
                    IngestStatus.SKIPPED.value,
                )
                for row in rows
            ],
        )
    conn.commit()


def reset_stale_loading(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingest_files SET status = %s WHERE status = %s",
            (IngestStatus.PENDING.value, IngestStatus.LOADING.value),
        )
    conn.commit()


def pending_files(
    conn: Connection,
    *,
    datasets: Sequence[Provider] | None = None,
    kinds: Sequence[FileKind] | None = None,
    force: bool = False,
    limit: int | None = None,
) -> list[PendingFile]:
    clauses = ["kind <> %s"]
    params: list[object] = [FileKind.SKIPPED.value]
    if datasets:
        clauses.append("dataset = ANY(%s)")
        params.append([dataset.value for dataset in datasets])
    if kinds:
        clauses.append("kind = ANY(%s)")
        params.append([kind.value for kind in kinds])
    if force:
        clauses.append("status <> %s")
        params.append(IngestStatus.SKIPPED.value)
    else:
        clauses.append("status IN (%s, %s)")
        params.extend([IngestStatus.PENDING.value, IngestStatus.FAILED.value])
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
    files = [
        PendingFile(path=row[0], dataset=Provider(row[1]), kind=FileKind(row[2])) for row in rows
    ]
    files.sort(key=lambda item: (KIND_PRIORITY[item.kind], item.path))
    return files


def mark_loading(conn: Connection, path: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_files
            SET status = %s, started_at = now(), error = NULL
            WHERE path = %s
            """,
            (IngestStatus.LOADING.value, path),
        )
    conn.commit()


def mark_done(conn: Connection, path: str, rows_loaded: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_files
            SET status = %s, rows_loaded = %s, finished_at = now(),
                error = NULL, updated_at = now()
            WHERE path = %s
            """,
            (IngestStatus.DONE.value, rows_loaded, path),
        )
    conn.commit()


def mark_failed(conn: Connection, path: str, error: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_files
            SET status = %s, error = %s, finished_at = now(),
                updated_at = now()
            WHERE path = %s
            """,
            (IngestStatus.FAILED.value, error[:4_000], path),
        )
    conn.commit()


def status_counts(conn: Connection) -> list[tuple[Provider, FileKind, IngestStatus, int]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dataset, kind, status, count(*)
            FROM ingest_files
            GROUP BY dataset, kind, status
            ORDER BY dataset, kind, status
            """
        )
        rows = cur.fetchall()
    return [
        (Provider(dataset), FileKind(kind), IngestStatus(status), int(count))
        for dataset, kind, status, count in rows
    ]
