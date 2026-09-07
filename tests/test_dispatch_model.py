import pandas as pd

from src import dispatch_model as dm


def _toy_two_day_scenario():
    """48 hours, 2 identical days: PV only 06:00-18:00, cheap price during
    that PV window, expensive price at night — a clear arbitrage incentive
    for the optimizer to charge from PV by day and discharge by night."""
    n = 48
    Plu = pd.Series([1.0] * n)
    Ppvu = pd.Series([1.0 if 6 <= (h % 24) < 18 else 0.0 for h in range(n)])
    lam = pd.Series([0.05 if 6 <= (h % 24) < 18 else 0.20 for h in range(n)])
    psi = pd.Series([0.01] * n)
    return Plu, Ppvu, lam, psi


def test_solve_sizing_dispatch_is_optimal_and_energy_balanced():
    Plu, Ppvu, lam, psi = _toy_two_day_scenario()
    params = dm.SizingParams(Plinst_kw=1000.0)
    result = dm.solve_sizing_dispatch(Plu, Ppvu, lam, psi, params)

    assert result.status == "Optimal"
    assert params.Ppv_min_kw - 1e-6 <= result.Ppvinst_kw <= params.Ppv_max_kw + 1e-6
    assert result.C_kwh >= 0

    # Sanity check on the big-M linearization of PinverterBESS * w1[t] (see
    # M_BESS_INVERTER in solve_sizing_dispatch): PinverterBESS_kw must stay well clear
    # of the M bound, confirming M is a non-binding linearization device and not an
    # accidental real constraint on the optimizer's sizing decision.
    M_BESS_INVERTER = 2.0 * params.Ppv_max_kw
    assert result.PinverterBESS_kw < M_BESS_INVERTER * 0.9, (
        "PinverterBESS_kw is within 10% of the big-M bound — M may be too small"
    )

    for t in range(len(Plu)):
        supply = result.Pd[t] + result.Pb[t] + result.Ppv[t]
        use = result.Pc[t] + result.Ps[t] + params.Plinst_kw * Plu.iloc[t]
        assert abs(supply - use) < 1e-3, f"energy balance violated at hour {t}"

        floor = ((1 - params.depth_of_discharge) / 2) * result.C_kwh
        ceiling = ((1 - params.depth_of_discharge) / 2 + params.depth_of_discharge) * result.C_kwh
        assert floor - 1e-3 <= result.SOC[t] <= ceiling + 1e-3, f"SOC out of bounds at hour {t}"


def test_solve_sizing_dispatch_rejects_mismatched_series_lengths():
    import pytest
    Plu, Ppvu, lam, psi = _toy_two_day_scenario()
    params = dm.SizingParams(Plinst_kw=1000.0)
    with pytest.raises(ValueError):
        dm.solve_sizing_dispatch(Plu, Ppvu.iloc[:24], lam, psi, params)
