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


def _toy_two_day_scenario_with_strong_arbitrage():
    """Same shape as _toy_two_day_scenario (48 hours, 2 identical days, PV only
    06:00-18:00, constant load), but with an intentionally exaggerated night price
    ($10.00/kWh vs $0.05/kWh during PV hours) — NOT a realistic price, only large
    enough to reliably force nonzero battery investment/dispatch in a small, fast
    test. _toy_two_day_scenario's more moderate spread optimizes to C=0 (a genuine,
    separately-verified optimal corner solution — see the task report), which leaves
    the SOC recursion, DoD floor/ceiling, and the big-M linearization's charge/
    discharge mutual exclusion untested whenever SOC is actually nonzero. A wider
    price spread alone does not reliably trigger battery investment either (confirmed
    up to a 10x spread with near-zero BESS costs); $10/kWh at night is the confirmed
    reliable trigger."""
    n = 48
    Plu = pd.Series([1.0] * n)
    Ppvu = pd.Series([1.0 if 6 <= (h % 24) < 18 else 0.0 for h in range(n)])
    lam = pd.Series([0.05 if 6 <= (h % 24) < 18 else 10.0 for h in range(n)])
    psi = pd.Series([0.01] * n)
    return Plu, Ppvu, lam, psi


def test_solve_sizing_dispatch_builds_and_correctly_cycles_a_battery_under_strong_arbitrage():
    Plu, Ppvu, lam, psi = _toy_two_day_scenario_with_strong_arbitrage()
    params = dm.SizingParams(Plinst_kw=1000.0)
    result = dm.solve_sizing_dispatch(Plu, Ppvu, lam, psi, params)

    assert result.status == "Optimal"
    assert result.C_kwh > 0, "expected a nonzero battery under a strongly incentivized arbitrage spread"
    assert max(result.SOC) > 0, "SOC never moved away from zero — dispatch machinery unexercised"

    floor = ((1 - params.depth_of_discharge) / 2) * result.C_kwh
    ceiling = ((1 - params.depth_of_discharge) / 2 + params.depth_of_discharge) * result.C_kwh
    assert ceiling > floor, "SOC bound is degenerate (C_kwh too small) — not a meaningful check"

    for t in range(len(Plu)):
        is_pv_hour = 6 <= (t % 24) < 18
        assert floor - 1e-3 <= result.SOC[t] <= ceiling + 1e-3, f"SOC out of bounds at hour {t}"
        assert result.Pc[t] * result.Pd[t] < 1e-6, f"charge and discharge both nonzero at hour {t}"
        if result.Pc[t] > 1e-6:
            assert is_pv_hour, f"charging happened outside PV hours at hour {t}"
        if result.Pd[t] > 1e-6:
            assert not is_pv_hour, f"discharging happened during a PV hour at hour {t}"


def test_solve_sizing_dispatch_raises_when_big_m_bound_is_implausibly_tight():
    """Runtime big-M non-binding guard (see M_BESS_INVERTER in
    solve_sizing_dispatch): _toy_two_day_scenario_with_strong_arbitrage, with
    the *default* AGGE bounds (Ppv_min_kw=1000, Ppv_max_kw=5000), already
    independently solves to Ppvinst_kw=1000 (the AGGE floor, chosen freely,
    not because it's pinned) and PinverterBESS_kw~=1852.4 (confirmed both in
    task-9-report.md and by re-running it directly here) — comfortably
    clear of the default M_BESS_INVERTER=2*5000=10000.

    This test narrows Ppv_max_kw down to 1000 (still a legal single-point
    AGGE range, and exactly the value the model already independently
    prefers) purely to shrink M_BESS_INVERTER to 2*1000=2000 kW, without
    changing the genuine underlying economics at all (Ppvinst=1000 either
    way) — so this is not a contrived/degenerate corner, just a case where a
    legitimate, narrow Ppv_max_kw configuration happens to leave M
    uncomfortably close (1852.4/2000 ~= 92.6%) to the real optimum. Confirms
    solve_sizing_dispatch raises rather than silently returning a result
    that may be distorted by a near-binding linearization constant."""
    import pytest

    Plu, Ppvu, lam, psi = _toy_two_day_scenario_with_strong_arbitrage()
    params = dm.SizingParams(Plinst_kw=1000.0, Ppv_min_kw=1000.0, Ppv_max_kw=1000.0)
    with pytest.raises(RuntimeError, match="big-M"):
        dm.solve_sizing_dispatch(Plu, Ppvu, lam, psi, params)
