"""Loads the three 1 MW load curves (industria1, industria2, datacenter)."""
from pathlib import Path

import pandas as pd

from . import gams_inc_parser

LOAD_CURVE_FILES = {
    "industria1": "Plu.inc",
    "industria2": "Plu2.inc",
    "datacenter": "PluDataCenter.inc",
}


def load_all_curves(data_dir: Path) -> dict[str, pd.Series]:
    data_dir = Path(data_dir)
    curves = {}
    for name, filename in LOAD_CURVE_FILES.items():
        series = gams_inc_parser.load_inc_as_series(data_dir / filename)
        if len(series) != 8760:
            raise ValueError(f"{filename}: expected 8760 hours, got {len(series)}")
        curves[name] = series
    return curves
