import pytest

from src import locations


def test_has_exactly_twelve_locations_covering_all_five_regions():
    assert len(locations.LOCATIONS) == 12
    assert {loc.region for loc in locations.LOCATIONS} == set(locations.REGIONS)


def test_all_coordinates_are_within_continental_colombia_bounding_box():
    for loc in locations.LOCATIONS:
        assert -4.5 <= loc.lat <= 13.0, f"{loc.name} latitude out of range"
        assert -80.0 <= loc.lon <= -66.5, f"{loc.name} longitude out of range"


def test_get_location_returns_expected_entry():
    bogota = locations.get_location("Bogota")
    assert bogota.region == "Andina"


def test_get_location_raises_for_unknown_name():
    with pytest.raises(KeyError):
        locations.get_location("Not A Real City")
