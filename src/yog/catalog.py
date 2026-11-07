from __future__ import annotations

from dataclasses import dataclass, field

AV_DOCS = "https://www.alphavantage.co/documentation/"


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    name: str
    asset_class: str = "etf"
    currency: str = "USD"
    exchange_tz: str = "America/New_York"


@dataclass(frozen=True)
class SeriesSpec:
    provider: str
    code: str
    name: str
    frequency: str
    kind: str
    description: str = ""
    unit: str | None = None
    source_url: str | None = None
    release_lag_days: int | None = None
    extra: dict = field(default_factory=dict)


INSTRUMENTS: tuple[InstrumentSpec, ...] = (
    InstrumentSpec("SPY", "SPDR S&P 500 ETF Trust"),
    InstrumentSpec("XLB", "Materials Select Sector SPDR Fund"),
    InstrumentSpec("XLE", "Energy Select Sector SPDR Fund"),
    InstrumentSpec("XLF", "Financial Select Sector SPDR Fund"),
    InstrumentSpec("XLI", "Industrial Select Sector SPDR Fund"),
    InstrumentSpec("XLP", "Consumer Staples Select Sector SPDR Fund"),
    InstrumentSpec("XLU", "Utilities Select Sector SPDR Fund"),
    InstrumentSpec("XLV", "Health Care Select Sector SPDR Fund"),
    InstrumentSpec("XLY", "Consumer Discretionary Select Sector SPDR Fund"),
)


def _av(
    code: str,
    name: str,
    frequency: str,
    kind: str,
    *,
    description: str = "",
    unit: str | None = None,
    extra: dict | None = None,
) -> SeriesSpec:
    return SeriesSpec(
        provider="alpha_vantage",
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
    code: str,
    name: str,
    frequency: str,
    kind: str,
    *,
    description: str = "",
    unit: str | None = None,
    release_lag_days: int | None = None,
) -> SeriesSpec:
    return SeriesSpec(
        provider="fred",
        code=code,
        name=name,
        frequency=frequency,
        kind=kind,
        description=description,
        unit=unit,
        source_url=f"https://fred.stlouisfed.org/series/{code}",
        release_lag_days=release_lag_days,
    )


SERIES: tuple[SeriesSpec, ...] = (
    # Alpha Vantage economic indicators
    _av(
        "CPI",
        "Consumer Price Index of the United States",
        "monthly",
        "macro",
        description=(
            "Monthly consumer price index (CPI) of the United States, a widely "
            "used barometer of inflation in the broader economy."
        ),
        unit="index 1982-1984 = 100",
        extra={"endpoint": "CPI"},
    ),
    _av(
        "FEDERAL_FUNDS_RATE",
        "Federal Funds Rate",
        "daily",
        "rate",
        description="Federal funds rate (interest rate) of the United States.",
        unit="percent",
        extra={"endpoint": "FEDERAL_FUNDS_RATE"},
    ),
    _av(
        "REAL_GDP",
        "Real GDP of the United States",
        "quarterly",
        "macro",
        description=(
            "Real gross domestic product of the United States. Alpha Vantage "
            "does not expose a unit for this endpoint; values are rescaled "
            "relative to the FRED GDPC1 series."
        ),
        unit=None,
        extra={"endpoint": "REAL_GDP", "unit_note": "not specified by provider"},
    ),
    _av(
        "DURABLES",
        "Manufacturers' New Orders: Durable Goods",
        "monthly",
        "macro",
        description=("Monthly manufacturers' new orders for durable goods in the United States."),
        unit="millions of dollars",
        extra={"endpoint": "DURABLES"},
    ),
    _av(
        "INFLATION",
        "Annual Inflation Rate",
        "annual",
        "macro",
        description="Annual inflation rate of the United States.",
        unit="percent",
        extra={"endpoint": "INFLATION"},
    ),
    _av(
        "RETAIL_SALES",
        "Advance Retail Sales: Retail Trade and Food Services",
        "monthly",
        "macro",
        description=(
            "Monthly advance retail sales for retail trade and food services in the United States."
        ),
        unit="millions of dollars",
        extra={"endpoint": "RETAIL_SALES"},
    ),
    _av(
        "NONFARM_PAYROLL",
        "All Employees: Total Nonfarm",
        "monthly",
        "macro",
        description=(
            "Total nonfarm payroll employment in the United States, excluding "
            "proprietors, private household employees, unpaid volunteers, farm "
            "employees, and the unincorporated self-employed."
        ),
        unit="thousands of persons",
        extra={"endpoint": "NONFARM_PAYROLL"},
    ),
    _av(
        "UNEMPLOYMENT",
        "Unemployment Rate",
        "monthly",
        "macro",
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
            f"TREASURY_YIELD_{maturity}",
            f"US Treasury Yield: {label}",
            "daily",
            "rate",
            description="US Treasury yield for a given maturity.",
            unit="percent",
            extra={"endpoint": "TREASURY_YIELD", "maturity": maturity.lower()},
        )
        for maturity, label in (
            ("3MONTH", "3-Month"),
            ("2YEAR", "2-Year"),
            ("5YEAR", "5-Year"),
            ("7YEAR", "7-Year"),
            ("10YEAR", "10-Year"),
            ("30YEAR", "30-Year"),
        )
    ),
    # Alpha Vantage commodities and metals
    _av(
        "BRENT",
        "Brent Crude Oil",
        "daily",
        "commodity",
        description="Brent (Europe) crude oil prices.",
        unit="USD per barrel",
        extra={"endpoint": "BRENT"},
    ),
    _av(
        "WTI",
        "West Texas Intermediate Crude Oil",
        "daily",
        "commodity",
        description="West Texas Intermediate (WTI) crude oil prices.",
        unit="USD per barrel",
        extra={"endpoint": "WTI"},
    ),
    _av(
        "NATURAL_GAS",
        "Henry Hub Natural Gas Spot Price",
        "daily",
        "commodity",
        description="Henry Hub natural gas spot prices.",
        unit="USD per MMBtu",
        extra={"endpoint": "NATURAL_GAS"},
    ),
    _av(
        "COPPER",
        "Global Price of Copper",
        "monthly",
        "commodity",
        description="Global price of copper.",
        unit="USD per metric ton",
        extra={"endpoint": "COPPER"},
    ),
    _av(
        "XAUUSD",
        "Gold Spot Price",
        "daily",
        "metal",
        description="Historical gold price (XAU).",
        unit="USD per troy ounce",
        extra={"endpoint": "GOLD_SILVER_HISTORY", "nominal": "XAUUSD"},
    ),
    _av(
        "XAGUSD",
        "Silver Spot Price",
        "daily",
        "metal",
        description="Historical silver price (XAG).",
        unit="USD per troy ounce",
        extra={"endpoint": "GOLD_SILVER_HISTORY", "nominal": "XAGUSD"},
    ),
    # FRED series
    _fred(
        "BAA10Y",
        "Moody's Seasoned Baa Corporate Bond Yield Relative to 10-Year Treasury",
        "daily",
        "rate",
        description=(
            "Spread between Moody's Seasoned Baa Corporate Bond yield (DBAA) and "
            "the 10-Year Treasury Constant Maturity yield (BC_10YEAR)."
        ),
        unit="percent, not seasonally adjusted",
    ),
    _fred(
        "DTWEXBGS",
        "Nominal Broad U.S. Dollar Index",
        "daily",
        "index",
        description=(
            "Trade-weighted index of the foreign exchange value of the U.S. "
            "dollar against a broad basket of currencies."
        ),
        unit="index Jan 2006 = 100, not seasonally adjusted",
    ),
    _fred(
        "HOUST",
        "New Privately-Owned Housing Units Started: Total Units",
        "monthly",
        "macro",
        description=(
            "Number of new privately owned housing units started; a start "
            "occurs when excavation begins for the footings or foundation."
        ),
        unit="thousands of units, seasonally adjusted annual rate",
    ),
    _fred(
        "ICSA",
        "Initial Claims",
        "weekly",
        "macro",
        description=(
            "Initial claims for unemployment insurance filed by individuals "
            "after separation from an employer."
        ),
        unit="number, seasonally adjusted",
        release_lag_days=5,
    ),
    _fred(
        "INDPRO",
        "Industrial Production: Total Index",
        "monthly",
        "macro",
        description=(
            "Federal Reserve index of real output of manufacturing, mining, and "
            "electric and gas utilities."
        ),
        unit="index 2017 = 100, seasonally adjusted",
    ),
    _fred(
        "NFCI",
        "Chicago Fed National Financial Conditions Index",
        "weekly",
        "index",
        description=(
            "Comprehensive weekly update on U.S. financial conditions in money "
            "markets, debt and equity markets, and the traditional and shadow "
            "banking systems. Positive values indicate tighter-than-average "
            "conditions; negative values indicate looser-than-average conditions."
        ),
        unit="index, not seasonally adjusted",
    ),
    _fred(
        "T5YIE",
        "5-Year Breakeven Inflation Rate",
        "daily",
        "rate",
        description=(
            "Expected inflation over the next 5 years, derived from the 5-Year "
            "Treasury Constant Maturity yield minus the 5-Year Treasury "
            "Inflation-Indexed Constant Maturity yield."
        ),
        unit="percent, not seasonally adjusted",
    ),
    _fred(
        "UMCSENT",
        "University of Michigan: Consumer Sentiment",
        "monthly",
        "index",
        description=(
            "Consumer sentiment index from the University of Michigan Surveys of Consumers."
        ),
        unit="index 1966:Q1 = 100, not seasonally adjusted",
        release_lag_days=30,
    ),
    _fred(
        "VIXCLS",
        "CBOE Volatility Index: VIX",
        "daily",
        "index",
        description=(
            "Market expectation of near-term volatility conveyed by S&P 500 index option prices."
        ),
        unit="index, not seasonally adjusted",
    ),
)

SERIES_BY_KEY: dict[tuple[str, str], SeriesSpec] = {
    (spec.provider, spec.code): spec for spec in SERIES
}

INSTRUMENTS_BY_SYMBOL: dict[str, InstrumentSpec] = {spec.symbol: spec for spec in INSTRUMENTS}
