"""Prueba rápida de paralelismo con funciones ligeras."""
import sys
import time
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Configurar path para el proceso principal
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Importar módulos ligeros (no el modelo MILP)
from src.locations import LOCATIONS
from src.load_curves import load_all_curves


def get_location_names():
    """Extrae los nombres de las ubicaciones."""
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        return list(loc_data.keys())
    try:
        return [loc.name for loc in loc_data]
    except AttributeError:
        return [loc[0] for loc in loc_data]


def funcion_ligera(location_name, year, load_curve_name):
    """
    Función de prueba: solo duerme 0.5 segundos y retorna un resultado simple.
    Esto verifica que el worker puede importar módulos y ejecutar código.
    """
    # Configurar path DENTRO del worker
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Importar algo ligero para verificar que funciona
    from src.locations import LOCATIONS  # noqa: F401
    
    # Simular trabajo ligero
    time.sleep(0.5)
    
    return {
        "location": location_name,
        "year": year,
        "load_curve": load_curve_name,
        "pid": multiprocessing.current_process().pid,
        "status": "OK",
    }


def main():
    print("=" * 60)
    print("   PRUEBA DE PARALELISMO - FUNCIONES LIGERAS")
    print("=" * 60)
    
    # Usar solo 3 ubicaciones y 2 años para prueba rápida
    loc_names = get_location_names()[:3]  # Solo 3 ubicaciones
    years = [2020, 2021]  # 2 años
    curve_names = list(load_all_curves(PROJECT_ROOT / "data" / "raw" / "load_curves").keys())[:1]  # 1 curva
    
    total_tasks = len(loc_names) * len(years) * len(curve_names)
    print(f"📋 Total de tareas: {total_tasks} (3 loc × 2 años × 1 curva)")
    print(f"📋 Probar con: {loc_names}")
    print("-" * 60)
    
    # Construir tareas
    tasks = []
    for loc in loc_names:
        for year in years:
            for curve in curve_names:
                tasks.append((loc, year, curve))
    
    # Configurar método spawn para Windows
    multiprocessing.set_start_method('spawn', force=True)
    
    max_workers = min(4, total_tasks)
    print(f"⚡ Usando {max_workers} procesos en paralelo...")
    print("⏳ Ejecutando...\n")
    
    resultados = []
    completados = 0
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(funcion_ligera, loc, year, curve): (loc, year, curve)
            for loc, year, curve in tasks
        }
        
        for future in as_completed(future_to_task):
            try:
                result = future.result()
                resultados.append(result)
            except Exception as e:
                loc, year, curve = future_to_task[future]
                resultados.append({
                    "location": loc,
                    "year": year,
                    "load_curve": curve,
                    "pid": None,
                    "status": f"ERROR: {str(e)}",
                })
            
            completados += 1
            sys.stdout.write(f"\r✅ {completados} de {total_tasks} completados")
            sys.stdout.flush()
    
    print("\n\n" + "-" * 60)
    print("   RESULTADOS")
    print("-" * 60)
    
    # Mostrar resultados
    for r in resultados:
        if r["status"] == "OK":
            print(f"  ✅ {r['location']}, {r['year']}, {r['load_curve']} → PID: {r['pid']}")
        else:
            print(f"  ❌ {r['location']}, {r['year']}, {r['load_curve']} → {r['status']}")
    
    # Verificar que todos los PIDs sean diferentes (evidencia de paralelismo)
    pids = [r["pid"] for r in resultados if r["status"] == "OK"]
    pids_unicos = set(pids)
    print("-" * 60)
    print(f"📊 PIDs únicos: {len(pids_unicos)} de {len(pids)} tareas exitosas")
    if len(pids_unicos) > 1:
        print("✅ ¡El paralelismo está funcionando! Se usaron múltiples procesos.")
    else:
        print("⚠️  Todas las tareas se ejecutaron en el mismo proceso (sin paralelismo).")
    print("=" * 60)


if __name__ == "__main__":
    main()