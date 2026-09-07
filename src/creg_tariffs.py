"""Colombian N2 tariff (T+D+Pr+R+Cv) and CREG 174/2021 AGGE backup charge.

PLACEHOLDER VALUES: order-of-magnitude defaults, not yet sourced from a
specific CREG/SUI resolution. N2_TARIFF_COP_PER_KWH uses one flat value for
every SDL. Replace with real per-SDL published figures in a follow-on plan.
"""

# Location name (see src/locations.py) -> SDL (regional distribution utility) code.
LOCATION_SDL = {
    "Bogota": "ENEL-CODENSA",
    "Medellin": "EPM",
    "Cali": "CELSIA",
    "Barranquilla": "AIR-E",
    "Cartagena": "AFINIA",
    "Riohacha": "AIR-E",
    "Quibdo": "DISPAC",
    "Buenaventura": "CELSIA",
    "Villavicencio": "EMSA",
    "Yopal": "ENERCA",
    "Florencia": "ELECTROHUILA",
    "Mocoa": "EMSA",
}

# Flat representative N2 = T+D+Pr+R+Cv total, COP/kWh. Placeholder: same value
# for every SDL (~ typical published range for Colombian medium-voltage
# tariffs) pending a real per-SDL CREG/SUI lookup.
_DEFAULT_N2_COP_PER_KWH = 150.0
N2_TARIFF_COP_PER_KWH = {sdl: _DEFAULT_N2_COP_PER_KWH for sdl in set(LOCATION_SDL.values())}

# CREG 174/2021 AGGE backup/respaldo charge (USD per kWp of installed PV
# capacity per year). Applied only when the PV+BESS project exists — an
# AGGE customer without self-generation pays no backup charge, so this does
# NOT appear in the no-project baseline (OPEX0).
AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR = 10.0


def get_n2_tariff_cop_per_kwh(location_name: str) -> float:
    sdl = LOCATION_SDL[location_name]
    return N2_TARIFF_COP_PER_KWH[sdl]
