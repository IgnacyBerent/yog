from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from yog.catalog import SERIES_BY_KEY

AV_ROOT = "alpha_vantage"
FRED_ROOT = "fred"

AV_TOP_LEVEL_SERIES = {
    "DURABLES",
    "INFLATION",
    "NONFARM_PAYROLL",
    "RETAIL_SALES",
    "UNEMPLOYMENT",
}
AV_DIRECTORY_SERIES = {
    "BRENT",
    "COPPER",
    "CPI",
    "FEDERAL_FUNDS_RATE",
    "NATURAL_GAS",
    "REAL_GDP",
    "WTI",
}
TREASURY_MATURITIES = {"3month", "2year", "5year", "7year", "10year", "30year"}
METALS = {"XAU": "XAUUSD", "XAG": "XAGUSD"}


@dataclass(frozen=True, slots=True)
class FileSpec:
    path: str
    dataset: str
    kind: str
    provider: str | None = None
    code: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    skip_reason: str | None = None
    size_bytes: int | None = None
    mtime: float | None = None


def _spec(
    rel: str,
    *,
    kind: str,
    dataset: str,
    provider: str | None = None,
    code: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    skip_reason: str | None = None,
) -> FileSpec:
    return FileSpec(
        path=rel,
        dataset=dataset,
        kind=kind,
        provider=provider,
        code=code,
        symbol=symbol,
        timeframe=timeframe,
        skip_reason=skip_reason,
    )


def classify(rel: str) -> FileSpec | None:
    """Map a path relative to ``dataset/raw`` to a loader specification."""
    rel = rel.replace("\\", "/").lstrip("./")
    path = PurePosixPath(rel)
    parts = path.parts
    if not parts:
        return None

    dataset = parts[0]
    if dataset == FRED_ROOT:
        if len(parts) != 2 or path.suffix.lower() != ".csv":
            return None
        code = path.stem
        if ("fred", code) not in SERIES_BY_KEY:
            return None
        return _spec(rel, kind="observation", dataset=dataset, provider="fred", code=code)

    if dataset != AV_ROOT:
        return None

    # alpha_vantage/TIME_SERIES_INTRADAY/{1min,5min}/{symbol}/{YYYY-MM}.csv
    if len(parts) == 5 and parts[1] == "TIME_SERIES_INTRADAY":
        interval, symbol = parts[2], parts[3]
        if path.suffix.lower() != ".csv" or interval not in {"1min", "5min"}:
            return None
        timeframe = "1m" if interval == "1min" else "5m"
        if interval == "1min":
            return _spec(
                rel,
                kind="skipped",
                dataset=dataset,
                symbol=symbol,
                timeframe=timeframe,
                skip_reason="1-minute intraday data is intentionally not loaded",
            )
        return _spec(
            rel,
            kind="bar",
            dataset=dataset,
            symbol=symbol,
            timeframe=timeframe,
        )

    # alpha_vantage/TIME_SERIES_DAILY/{symbol}.csv
    if len(parts) == 3 and parts[1] == "TIME_SERIES_DAILY":
        if path.suffix.lower() != ".csv":
            return None
        return _spec(rel, kind="daily_bar", dataset=dataset, symbol=path.stem)

    # alpha_vantage/HISTORICAL_PUT_CALL_RATIO/{symbol}/{YYYY-MM-DD}.json
    if (
        len(parts) == 4
        and parts[1] == "HISTORICAL_PUT_CALL_RATIO"
        and path.suffix.lower() == ".json"
    ):
        return _spec(rel, kind="put_call", dataset=dataset, symbol=parts[2])

    # alpha_vantage/NEWS_SENTIMENT/{topic}/{window}.json
    if len(parts) == 4 and parts[1] == "NEWS_SENTIMENT" and path.suffix.lower() == ".json":
        return _spec(rel, kind="news", dataset=dataset)

    # alpha_vantage/GOLD_SILVER_HISTORY/daily/{XAU,XAG}.json
    if (
        len(parts) == 4
        and parts[1] == "GOLD_SILVER_HISTORY"
        and parts[2] == "daily"
        and path.suffix.lower() == ".json"
    ):
        code = METALS.get(path.stem.upper())
        if code is None:
            return None
        return _spec(
            rel,
            kind="observation",
            dataset=dataset,
            provider="alpha_vantage",
            code=code,
        )

    # alpha_vantage/TREASURY_YIELD/daily/{maturity}.csv
    if (
        len(parts) == 4
        and parts[1] == "TREASURY_YIELD"
        and parts[2] == "daily"
        and path.suffix.lower() == ".csv"
    ):
        maturity = path.stem.lower()
        if maturity not in TREASURY_MATURITIES:
            return None
        code = f"TREASURY_YIELD_{maturity.upper()}"
        return _spec(
            rel,
            kind="observation",
            dataset=dataset,
            provider="alpha_vantage",
            code=code,
        )

    # alpha_vantage/{SERIES}/{frequency}.csv
    if len(parts) == 3 and path.suffix.lower() == ".csv":
        code = parts[1]
        if code not in AV_DIRECTORY_SERIES:
            return None
        return _spec(
            rel,
            kind="observation",
            dataset=dataset,
            provider="alpha_vantage",
            code=code,
        )

    # alpha_vantage/{SERIES}.csv
    if len(parts) == 2 and path.suffix.lower() == ".csv":
        code = path.stem
        if code not in AV_TOP_LEVEL_SERIES:
            return None
        return _spec(
            rel,
            kind="observation",
            dataset=dataset,
            provider="alpha_vantage",
            code=code,
        )

    return None


def discover_files(data_root: Path) -> list[FileSpec]:
    """Return every recognised file below ``data_root``, with stat metadata."""
    root = data_root.resolve()
    specs: list[FileSpec] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        spec = classify(rel)
        if spec is None:
            continue
        stat = path.stat()
        specs.append(
            FileSpec(
                path=spec.path,
                dataset=spec.dataset,
                kind=spec.kind,
                provider=spec.provider,
                code=spec.code,
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                skip_reason=spec.skip_reason,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
            )
        )
    return specs
