from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from yog.catalog import SERIES_BY_KEY
from yog.enums import (
    CSV_SUFFIX,
    JSON_SUFFIX,
    AvEndpoint,
    FileKind,
    Frequency,
    Provider,
    SeriesCode,
    Symbol,
    Timeframe,
)

AV_TOP_LEVEL_SERIES: frozenset[SeriesCode] = frozenset(
    {
        SeriesCode.DURABLES,
        SeriesCode.INFLATION,
        SeriesCode.NONFARM_PAYROLL,
        SeriesCode.RETAIL_SALES,
        SeriesCode.UNEMPLOYMENT,
    }
)
AV_DIRECTORY_SERIES: frozenset[SeriesCode] = frozenset(
    {
        SeriesCode.BRENT,
        SeriesCode.COPPER,
        SeriesCode.CPI,
        SeriesCode.FEDERAL_FUNDS_RATE,
        SeriesCode.NATURAL_GAS,
        SeriesCode.REAL_GDP,
        SeriesCode.WTI,
    }
)
TREASURY_MATURITY_TO_CODE: dict[str, SeriesCode] = {
    "3month": SeriesCode.TREASURY_YIELD_3MONTH,
    "2year": SeriesCode.TREASURY_YIELD_2YEAR,
    "5year": SeriesCode.TREASURY_YIELD_5YEAR,
    "7year": SeriesCode.TREASURY_YIELD_7YEAR,
    "10year": SeriesCode.TREASURY_YIELD_10YEAR,
    "30year": SeriesCode.TREASURY_YIELD_30YEAR,
}
METALS: dict[str, SeriesCode] = {
    "XAU": SeriesCode.XAUUSD,
    "XAG": SeriesCode.XAGUSD,
}
INTERVAL_TO_TIMEFRAME: dict[str, Timeframe] = {
    "1min": Timeframe.M1,
    "5min": Timeframe.M5,
}
SKIP_ONE_MINUTE = "1-minute intraday data is intentionally not loaded"


@dataclass(frozen=True, slots=True)
class FileSpec:
    path: str
    dataset: Provider
    kind: FileKind
    provider: Provider | None = None
    code: SeriesCode | None = None
    symbol: Symbol | None = None
    timeframe: Timeframe | None = None
    skip_reason: str | None = None
    size_bytes: int | None = None
    mtime: float | None = None


def _spec(
    rel: str,
    *,
    kind: FileKind,
    dataset: Provider,
    provider: Provider | None = None,
    code: SeriesCode | None = None,
    symbol: Symbol | None = None,
    timeframe: Timeframe | None = None,
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


def _as_series_code(value: str) -> SeriesCode | None:
    try:
        return SeriesCode(value)
    except ValueError:
        return None


def _as_symbol(value: str) -> Symbol | None:
    try:
        return Symbol(value)
    except ValueError:
        return None


def _classify_fred(rel: str, path: PurePosixPath, parts: tuple[str, ...]) -> FileSpec | None:
    if len(parts) != 2 or path.suffix.lower() != CSV_SUFFIX:
        return None
    code = _as_series_code(path.stem)
    if code is None or (Provider.FRED, code) not in SERIES_BY_KEY:
        return None
    return _spec(
        rel,
        kind=FileKind.OBSERVATION,
        dataset=Provider.FRED,
        provider=Provider.FRED,
        code=code,
    )


def _classify_intraday(rel: str, path: PurePosixPath, parts: tuple[str, ...]) -> FileSpec | None:
    timeframe = INTERVAL_TO_TIMEFRAME.get(parts[2])
    symbol = _as_symbol(parts[3])
    if path.suffix.lower() != CSV_SUFFIX or timeframe is None or symbol is None:
        return None
    if timeframe is Timeframe.M1:
        return _spec(
            rel,
            kind=FileKind.SKIPPED,
            dataset=Provider.ALPHA_VANTAGE,
            symbol=symbol,
            timeframe=timeframe,
            skip_reason=SKIP_ONE_MINUTE,
        )
    return _spec(
        rel,
        kind=FileKind.BAR,
        dataset=Provider.ALPHA_VANTAGE,
        symbol=symbol,
        timeframe=timeframe,
    )


def _classify_daily(rel: str, path: PurePosixPath) -> FileSpec | None:
    symbol = _as_symbol(path.stem)
    if symbol is None:
        return None
    return _spec(
        rel,
        kind=FileKind.DAILY_BAR,
        dataset=Provider.ALPHA_VANTAGE,
        symbol=symbol,
    )


def _classify_put_call(rel: str, parts: tuple[str, ...]) -> FileSpec | None:
    symbol = _as_symbol(parts[2])
    if symbol is None:
        return None
    return _spec(
        rel,
        kind=FileKind.PUT_CALL,
        dataset=Provider.ALPHA_VANTAGE,
        symbol=symbol,
    )


def _classify_news(rel: str) -> FileSpec:
    return _spec(rel, kind=FileKind.NEWS, dataset=Provider.ALPHA_VANTAGE)


def _classify_metals(rel: str, path: PurePosixPath) -> FileSpec | None:
    code = METALS.get(path.stem.upper())
    if code is None:
        return None
    return _spec(
        rel,
        kind=FileKind.OBSERVATION,
        dataset=Provider.ALPHA_VANTAGE,
        provider=Provider.ALPHA_VANTAGE,
        code=code,
    )


def _classify_treasury(rel: str, path: PurePosixPath) -> FileSpec | None:
    code = TREASURY_MATURITY_TO_CODE.get(path.stem.lower())
    if code is None:
        return None
    return _spec(
        rel,
        kind=FileKind.OBSERVATION,
        dataset=Provider.ALPHA_VANTAGE,
        provider=Provider.ALPHA_VANTAGE,
        code=code,
    )


def _classify_directory_series(rel: str, parts: tuple[str, ...]) -> FileSpec | None:
    code = _as_series_code(parts[1])
    if code is None or code not in AV_DIRECTORY_SERIES:
        return None
    return _spec(
        rel,
        kind=FileKind.OBSERVATION,
        dataset=Provider.ALPHA_VANTAGE,
        provider=Provider.ALPHA_VANTAGE,
        code=code,
    )


def _classify_top_level_series(rel: str, path: PurePosixPath) -> FileSpec | None:
    code = _as_series_code(path.stem)
    if code is None or code not in AV_TOP_LEVEL_SERIES:
        return None
    return _spec(
        rel,
        kind=FileKind.OBSERVATION,
        dataset=Provider.ALPHA_VANTAGE,
        provider=Provider.ALPHA_VANTAGE,
        code=code,
    )


def _classify_four_part(rel: str, path: PurePosixPath, parts: tuple[str, ...]) -> FileSpec | None:
    endpoint = parts[1]
    if endpoint == AvEndpoint.HISTORICAL_PUT_CALL_RATIO.value:
        return _classify_put_call(rel, parts)
    if endpoint == AvEndpoint.NEWS_SENTIMENT.value:
        return _classify_news(rel)
    if endpoint == AvEndpoint.GOLD_SILVER_HISTORY.value:
        return _classify_metals(rel, path) if parts[2] == Frequency.DAILY.value else None
    return None


def _classify_alpha_vantage(
    rel: str, path: PurePosixPath, parts: tuple[str, ...]
) -> FileSpec | None:
    is_csv = path.suffix.lower() == CSV_SUFFIX
    if len(parts) == 5 and parts[1] == AvEndpoint.TIME_SERIES_INTRADAY.value:
        return _classify_intraday(rel, path, parts)
    if len(parts) == 3 and parts[1] == AvEndpoint.TIME_SERIES_DAILY.value and is_csv:
        return _classify_daily(rel, path)
    if len(parts) == 4:
        if parts[1] == AvEndpoint.TREASURY_YIELD.value:
            return (
                _classify_treasury(rel, path)
                if parts[2] == Frequency.DAILY.value and is_csv
                else None
            )
        if path.suffix.lower() == JSON_SUFFIX:
            return _classify_four_part(rel, path, parts)
    if len(parts) == 3 and is_csv:
        return _classify_directory_series(rel, parts)
    if len(parts) == 2 and is_csv:
        return _classify_top_level_series(rel, path)
    return None


def classify(rel: str) -> FileSpec | None:
    """Map a path relative to ``dataset/raw`` to a loader specification."""
    rel = rel.replace("\\", "/").lstrip("./")
    path = PurePosixPath(rel)
    parts = path.parts
    if not parts:
        return None
    try:
        provider = Provider(parts[0])
    except ValueError:
        return None
    if provider is Provider.FRED:
        return _classify_fred(rel, path, parts)
    return _classify_alpha_vantage(rel, path, parts)


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
