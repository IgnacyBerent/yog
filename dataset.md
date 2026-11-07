# Dataset Description

Market and macroeconomic dataset.

The data was fetched from two public providers:

- **[Alpha Vantage](https://www.alphavantage.co/documentation/)** — equity/ETF time
  series, options statistics, news sentiment, commodities and US economic
  indicators.
- **[FRED](https://fred.stlouisfed.org/)** (Federal Reserve Bank of St. Louis) —
  additional US macroeconomic and financial series.

Descriptions in this document are taken from the official provider
documentation (Alpha Vantage documentation page and the individual FRED series
pages). Each subsection links to its source.

The dataset is stored under `dataset/raw/` and is **not committed to git**
(`dataset/` is listed in `.gitignore`). Snapshot date: **2026-10-23/24**; most
series therefore end in mid/late October 2026.

---

## Contents

- [Repository layout](#repository-layout)
- [Dataset at a glance](#dataset-at-a-glance)
- [Tickers](#tickers)
- [Alpha Vantage data](#alpha-vantage-data)
  - [Core stock time series](#core-stock-time-series)
  - [Historical put-call ratio](#historical-put-call-ratio)
  - [News & sentiment](#news--sentiment)
  - [Commodities](#commodities)
  - [Economic indicators](#economic-indicators)
- [FRED data](#fred-data)
- [File formats](#file-formats)
- [Notes and caveats](#notes-and-caveats)
- [Attribution and terms](#attribution-and-terms)

---

## Repository layout

```text
dataset/
└── raw/
    ├── alpha_vantage/
    │   ├── BRENT/daily.csv
    │   ├── COPPER/monthly.csv
    │   ├── CPI/monthly.csv
    │   ├── DURABLES.csv
    │   ├── FEDERAL_FUNDS_RATE/daily.csv
    │   ├── GOLD_SILVER_HISTORY/daily/{XAU,XAG}.json
    │   ├── HISTORICAL_PUT_CALL_RATIO/<ticker>/<YYYY-MM-DD>.json
    │   ├── INFLATION.csv
    │   ├── NATURAL_GAS/daily.csv
    │   ├── NEWS_SENTIMENT/<topic>/<window>.json
    │   ├── NONFARM_PAYROLL.csv
    │   ├── REAL_GDP/quarterly.csv
    │   ├── RETAIL_SALES.csv
    │   ├── TIME_SERIES_DAILY/SPY.csv
    │   ├── TIME_SERIES_INTRADAY/{1min,5min}/<ticker>/<YYYY-MM>.csv
    │   ├── TREASURY_YIELD/daily/<maturity>.csv
    │   ├── UNEMPLOYMENT.csv
    │   └── WTI/daily.csv
    └── fred/
        ├── BAA10Y.csv
        ├── DTWEXBGS.csv
        ├── HOUST.csv
        ├── ICSA.csv
        ├── INDPRO.csv
        ├── NFCI.csv
        ├── T5YIE.csv
        ├── UMCSENT.csv
        └── VIXCLS.csv
```

---

## Dataset at a glance

| Dataset | Files | Coverage | Granularity |
| --- | ---: | --- | --- |
| `TIME_SERIES_INTRADAY/1min` | 2,898 | 2000-01 → 2026-10 | 1-minute OHLCV |
| `TIME_SERIES_INTRADAY/5min` | 2,898 | 2000-01 → 2026-10 | 5-minute OHLCV |
| `TIME_SERIES_DAILY` | 1 | 1999-11-01 → 2026-10-23 | Daily OHLCV (SPY) |
| `HISTORICAL_PUT_CALL_RATIO` | 42,588 | 2008-01-02 → 2026-10-23 | Daily, per ticker |
| `NEWS_SENTIMENT` | 9,679 | 2010-01 → 2026-10-23 | Weekly archives, 9 topics |
| Commodities (`WTI`, `BRENT`, `NATURAL_GAS`, `COPPER`, `GOLD_SILVER_HISTORY`) | 6 | 1980 → 2026 | Daily / monthly |
| Economic indicators (Alpha Vantage) | 14 | 1913 → 2026 | Daily / monthly / quarterly / annual |
| FRED series | 9 | 1919 → 2026 | Daily / weekly / monthly |

Total: **58,093 files**, approximately **6.9 GB**.

---

## Tickers

The equity/ETF datasets cover the S&P 500 proxy plus eight SPDR Select
Sector ETFs:

| Ticker | Instrument |
| --- | --- |
| `SPY` | SPDR S&P 500 ETF Trust |
| `XLB` | Materials Select Sector SPDR Fund |
| `XLE` | Energy Select Sector SPDR Fund |
| `XLF` | Financial Select Sector SPDR Fund |
| `XLI` | Industrial Select Sector SPDR Fund |
| `XLP` | Consumer Staples Select Sector SPDR Fund |
| `XLU` | Utilities Select Sector SPDR Fund |
| `XLV` | Health Care Select Sector SPDR Fund |
| `XLY` | Consumer Discretionary Select Sector SPDR Fund |

---

## Alpha Vantage data

Source: <https://www.alphavantage.co/documentation/>

### Core stock time series

#### Intraday — `TIME_SERIES_INTRADAY`

> This API returns current and 25+ years of historical intraday OHLCV time
> series of the equity specified, covering pre-market and post-market hours
> where applicable (e.g., 4:00am to 8:00pm Eastern Time for the US market). You
> can query both raw (as-traded) and split/dividend-adjusted intraday data from
> this endpoint. The OHLCV data is sometimes called "candles" in finance
> literature.

- Stored as one CSV per ticker and calendar month, e.g.
  `TIME_SERIES_INTRADAY/5min/SPY/2024-01.csv`.
- Both `1min` and `5min` intervals are present, for all nine tickers.
- Files are downloaded month-by-month using the endpoint's `month=YYYY-MM`
  parameter (`outputsize=full`), which is why the data reaches back to January
  2000.

**Columns**

| Column | Meaning |
| --- | --- |
| `timestamp` | Bar timestamp (US Eastern Time); extended-hours bars included |
| `open` | Opening price of the bar |
| `high` | Highest price during the bar |
| `low` | Lowest price during the bar |
| `close` | Closing price of the bar |
| `volume` | Number of shares traded during the bar |

Rows are ordered **newest first**.

#### Daily — `TIME_SERIES_DAILY`

> This API returns raw (as-traded) daily time series (date, daily open, daily
> high, daily low, daily close, daily volume) of the global equity specified,
> covering 25+ years of historical data. The OHLCV data is sometimes called
> "candles" in finance literature.

- `TIME_SERIES_DAILY/SPY.csv`, covering 1999-11-01 → 2026-10-23.
- Columns: `timestamp,open,high,low,close,volume` (newest first).

---

### Historical put-call ratio

`HISTORICAL_PUT_CALL_RATIO`

> This API returns historical put-call ratios for both the entire option chain
> and for specific expiration dates. A lower put-call ratio (<=0.6) typically
> signals bullish sentiment, as investors are purchasing more call options in
> expectation of rising prices. On the other hand, a higher ratio (>=1.0)
> suggests bearish sentiment. However, because this metric is often used as a
> contrarian indicator, extreme values can imply the opposite — e.g., readings
> much higher than 1.0 may actually indicate a bullish outlook, while very low
> readings close to zero can point to potential bearish conditions.

- One JSON file per ticker per trading day:
  `HISTORICAL_PUT_CALL_RATIO/<ticker>/<YYYY-MM-DD>.json`.
- 9 tickers × 4,732 trading days = 42,588 files, covering 2008-01-02 →
  2026-10-23.

**Structure**

```json
{
  "symbol": "SPY",
  "date": "2024-01-02",
  "put_call_ratio_full_chain": "1.03",
  "put_call_ratio_by_expiration": [
    { "date": "2024-01-02", "value": "0.98" },
    { "date": "2024-01-03", "value": "0.93" }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `symbol` | Underlying ticker |
| `date` | Trading date of the observation |
| `put_call_ratio_full_chain` | Put/call ratio across the full option chain |
| `put_call_ratio_by_expiration` | Ratio broken down by expiration date; each `date` is the expiration date |

---

### News & sentiment

`NEWS_SENTIMENT`

> Looking for market news data to train your LLM models or to augment your
> trading strategy? You have just found it. This API returns live and historical
> market news & sentiment data from a large & growing selection of premier news
> outlets around the world, covering stocks, cryptocurrencies, forex, and a
> wide range of topics such as fiscal policy, mergers & acquisitions, IPOs, etc.
> This API, combined with our core stock API, fundamental data, and technical
> indicator APIs, can provide you with a 360-degree view of the financial market
> and the broader economy.

- Stored per **topic**, in weekly archive files:
  `NEWS_SENTIMENT/<topic>/<from>_<to>.json`, where timestamps use the
  `YYYYMMDDTHHMM` format.
- Nine topics are present:

  | Topic | Description (Alpha Vantage) |
  | --- | --- |
  | `economy_fiscal` | Economy — fiscal policy (e.g., tax reform, government spending) |
  | `economy_macro` | Economy — macro/overall |
  | `economy_monetary` | Economy — monetary policy (e.g., interest rates, inflation) |
  | `energy_transportation` | Energy & transportation |
  | `finance` | Finance |
  | `financial_markets` | Financial markets |
  | `life_sciences` | Life sciences |
  | `manufacturing` | Manufacturing |
  | `retail_wholesale` | Retail & wholesale |

- Weekly archives run from early January 2010 → 2026-10-23. Each topic also
  contains a small `20000101T0000_now.json` snapshot file.
- ~5.1 GB in total.

**Structure**

```json
{
  "items": "7",
  "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat_Bullish; x >= 0.35: Bullish",
  "relevance_score_definition": "0 < x <= 1, with a higher score indicating higher relevance.",
  "feed": [
    {
      "title": "...",
      "url": "...",
      "time_published": "20150918T085644",
      "authors": ["..."],
      "summary": "...",
      "banner_image": null,
      "source": "...",
      "category_within_source": "...",
      "source_domain": "...",
      "topics": [
        { "topic": "economy_fiscal", "relevance_score": "0.913968" }
      ],
      "overall_sentiment_score": -0.401563,
      "overall_sentiment_label": "Bearish",
      "ticker_sentiment": [
        {
          "ticker": "KO",
          "relevance_score": "1.000000",
          "ticker_sentiment_score": "-0.405763",
          "ticker_sentiment_label": "Bearish"
        }
      ]
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `items` | Number of articles in the archive |
| `sentiment_score_definition` | Mapping of sentiment score to label |
| `relevance_score_definition` | Definition of the relevance scale |
| `feed[].time_published` | Publication timestamp in `YYYYMMDDTHHMMSS` |
| `feed[].topics[].relevance_score` | Relevance of the article to that topic |
| `feed[].overall_sentiment_score` | Article-level sentiment score |
| `feed[].overall_sentiment_label` | Article-level sentiment label |
| `feed[].ticker_sentiment` | Per-ticker relevance and sentiment |

---

### Commodities

Source descriptions from the Alpha Vantage **Commodities** section. Underlying
data comes from the U.S. Energy Information Administration (EIA), the
International Monetary Fund (IMF), and other providers via FRED.

| Folder | Alpha Vantage endpoint | Description (from docs) | Unit / form | Coverage |
| --- | --- | --- | --- | --- |
| `WTI/daily.csv` | `WTI` | West Texas Intermediate (WTI) crude oil prices | USD per barrel, daily | 1986-01-02 → 2026-10-20 |
| `BRENT/daily.csv` | `BRENT` | Brent (Europe) crude oil prices | USD per barrel, daily | 1987-05-20 → 2026-10-20 |
| `NATURAL_GAS/daily.csv` | `NATURAL_GAS` | Henry Hub natural gas spot prices | USD per MMBtu, daily | 1997-01-07 → 2026-10-20 |
| `COPPER/monthly.csv` | `COPPER` | Global price of copper | USD per metric ton, monthly | 1980-01-01 → 2026-09-01 |
| `GOLD_SILVER_HISTORY/daily/XAU.json` | `GOLD_SILVER_HISTORY` | Historical gold price (`XAU`, `GOLD`) | USD per troy ounce, daily | 2011-06-01 → 2026-10-23 |
| `GOLD_SILVER_HISTORY/daily/XAG.json` | `GOLD_SILVER_HISTORY` | Historical silver price (`XAG`, `SILVER`) | USD per troy ounce, daily | 2011-06-01 → 2026-10-23 |

Official wording:

- **WTI** — "This API returns the West Texas Intermediate (WTI) crude oil
  prices in daily, weekly, and monthly horizons."
- **Brent** — "This API returns the Brent (Europe) crude oil prices in daily,
  weekly, and monthly horizons."
- **Natural Gas** — "This API returns the Henry Hub natural gas spot prices in
  daily, weekly, and monthly horizons."
- **Copper** — "This API returns the global price of copper in monthly,
  quarterly, and annual horizons."
- **Gold & Silver (History)** — "This API returns the historical gold and silver
  prices in daily, weekly, and monthly horizons."

The commodity CSVs use the columns `timestamp,value`. The gold/silver JSON files
use:

```json
{
  "nominal": "XAUUSD",
  "data": [
    { "date": "2026-10-23", "price": "4024.3473011721" }
  ]
}
```

---

### Economic indicators

Source descriptions from the Alpha Vantage **Economic Indicators** section. All
series ultimately come from U.S. government statistical agencies via FRED.

| Folder | Endpoint | Description (from docs) | Frequency | Coverage |
| --- | --- | --- | --- | --- |
| `REAL_GDP/quarterly.csv` | `REAL_GDP` | Real GDP of the United States | Quarterly | 2002-01-01 → 2026-04-01 |
| `TREASURY_YIELD/daily/*.csv` | `TREASURY_YIELD` | US Treasury yield for a given maturity (3-month, 2-, 5-, 7-, 10-, 30-year) | Daily | 1962 → 2026-10-22 |
| `FEDERAL_FUNDS_RATE/daily.csv` | `FEDERAL_FUNDS_RATE` | Federal funds rate (interest rate) of the United States | Daily | 1954-07-01 → 2026-10-22 |
| `CPI/monthly.csv` | `CPI` | Consumer Price Index of the United States | Monthly | 1913-01-01 → 2026-09-01 |
| `DURABLES.csv` | `DURABLES` | Manufacturers' New Orders: Durable Goods | Monthly | 1992-02-01 → 2026-08-01 |
| `INFLATION.csv` | `INFLATION` | Annual inflation rate (consumer prices) of the United States | Annual | 1960-01-01 → 2024-01-01 |
| `RETAIL_SALES.csv` | `RETAIL_SALES` | Advance Retail Sales: Retail Trade and Food Services | Monthly | 1992-01-01 → 2026-09-01 |
| `UNEMPLOYMENT.csv` | `UNEMPLOYMENT` | Monthly unemployment data of the United States | Monthly | 1948-01-01 → 2026-09-01 |
| `NONFARM_PAYROLL.csv` | `NONFARM_PAYROLL` | All Employees: Total Nonfarm (Total Nonfarm Payroll) | Monthly | 1939-01-01 → 2026-09-01 |

Official wording:

- **Real GDP** — "This API returns the annual and quarterly Real GDP of the
  United States." Source: U.S. Bureau of Economic Analysis via FRED.
- **Treasury Yield** — "This API returns the daily, weekly, and monthly US
  treasury yield of a given maturity timeline (e.g., 5 year, 30 year, etc)."
  Source: Board of Governors of the Federal Reserve System via FRED.
- **Federal Funds Rate** — "This API returns the daily, weekly, and monthly
  federal funds rate (interest rate) of the United States." Source: Board of
  Governors of the Federal Reserve System via FRED.
- **CPI** — "This API returns the monthly and semiannual consumer price index
  (CPI) of the United States. CPI is widely regarded as the barometer of
  inflation levels in the broader economy." Source: U.S. Bureau of Labor
  Statistics via FRED. Unit: **index 1982-1984 = 100**.
- **Durables** — "This API returns the monthly manufacturers' new orders for
  durable goods in the United States." Source: U.S. Census Bureau via FRED.
  Unit: **millions of dollars**.
- **Inflation** — "This API returns the annual inflation rates (consumer
  prices) of the United States." Source: World Bank via FRED. Unit:
  **percent**.
- **Retail Sales** — "This API returns the monthly Advance Retail Sales: Retail
  Trade and Food Services data of the United States." Source: U.S. Census
  Bureau via FRED. Unit: **millions of dollars**.
- **Unemployment** — "This API returns the monthly unemployment data of the
  United States. The unemployment rate represents the number of unemployed as a
  percentage of the labor force. Labor force data are restricted to people 16
  years of age and older, who currently reside in 1 of the 50 states or the
  District of Columbia, who do not reside in institutions (e.g., penal and
  mental facilities, homes for the aged), and who are not on active duty in the
  Armed Forces." Source: U.S. Bureau of Labor Statistics via FRED.
- **Nonfarm Payroll** — "This API returns the monthly US All Employees: Total
  Nonfarm (commonly known as Total Nonfarm Payroll), a measure of the number of
  U.S. workers in the economy that excludes proprietors, private household
  employees, unpaid volunteers, farm employees, and the unincorporated
  self-employed." Source: U.S. Bureau of Labor Statistics via FRED.

Treasury maturities available:

| File | Maturity | Coverage |
| --- | --- | --- |
| `TREASURY_YIELD/daily/3month.csv` | 3-month | 1981-09-01 → 2026-10-22 |
| `TREASURY_YIELD/daily/2year.csv` | 2-year | 1976-06-01 → 2026-10-22 |
| `TREASURY_YIELD/daily/5year.csv` | 5-year | 1962-01-02 → 2026-10-22 |
| `TREASURY_YIELD/daily/7year.csv` | 7-year | 1969-07-01 → 2026-10-22 |
| `TREASURY_YIELD/daily/10year.csv` | 10-year | 1962-01-02 → 2026-10-22 |
| `TREASURY_YIELD/daily/30year.csv` | 30-year | 1977-02-15 → 2026-10-22 |

The economic-indicator CSVs use the columns `timestamp,value`.

---

## FRED data

Source: <https://fred.stlouisfed.org/>. Files use the columns
`observation_date,<SERIES_ID>` and are sorted **oldest first**.

| File | Series | Description | Units | Frequency | Coverage |
| --- | --- | --- | --- | --- | --- |
| `BAA10Y.csv` | Moody's Seasoned Baa Corporate Bond Yield Relative to Yield on 10-Year Treasury Constant Maturity | Spread between Moody's Seasoned Baa Corporate Bond (`DBAA`) and the 10-Year Treasury Constant Maturity (`BC_10YEAR`) | Percent, not seasonally adjusted | Daily | 1986-01-02 → 2026-10-22 |
| `DTWEXBGS.csv` | Nominal Broad U.S. Dollar Index | Trade-weighted index of the foreign exchange value of the U.S. dollar against a broad basket of currencies | Index Jan 2006 = 100, NSA | Daily | 2006-01-02 → 2026-10-16 |
| `HOUST.csv` | New Privately-Owned Housing Units Started: Total Units | Number of new privately owned housing units started; a start occurs when excavation begins for the footings or foundation | Thousands of units, seasonally adjusted annual rate | Monthly | 1959-01-01 → 2026-09-01 |
| `ICSA.csv` | Initial Claims | Initial claims for unemployment insurance filed by individuals after separation from an employer | Number, seasonally adjusted | Weekly, ending Saturday | 1967-01-07 → 2026-10-17 |
| `INDPRO.csv` | Industrial Production: Total Index | Federal Reserve index of real output of manufacturing, mining, and electric and gas utilities | Index 2017 = 100, seasonally adjusted | Monthly | 1919-01-01 → 2026-09-01 |
| `NFCI.csv` | Chicago Fed National Financial Conditions Index | Comprehensive weekly update on U.S. financial conditions in money markets, debt and equity markets, and the traditional and "shadow" banking systems. Positive values indicate tighter-than-average conditions; negative values indicate looser-than-average conditions | Index, NSA | Weekly, ending Friday | 1971-01-08 → 2026-10-16 |
| `T5YIE.csv` | 5-Year Breakeven Inflation Rate | Expected inflation over the next 5 years derived from 5-Year Treasury Constant Maturity (`DGS5`) minus 5-Year Treasury Inflation-Indexed Constant Maturity (`DFII5`) | Percent, NSA | Daily | 2003-01-02 → 2026-10-23 |
| `UMCSENT.csv` | University of Michigan: Consumer Sentiment | Consumer sentiment index from the University of Michigan Surveys of Consumers | Index 1966:Q1 = 100, NSA | Monthly | 1952-11-01 → 2026-09-01 |
| `VIXCLS.csv` | CBOE Volatility Index: VIX | Market expectation of near-term volatility conveyed by S&P 500 index option prices | Index, NSA | Daily, close | 1990-01-02 → 2026-10-22 |

### FRED source notes

- **BAA10Y** — Source: Federal Reserve Bank of St. Louis; Release: Interest Rate
  Spreads. Series is calculated as the spread between Moody's Seasoned Baa
  Corporate Bond (`DBAA`) and the 10-Year Treasury Constant Maturity
  (`BC_10YEAR`). Starting with the update on June 21, 2019, the Treasury bond
  data used in the spread is obtained directly from the U.S. Treasury
  Department.
- **DTWEXBGS** — Source: Board of Governors of the Federal Reserve System (US);
  Release: H.10 Foreign Exchange Rates.
- **HOUST** — Source: U.S. Census Bureau and U.S. Department of Housing and
  Urban Development; Release: New Residential Construction.
- **ICSA** — Source: U.S. Employment and Training Administration; Release:
  Unemployment Insurance Weekly Claims Report.
- **INDPRO** — Source: Board of Governors of the Federal Reserve System (US);
  Release: G.17 Industrial Production and Capacity Utilization.
- **NFCI** — Source: Federal Reserve Bank of Chicago; Release: Chicago Fed
  National Financial Conditions Index.
- **T5YIE** — Source: Federal Reserve Bank of St. Louis; Release: Interest Rate
  Spreads.
- **UMCSENT** — Source: University of Michigan; Release: Surveys of Consumers.
  At the request of the source, data is delayed by 1 month.
- **VIXCLS** — Source: Chicago Board Options Exchange (CBOE); Release: CBOE
  Market Statistics. VIX measures market expectation of near-term volatility
  conveyed by stock index option prices.

---

## File formats

### CSV files

All CSV files have a header row and comma-separated values.

- Alpha Vantage CSVs are sorted **newest first**:
  `timestamp,open,high,low,close,volume` (OHLCV) or `timestamp,value`
  (single-series indicators).
- FRED CSVs are sorted **oldest first** and use
  `observation_date,<SERIES_ID>`.

### JSON files

- **Put-call ratio** — one object per file with `symbol`, `date`,
  `put_call_ratio_full_chain`, and `put_call_ratio_by_expiration`.
- **News sentiment** — one object per archive with `items`,
  `sentiment_score_definition`, `relevance_score_definition`, and a `feed`
  array of articles.
- **Gold/silver history** — one object per metal with `nominal` (`XAUUSD` /
  `XAGUSD`) and a `data` array of `{date, price}` objects.

---

## Notes and caveats

- **Snapshot, not a live feed.** All files are a point-in-time capture from
  around 2026-10-23/24. Newer observations may exist at the provider.
- **No cleaning applied.** Data is stored as fetched. Missing observations can
  appear as empty fields (FRED) or `"."` (some Alpha Vantage endpoints).
- **Different orderings.** Remember that Alpha Vantage CSVs are newest-first
  while FRED CSVs are oldest-first.
- **Timestamps.** Intraday timestamps are in US Eastern Time and include
  pre-market/post-market bars. Daily/monthly/quarterly timestamps use the first
  day of the period for economic series.
- **Mixed frequencies.** Do not join series blindly: daily, weekly, monthly,
  quarterly and annual series are mixed. Resample/align explicitly.
- **Revisions.** Macro series (especially GDP, payrolls, CPI, claims) are subject
  to revision by the source agency. Values shown are the latest vintage at
  capture time.
- **Storage.** `dataset/` is git-ignored, so the data must be fetched separately
  from the repository.

---

## Attribution and terms

- **Alpha Vantage** — <https://www.alphavantage.co/documentation/>. Alpha Vantage
  data is subject to its own [terms of use](https://www.alphavantage.co/terms_of_service/).
  Several Alpha Vantage endpoints redistribute FRED data; Alpha Vantage notes
  that its data feed uses the FRED® API but is not endorsed or certified by the
  Federal Reserve Bank of St. Louis.
- **FRED** — <https://fred.stlouisfed.org/>. Series are subject to the
  [FRED® API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html)
  and the copyright/citation requirements noted on each series page. Some series
  (e.g., `BAA10Y`, `NFCI`, `UMCSENT`, `VIXCLS`) carry third-party copyright and
  require citation.

Suggested citation format for FRED series:

> Federal Reserve Bank of St. Louis, *[Series name]* [*SERIES_ID*], retrieved
> from FRED, Federal Reserve Bank of St. Louis;
> <https://fred.stlouisfed.org/series/*SERIES_ID>*.
