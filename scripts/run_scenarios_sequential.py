"""Ejecuta las 684 corridas secuencialmente con guardado incremental y reanudación.
- Guarda resultados después de cada corrida.
- Al reiniciar, retoma desde el último caso no completado.
"""
import sys
import csv
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.locations import LOCATIONS
from src.load_curves import load_all_curves
from scripts.run_single_case import run

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR / "version_A_results_sequential_checkpoint.csv"
YEARS = list(range(2005, 2024))


def get_location_names():
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        return list(loc_data.keys())
    try:
        return [loc.name for loc in loc_data]
    except AttributeError:
        return [loc[0] for loc in loc_data]


def load_completed_results():
    """Carga los casos ya completados desde el CSV (si existe)."""
    completados = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Crear una clave única para cada combinación
                key = (row['location'], int(row['year']), row['load_curve'])
                completados.add(key)
    return completados


def append_result(result_dict):
    """Añade una fila al CSV (crea el archivo si no existe)."""
    fieldnames = [
        "location", "year", "load_curve", "status",
        "Ppvinst_kw", "C_kwh", "PinverterBESS_kw",
        "lcoe_gross_usd_per_mwh", "lcoe_net_usd_per_mwh",
        "error_msg"
    ]
    file_exists = OUTPUT_CSV.exists()
    with open(OUTPUT_CSV, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(result_dict)


def main():
    print("=" * 60)
    print("   VERSIÓN A - 684 CORRIDAS SECUENCIALES CON CHECKPOINT")
    print("   (guardado incremental, reanudación automática)")
    print("=" * 60)

    loc_names = get_location_names()
    curve_names = list(load_all_curves(DATA_DIR / "raw" / "load_curves").keys())

    total = len(loc_names) * len(YEARS) * len(curve_names)
    print(f"Total de corridas: {total}")
    print(f"Resultados se guardarán en: {OUTPUT_CSV}")
    print("-" * 60)

    # Cargar casos ya completados
    completados_set = load_completed_results()
    print(f"Casos ya completados: {len(completados_set)}")

    count = 0
    nuevos = 0
    for loc in loc_names:
        for year in YEARS:
            for curve in curve_names:
                count += 1
                key = (loc, year, curve)
                if key in completados_set:
                    # Ya está hecho, lo saltamos
                    print(f"\r{count} de {total} (ya completado)", end="", flush=True)
                    continue

                # Ejecutar el caso
                print(f"\r{count} de {total} - Ejecutando {loc}, {year}, {curve}...", end="", flush=True)
                try:
                    result, lcoe_res = run(loc, year, curve)
                    row = {
                        "location": loc,
                        "year": year,
                        "load_curve": curve,
                        "status": result.status,
                        "Ppvinst_kw": round(result.Ppvinst_kw, 2),
                        "C_kwh": round(result.C_kwh, 2),
                        "PinverterBESS_kw": round(result.PinverterBESS_kw, 2),
                        "lcoe_gross_usd_per_mwh": round(lcoe_res.lcoe_gross_usd_per_mwh, 4),
                        "lcoe_net_usd_per_mwh": round(lcoe_res.lcoe_net_usd_per_mwh, 4),
                        "error_msg": "",
                    }
                except Exception as e:
                    row = {
                        "location": loc,
                        "year": year,
                        "load_curve": curve,
                        "status": "ERROR",
                        "Ppvinst_kw": None,
                        "C_kwh": None,
                        "PinverterBESS_kw": None,
                        "lcoe_gross_usd_per_mwh": None,
                        "lcoe_net_usd_per_mwh": None,
                        "error_msg": f"{type(e).__name__}: {str(e)}",
                    }

                # Guardar inmediatamente
                append_result(row)
                nuevos += 1

                # Actualizar el conjunto de completados para que no se repita si se interrumpe
                completados_set.add(key)

    print()  # salto de línea
    print("-" * 60)
    print(f"✅ Nuevas corridas ejecutadas: {nuevos}")
    print(f"📁 Resultados totales en: {OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()