from src import creg_tariffs, locations


def test_every_location_has_an_sdl_mapping():
    for loc in locations.LOCATIONS:
        assert loc.name in creg_tariffs.LOCATION_SDL, f"{loc.name} missing from LOCATION_SDL"


def test_get_n2_tariff_returns_a_positive_value_for_every_location():
    for loc in locations.LOCATIONS:
        tariff = creg_tariffs.get_n2_tariff_cop_per_kwh(loc.name)
        assert tariff > 0


def test_agge_backup_charge_is_positive():
    assert creg_tariffs.AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR > 0
