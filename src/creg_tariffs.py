"""Colombian N2 tariff (T+D+Pr+R+Cv) and CREG Res. 015/2018 AGGE backup charge.

Sourced from real research (CREG/SUI/utility-published tariff bulletins and
CREG's own 2025 policy review, D-901-172-2025) -- see
docs/superpowers/specs/2026-09-07-creg-tariff-research-notes.md for full
sourcing, confidence levels, and the backup-charge formula derivation.
"""
from . import xm_prices  # no cycle: xm_prices only imports http_utils, not this module

# Location name (see src/locations.py) -> SDL (regional distribution utility) code.
LOCATION_SDL = {
    "Bogota": "ENEL-CODENSA",
    "Medellin": "EPM",
    "Cali": "EMCALI",
    "Barranquilla": "AIR-E",
    "Cartagena": "AFINIA",
    "Riohacha": "AIR-E",
    "Quibdo": "DISPAC",
    "Buenaventura": "CELSIA",
    "Villavicencio": "EMSA",
    "Yopal": "ENERCA",
    "Florencia": "ELECTROCAQUETA",
    "Mocoa": "EE-PUTUMAYO",
}

# N2 = T+D+Pr+R+Cv (network/regulated charges only, G excluded -- G is already
# captured by the XM spot price series elsewhere in this project). Sourced from
# each operator's own current tariff bulletins (CREG Res. 119/2007 methodology),
# except where noted. COP/kWh.
N2_TARIFF_COP_PER_KWH = {
    # High confidence: each operator's own current (2026) published N2 bulletin.
    "ENEL-CODENSA": 358.25,   # Jan 2026: T=52.97+D=191.75+Pr=19.28+R=17.79+Cv=76.46
    "EPM": 379.50,            # Jan 2026, punta/fuera-punta average: (383.56+375.36)/2
    "CELSIA": 415.92,         # Aug 2026, Valle del Cauca (excl. Cali): T=49.31+D=163.75+Pr=31.02+R=6.09+Cv=165.75
    "EMCALI": 271.33,         # Jan 2026 (via EPM cross-reference table), Cali: T=54.14+D=154.03+Pr=24.16+R=16.70+Cv=22.30
    "AIR-E": 306.70,          # Aug 2026: T=49.31+D=77.22+Pr=33.85+R=8.23+Cv=138.09
    "DISPAC": 404.89,         # Aug 2026: T=49.31+D=127.75+Pr=28.94+R=4.89+Cv=194.00
    "EMSA": 423.50,           # Jan 2026: T=52.97+D=183.73+Pr=27.42+R=21.21+Cv=138.17
    # Medium confidence: total N2 CU is real and current (Afinia's own site), but
    # the T/D/Pr/R/Cv split isn't published at N2 -- G approximated using Air-e's
    # (a comparable Caribbean-coast operator) Aug 2026 G=451.59 as a regional proxy.
    "AFINIA": 335.00,         # Sep 2026 CU=786.60 (sin COT) minus proxy G=451.59
}
# Low confidence: no usable current N2 breakdown was found for these three SDLs
# (Enerca, Electrocaqueta, EE-Putumayo all lack a public, current, per-operator N2
# filing). Falls back to the average of the 8 SDLs above with real data, as a
# documented national-reference proxy rather than an invented number.
_NATIONAL_AVERAGE_PSI_COP_PER_KWH = sum(N2_TARIFF_COP_PER_KWH.values()) / len(N2_TARIFF_COP_PER_KWH)
for _sdl in ("ENERCA", "ELECTROCAQUETA", "EE-PUTUMAYO"):
    N2_TARIFF_COP_PER_KWH[_sdl] = _NATIONAL_AVERAGE_PSI_COP_PER_KWH

# D only (distribution component), COP/kWh -- needed for the AGGE backup-charge
# formula below, which is legally defined in terms of D specifically, not the
# full N2 tariff. Same sourcing as N2_TARIFF_COP_PER_KWH above.
D_TARIFF_COP_PER_KWH = {
    "ENEL-CODENSA": 191.75,
    "EPM": 198.48,
    "CELSIA": 163.75,
    "EMCALI": 154.03,
    "AIR-E": 77.22,
    "DISPAC": 127.75,
    "EMSA": 183.73,
}
_NATIONAL_AVERAGE_D_COP_PER_KWH = sum(D_TARIFF_COP_PER_KWH.values()) / len(D_TARIFF_COP_PER_KWH)
for _sdl in ("AFINIA", "ENERCA", "ELECTROCAQUETA", "EE-PUTUMAYO"):
    D_TARIFF_COP_PER_KWH[_sdl] = _NATIONAL_AVERAGE_D_COP_PER_KWH

# CREG Res. 015/2018, Cap. 10: CRESP = D * 365 * h * Pot(kW). D varies by SDL (see
# D_TARIFF_COP_PER_KWH above); h (hours/day the connecting circuit carries >=95% of
# its own peak load) is genuinely circuit-specific and unknowable without an actual
# grid-connection study -- real circuits studied in industry research ranged
# roughly 1-11 hours/day. This uses h=3 as a documented, adjustable, middle-of-range
# planning assumption (not a regulatory constant) -- a natural candidate for later
# sensitivity analysis. A real project's actual charge must come from its OR's
# connection study, not this default.
AGGE_BACKUP_HOURS_PER_DAY_ASSUMPTION = 3.0


def get_n2_tariff_cop_per_kwh(location_name: str) -> float:
    sdl = LOCATION_SDL[location_name]
    return N2_TARIFF_COP_PER_KWH[sdl]


def get_agge_backup_charge_usd_per_kwp_year(location_name: str, year: int) -> float:
    """CRESP/kW, annualized, converted to USD via that year's FX rate.

    CRESP(COP/kW-year) = D(COP/kWh) * 365 * h. Dividing by an FX rate (COP/USD)
    gives USD/kW-year, matching this project's other USD-denominated cost rates.
    """
    sdl = LOCATION_SDL[location_name]
    d_cop_per_kwh = D_TARIFF_COP_PER_KWH[sdl]
    cresp_cop_per_kw_year = d_cop_per_kwh * 365 * AGGE_BACKUP_HOURS_PER_DAY_ASSUMPTION
    fx_rate = xm_prices.FX_RATE_COP_PER_USD[year]
    return cresp_cop_per_kw_year / fx_rate
