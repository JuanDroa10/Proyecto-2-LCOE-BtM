import pytest

from src import lcoe
from src.dispatch_model import SizingResult


def _make_result(**overrides) -> SizingResult:
    defaults = dict(
        status="Optimal", Ppvinst_kw=2000.0, C_kwh=1000.0, PinverterBESS_kw=200.0,
        PinverterPV_kw=3000.0, Investment0_usd=1_000_000.0, OPEX_usd_per_year=50_000.0,
        OPEX0_usd_per_year=80_000.0, OPEXgross_usd_per_year=30_000.0, Es_usd_per_year=10_000.0,
        Wl_kwh_per_year=2_000_000.0, crf=0.0995890201914585, crfe=0.08275970609929227,
        Ppv=[], Pb=[], Ps=[], Pc=[], Pd=[], SOC=[],
    )
    defaults.update(overrides)
    return SizingResult(**defaults)


def test_compute_lcoe_matches_the_reference_formula_exactly():
    result = _make_result()
    out = lcoe.compute_lcoe(result)

    expected_gross = 1000 * (result.Investment0_usd + result.OPEXgross_usd_per_year / result.crfe) / (
        result.Wl_kwh_per_year / result.crf
    )
    expected_net = 1000 * (
        result.Investment0_usd
        + (result.OPEX_usd_per_year - result.OPEX0_usd_per_year - result.Es_usd_per_year) / result.crfe
    ) / (result.Wl_kwh_per_year / result.crf)

    assert out.lcoe_gross_usd_per_mwh == pytest.approx(expected_gross, rel=1e-9)
    assert out.lcoe_net_usd_per_mwh == pytest.approx(expected_net, rel=1e-9)


def test_compute_lcoe_raises_when_load_energy_is_zero():
    result = _make_result(Wl_kwh_per_year=0.0)
    with pytest.raises(ValueError):
        lcoe.compute_lcoe(result)
