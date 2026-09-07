import pandas as pd
import pytest

from src import xm_prices


def test_fetch_spot_prices_returns_8760_plausible_values(tmp_path):
    series = xm_prices.fetch_spot_prices_cop_per_kwh(year=2023, cache_dir=tmp_path)
    assert len(series) == 8760
    assert series.index.min() == 0
    assert series.index.max() == 8759
    assert (series > 0).all()
    assert (series < 5000).all()  # COP/kWh — generous upper bound


def test_fetch_spot_prices_uses_cache_on_second_call(tmp_path):
    first = xm_prices.fetch_spot_prices_cop_per_kwh(year=2023, cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("*.csv"))
    assert len(cache_files) == 1
    second = xm_prices.fetch_spot_prices_cop_per_kwh(year=2023, cache_dir=tmp_path)
    assert first.equals(second)


def test_to_usd_per_kwh_divides_by_the_correct_annual_fx_rate():
    series_cop = pd.Series([4325.0, 8650.0])  # chosen to be exact multiples of the 2023 rate
    series_usd = xm_prices.to_usd_per_kwh(series_cop, year=2023)
    assert series_usd.iloc[0] == pytest.approx(1.0, rel=1e-6)
    assert series_usd.iloc[1] == pytest.approx(2.0, rel=1e-6)


def test_to_usd_per_kwh_raises_for_unconfigured_year():
    with pytest.raises(KeyError):
        xm_prices.to_usd_per_kwh(pd.Series([100.0]), year=1999)
