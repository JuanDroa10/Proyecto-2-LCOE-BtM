"""Descarga todos precios de los operadores de las ubicaciones y años (2005-2024).
Con reintentos automáticos y verificación de archivos existentes.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.xm_prices import fetch_spot_prices_cop_per_kwh

YEARS = list(range(2005, 2024))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

for year in YEARS:
    print(f"Descargando precios para {year}...")
    try:
        prices = fetch_spot_prices_cop_per_kwh(year, DATA_DIR / "cache" / "xm")
        print(f"  OK: {len(prices)} registros")
    except Exception as e:
        print(f"  ERROR: {e}")