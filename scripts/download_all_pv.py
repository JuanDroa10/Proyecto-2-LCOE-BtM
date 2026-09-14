"""Descarga todos los perfiles PV para todas las ubicaciones y años (2005-2024).
Con reintentos automáticos y verificación de archivos existentes.
"""
import sys
import time
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.locations import LOCATIONS
from src.pvgis_client import fetch_pv_profile

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache" / "pvgis"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2005, 2024))
MAX_RETRIES = 1
RETRY_DELAY = 1 

def get_location_names():
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        return list(loc_data.keys())
    try:
        return [loc.name for loc in loc_data]
    except AttributeError:
        return [loc[0] for loc in loc_data]

def get_location_coords(loc_name):
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        loc = loc_data[loc_name]
    else:
        idx = list(get_location_names()).index(loc_name)
        loc = loc_data[idx]
    if hasattr(loc, 'lat'):
        return loc.lat, loc.lon
    return loc[1], loc[2]

def descargar_con_reintento(loc_name, year):
    """Intenta descargar un archivo con reintentos."""
    # Verificar si ya existe
    filename = f"{loc_name}_{year}.csv"
    filepath = CACHE_DIR / filename
    if filepath.exists():
        # Verificar que el archivo no esté vacío
        if filepath.stat().st_size > 100:
            return True, "ya existe"
    
    lat, lon = get_location_coords(loc_name)
    for intento in range(1, MAX_RETRIES + 1):
        try:
            fetch_pv_profile(lat, lon, year, CACHE_DIR)
            return True, "OK"
        except Exception as e:
            if intento < MAX_RETRIES:
                print(f"  Reintento {intento}/{MAX_RETRIES} en {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                return False, str(e)
    return False, "Máximos reintentos alcanzados"

def main():
    locations = get_location_names()
    total = len(locations) * len(YEARS)
    print(f"Descargando perfiles PV para {len(locations)} ubicaciones y {len(YEARS)} años...")
    print(f"Total: {total} archivos")
    print("-" * 50)
    
    count = 0
    exitosos = 0
    fallidos = 0
    saltados = 0
    
    for loc_name in locations:
        for year in YEARS:
            count += 1
            print(f"[{count}/{total}] {loc_name}, {year}...", end=" ", flush=True)
            
            ok, msg = descargar_con_reintento(loc_name, year)
            if ok:
                if msg == "ya existe":
                    saltados += 1
                    print("⏭️  saltado (ya existe)")
                else:
                    exitosos += 1
                    print("✅ OK")
            else:
                fallidos += 1
                print(f"❌ ERROR: {msg}")
    
    print("-" * 50)
    print(f"Resumen: {exitosos} descargados, {saltados} saltados (existentes), {fallidos} fallidos")

if __name__ == "__main__":
    main()