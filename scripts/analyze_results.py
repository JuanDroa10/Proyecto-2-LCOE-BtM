"""Analiza los resultados de las 684 corridas de la Versión A."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_CSV = PROJECT_ROOT / "results" / "version_A_results_sequential_checkpoint.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cargar_datos():
    if not RESULTS_CSV.exists():
        # Intentar con el nombre alternativo
        alt = PROJECT_ROOT / "results" / "version_A_results.csv"
        if alt.exists():
            return pd.read_csv(alt)
        alt2 = PROJECT_ROOT / "results" / "version_A_results_parallel.csv"
        if alt2.exists():
            return pd.read_csv(alt2)
        raise FileNotFoundError(f"No se encontró el CSV en {RESULTS_CSV}")
    return pd.read_csv(RESULTS_CSV)


def imprimir_resumen(df):
    print("=" * 70)
    print("   ANÁLISIS DE RESULTADOS - VERSIÓN A")
    print("=" * 70)
    print(f"Total de corridas: {len(df)}")
    print(f"Exitosas (Optimal): {(df['status'] == 'Optimal').sum()}")
    print(f"Fallidas (ERROR):   {(df['status'] == 'ERROR').sum()}")
    print("-" * 70)

    # Filtrar solo exitosas
    df_ok = df[df['status'] == 'Optimal'].copy()

    print("\n📊 ESTADÍSTICAS GLOBALES (solo exitosas):")
    print(f"  LCOE bruto  (USD/MWh): min={df_ok['lcoe_gross_usd_per_mwh'].min():.2f}, "
          f"max={df_ok['lcoe_gross_usd_per_mwh'].max():.2f}, "
          f"media={df_ok['lcoe_gross_usd_per_mwh'].mean():.2f}, "
          f"mediana={df_ok['lcoe_gross_usd_per_mwh'].median():.2f}")
    print(f"  LCOE neto   (USD/MWh): min={df_ok['lcoe_net_usd_per_mwh'].min():.2f}, "
          f"max={df_ok['lcoe_net_usd_per_mwh'].max():.2f}, "
          f"media={df_ok['lcoe_net_usd_per_mwh'].mean():.2f}, "
          f"mediana={df_ok['lcoe_net_usd_per_mwh'].median():.2f}")
    print(f"  PV óptimo   (kWp):     min={df_ok['Ppvinst_kw'].min():.1f}, "
          f"max={df_ok['Ppvinst_kw'].max():.1f}, media={df_ok['Ppvinst_kw'].mean():.1f}")
    print(f"  BESS óptimo (kWh):     min={df_ok['C_kwh'].min():.1f}, "
          f"max={df_ok['C_kwh'].max():.1f}, media={df_ok['C_kwh'].mean():.1f}")

    print("\n📊 LCOE BRUTO PROMEDIO POR UBICACIÓN (USD/MWh):")
    por_loc = df_ok.groupby('location')['lcoe_gross_usd_per_mwh'].agg(['mean', 'min', 'max', 'std']).round(2)
    por_loc = por_loc.sort_values('mean')
    print(por_loc.to_string())

    print("\n📊 LCOE BRUTO PROMEDIO POR CURVA DE CARGA (USD/MWh):")
    por_curva = df_ok.groupby('load_curve')['lcoe_gross_usd_per_mwh'].agg(['mean', 'min', 'max', 'std']).round(2)
    print(por_curva.to_string())

    print("\n📊 LCOE BRUTO PROMEDIO POR AÑO (USD/MWh):")
    por_year = df_ok.groupby('year')['lcoe_gross_usd_per_mwh'].agg(['mean', 'min', 'max']).round(2)
    print(por_year.to_string())

    # Guardar tablas en CSV
    por_loc.to_csv(OUTPUT_DIR / "lcoe_por_ubicacion.csv")
    por_curva.to_csv(OUTPUT_DIR / "lcoe_por_curva.csv")
    por_year.to_csv(OUTPUT_DIR / "lcoe_por_year.csv")
    print(f"\n💾 Tablas guardadas en: {OUTPUT_DIR}")


def generar_graficos(df):
    df_ok = df[df['status'] == 'Optimal'].copy()
    sns.set_theme(style="whitegrid")

    # 1. Barra: LCOE bruto y neto promedio por ubicación
    fig, ax = plt.subplots(figsize=(12, 6))
    por_loc = df_ok.groupby('location')[['lcoe_gross_usd_per_mwh', 'lcoe_net_usd_per_mwh']].mean().sort_values('lcoe_gross_usd_per_mwh')
    por_loc.plot(kind='barh', ax=ax, color=['#2E86AB', '#E63946'])
    ax.set_xlabel("LCOE (USD/MWh)")
    ax.set_ylabel("Ubicación")
    ax.set_title("LCOE bruto y neto promedio por ubicación (Versión A, 2005-2023)")
    ax.axvline(0, color='black', linewidth=0.8, linestyle='--')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "lcoe_por_ubicacion.png", dpi=150)
    plt.close()

    # 2. Boxplot: LCOE bruto por curva de carga
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(x='load_curve', y='lcoe_gross_usd_per_mwh', data=df_ok, ax=ax, palette='Set2')
    ax.set_xlabel("Curva de carga")
    ax.set_ylabel("LCOE bruto (USD/MWh)")
    ax.set_title("Distribución del LCOE bruto por tipo de carga")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "lcoe_por_curva_boxplot.png", dpi=150)
    plt.close()

    # 3. Serie temporal: LCOE bruto promedio por año
    fig, ax = plt.subplots(figsize=(10, 5))
    por_year = df_ok.groupby('year')['lcoe_gross_usd_per_mwh'].mean()
    ax.plot(por_year.index, por_year.values, marker='o', color='#2E86AB')
    ax.set_xlabel("Año")
    ax.set_ylabel("LCOE bruto (USD/MWh)")
    ax.set_title("Evolución del LCOE bruto promedio por año")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "lcoe_por_year.png", dpi=150)
    plt.close()

    # 4. Heatmap: LCOE bruto por ubicación × año
    fig, ax = plt.subplots(figsize=(14, 6))
    pivot = df_ok.pivot_table(index='location', columns='year', values='lcoe_gross_usd_per_mwh', aggfunc='mean')
    sns.heatmap(pivot, cmap='RdYlGn_r', annot=False, fmt=".1f", ax=ax, cbar_kws={'label': 'LCOE bruto (USD/MWh)'})
    ax.set_title("LCOE bruto por ubicación y año")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "heatmap_lcoe_ubicacion_year.png", dpi=150)
    plt.close()

    # 5. Scatter: PV vs BESS
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(df_ok['Ppvinst_kw'], df_ok['C_kwh'],
                        c=df_ok['lcoe_gross_usd_per_mwh'], cmap='viridis',
                        alpha=0.6, s=20)
    ax.set_xlabel("Potencia PV óptima (kWp)")
    ax.set_ylabel("Capacidad BESS óptima (kWh)")
    ax.set_title("Dimensionamiento óptimo PV+BESS")
    plt.colorbar(scatter, label='LCOE bruto (USD/MWh)')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "scatter_pv_bess.png", dpi=150)
    plt.close()

    print(f"📈 Gráficos guardados en: {OUTPUT_DIR}")


if __name__ == "__main__":
    df = cargar_datos()
    imprimir_resumen(df)
    generar_graficos(df)