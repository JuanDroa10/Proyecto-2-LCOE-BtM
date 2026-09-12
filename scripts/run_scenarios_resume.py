"""Re-ejecuta SOLO los casos afectados por archivos PV que antes faltaban
   (o que fallaron), conservando el resto del CSV anterior."""
import sys, csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.locations import LOCATIONS
from src.load_curves import load_all_curves
from scripts.run_single_case import run

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_CSV = OUTPUT_DIR / "version_A_results_sequential_checkpoint.csv"
YEARS = list(range(2005, 2024))

# Casos cuyo PV antes era fallback/error y que DEBEN re-ejecutarse
FORCE_RERUN = {
    ("Medellin", 2009),
    ("Cali", 2010), ("Cali", 2017), ("Cali", 2018), ("Cali", 2019),
    ("Cali", 2020), ("Cali", 2021),
    ("Buenaventura", 2013),
    ("Florencia", 2019),
    ("Mocoa", 2010), ("Mocoa", 2011), ("Mocoa", 2013),
    ("Mocoa", 2015), ("Mocoa", 2018), ("Mocoa", 2019),
}

FIELDNAMES = [
    "location", "year", "load_curve", "status",
    "Ppvinst_kw", "C_kwh", "PinverterBESS_kw",
    "lcoe_gross_usd_per_mwh", "lcoe_net_usd_per_mwh",
    "error_msg",
]


def get_location_names():
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        return list(loc_data.keys())
    try:
        return [loc.name for loc in loc_data]
    except AttributeError:
        return [loc[0] for loc in loc_data]


def load_previous():
    """Carga el CSV anterior. Retorna dict {(loc, year, curve): row}."""
    if not OUTPUT_CSV.exists():
        print(f"⚠️  No existe {OUTPUT_CSV}. Se ejecutará todo desde cero.")
        return {}
    rows = {}
    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (r["location"], int(r["year"]), r["load_curve"])
            rows[key] = r
    return rows


def run_single(loc, year, curve):
    try:
        result, lcoe_res = run(loc, year, curve)
        return {
            "location": loc, "year": year, "load_curve": curve,
            "status": result.status,
            "Ppvinst_kw": round(result.Ppvinst_kw, 2),
            "C_kwh": round(result.C_kwh, 2),
            "PinverterBESS_kw": round(result.PinverterBESS_kw, 2),
            "lcoe_gross_usd_per_mwh": round(lcoe_res.lcoe_gross_usd_per_mwh, 4),
            "lcoe_net_usd_per_mwh": round(lcoe_res.lcoe_net_usd_per_mwh, 4),
            "error_msg": "",
        }
    except Exception as e:
        return {
            "location": loc, "year": year, "load_curve": curve,
            "status": "ERROR",
            "Ppvinst_kw": None, "C_kwh": None, "PinverterBESS_kw": None,
            "lcoe_gross_usd_per_mwh": None, "lcoe_net_usd_per_mwh": None,
            "error_msg": f"{type(e).__name__}: {str(e)}",
        }


def main():
    print("=" * 60)
    print("   REANUDACIÓN QUIRÚRGICA DE VERSION A")
    print("=" * 60)

    loc_names = get_location_names()
    curve_names = list(load_all_curves(DATA_DIR / "raw" / "load_curves").keys())

    prev = load_previous()
    print(f"Casos ya en el CSV anterior: {len(prev)}")

    # Decidir qué correr y qué conservar
    to_run = []
    kept = []
    for loc in loc_names:
        for year in YEARS:
            for curve in curve_names:
                key = (loc, year, curve)
                force = (loc, year) in FORCE_RERUN
                old = prev.get(key)
                if force or old is None or old["status"] != "Optimal":
                    to_run.append((loc, year, curve))
                else:
                    kept.append(old)

    print(f"Casos a RE-EJECUTAR: {len(to_run)}")
    print(f"Casos CONSERVADOS del CSV anterior: {len(kept)}\n")

    # Re-ejecutar los que faltan
    new_results = []
    for i, (loc, year, curve) in enumerate(to_run, 1):
        print(f"\r{i} de {len(to_run)} — {loc} {year} {curve}    ", end="", flush=True)
        new_results.append(run_single(loc, year, curve))
    print()

    # Combinar y guardar
    all_results = kept + new_results
    # Ordenar para que el CSV quede ordenado
    all_results.sort(key=lambda r: (r["location"], int(r["year"]), r["load_curve"]))

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_results)

    ok = sum(1 for r in all_results if r["status"] == "Optimal")
    fail = sum(1 for r in all_results if r["status"] != "Optimal")
    print("=" * 60)
    print(f"✅ Guardado en: {OUTPUT_CSV}")
    print(f"   Total filas: {len(all_results)} (esperado: 684)")
    print(f"   Optimal: {ok}  |  ERROR: {fail}")
    print("=" * 60)


if __name__ == "__main__":
    main()