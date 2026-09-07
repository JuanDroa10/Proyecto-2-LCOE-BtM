"""Parser for the GAMS-style `.inc` table files used by the reference repo.

Handles both the normal one-pair-per-line format and the flattened
single-line format (see PpvuMadridSarah20052023_localtime.inc, which has
zero newlines) by matching `t<digits><whitespace><number>` across the whole
file content rather than iterating line by line.
"""
import re
from pathlib import Path

import pandas as pd

_TOKEN_RE = re.compile(r"t(\d+)\s+([-+0-9.eE]+)")


def parse_inc_series(text: str) -> dict[int, float]:
    return {int(hour): float(value) for hour, value in _TOKEN_RE.findall(text)}


def load_inc_as_series(path: Path) -> pd.Series:
    """Load an `.inc` file into a 0-indexed (0..N-1) hourly Series."""
    text = Path(path).read_text(encoding="utf-8")
    values = parse_inc_series(text)
    series = pd.Series(values).sort_index()
    series.index = series.index - 1
    return series
