import pytest

from src import creg_tariffs, locations


def test_every_location_has_an_sdl_mapping():
    for loc in locations.LOCATIONS:
        assert loc.name in creg_tariffs.LOCATION_SDL, f"{loc.name} missing from LOCATION_SDL"


def test_get_n2_tariff_returns_a_positive_value_for_every_location():
    for loc in locations.LOCATIONS:
        tariff = creg_tariffs.get_n2_tariff_cop_per_kwh(loc.name)
        assert tariff > 0


def test_agge_backup_charge_is_positive():
    for loc in locations.LOCATIONS:
        charge = creg_tariffs.get_agge_backup_charge_usd_per_kwp_year(loc.name, 2020)
        assert charge > 0


def test_agge_backup_charge_matches_creg_015_formula_for_bogota_2020():
    # Bogota -> ENEL-CODENSA, D=191.75 COP/kWh. CRESP = D * 365 * h, converted
    # to USD at the 2020 FX rate (3693 COP/USD).
    expected = 191.75 * 365 * 3.0 / 3693
    actual = creg_tariffs.get_agge_backup_charge_usd_per_kwp_year("Bogota", 2020)
    assert actual == pytest.approx(expected)


def test_corrected_sdl_mappings():
    assert creg_tariffs.LOCATION_SDL["Cali"] == "EMCALI"
    assert creg_tariffs.LOCATION_SDL["Florencia"] == "ELECTROCAQUETA"
    assert creg_tariffs.LOCATION_SDL["Mocoa"] == "EE-PUTUMAYO"
