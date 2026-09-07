"""End-to-end smoke run: one location, one year, one load curve."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import creg_tariffs, dispatch_model, lcoe, load_curves, locations, pvgis_client, xm_prices

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def run(location_name: str, year: int, load_curve_name: str):
    loc = locations.get_location(location_name)

    pv_per_unit = pvgis_client.fetch_pv_profile(loc.lat, loc.lon, year, DATA_DIR / "cache" / "pvgis")

    prices_cop = xm_prices.fetch_spot_prices_cop_per_kwh(year, DATA_DIR / "cache" / "xm")
    prices_usd = xm_prices.to_usd_per_kwh(prices_cop, year)

    n2_cop_series = pd.Series([creg_tariffs.get_n2_tariff_cop_per_kwh(location_name)] * 8760)
    n2_usd_series = xm_prices.to_usd_per_kwh(n2_cop_series, year)

    curves = load_curves.load_all_curves(DATA_DIR / "raw" / "load_curves")
    plu = curves[load_curve_name]

    params = dispatch_model.SizingParams(
        Plinst_kw=1000.0,
        agge_backup_charge_usd_per_kwp_year=creg_tariffs.AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR,
    )
    result = dispatch_model.solve_sizing_dispatch(plu, pv_per_unit, prices_usd, n2_usd_series, params)
    lcoe_result = lcoe.compute_lcoe(result)
    return result, lcoe_result


if __name__ == "__main__":
    r, l = run("Bogota", 2020, "datacenter")
    print(f"status={r.status}")
    print(f"Ppvinst={r.Ppvinst_kw:.1f} kWp, C={r.C_kwh:.1f} kWh, PinverterBESS={r.PinverterBESS_kw:.1f} kW")
    print(f"LCOE_gross={l.lcoe_gross_usd_per_mwh:.2f} USD/MWh")
    print(f"LCOE_net={l.lcoe_net_usd_per_mwh:.2f} USD/MWh")
