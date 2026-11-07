from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from yog.config import get_settings
from yog.db.catalog import seed_catalog
from yog.enums import FileKind, Provider
from yog.ingest.common import connect
from yog.ingest.discovery import discover_files
from yog.ingest.manifest import status_counts, sync_manifest
from yog.ingest.runner import run_ingest
from yog.validate import print_checks, table_counts, validate

if TYPE_CHECKING:
    from alembic.config import Config

app = typer.Typer(
    no_args_is_help=True,
    help="Load the yog dataset into PostgreSQL and query it for ML.",
)
catalog_app = typer.Typer(help="Manage the static series/instrument catalogue.")
db_app = typer.Typer(help="Database migrations and maintenance.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(db_app, name="db")

console = Console()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    from alembic.config import Config

    root = _repo_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


@app.command()
def scan() -> None:
    """Discover raw files and synchronise the ingest manifest."""
    settings = get_settings()
    specs = discover_files(settings.data_root.resolve())
    with connect() as conn:
        sync_manifest(conn, specs)
        counts = status_counts(conn)
    table = Table(title="manifest after scan")
    table.add_column("dataset")
    table.add_column("kind")
    table.add_column("status")
    table.add_column("files", justify="right")
    for dataset, kind, status, count in counts:
        table.add_row(dataset, kind, status, f"{count:,}")
    console.print(table)
    console.print(f"discovered [bold]{len(specs):,}[/bold] files")


@app.command()
def ingest(
    dataset: list[Provider] | None = typer.Option(
        None, "--dataset", "-d", help="Restrict to a dataset."
    ),
    kind: list[FileKind] | None = typer.Option(
        None,
        "--kind",
        "-k",
        help="Restrict to a kind.",
    ),
    force: bool = typer.Option(False, help="Re-process files already marked done."),
    limit: int | None = typer.Option(None, help="Process at most this many files."),
    workers: int | None = typer.Option(None, help="Worker count for this run."),
    fail_fast: bool = typer.Option(False, help="Stop after the first failure."),
    dry_run: bool = typer.Option(False, help="Report selected files without loading."),
) -> None:
    """Load raw files into PostgreSQL."""
    stats = run_ingest(
        datasets=dataset,
        kinds=kind,
        force=force,
        limit=limit,
        workers=workers,
        fail_fast=fail_fast,
        dry_run=dry_run,
    )
    console.print(
        f"processed=[bold]{stats.processed:,}[/bold] "
        f"rows=[bold]{stats.rows:,}[/bold] "
        f"failed={stats.failed:,} skipped={stats.skipped:,}"
    )
    for error in stats.errors[:20]:
        console.print(f"[red]{error}[/red]")
    if stats.failed:
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show manifest progress and table row counts."""
    with connect() as conn:
        counts = status_counts(conn)
        tables = table_counts(conn)
    manifest_table = Table(title="ingest manifest")
    manifest_table.add_column("dataset")
    manifest_table.add_column("kind")
    manifest_table.add_column("status")
    manifest_table.add_column("files", justify="right")
    for dataset, kind, state, count in counts:
        manifest_table.add_row(dataset, kind, state, f"{count:,}")
    console.print(manifest_table)

    counts_table = Table(title="table row counts")
    counts_table.add_column("table")
    counts_table.add_column("rows", justify="right")
    for name, count in tables.items():
        counts_table.add_row(name, f"{count:,}")
    console.print(counts_table)


@app.command("validate")
def validate_data(
    full: bool = typer.Option(True, "--full/--no-full", help="Include quality checks."),
) -> None:
    """Validate row counts and data quality."""
    with connect() as conn:
        checks, ok = validate(conn, full=full)
    print_checks(checks)
    if not ok:
        raise typer.Exit(1)


@catalog_app.command("seed")
def catalog_seed() -> None:
    """Insert or update the series and instrument catalogue."""
    with connect() as conn:
        instruments, series = seed_catalog(conn)
    console.print(f"seeded {instruments} instruments and {series} series")


@db_app.command("upgrade")
def db_upgrade(revision: str = typer.Argument("head")) -> None:
    """Run Alembic migrations."""
    from alembic import command

    command.upgrade(_alembic_config(), revision)
    console.print(f"database upgraded to {revision}")


@db_app.command("current")
def db_current() -> None:
    """Show the current Alembic revision."""
    from alembic import command

    command.current(_alembic_config())


@db_app.command("stamp")
def db_stamp(revision: str = typer.Argument("head")) -> None:
    """Stamp the database without running migrations."""
    from alembic import command

    command.stamp(_alembic_config(), revision)
