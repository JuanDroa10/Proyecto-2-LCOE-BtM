"""PV+BESS behind-the-meter optimal sizing + dispatch (Colombia AGGE adaptation).

Ports the reference Spain model (Gurobi; see
github.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing) to PuLP/CBC.

Two structural changes from the Spain original (see design doc section 3.3):
1. Spain's 6-period contracted-power capacity charge is dropped (the brief
   says not to model hourly/periodic power charges); replaced by a flat CREG
   AGGE backup charge that applies only when the PV+BESS project exists
   (CapacityP0 = 0 in the no-project baseline).
2. Currency: inputs are already USD/kWh (converted upstream from COP); no
   internal EUR->USD exchange-rate factor.
"""
from dataclasses import dataclass

import pandas as pd
import pulp

from . import finance


@dataclass
class SizingParams:
    Plinst_kw: float
    depth_of_discharge: float = 0.90
    eff_charge: float = 0.9624
    eff_discharge: float = 0.9624
    Ppv_min_kw: float = 1000.0   # CREG 174/2021 AGGE floor (1 MW)
    Ppv_max_kw: float = 5000.0   # CREG 174/2021 AGGE ceiling (5 MW)
    oam_pv_usd_per_kwp_year: float = 12.5
    oam_bess_usd_per_kwh_year: float = 5.9
    capex_pv_usd_per_kwp: float = 388.0
    capex_bess_usd_per_kwh: float = 185.0
    capex_inverter_usd_per_kw: float = 48.0
    balance_of_plant_usd: float = 0.0
    soft_cost_multiplier: float = 1.2
    discount_rate: float = 0.077
    project_life_years: int = 20
    escalation_rate: float = 0.025
    agge_backup_charge_usd_per_kwp_year: float = 10.0

    @property
    def PmaxF_kw(self) -> float:
        """Grid import/export frontier. Interpreted as the load's own peak,
        matching the reference model's own convention (PmaxF = Plinst) — see
        design doc section 3.3 for why the brief's '1000 MW' is read as a
        units slip rather than taken literally."""
        return self.Plinst_kw


@dataclass
class SizingResult:
    status: str
    Ppvinst_kw: float
    C_kwh: float
    PinverterBESS_kw: float
    PinverterPV_kw: float
    Investment0_usd: float
    OPEX_usd_per_year: float
    OPEX0_usd_per_year: float
    OPEXgross_usd_per_year: float
    Es_usd_per_year: float
    Wl_kwh_per_year: float
    crf: float
    crfe: float
    Ppv: list
    Pb: list
    Ps: list
    Pc: list
    Pd: list
    SOC: list


def solve_sizing_dispatch(
    Plu: pd.Series,
    Ppvu: pd.Series,
    lambda_usd_per_kwh: pd.Series,
    psi_usd_per_kwh: pd.Series,
    params: SizingParams,
) -> SizingResult:
    n_hours = len(Plu)
    if not (len(Ppvu) == len(lambda_usd_per_kwh) == len(psi_usd_per_kwh) == n_hours):
        raise ValueError("All hourly series must have the same length")

    T = range(n_hours)
    Plu_v = Plu.to_numpy()
    Ppvu_v = Ppvu.to_numpy()
    lam_v = lambda_usd_per_kwh.to_numpy()
    psi_v = psi_usd_per_kwh.to_numpy()

    prob = pulp.LpProblem("PV_BESS_Sizing_Colombia", pulp.LpMaximize)

    Ppvinst = pulp.LpVariable("Ppvinst", lowBound=params.Ppv_min_kw, upBound=params.Ppv_max_kw)
    C = pulp.LpVariable("C", lowBound=0)
    PinverterBESS = pulp.LpVariable("PinverterBESS", lowBound=0)
    PinverterPV = pulp.LpVariable("PinverterPV", lowBound=0)
    SOC0 = pulp.LpVariable("SOC0", lowBound=0)

    Ppv = pulp.LpVariable.dicts("Ppv", T, lowBound=0)
    Ppvmx = pulp.LpVariable.dicts("Ppvmx", T, lowBound=0)
    Pd = pulp.LpVariable.dicts("Pd", T, lowBound=0)
    Pc = pulp.LpVariable.dicts("Pc", T, lowBound=0)
    Pb = pulp.LpVariable.dicts("Pb", T, lowBound=0)
    Ps = pulp.LpVariable.dicts("Ps", T, lowBound=0)
    SOC = pulp.LpVariable.dicts("SOC", T, lowBound=0)
    w1 = pulp.LpVariable.dicts("w1", T, cat="Binary")
    w3 = pulp.LpVariable.dicts("w3", T, cat="Binary")

    PmaxF = params.PmaxF_kw
    DoD = params.depth_of_discharge
    Plinst = params.Plinst_kw
    M_BESS_INVERTER = 2.0 * params.Ppv_max_kw  # big-M bound for linearizing PinverterBESS * w1[t];
    # generous relative to the AGGE PV ceiling (params.Ppv_max_kw), since a BESS inverter larger than
    # 2x the max allowed PV system would never be economically optimal for this class of project

    Es = pulp.lpSum(lam_v[t] * Ps[t] for t in T)
    Eb = pulp.lpSum((lam_v[t] + psi_v[t]) * Pb[t] for t in T)
    Eb0 = pulp.lpSum((lam_v[t] + psi_v[t]) * Plinst * Plu_v[t] for t in T)

    CapacityP = params.agge_backup_charge_usd_per_kwp_year * Ppvinst
    CapacityP0 = 0.0  # no backup charge without self-generation

    OPEX = CapacityP + Eb + params.oam_pv_usd_per_kwp_year * Ppvinst + params.oam_bess_usd_per_kwh_year * C
    OPEX0 = Eb0 + CapacityP0
    OPEXgross = params.oam_pv_usd_per_kwp_year * Ppvinst + params.oam_bess_usd_per_kwh_year * C

    Investment0 = params.balance_of_plant_usd + params.soft_cost_multiplier * (
        params.capex_pv_usd_per_kwp * Ppvinst
        + params.capex_bess_usd_per_kwh * C
        + params.capex_inverter_usd_per_kw * (PinverterBESS + PinverterPV)
    )

    CashFlow = Es + OPEX0 - OPEX
    crfe = finance.escalated_capital_recovery_factor(
        params.discount_rate, params.project_life_years, params.escalation_rate
    )
    npv = CashFlow * (1.0 / crfe) - Investment0
    prob += npv  # objective: maximize NPV == minimize LCOE_net (see design doc section 3.4)

    for t in T:
        prob += Pd[t] + Pb[t] + Ppv[t] == Pc[t] + Ps[t] + Plinst * Plu_v[t], f"balance_{t}"
        prob += Ppvmx[t] == Ppvinst * Ppvu_v[t], f"pv_avail_{t}"
        prob += Ppv[t] <= Ppvmx[t], f"pv_curtail_{t}"
        if t == 0:
            prob += SOC[t] == SOC0 + Pc[t] * params.eff_charge - Pd[t] / params.eff_discharge, f"soc_{t}"
        else:
            prob += SOC[t] == SOC[t - 1] + Pc[t] * params.eff_charge - Pd[t] / params.eff_discharge, f"soc_{t}"
        prob += Pc[t] <= PinverterBESS, f"charge_cap_{t}"
        prob += Pc[t] <= M_BESS_INVERTER * w1[t], f"charge_excl_{t}"
        prob += Pd[t] <= PinverterBESS, f"discharge_cap_{t}"
        prob += Pd[t] <= M_BESS_INVERTER * (1 - w1[t]), f"discharge_excl_{t}"
        prob += Pb[t] <= PmaxF * w3[t], f"buy_excl_{t}"
        prob += Ps[t] <= PmaxF * (1 - w3[t]), f"sell_excl_{t}"
        prob += SOC[t] <= ((1 - DoD) / 2 + DoD) * C, f"soc_ub_{t}"
        prob += SOC[t] >= ((1 - DoD) / 2) * C, f"soc_lb_{t}"

    prob += SOC0 <= ((1 - DoD) / 2 + DoD) * C, "soc0_ub"
    prob += SOC0 >= ((1 - DoD) / 2) * C, "soc0_lb"
    prob += PinverterBESS <= C * 2.0, "bess_crate_ub"
    prob += PinverterBESS >= C * 0.1, "bess_crate_lb"
    prob += PinverterPV == Plinst + PmaxF + PinverterBESS, "pv_inverter_size"

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]

    # Big-M non-binding guard (runtime, not just the test-time checks in
    # tests/test_dispatch_model.py and tests/test_dispatch_model_full_scale.py):
    # M_BESS_INVERTER is only meant to be a linearization device (see its
    # definition above), generous enough to never actually constrain the
    # optimal battery-inverter size. If some future location/year/load-curve
    # combination in the multi-location sweep pushes the solved PinverterBESS
    # within 10% of that bound, the reported "optimum" may actually be
    # artificially capped by the linearization rather than reflecting genuine
    # project economics, and must not be trusted silently. Raised as an
    # exception (rather than warnings.warn) to match how the rest of this
    # module, and sibling data-client modules (pvgis_client.py, xm_prices.py,
    # lcoe.py), already signal an untrustworthy result — via a raised
    # exception, not a warning — since a warning can be filtered or simply
    # scroll by unnoticed in an unattended multi-location/multi-year sweep,
    # exactly the scenario this guard exists to protect.
    if status == "Optimal" and PinverterBESS.varValue is not None:
        if PinverterBESS.varValue >= 0.9 * M_BESS_INVERTER:
            raise RuntimeError(
                f"PinverterBESS solved to {PinverterBESS.varValue:.2f} kW, within 10% of the "
                f"big-M linearization bound M_BESS_INVERTER={M_BESS_INVERTER:.2f} kW "
                f"(= 2.0 * Ppv_max_kw={params.Ppv_max_kw:.2f}). The big-M constant may be "
                "binding and distorting the reported optimum — this result should not be "
                "trusted. Consider raising Ppv_max_kw or otherwise increasing the M_BESS_INVERTER "
                "linearization bound and re-solving."
            )

    Wl = float(sum(Plinst * Plu_v[t] for t in T))
    crf = finance.capital_recovery_factor(params.discount_rate, params.project_life_years)

    return SizingResult(
        status=status,
        Ppvinst_kw=Ppvinst.varValue,
        C_kwh=C.varValue,
        PinverterBESS_kw=PinverterBESS.varValue,
        PinverterPV_kw=PinverterPV.varValue,
        Investment0_usd=pulp.value(Investment0),
        OPEX_usd_per_year=pulp.value(OPEX),
        OPEX0_usd_per_year=pulp.value(OPEX0),
        OPEXgross_usd_per_year=pulp.value(OPEXgross),
        Es_usd_per_year=pulp.value(Es),
        Wl_kwh_per_year=Wl,
        crf=crf,
        crfe=crfe,
        Ppv=[Ppv[t].varValue for t in T],
        Pb=[Pb[t].varValue for t in T],
        Ps=[Ps[t].varValue for t in T],
        Pc=[Pc[t].varValue for t in T],
        Pd=[Pd[t].varValue for t in T],
        SOC=[SOC[t].varValue for t in T],
    )
