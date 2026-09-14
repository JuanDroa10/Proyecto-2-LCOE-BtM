"""Ejecuta los 684 escenarios (Versión A: 12 ubicaciones × 19 años × 3 curvas de carga) en paralelo utilizando procesos."""
import sys
import csv
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configurar el path para el proceso principal
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ahora podemos importar módulos del proyecto
from src.locations import LOCATIONS
from src.load_curves import load_all_curves

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR / "version_A_results_parallel.csv"
YEARS = list(range(2005, 2024))


def get_location_names():
    """Extrae los nombres de las ubicaciones desde LOCATIONS."""
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        return list(loc_data.keys())
    try:
        return [loc.name for loc in loc_data]
    except AttributeError:
        return [loc[0] for loc in loc_data]


def run_single_scenario(location_name, year, load_curve_name):
    """
    Ejecuta un caso. Configura el sys.path dentro del worker (necesario en Windows).
    """
    # --- Configurar el path DENTRO del worker ---
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Ahora importar lo que necesitamos dentro del worker
    from scripts.run_single_case import run

    try:
        result, lcoe_res = run(location_name, year, load_curve_name)
        return {
            "location": location_name,
            "year": year,
            "load_curve": load_curve_name,
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
            "location": location_name,
            "year": year,
            "load_curve": load_curve_name,
            "status": "ERROR",
            "Ppvinst_kw": None,
            "C_kwh": None,
            "PinverterBESS_kw": None,
            "lcoe_gross_usd_per_mwh": None,
            "lcoe_net_usd_per_mwh": None,
            "error_msg": f"{type(e).__name__}: {str(e)}",
        }


def main():
    print("=" * 60)
    print("   VERSIÓN A - 684 ESCENARIOS (12 loc × 19 años × 3 curvas)")
    print("   EJECUCIÓN PARALELA CON PROCESOS")
    print("=" * 60)

    loc_names = get_location_names()
    curve_names = list(load_all_curves(DATA_DIR / "raw" / "load_curves").keys())

    print(f"📋 Ubicaciones: {len(loc_names)}")
    print(f"📋 Años: {len(YEARS)} (2005-2023)")
    print(f"📋 Curvas: {len(curve_names)} ({', '.join(curve_names)})")
    total_tasks = len(loc_names) * len(YEARS) * len(curve_names)
    print(f"📋 Total de corridas: {total_tasks}")
    print(f"📁 Los resultados se guardarán en: {OUTPUT_CSV}")
    print("-" * 60)

    # Construir lista de tareas
    tasks = []
    for loc in loc_names:
        for year in YEARS:
            for curve in curve_names:
                tasks.append((loc, year, curve))

    max_workers = min(8, total_tasks)  # Usar hasta 8 procesos en paralelo
    print(f"⚡ Usando {max_workers} procesos en paralelo...")
    print("⏳ Iniciando workers (esto puede tomar unos segundos)...\n")

    resultados = []
    completados = 0

    # 🔥 Forzar método 'spawn' en Windows para evitar problemas de importación
    multiprocessing.set_start_method('spawn', force=True)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Enviar todas las tareas
        future_to_task = {
            executor.submit(run_single_scenario, loc, year, curve): (loc, year, curve)
            for loc, year, curve in tasks
        }

        # Procesar resultados a medida que terminan
        for future in as_completed(future_to_task):
            try:
                result = future.result()
                resultados.append(result)
            except Exception as e:
                # Si el future falla por error del worker, capturamos el error
                loc, year, curve = future_to_task[future]
                resultados.append({
                    "location": loc,
                    "year": year,
                    "load_curve": curve,
                    "status": "ERROR",
                    "Ppvinst_kw": None,
                    "C_kwh": None,
                    "PinverterBESS_kw": None,
                    "lcoe_gross_usd_per_mwh": None,
                    "lcoe_net_usd_per_mwh": None,
                    "error_msg": f"FutureError: {str(e)}",
                })

            completados += 1
            sys.stdout.write(f"\r{completados} de {total_tasks} completados")
            sys.stdout.flush()

    print()  # Salto de línea

    # Guardar resultados
    if resultados:
        fieldnames = [
            "location", "year", "load_curve", "status",
            "Ppvinst_kw", "C_kwh", "PinverterBESS_kw",
            "lcoe_gross_usd_per_mwh", "lcoe_net_usd_per_mwh",
            "error_msg"
        ]
        with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(resultados)

        print(f"\n✅ {len(resultados)} resultados guardados en:")
        print(f"   {OUTPUT_CSV}")

        exitosos = [r for r in resultados if r["status"] == "Optimal"]
        fallidos = [r for r in resultados if r["status"] == "ERROR"]
        print(f"\n📊 Resumen:")
        print(f"   ✅ Exitosos: {len(exitosos)}")
        print(f"   ❌ Fallidos: {len(fallidos)}")
        if fallidos:
            print("\n   ⚠️  Los siguientes casos fallaron (revisa error_msg en el CSV):")
            for f in fallidos[:5]:
                print(f"      - {f['location']}, {f['year']}, {f['load_curve']}")
            if len(fallidos) > 5:
                print(f"      ... y {len(fallidos) - 5} más.")
    else:
        print("⚠️  No se generaron resultados.")


if __name__ == "__main__":
    main()