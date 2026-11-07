from __future__ import annotations

import os
import queue
import threading
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from psycopg.types.json import Jsonb
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from yog.config import get_settings
from yog.db.catalog import load_instrument_ids, load_series_ids, seed_catalog
from yog.ingest.common import connect
from yog.ingest.discovery import FileSpec, discover_files
from yog.ingest.loaders import LoaderContext, load_file, load_news_batch
from yog.ingest.manifest import (
    mark_done,
    mark_failed,
    mark_loading,
    pending_files,
    reset_stale_loading,
    sync_manifest,
)
from yog.ingest.news import parse_news_file


@dataclass
class IngestStats:
    processed: int = 0
    failed: int = 0
    rows: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: IngestStats) -> None:
        self.processed += other.processed
        self.failed += other.failed
        self.rows += other.rows
        self.skipped += other.skipped
        self.errors.extend(other.errors)


def _progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )


def _chunks(items: Sequence, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _start_run(args: dict) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingest_runs (args) VALUES (%s) RETURNING id",
                (Jsonb(args),),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
    return int(run_id)


def _finish_run(run_id: int, stats: IngestStats) -> None:
    payload = {
        "processed": stats.processed,
        "rows": stats.rows,
        "failed": stats.failed,
        "skipped": stats.skipped,
        "errors": stats.errors[:50],
    }
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ingest_runs SET finished_at = now(), stats = %s WHERE id = %s",
                (Jsonb(payload), run_id),
            )
        conn.commit()


def _process_one(conn, spec: FileSpec, ctx: LoaderContext) -> tuple[int, bool, str | None]:
    mark_loading(conn, spec.path)
    try:
        rows = load_file(conn, spec, ctx)
    except Exception as exc:  # noqa: BLE001 - recorded on the manifest
        conn.rollback()
        message = f"{type(exc).__name__}: {exc}"
        mark_failed(conn, spec.path, message)
        return 0, False, message
    mark_done(conn, spec.path, rows)
    return rows, True, None


def _thread_worker(
    work_queue: queue.Queue[str],
    spec_by_path: dict[str, FileSpec],
    ctx: LoaderContext,
    progress: Progress,
    task_id,
    stats: IngestStats,
    stats_lock: threading.Lock,
    stop_event: threading.Event,
    fail_fast: bool,
) -> None:
    local = IngestStats()
    with connect() as conn:
        while not stop_event.is_set():
            try:
                path = work_queue.get_nowait()
            except queue.Empty:
                break
            spec = spec_by_path.get(path)
            try:
                if spec is None:
                    raise FileNotFoundError(path)
                rows, ok, message = _process_one(conn, spec, ctx)
                if ok:
                    local.processed += 1
                    local.rows += rows
                else:
                    local.failed += 1
                    local.errors.append(f"{path}: {message}")
                    if fail_fast:
                        stop_event.set()
            except Exception as exc:  # noqa: BLE001 - keep the run alive
                local.failed += 1
                local.errors.append(f"{path}: {type(exc).__name__}: {exc}")
                if fail_fast:
                    stop_event.set()
                try:
                    conn.rollback()
                    mark_failed(conn, path, f"{type(exc).__name__}: {exc}")
                except Exception:  # noqa: BLE001
                    conn.close()
                    conn = connect()
            finally:
                work_queue.task_done()
                progress.advance(task_id)
    with stats_lock:
        stats.merge(local)


def _run_parallel_files(
    files: list[FileSpec],
    spec_by_path: dict[str, FileSpec],
    ctx: LoaderContext,
    *,
    workers: int,
    fail_fast: bool,
) -> IngestStats:
    stats = IngestStats()
    stats_lock = threading.Lock()
    stop_event = threading.Event()
    work_queue: queue.Queue[str] = queue.Queue()
    for spec in files:
        work_queue.put(spec.path)

    with _progress() as progress:
        task_id = progress.add_task("loading files", total=len(files))
        threads = [
            threading.Thread(
                target=_thread_worker,
                args=(
                    work_queue,
                    spec_by_path,
                    ctx,
                    progress,
                    task_id,
                    stats,
                    stats_lock,
                    stop_event,
                    fail_fast,
                ),
                daemon=True,
            )
            for _ in range(min(workers, max(1, len(files))))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    return stats


def _run_news_files(
    files: list[FileSpec],
    data_root: Path,
    *,
    workers: int,
    batch_size: int,
    fail_fast: bool,
) -> IngestStats:
    stats = IngestStats()
    pairs = [(str(data_root / spec.path), spec.path) for spec in files]
    with connect() as conn, _progress() as progress:
        task_id = progress.add_task("loading news", total=len(files))
        with ProcessPoolExecutor(max_workers=min(workers, os.cpu_count() or workers)) as pool:
            for batch in _chunks(pairs, batch_size):
                results = list(pool.map(parse_news_file, batch))
                try:
                    load_news_batch(conn, results)
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    message = f"{type(exc).__name__}: {exc}"
                    for result in results:
                        mark_failed(conn, result.path, message)
                        stats.failed += 1
                        stats.errors.append(f"{result.path}: {message}")
                else:
                    for result in results:
                        if result.error:
                            mark_failed(conn, result.path, result.error)
                            stats.failed += 1
                            stats.errors.append(f"{result.path}: {result.error}")
                        else:
                            mark_done(conn, result.path, result.count)
                            stats.processed += 1
                            stats.rows += result.count
                progress.advance(task_id, len(batch))
                if fail_fast and stats.failed:
                    break
    return stats


def run_ingest(
    *,
    datasets: Sequence[str] | None = None,
    kinds: Sequence[str] | None = None,
    force: bool = False,
    limit: int | None = None,
    workers: int | None = None,
    fail_fast: bool = False,
    dry_run: bool = False,
) -> IngestStats:
    settings = get_settings()
    data_root = settings.data_root.resolve()
    if not data_root.exists():
        raise FileNotFoundError(f"data root does not exist: {data_root}")

    workers = workers or settings.ingest_workers
    all_specs = discover_files(data_root)
    spec_by_path = {spec.path: spec for spec in all_specs}

    with connect() as conn:
        sync_manifest(conn, all_specs)
        reset_stale_loading(conn)
        seed_catalog(conn)
        selected = pending_files(
            conn,
            datasets=datasets,
            kinds=kinds,
            force=force,
            limit=limit,
        )
        ctx = LoaderContext(
            data_root=data_root,
            series_ids=load_series_ids(conn),
            instrument_ids=load_instrument_ids(conn),
        )

    files: list[FileSpec] = []
    missing: list[str] = []
    for item in selected:
        spec = spec_by_path.get(item.path)
        if spec is None:
            missing.append(item.path)
        else:
            files.append(spec)

    if dry_run:
        news_files = [spec for spec in files if spec.kind == "news"]
        other_files = [spec for spec in files if spec.kind != "news"]
        stats = IngestStats(processed=len(files), skipped=len(missing))
        print(
            f"would process {len(other_files)} regular files and "
            f"{len(news_files)} news files; missing {len(missing)}"
        )
        return stats

    news_files = [spec for spec in files if spec.kind == "news"]
    other_files = [spec for spec in files if spec.kind != "news"]

    run_id = _start_run(
        {
            "datasets": list(datasets) if datasets else None,
            "kinds": list(kinds) if kinds else None,
            "force": force,
            "limit": limit,
            "workers": workers,
            "fail_fast": fail_fast,
        }
    )
    stats = IngestStats(skipped=len(missing))
    try:
        if missing:
            with connect() as conn:
                for path in missing:
                    mark_failed(conn, path, "source file no longer exists")
                    stats.failed += 1

        if other_files:
            stats.merge(
                _run_parallel_files(
                    other_files,
                    spec_by_path,
                    ctx,
                    workers=workers,
                    fail_fast=fail_fast,
                )
            )
        if news_files and not (fail_fast and stats.failed):
            stats.merge(
                _run_news_files(
                    news_files,
                    data_root,
                    workers=workers,
                    batch_size=settings.news_batch_size,
                    fail_fast=fail_fast,
                )
            )
        return stats
    finally:
        _finish_run(run_id, stats)
