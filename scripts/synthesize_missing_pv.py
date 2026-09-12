"""
Sintetiza los años PV faltantes usando el promedio de los años disponibles
de cada ubicación (climatología de largo plazo).

Lee y escribe archivos con el prefijo 'pvgis_' (con S).
"""
import re
from pathlib import Path
import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "pvgis"
YEARS = list(range(2005, 2024))
PATTERN = re.compile(r"^pvgis_([-\d.]+)_([-\d.]+)_(\d{4})\.csv$")


def load_profile(filepath):
    """Carga una serie de 8760 valores desde un CSV pvgis_*."""
    df = pd.read_csv(filepath, index_col=0)
    if 'pv_per_unit' in df.columns:
        s = df['pv_per_unit'].values
    else:
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        s = df[numeric_cols[0]].values
    if len(s) < 8760:
        s = np.concatenate([s, np.zeros(8760 - len(s))])
    elif len(s) > 8760:
        s = s[:8760]
    return s


def main():
    print("=" * 60)
    print("   SÍNTESIS DE AÑOS PV FALTANTES")
    print("=" * 60)

    # 1. Agrupar por (lat, lon)
    groups = {}  # key = (lat_rounded, lon_rounded) → {'_fmt': (lat_str, lon_str), year: path}
    for f in CACHE_DIR.glob("pvgis_*.csv"):
        m = PATTERN.match(f.name)
        if not m:
            continue
        lat_s, lon_s, y_s = m.group(1), m.group(2), m.group(3)
        key = (round(float(lat_s), 3), round(float(lon_s), 3))
        g = groups.setdefault(key, {"_fmt": (lat_s, lon_s)})
        g[int(y_s)] = f

    print(f"Ubicaciones encontradas: {len(groups)}\n")

    total_synth = 0
    for key, g in sorted(groups.items()):
        lat_s, lon_s = g["_fmt"]
        available = sorted([y for y in g if isinstance(y, int)])
        missing = [y for y in YEARS if y not in available]

        if not missing:
            print(f"✅ ({lat_s}, {lon_s}) — completo ({len(available)} años)")
            continue

        print(f"📍 ({lat_s}, {lon_s})")
        print(f"   Tiene {len(available)} años: {available[0]}–{available[-1]}")
        print(f"   Faltan: {missing}")

        # Promedio de todos los años disponibles (año típico)
        profiles = [load_profile(g[y]) for y in available]
        mean_profile = np.mean(profiles, axis=0)

        for y in missing:
            dest = CACHE_DIR / f"pvgis_{lat_s}_{lon_s}_{y}.csv"
            if dest.exists():
                print(f"   ⏭️  {dest.name} ya existe, saltando")
                continue
            df = pd.DataFrame({'pv_per_unit': mean_profile})
            df.index.name = ''
            df.to_csv(dest)
            print(f"   ✅ {dest.name}")
            total_synth += 1
        print()

    print("=" * 60)
    print(f"Total sintetizados: {total_synth}")
    total_files = len(list(CACHE_DIR.glob("pvgis_*.csv")))
    print(f"Total archivos pvgis_* en caché: {total_files} (esperado: 228)")
    print("=" * 60)


if __name__ == "__main__":
    main()