"""LCOE_gross and LCOE_net, exactly as defined in the reference model.

The denominator is the annual LOAD energy (Wl), not PV generation — this
matches the reference model's own definition (see design doc section 3.4),
kept as-is to stay faithful to the methodology being adapted.

Note: `lcoe_net` can be legitimately negative. Algebraically,
`lcoe_net == -1000 * NPV / annuitized_load` (compare the formula below with
`dispatch_model.solve_sizing_dispatch`'s `npv` expression), and that model's
objective explicitly *maximizes* NPV. So a genuinely profitable optimal
project produces a negative `lcoe_net` by construction — this is not a bug,
it mirrors the reference model's own definition, and should not be alarming.
"""
from dataclasses import dataclass

from .dispatch_model import SizingResult


@dataclass
class LCOEResult:
    lcoe_gross_usd_per_mwh: float
    lcoe_net_usd_per_mwh: float


def compute_lcoe(result: SizingResult) -> LCOEResult:
    if result.Wl_kwh_per_year <= 0:
        raise ValueError("Wl_kwh_per_year (annual load energy) must be positive")

    annuitized_load = result.Wl_kwh_per_year / result.crf

    lcoe_gross = 1000 * (
        result.Investment0_usd + result.OPEXgross_usd_per_year / result.crfe
    ) / annuitized_load

    lcoe_net = 1000 * (
        result.Investment0_usd
        + (result.OPEX_usd_per_year - result.OPEX0_usd_per_year - result.Es_usd_per_year) / result.crfe
    ) / annuitized_load

    return LCOEResult(lcoe_gross_usd_per_mwh=lcoe_gross, lcoe_net_usd_per_mwh=lcoe_net)
