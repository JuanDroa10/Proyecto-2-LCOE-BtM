"""XM Sinergox hourly national spot price client + COP->USD conversion.

Uses pydataxm (XM's own public SDK). Requires the Task 5 CA-trust fix:
pydataxm's constructor makes an unconditional `requests.post` call, and its
`request_data()` uses `aiohttp` internally for the actual data fetch — both
need the combined CA bundle (aiohttp reads it via the SSL_CERT_FILE env var;
requests via REQUESTS_CA_BUNDLE), which `http_utils.ensure_ca_trust()` sets.
"""
import datetime as dt
from pathlib import Path

import pandas as pd

from . import http_utils

_client = None


def _get_client():
    global _client
    if _client is None:
        http_utils.ensure_ca_trust()
        from pydataxm.pydataxm import ReadDB
        _client = ReadDB()
    return _client


def fetch_spot_prices_cop_per_kwh(year: int, cache_dir: Path) -> pd.Series:
    """Hourly national spot price (COP/kWh) for the given year, index 0..8759.

    Feb 29 is dropped on leap years to keep exactly 8760 hours/year.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"xm_prices_{year}.csv"
    if cache_file.exists():
        return pd.read_csv(cache_file, index_col=0).iloc[:, 0]

    client = _get_client()
    df = client.request_data("PrecBolsNaci", "Sistema", dt.date(year, 1, 1), dt.date(year, 12, 31))
    if df.empty:
        raise ValueError(f"XM returned no data for {year}")
    df = df.sort_values("Date").reset_index(drop=True)

    hour_cols = [f"Values_Hour{h:02d}" for h in range(1, 25)]
    values = []
    for _, row in df.iterrows():
        date = row["Date"]
        if date.month == 2 and date.day == 29:
            continue
        values.extend(float(row[c]) for c in hour_cols)

    if len(values) != 8760:
        raise ValueError(f"Expected 8760 hourly prices for {year}, got {len(values)}")

    series = pd.Series(values, index=range(8760), name="cop_per_kwh")
    series.to_csv(cache_file)
    return series


# Banco de la República annual-average COP/USD rates. Approximate — verify
# against BanRep's official "TRM promedio anual" series before using for
# anything beyond order-of-magnitude currency conversion.
FX_RATE_COP_PER_USD = {
    2005: 2321, 2006: 2358, 2007: 2078, 2008: 1967, 2009: 2153,
    2010: 1898, 2011: 1848, 2012: 1798, 2013: 1869, 2014: 2001,
    2015: 2743, 2016: 3055, 2017: 2951, 2018: 2957, 2019: 3281,
    2020: 3693, 2021: 3744, 2022: 4256, 2023: 4325,
}


def to_usd_per_kwh(series_cop_per_kwh: pd.Series, year: int) -> pd.Series:
    if year not in FX_RATE_COP_PER_USD:
        raise KeyError(f"No FX rate configured for year {year}")
    return series_cop_per_kwh / FX_RATE_COP_PER_USD[year]
