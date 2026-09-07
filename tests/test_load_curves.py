from pathlib import Path

from src import load_curves

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "load_curves"


def test_load_all_curves_returns_the_three_expected_curves():
    curves = load_curves.load_all_curves(DATA_DIR)
    assert set(curves.keys()) == {"industria1", "industria2", "datacenter"}


def test_each_curve_has_exactly_8760_hours_indexed_from_zero():
    curves = load_curves.load_all_curves(DATA_DIR)
    for name, series in curves.items():
        assert len(series) == 8760, f"{name} has {len(series)} hours, expected 8760"
        assert series.index.min() == 0
        assert series.index.max() == 8759


def test_load_factors_are_non_negative_and_plausibly_bounded():
    curves = load_curves.load_all_curves(DATA_DIR)
    for name, series in curves.items():
        assert (series >= 0).all(), f"{name} has negative load factors"
        assert (series <= 1.5).all(), f"{name} has implausibly large load factors"
