"""The 12 representative locations used to build interpolated LCOE maps.

See design doc section 2 for the rationale (a true 5 km national raster is
not computationally tractable; these 12 points, one-to-three per natural
region, are interpolated instead). Leticia (Amazonas) is deliberately
excluded in favor of Florencia/Mocoa — Leticia is pure ZNI (no spot market,
no AGGE applicability); Florencia and Mocoa are SIN-connected.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    name: str
    region: str  # one of REGIONS
    lat: float
    lon: float


REGIONS = ("Andina", "Caribe", "Pacifica", "Orinoquia", "Amazonia")

LOCATIONS: tuple[Location, ...] = (
    Location("Bogota", "Andina", 4.7110, -74.0721),
    Location("Medellin", "Andina", 6.2442, -75.5812),
    Location("Cali", "Andina", 3.4516, -76.5320),
    Location("Barranquilla", "Caribe", 10.9685, -74.7813),
    Location("Cartagena", "Caribe", 10.3910, -75.4794),
    Location("Riohacha", "Caribe", 11.5444, -72.9072),
    Location("Quibdo", "Pacifica", 5.6947, -76.6611),
    Location("Buenaventura", "Pacifica", 3.8801, -77.0312),
    Location("Villavicencio", "Orinoquia", 4.1420, -73.6266),
    Location("Yopal", "Orinoquia", 5.3378, -72.3959),
    Location("Florencia", "Amazonia", 1.6144, -75.6062),
    Location("Mocoa", "Amazonia", 1.1466, -76.6486),
)


def get_location(name: str) -> Location:
    for loc in LOCATIONS:
        if loc.name == name:
            return loc
    raise KeyError(f"Unknown location: {name}")
