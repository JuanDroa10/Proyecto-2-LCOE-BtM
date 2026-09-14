"""Ejecuta un escenario en especifico con una curva en especifico.
Si falta el archivo PV de un año, usa el promedio del año anterior y siguiente.
"""
import sys
import time
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src import creg_tariffs, dispatch_model, lcoe, load_curves, locations, pvgis_client, xm_prices

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache" / "pvgis"
YEARS = list(range(2005, 2024))


# ------------------------------------------------------------
# Funciones de carga PV con fallback por promedio de vecinos
# ------------------------------------------------------------
def load_single_year(lat: float, lon: float, year: int):
    """
    Busca un archivo PV para el año dado en la caché.
    Usa glob para encontrar cualquier archivo que termine en _{year}.csv
    y selecciona el que tenga lat/lon más cercana (tolerancia 0.01°).
    Retorna un pd.Series con la producción horaria o None si no encuentra.
    """
    pattern = str(CACHE_DIR / f"*_{year}.csv")
    matches = glob.glob(pattern)
    if not matches:
        return None

    best_match = None
    best_diff = float('inf')
    for filepath_str in matches:
        filename = Path(filepath_str).stem  # pvgi_4.711_-74.0721_2020
        parts = filename.split('_')
        if len(parts) >= 3:
            try:
                file_lat = float(parts[1])
                file_lon = float(parts[2])
                diff = abs(file_lat - lat) + abs(file_lon - lon)
                if diff < best_diff:
                    best_diff = diff
                    best_match = filepath_str
            except ValueError:
                continue

    if best_match is None or best_diff > 0.01:
        return None

    try:
        df = pd.read_csv(best_match, index_col=0)
        if 'pv_per_unit' in df.columns:
            return df['pv_per_unit']
        elif 'G(i)' in df.columns:
            # Conversión aproximada si se descargó manualmente con G(i)
            return df['G(i)'] * 0.15
        else:
            # Usar la primera columna numérica como fallback
            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
            if len(numeric_cols) > 0:
                return df[numeric_cols[0]]
            return None
    except Exception:
        return None


def load_pv_with_fallback(lat: float, lon: float, year: int) -> pd.Series:
    """
    Carga el perfil PV del año solicitado desde caché.
    Si no existe, usa el promedio del año anterior y siguiente.
    Para 2005 usa solo 2006; para 2023 usa solo 2022.
    """
    # Intentar cargar el año solicitado
    data = load_single_year(lat, lon, year)
    if data is not None:
        return data

    # Si no existe, buscar vecinos
    print(f"⚠️  No se encontró archivo para {year}. Buscando vecinos...")

    neighbor_years = []
    if year > 2005:
        neighbor_years.append(year - 1)
    if year < 2023:
        neighbor_years.append(year + 1)

    neighbors = []
    for y in neighbor_years:
        d = load_single_year(lat, lon, y)
        if d is not None:
            neighbors.append(d)
            print(f"   → Vecino {y} encontrado.")

    if len(neighbors) == 2:
        avg = (neighbors[0] + neighbors[1]) / 2.0
        print(f"   ✅ Usando promedio de {neighbor_years[0]} y {neighbor_years[1]} para {year}")
        return avg
    elif len(neighbors) == 1:
        used_year = neighbor_years[0]
        print(f"   ✅ Usando datos de {used_year} para {year} (solo un vecino disponible)")
        return neighbors[0]
    else:
        raise FileNotFoundError(
            f"No se encontró archivo para {year} ni para sus vecinos {neighbor_years}. "
            f"Verifica la carpeta: {CACHE_DIR}"
        )


# ------------------------------------------------------------
# Función principal 'run'
# ------------------------------------------------------------
def run(location_name: str, year: int, load_curve_name: str):
    """
    Ejecuta el pipeline completo para un caso específico.
    Retorna: (resultado_optimizacion, resultado_lcoe)
    """
    loc = locations.get_location(location_name)

    # --- 1. Cargar PV (con fallback a vecinos) ---
    pv_per_unit = load_pv_with_fallback(loc.lat, loc.lon, year)

    # --- 2. Precios de bolsa (desde caché o descarga) ---
    prices_cop = xm_prices.fetch_spot_prices_cop_per_kwh(
        year, DATA_DIR / "cache" / "xm"
    )
    prices_usd = xm_prices.to_usd_per_kwh(prices_cop, year)

    # --- 3. Tarifas CREG ---
    n2_cop_series = pd.Series(
        [creg_tariffs.get_n2_tariff_cop_per_kwh(location_name)] * 8760
    )
    n2_usd_series = xm_prices.to_usd_per_kwh(n2_cop_series, year)

    # --- 4. Curva de demanda ---
    curves = load_curves.load_all_curves(DATA_DIR / "raw" / "load_curves")
    plu = curves[load_curve_name]

    # --- 5. Cargo de respaldo ---
    backup_charge = creg_tariffs.get_agge_backup_charge_usd_per_kwp_year(
        location_name, year
    )
    params = dispatch_model.SizingParams(
        Plinst_kw=1000.0,
        agge_backup_charge_usd_per_kwp_year=backup_charge,
    )

    # --- 6. Optimización ---
    result = dispatch_model.solve_sizing_dispatch(
        plu, pv_per_unit, prices_usd, n2_usd_series, params
    )

    # --- 7. LCOE ---
    lcoe_result = lcoe.compute_lcoe(result)
    return result, lcoe_result


# ------------------------------------------------------------
# Funciones auxiliares para la versión interactiva
# ------------------------------------------------------------
def get_location_names():
    """Extrae los nombres de las ubicaciones."""
    loc_data = locations.LOCATIONS
    if isinstance(loc_data, dict):
        return sorted(loc_data.keys())
    try:
        return sorted([loc.name for loc in loc_data])
    except AttributeError:
        return sorted([loc[0] for loc in loc_data])


def mostrar_menu(opciones, titulo):
    """Muestra un menú numerado."""
    print(f"\n=== {titulo} ===")
    for i, item in enumerate(opciones, start=1):
        print(f"  {i}. {item}")
    while True:
        try:
            seleccion = input("Selecciona el número (o 'q' para salir): ").strip()
            if seleccion.lower() == 'q':
                print("Saliendo...")
                sys.exit(0)
            idx = int(seleccion) - 1
            if 0 <= idx < len(opciones):
                return idx
            print(f"❌ Número inválido. Elige entre 1 y {len(opciones)}.")
        except ValueError:
            print("❌ Entrada inválida. Ingresa un número.")


def spinner_animation(stop_event, mensaje="Resolviendo"):
    """Spinner para el solver."""
    import threading
    import itertools
    spinner = itertools.cycle(['|', '/', '-', '\\'])
    while not stop_event.is_set():
        sys.stdout.write(f"\r{mensaje} {next(spinner)}")
        sys.stdout.flush()
        time.sleep(0.2)
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()


def mostrar_progreso(porcentaje, mensaje):
    """Barra de progreso numérica."""
    barra = "=" * int(porcentaje // 2) + ">" + " " * (50 - int(porcentaje // 2))
    sys.stdout.write(f"\r[{barra}] {porcentaje:3.0f}%  {mensaje}")
    sys.stdout.flush()


# ------------------------------------------------------------
# Bloque interactivo (cuando se ejecuta directamente)
# ------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("   COLOMBIA PV+BESS LCOE - SELECCIÓN DE CASO")
    print("=" * 50)

    # Menús
    loc_names = get_location_names()
    idx_loc = mostrar_menu(loc_names, "UBICACIONES DISPONIBLES")
    selected_loc = loc_names[idx_loc]

    idx_year = mostrar_menu(YEARS, "AÑOS DISPONIBLES (2005-2023)")
    selected_year = YEARS[idx_year]

    temp_curves = load_curves.load_all_curves(DATA_DIR / "raw" / "load_curves")
    curve_names = sorted(temp_curves.keys())
    idx_curve = mostrar_menu(curve_names, "CURVAS DE CARGA DISPONIBLES")
    selected_curve = curve_names[idx_curve]

    print("\n" + "-" * 50)
    print(f"✅ Ejecutando caso:")
    print(f"   📍 Ubicación : {selected_loc}")
    print(f"   📅 Año       : {selected_year}")
    print(f"   ⚡ Curva     : {selected_curve}")
    print("-" * 50 + "\n")

    # --- Variables para el progreso ---
    progreso = 0
    mostrar_progreso(progreso, "Iniciando...")

    try:
        # 1. Obtener coordenadas (0% → 5%)
        progreso = 5
        mostrar_progreso(progreso, f"Obteniendo coordenadas de {selected_loc}")
        loc = locations.get_location(selected_loc)
        time.sleep(0.2)

        # 2. Cargar PV con fallback (5% → 30%)
        progreso = 10
        mostrar_progreso(progreso, "Cargando radiación solar (caché / promedio de vecinos)...")
        pv_per_unit = load_pv_with_fallback(loc.lat, loc.lon, selected_year)
        progreso = 30
        mostrar_progreso(progreso, "Datos PV cargados")

        # 3. Descargar precios (30% → 50%)
        progreso = 35
        mostrar_progreso(progreso, "Descargando precios de bolsa (XM)...")
        prices_cop = xm_prices.fetch_spot_prices_cop_per_kwh(
            selected_year, DATA_DIR / "cache" / "xm"
        )
        prices_usd = xm_prices.to_usd_per_kwh(prices_cop, selected_year)
        progreso = 50
        mostrar_progreso(progreso, "Precios descargados")

        # 4. Tarifas CREG (50% → 60%)
        progreso = 55
        mostrar_progreso(progreso, "Calculando tarifas CREG y respaldo...")
        n2_cop_series = pd.Series(
            [creg_tariffs.get_n2_tariff_cop_per_kwh(selected_loc)] * 8760
        )
        n2_usd_series = xm_prices.to_usd_per_kwh(n2_cop_series, selected_year)
        backup_charge = creg_tariffs.get_agge_backup_charge_usd_per_kwp_year(
            selected_loc, selected_year
        )
        progreso = 60
        mostrar_progreso(progreso, "Tarifas calculadas")

        # 5. Cargar curva (60% → 65%)
        progreso = 62
        mostrar_progreso(progreso, "Cargando curva de demanda...")
        curves = load_curves.load_all_curves(DATA_DIR / "raw" / "load_curves")
        plu = curves[selected_curve]
        progreso = 65
        mostrar_progreso(progreso, f"Curva '{selected_curve}' cargada")

        # 6. OPTIMIZACIÓN MILP (65% → 95%)
        import threading
        stop_spinner = threading.Event()
        spinner_thread = threading.Thread(
            target=spinner_animation,
            args=(stop_spinner, "Resolviendo optimización MILP (esto toma ~1-2 min)")
        )
        spinner_thread.start()

        progreso = 70
        mostrar_progreso(progreso, "Resolviendo optimización...")

        params = dispatch_model.SizingParams(
            Plinst_kw=1000.0,
            agge_backup_charge_usd_per_kwp_year=backup_charge,
        )
        result = dispatch_model.solve_sizing_dispatch(
            plu, pv_per_unit, prices_usd, n2_usd_series, params
        )

        stop_spinner.set()
        spinner_thread.join()
        progreso = 95
        mostrar_progreso(progreso, "Optimización completada")

        # 7. LCOE (95% → 100%)
        progreso = 97
        mostrar_progreso(progreso, "Calculando LCOE bruto y neto...")
        lcoe_result = lcoe.compute_lcoe(result)
        progreso = 100
        mostrar_progreso(progreso, "✅ Simulación finalizada")
        print()

    except KeyboardInterrupt:
        print("\n\n⏹️  Ejecución cancelada por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {e}")
        sys.exit(1)

    # --- RESULTADOS ---
    print("\n" + "=" * 50)
    print("   RESULTADOS DE LA SIMULACIÓN")
    print("=" * 50)
    print(f"  Status del solver   : {result.status}")
    print(f"  Potencia PV óptima  : {result.Ppvinst_kw:.1f} kWp")
    print(f"  Capacidad BESS ópt. : {result.C_kwh:.1f} kWh")
    print(f"  Potencia inversor   : {result.PinverterBESS_kw:.1f} kW")
    print("-" * 50)
    print(f"  LCOE bruto (gross)  : {lcoe_result.lcoe_gross_usd_per_mwh:.2f} USD/MWh")
    print(f"  LCOE neto (net)     : {lcoe_result.lcoe_net_usd_per_mwh:.2f} USD/MWh")
    print("=" * 50)