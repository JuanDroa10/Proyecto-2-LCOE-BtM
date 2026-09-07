"""PVGIS 5.3 (ERA5) hourly PV output client.

Uses PVGIS's own PV simulation (pvcalculation=1), which already accounts for
module temperature de-rating and system losses, so no separate cell-
temperature model is needed for the historical (Version A) case.
"""
import ast
from pathlib import Path

import pandas as pd

from . import http_utils

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"


def fetch_pv_profile(lat: float, lon: float, year: int, cache_dir: Path) -> pd.Series:
    """Hourly per-unit PV output (kW per kWp installed) for one calendar year.

    Index 0..8759 — Feb 29 is dropped on leap years so every year lines up
    to the same 8760-hour convention used throughout this project.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"pvgis_{lat:.4f}_{lon:.4f}_{year}.csv"
    if cache_file.exists():
        index_vals = []
        data_vals = []
        with open(cache_file, 'r') as f:
            next(f)  # skip header
            for line in f:
                idx_str, val_str = line.rstrip().split(',')
                index_vals.append(int(idx_str))
                data_vals.append(ast.literal_eval(val_str))
        return pd.Series(data_vals, index=index_vals, name="pv_per_unit")

    session = http_utils.get_session()
    params = {
        "lat": lat, "lon": lon, "outputformat": "json",
        "startyear": year, "endyear": year,
        "pvcalculation": 1, "peakpower": 1, "loss": 14,
        "pvtechchoice": "crystSi", "optimalangles": 1,
    }
    r = session.get(PVGIS_URL, params=params, timeout=60)
    r.raise_for_status()
    hourly = r.json()["outputs"]["hourly"]

    values = []
    for rec in hourly:
        date_part = rec["time"].split(":")[0]  # e.g. '20200101'
        month, day = int(date_part[4:6]), int(date_part[6:8])
        if month == 2 and day == 29:
            continue
        values.append(rec["P"] / 1000.0)  # W for a 1 kWp system -> per-unit kW/kWp

    if len(values) != 8760:
        raise ValueError(
            f"Expected 8760 hourly PV values for ({lat},{lon},{year}), got {len(values)}"
        )

    series = pd.Series(values, index=range(8760), name="pv_per_unit")
    
    # Write to CSV using repr() to preserve floating-point precision exactly
    with open(cache_file, 'w') as f:
        f.write(',pv_per_unit\n')
        for idx, val in series.items():
            f.write(f'{idx},{repr(val)}\n')
    
    return series
