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


def test_get_n2_tariff_returns_the_real_sourced_value_for_well_sourced_sdls():
    # Pins the real, sourced N2 values so a regression back to the old flat
    # placeholder (150 COP/kWh) or any other wrong-but-positive value fails.
    assert creg_tariffs.get_n2_tariff_cop_per_kwh("Bogota") == pytest.approx(358.25)  # ENEL-CODENSA
    assert creg_tariffs.get_n2_tariff_cop_per_kwh("Villavicencio") == pytest.approx(423.50)  # EMSA


def test_get_n2_tariff_uses_the_national_average_fallback_for_unsourced_sdls():
    # Yopal -> ENERCA, one of the 3 SDLs with no real per-operator N2 filing found.
    assert creg_tariffs.get_n2_tariff_cop_per_kwh("Yopal") == creg_tariffs._NATIONAL_AVERAGE_PSI_COP_PER_KWH
