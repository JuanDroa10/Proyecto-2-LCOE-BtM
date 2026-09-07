from pathlib import Path

import pandas as pd
import pytest

from src import gams_inc_parser


def test_parse_inc_series_handles_normal_multiline_format():
    text = "Table data4(t,*)\n\tPlu\nt1\t0.5\nt2\t0.75\nt3\t1.0\n"
    result = gams_inc_parser.parse_inc_series(text)
    assert result == {1: 0.5, 2: 0.75, 3: 1.0}


def test_parse_inc_series_handles_flattened_single_line_format():
    text = "Table data3(t,*)Ppvut1\t0t2\t0.0848t3\t0.259"
    result = gams_inc_parser.parse_inc_series(text)
    assert result == {1: 0.0, 2: 0.0848, 3: 0.259}


def test_load_inc_as_series_returns_zero_indexed_series(tmp_path):
    p = tmp_path / "sample.inc"
    p.write_text("Table data4(t,*)\n\tX\nt1\t10.0\nt2\t20.0\n")
    series = gams_inc_parser.load_inc_as_series(p)
    assert series.index.tolist() == [0, 1]
    assert series.tolist() == [10.0, 20.0]


def test_load_inc_as_series_raises_on_missing_hours():
    with pytest.raises(FileNotFoundError):
        gams_inc_parser.load_inc_as_series(Path("/no/such/file.inc"))
