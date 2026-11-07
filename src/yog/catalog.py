from __future__ import annotations

from dataclasses import dataclass, field

from yog.enums import (
    EASTERN_TZ,
    AssetClass,
    AvEndpoint,
    Frequency,
    Provider,
    SeriesCode,
    SeriesExtra,
    SeriesKind,
    Symbol,
)

AV_DOCS = "https://www.alphavantage.co/documentation/"


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: Symbol
    name: str
    asset_class: AssetClass = AssetClass.ETF
    currency: str = "USD"
    exchange_tz: str = EASTERN_TZ


@dataclass(frozen=True)
class SeriesSpec:
    provider: Provider
    code: SeriesCode
    name: str
    frequency: Frequency
    kind: SeriesKind
    description: str = ""
    unit: str | None = None
    source_url: str | None = None
    release_lag_days: int | None = None
    extra: SeriesExtra = field(default_factory=lambda: SeriesExtra())


INSTRUMENTS: tuple[InstrumentSpec, ...] = (
    InstrumentSpec(Symbol.SPY, "SPDR S&P 500 ETF Trust"),
    InstrumentSpec(Symbol.XLB, "Materials Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLE, "Energy Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLF, "Financial Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLI, "Industrial Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLP, "Consumer Staples Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLU, "Utilities Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLV, "Health Care Select Sector SPDR Fund"),
    InstrumentSpec(Symbol.XLY, "Consumer Discretionary Select Sector SPDR Fund"),
)


def _av(
    code: SeriesCode,
    name: str,
    frequency: Frequency,
    kind: SeriesKind,
    *,
    description: str = "",
    unit: str | None = None,
    extra: SeriesExtra | None = None,
) -> SeriesSpec:
    return SeriesSpec(
        provider=Provider.ALPHA_VANTAGE,
        code=code,
        name=name,
        frequency=frequency,
        kind=kind,
        description=description,
        unit=unit,
        source_url=AV_DOCS,
        extra=extra or {},
    )


def _fred(
    code: SeriesCode,
    name: str,
    frequency: Frequency,
    kind: SeriesKind,
    *,
    description: str = "",
    unit: str | None = None,
    release_lag_days: int | None = None,
) -> SeriesSpec:
    return SeriesSpec(
        provider=Provider.FRED,
        code=code,
        name=name,
        frequency=frequency,
        kind=kind,
        description=description,
        unit=unit,
        source_url=f"https://fred.stlouisfed.org/series/{code.value}",
        release_lag_days=release_lag_days,
    )


SERIES: tuple[SeriesSpec, ...] = (
    # Alpha Vantage economic indicators
    _av(
        SeriesCode.CPI,
        "Consumer Price Index of the United States",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=(
            "Monthly consumer price index (CPI) of the United States, a widely "
            "used barometer of inflation in the broader economy."
        ),
        unit="index 1982-1984 = 100",
        extra={"endpoint": "CPI"},
    ),
    _av(
        SeriesCode.FEDERAL_FUNDS_RATE,
        "Federal Funds Rate",
        Frequency.DAILY,
        SeriesKind.RATE,
        description="Federal funds rate (interest rate) of the United States.",
        unit="percent",
        extra={"endpoint": "FEDERAL_FUNDS_RATE"},
    ),
    _av(
        SeriesCode.REAL_GDP,
        "Real GDP of the United States",
        Frequency.QUARTERLY,
        SeriesKind.MACRO,
        description=(
            "Real gross domestic product of the United States. Alpha Vantage "
            "does not expose a unit for this endpoint; values are rescaled "
            "relative to the FRED GDPC1 series."
        ),
        unit=None,
        extra={"endpoint": "REAL_GDP", "unit_note": "not specified by provider"},
    ),
    _av(
        SeriesCode.DURABLES,
        "Manufacturers' New Orders: Durable Goods",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=("Monthly manufacturers' new orders for durable goods in the United States."),
        unit="millions of dollars",
        extra={"endpoint": "DURABLES"},
    ),
    _av(
        SeriesCode.INFLATION,
        "Annual Inflation Rate",
        Frequency.ANNUAL,
        SeriesKind.MACRO,
        description="Annual inflation rate of the United States.",
        unit="percent",
        extra={"endpoint": "INFLATION"},
    ),
    _av(
        SeriesCode.RETAIL_SALES,
        "Advance Retail Sales: Retail Trade and Food Services",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=(
            "Monthly advance retail sales for retail trade and food services in the United States."
        ),
        unit="millions of dollars",
        extra={"endpoint": "RETAIL_SALES"},
    ),
    _av(
        SeriesCode.NONFARM_PAYROLL,
        "All Employees: Total Nonfarm",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=(
            "Total nonfarm payroll employment in the United States, excluding "
            "proprietors, private household employees, unpaid volunteers, farm "
            "employees, and the unincorporated self-employed."
        ),
        unit="thousands of persons",
        extra={"endpoint": "NONFARM_PAYROLL"},
    ),
    _av(
        SeriesCode.UNEMPLOYMENT,
        "Unemployment Rate",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=(
            "Monthly unemployment rate of the United States: unemployed persons "
            "as a percentage of the labor force, restricted to people 16 years "
            "and older in the 50 states and DC."
        ),
        unit="percent",
        extra={"endpoint": "UNEMPLOYMENT"},
    ),
    # Alpha Vantage Treasury yields
    *(
        _av(
            code,
            f"US Treasury Yield: {label}",
            Frequency.DAILY,
            SeriesKind.RATE,
            description="US Treasury yield for a given maturity.",
            unit="percent",
            extra={
                "endpoint": AvEndpoint.TREASURY_YIELD.value,
                "maturity": maturity,
            },
        )
        for code, maturity, label in (
            (SeriesCode.TREASURY_YIELD_3MONTH, "3month", "3-Month"),
            (SeriesCode.TREASURY_YIELD_2YEAR, "2year", "2-Year"),
            (SeriesCode.TREASURY_YIELD_5YEAR, "5year", "5-Year"),
            (SeriesCode.TREASURY_YIELD_7YEAR, "7year", "7-Year"),
            (SeriesCode.TREASURY_YIELD_10YEAR, "10year", "10-Year"),
            (SeriesCode.TREASURY_YIELD_30YEAR, "30year", "30-Year"),
        )
    ),
    # Alpha Vantage commodities and metals
    _av(
        SeriesCode.BRENT,
        "Brent Crude Oil",
        Frequency.DAILY,
        SeriesKind.COMMODITY,
        description="Brent (Europe) crude oil prices.",
        unit="USD per barrel",
        extra={"endpoint": "BRENT"},
    ),
    _av(
        SeriesCode.WTI,
        "West Texas Intermediate Crude Oil",
        Frequency.DAILY,
        SeriesKind.COMMODITY,
        description="West Texas Intermediate (WTI) crude oil prices.",
        unit="USD per barrel",
        extra={"endpoint": "WTI"},
    ),
    _av(
        SeriesCode.NATURAL_GAS,
        "Henry Hub Natural Gas Spot Price",
        Frequency.DAILY,
        SeriesKind.COMMODITY,
        description="Henry Hub natural gas spot prices.",
        unit="USD per MMBtu",
        extra={"endpoint": "NATURAL_GAS"},
    ),
    _av(
        SeriesCode.COPPER,
        "Global Price of Copper",
        Frequency.MONTHLY,
        SeriesKind.COMMODITY,
        description="Global price of copper.",
        unit="USD per metric ton",
        extra={"endpoint": "COPPER"},
    ),
    _av(
        SeriesCode.XAUUSD,
        "Gold Spot Price",
        Frequency.DAILY,
        SeriesKind.METAL,
        description="Historical gold price (XAU).",
        unit="USD per troy ounce",
        extra={"endpoint": "GOLD_SILVER_HISTORY", "nominal": "XAUUSD"},
    ),
    _av(
        SeriesCode.XAGUSD,
        "Silver Spot Price",
        Frequency.DAILY,
        SeriesKind.METAL,
        description="Historical silver price (XAG).",
        unit="USD per troy ounce",
        extra={"endpoint": "GOLD_SILVER_HISTORY", "nominal": "XAGUSD"},
    ),
    # FRED series
    _fred(
        SeriesCode.BAA10Y,
        "Moody's Seasoned Baa Corporate Bond Yield Relative to 10-Year Treasury",
        Frequency.DAILY,
        SeriesKind.RATE,
        description=(
            "Spread between Moody's Seasoned Baa Corporate Bond yield (DBAA) and "
            "the 10-Year Treasury Constant Maturity yield (BC_10YEAR)."
        ),
        unit="percent, not seasonally adjusted",
    ),
    _fred(
        SeriesCode.DTWEXBGS,
        "Nominal Broad U.S. Dollar Index",
        Frequency.DAILY,
        SeriesKind.INDEX,
        description=(
            "Trade-weighted index of the foreign exchange value of the U.S. "
            "dollar against a broad basket of currencies."
        ),
        unit="index Jan 2006 = 100, not seasonally adjusted",
    ),
    _fred(
        SeriesCode.HOUST,
        "New Privately-Owned Housing Units Started: Total Units",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=(
            "Number of new privately owned housing units started; a start "
            "occurs when excavation begins for the footings or foundation."
        ),
        unit="thousands of units, seasonally adjusted annual rate",
    ),
    _fred(
        SeriesCode.ICSA,
        "Initial Claims",
        Frequency.WEEKLY,
        SeriesKind.MACRO,
        description=(
            "Initial claims for unemployment insurance filed by individuals "
            "after separation from an employer."
        ),
        unit="number, seasonally adjusted",
        release_lag_days=5,
    ),
    _fred(
        SeriesCode.INDPRO,
        "Industrial Production: Total Index",
        Frequency.MONTHLY,
        SeriesKind.MACRO,
        description=(
            "Federal Reserve index of real output of manufacturing, mining, and "
            "electric and gas utilities."
        ),
        unit="index 2017 = 100, seasonally adjusted",
    ),
    _fred(
        SeriesCode.NFCI,
        "Chicago Fed National Financial Conditions Index",
        Frequency.WEEKLY,
        SeriesKind.INDEX,
        description=(
            "Comprehensive weekly update on U.S. financial conditions in money "
            "markets, debt and equity markets, and the traditional and shadow "
            "banking systems. Positive values indicate tighter-than-average "
            "conditions; negative values indicate looser-than-average conditions."
        ),
        unit="index, not seasonally adjusted",
    ),
    _fred(
        SeriesCode.T5YIE,
        "5-Year Breakeven Inflation Rate",
        Frequency.DAILY,
        SeriesKind.RATE,
        description=(
            "Expected inflation over the next 5 years, derived from the 5-Year "
            "Treasury Constant Maturity yield minus the 5-Year Treasury "
            "Inflation-Indexed Constant Maturity yield."
        ),
        unit="percent, not seasonally adjusted",
    ),
    _fred(
        SeriesCode.UMCSENT,
        "University of Michigan: Consumer Sentiment",
        Frequency.MONTHLY,
        SeriesKind.INDEX,
        description=(
            "Consumer sentiment index from the University of Michigan Surveys of Consumers."
        ),
        unit="index 1966:Q1 = 100, not seasonally adjusted",
        release_lag_days=30,
    ),
    _fred(
        SeriesCode.VIXCLS,
        "CBOE Volatility Index: VIX",
        Frequency.DAILY,
        SeriesKind.INDEX,
        description=(
            "Market expectation of near-term volatility conveyed by S&P 500 index option prices."
        ),
        unit="index, not seasonally adjusted",
    ),
)

SERIES_BY_KEY: dict[tuple[Provider, SeriesCode], SeriesSpec] = {
    (spec.provider, spec.code): spec for spec in SERIES
}

INSTRUMENTS_BY_SYMBOL: dict[Symbol, InstrumentSpec] = {spec.symbol: spec for spec in INSTRUMENTS}
