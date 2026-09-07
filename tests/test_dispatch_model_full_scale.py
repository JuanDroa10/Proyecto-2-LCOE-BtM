# tests/test_dispatch_model_full_scale.py (separate file: this test is slow — full 8760h MILP solve)
from pathlib import Path

from src import dispatch_model as dm
from src import gams_inc_parser

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "reference_spain"


# Measured wall-clock solve time on this project's reference hardware: ~140s (4 runs,
# range 139.9-141.4s). See design spec section 8 for what this implies for the full
# ~684-solve Version A+B sweep (~26.6h sequential at this rate).
def test_full_scale_solve_on_real_spain_reference_data_is_optimal_and_balanced():
    Ppvu = gams_inc_parser.load_inc_as_series(DATA_DIR / "PpvuMadridSarah20052023_localtime.inc")
    lam = gams_inc_parser.load_inc_as_series(DATA_DIR / "lambda_spain_localtime.inc")
    psi = gams_inc_parser.load_inc_as_series(DATA_DIR / "psi.inc")
    Plu = gams_inc_parser.load_inc_as_series(DATA_DIR / "PluDataCenter.inc")
    assert len(Ppvu) == len(lam) == len(psi) == len(Plu) == 8760

    params = dm.SizingParams(Plinst_kw=1000.0)
    result = dm.solve_sizing_dispatch(Plu, Ppvu, lam, psi, params)

    assert result.status == "Optimal"
    assert params.Ppv_min_kw - 1e-6 <= result.Ppvinst_kw <= params.Ppv_max_kw + 1e-6

    # Same big-M sanity check as the fast test (see M_BESS_INVERTER in
    # solve_sizing_dispatch, added to linearize the reference model's bilinear
    # PinverterBESS * w1[t] terms for PuLP): confirm the bound is still non-binding
    # at full 8760h scale, not just in the 48-hour toy scenario.
    M_BESS_INVERTER = 2.0 * params.Ppv_max_kw
    assert result.PinverterBESS_kw < M_BESS_INVERTER * 0.9, (
        "PinverterBESS_kw is within 10% of the big-M bound — M may be too small"
    )

    total_supply = sum(result.Pd) + sum(result.Pb) + sum(result.Ppv)
    total_use = sum(result.Pc) + sum(result.Ps) + result.Wl_kwh_per_year
    assert abs(total_supply - total_use) < 1.0  # kWh, over a full year — tight tolerance
