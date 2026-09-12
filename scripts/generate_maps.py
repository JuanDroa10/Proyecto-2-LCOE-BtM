"""Genera mapas de LCOE (gross y neto) para Colombia con contorno del país."""
import sys
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.path as mpath
from matplotlib.patches import PathPatch
from scipy.interpolate import Rbf

from src.locations import LOCATIONS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_CSV = PROJECT_ROOT / "results" / "version_A_results_sequential_checkpoint.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "maps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GEOJSON_URL = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/COL.geo.json"
GEOJSON_PATH = PROJECT_ROOT / "data" / "colombia.geojson"


def descargar_geojson():
    """Descarga el GeoJSON de Colombia si no existe localmente."""
    if GEOJSON_PATH.exists():
        return
    print(f"⬇️  Descargando GeoJSON de Colombia...")
    GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(GEOJSON_URL, GEOJSON_PATH)
    print(f"   ✅ Guardado en {GEOJSON_PATH}")


def cargar_poligono_colombia():
    """Carga el GeoJSON de Colombia y retorna una lista de trayectorias (paths) y un Path compuesto."""
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Puede haber múltiples features (continente + islas)
    paths = []
    vertices_all = []
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            coords = [geom["coordinates"]]
        elif geom["type"] == "MultiPolygon":
            coords = geom["coordinates"]
        else:
            continue
        for poly in coords:
            for ring in poly:
                arr = np.array(ring)
                paths.append(arr)
                vertices_all.append(arr)

    return paths


def generar_mapa(lons, lats, values, titulo, output_path, colombia_paths):
    """Genera un mapa de Colombia con LCOE interpolado y enmascarado al territorio."""

    # Malla geográfica
    lon_grid = np.linspace(-79.5, -66, 300)
    lat_grid = np.linspace(-4.5, 13.5, 300)
    lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)

    # Interpolación RBF
    rbf = Rbf(lons, lats, values, function='linear', smooth=0.5)
    lcoe_grid = rbf(lon_mesh, lat_mesh)

    # ------- Crear máscara con el polígono de Colombia -------
    # Convertir el meshgrid en puntos y verificar si están dentro del polígono
    from matplotlib.path import Path as MplPath
    puntos = np.column_stack([lon_mesh.ravel(), lat_mesh.ravel()])
    mascara = np.zeros(len(puntos), dtype=bool)
    for ring in colombia_paths:
        mpl_path = MplPath(ring)
        mascara |= mpl_path.contains_points(puntos)
    mascara = mascara.reshape(lon_mesh.shape)

    lcoe_grid_masked = np.where(mascara, lcoe_grid, np.nan)

    # ------- Plot -------
    fig, ax = plt.subplots(figsize=(10, 12))

    # Relleno de LCOE dentro de Colombia
    contour = ax.contourf(lon_mesh, lat_mesh, lcoe_grid_masked,
                          levels=20, cmap='RdYlGn_r', extend='both')
    cbar = plt.colorbar(contour, ax=ax, shrink=0.7, label='LCOE (USD/MWh)')

    # Contorno de Colombia (líneas negras)
    for ring in colombia_paths:
        ax.plot(ring[:, 0], ring[:, 1], color='black', linewidth=1.2, zorder=4)

    # Puntos de ubicaciones
    ax.scatter(lons, lats, c='black', s=70, marker='o',
               edgecolors='white', linewidths=1.5, zorder=5)
    for lon, lat, name in zip(lons, lats, values.index):
        ax.annotate(name, (lon, lat), xytext=(6, 6), textcoords='offset points',
                    fontsize=9, fontweight='bold', color='black', zorder=6,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='none'))

    ax.set_xlim(-79.5, -66)
    ax.set_ylim(-4.5, 13.5)
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_title(titulo, fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2)
    ax.set_facecolor('white')

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"✅ Mapa guardado: {output_path.name}")


def get_location_coords():
    coords = {}
    loc_data = LOCATIONS
    if isinstance(loc_data, dict):
        for name, loc in loc_data.items():
            if hasattr(loc, 'lat'):
                coords[name] = (loc.lat, loc.lon)
            else:
                coords[name] = (loc[1], loc[2])
    else:
        for loc in loc_data:
            if hasattr(loc, 'name'):
                coords[loc.name] = (loc.lat, loc.lon)
            else:
                coords[loc[0]] = (loc[1], loc[2])
    return coords


def cargar_datos():
    if not RESULTS_CSV.exists():
        raise FileNotFoundError(f"No se encontró {RESULTS_CSV}")
    return pd.read_csv(RESULTS_CSV)


def main():
    print("=" * 70)
    print("   GENERACIÓN DE MAPAS DE LCOE PARA COLOMBIA")
    print("=" * 70)

    descargar_geojson()
    colombia_paths = cargar_poligono_colombia()
    print(f"Polígono de Colombia cargado ({len(colombia_paths)} anillos).\n")

    df = cargar_datos()
    df_ok = df[df['status'] == 'Optimal'].copy()
    coords = get_location_coords()

    lcoe_gross = df_ok.groupby('location')['lcoe_gross_usd_per_mwh'].mean()
    lcoe_net = df_ok.groupby('location')['lcoe_net_usd_per_mwh'].mean()

    lons = np.array([coords[loc][1] for loc in lcoe_gross.index])
    lats = np.array([coords[loc][0] for loc in lcoe_gross.index])

    print(f"📍 Ubicaciones: {len(lcoe_gross)}")
    print(f"📊 Rango LCOE bruto: {lcoe_gross.min():.2f} - {lcoe_gross.max():.2f} USD/MWh")
    print(f"📊 Rango LCOE neto:  {lcoe_net.min():.2f} - {lcoe_net.max():.2f} USD/MWh\n")

    # Mapa 1: LCOE bruto histórico
    generar_mapa(lons, lats, lcoe_gross,
                 "LCOE Bruto - Versión A (Histórico 2005-2023)",
                 OUTPUT_DIR / "mapa_lcoe_gross_historico.png",
                 colombia_paths)

    # Mapa 2: LCOE neto histórico
    generar_mapa(lons, lats, lcoe_net,
                 "LCOE Neto - Versión A (Histórico 2005-2023)",
                 OUTPUT_DIR / "mapa_lcoe_net_historico.png",
                 colombia_paths)

    # Mapa 3: LCOE bruto por curva de carga
    for curva in ['industria1', 'industria2', 'datacenter']:
        df_curva = df_ok[df_ok['load_curve'] == curva]
        lcoe_curva = df_curva.groupby('location')['lcoe_gross_usd_per_mwh'].mean()
        lons_c = np.array([coords[loc][1] for loc in lcoe_curva.index])
        lats_c = np.array([coords[loc][0] for loc in lcoe_curva.index])
        generar_mapa(lons_c, lats_c, lcoe_curva,
                     f"LCOE Bruto - Curva {curva} (Versión A)",
                     OUTPUT_DIR / f"mapa_lcoe_gross_{curva}.png",
                     colombia_paths)

    print("\n" + "=" * 70)
    print("✅ Mapas generados")
    print(f"📁 Carpeta: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()