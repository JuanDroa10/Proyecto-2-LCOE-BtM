import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_single_case import run


def test_bogota_2020_datacenter_end_to_end():
    result, lcoe_result = run("Bogota", 2020, "datacenter")

    assert result.status == "Optimal"
    assert 1000.0 - 1e-6 <= result.Ppvinst_kw <= 5000.0 + 1e-6
    assert result.C_kwh >= 0

    # Broad sanity bounds — plausible order of magnitude for USD/MWh, not a
    # tight expected value (real market/PV data varies year to year).
    assert 10.0 < lcoe_result.lcoe_gross_usd_per_mwh < 2000.0

    # LCOE_net has no floor at 0: algebraically LCOE_net == -1000*NPV/annuitized_load
    # (see lcoe.compute_lcoe vs. dispatch_model.solve_sizing_dispatch's `npv` objective),
    # and the dispatch model's objective explicitly *maximizes* NPV. Whenever the optimizer
    # finds a genuinely profitable project (positive NPV — common here given Bogota's strong
    # solar resource and the AGGE backup charge, see creg_tariffs.py),
    # LCOE_net is negative by construction. This is not a defect: Task 9's own full-scale
    # reference-data run hit the identical sign (LCOE_net ~= -$18.1/MWh on Spain data,
    # see task-9-report.md) and documented it as expected, not a red flag. Bound magnitude
    # only, symmetric with the gross check above, to still catch a genuine units/scaling bug.
    assert -2000.0 < lcoe_result.lcoe_net_usd_per_mwh < 2000.0
