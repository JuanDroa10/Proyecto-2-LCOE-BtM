from pathlib import Path

from src import pvgis_client


def test_fetch_pv_profile_returns_8760_plausible_values(tmp_path):
    series = pvgis_client.fetch_pv_profile(lat=4.7110, lon=-74.0721, year=2020, cache_dir=tmp_path)
    assert len(series) == 8760
    assert series.index.min() == 0
    assert series.index.max() == 8759
    assert (series >= 0).all()
    assert (series <= 1.5).all()
    # Plausible annual specific yield range for a fixed-tilt system in Colombia (kWh/kWp/year).
    assert 800 < series.sum() < 2500


def test_fetch_pv_profile_uses_cache_on_second_call(tmp_path):
    first = pvgis_client.fetch_pv_profile(lat=4.7110, lon=-74.0721, year=2020, cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("*.csv"))
    assert len(cache_files) == 1
    second = pvgis_client.fetch_pv_profile(lat=4.7110, lon=-74.0721, year=2020, cache_dir=tmp_path)
    assert first.equals(second)
    assert len(list(tmp_path.glob("*.csv"))) == 1  # no new file written
