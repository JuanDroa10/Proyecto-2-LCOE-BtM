# Escalamiento a Versión A completa (12 ubicaciones × 19 años × 3 curvas) — Diseño

Fecha: 2026-09-07

## 1. Contexto

El plan anterior (`2026-09-06-colombia-pv-bess-foundation.md`) construyó y validó el pipeline
completo de extremo a extremo para **un solo caso** (Bogotá/2020/datacenter), con datos reales de
PVGIS y XM. Este plan escala esa base a **todas las combinaciones de Versión A**: 12 ubicaciones ×
19 años (2005-2023 — corrigiendo la cuenta de "17 años" del brief original, que fue un error
aritmético) × 3 curvas de carga = **684 corridas**.

## 2. Prerrequisito ya completado: tarifas CREG reales

Antes de escalar, se reemplazaron los valores placeholder de `src/creg_tariffs.py` por valores
investigados y sourced (commits `b355572`, `6d5cb3e`):

- **N2 (T+D+Pr+R+Cv, sin G)** real para 8 de las 9 SDL usadas (de boletines tarifarios propios de
  cada operador, 2026), con un fallback documentado (promedio nacional de las 8 SDL con datos reales)
  para las 3 SDL sin filing público claro (Enerca, Electrocaquetá, EE-Putumayo).
- Se corrigieron 3 mapeos ubicación→SDL que eran incorrectos: Mocoa (antes EMSA → ahora
  EE-Putumayo), Florencia (antes Electrohuila → ahora Electrocaquetá), Cali (antes Celsia → ahora
  EMCALI, ya que Celsia solo cubre el resto del Valle del Cauca).
- **Cargo de respaldo AGGE**: se reemplazó el placeholder plano ($10/kWp-año) por la fórmula real de
  CREG 015/2018 (`CRESP = D × 365 × h × Pot`), usando el valor D real por SDL y `h=3` horas/día como
  supuesto de planeación documentado (el valor real de `h` es específico de cada circuito y requiere
  un estudio de conexión real — el rango observado en estudios de la industria es 1-11 h/día).
- Detalle completo de fuentes y niveles de confianza:
  `docs/superpowers/specs/2026-09-07-creg-tariff-research-notes.md`.

**Implicación para este plan**: `get_agge_backup_charge_usd_per_kwp_year` ahora depende de
`(location_name, year)` (necesita el año para la tasa de cambio), no solo de la ubicación — la
orquestación debe llamarlo dentro del loop de años, no una sola vez por ubicación.

**Cambio de magnitud ya observado**: con tarifas reales, el caso de validación (Bogotá/2020/
datacenter) pasó de Ppvinst=4402→4825 kWp, C=872→5773 kWh, LCOE_bruto=35.48→55.89 USD/MWh,
LCOE_neto=-34.37→-38.89 USD/MWh. Esto es económicamente esperable (tarifa de red real ~2-3× más alta
que el placeholder hace que el autoconsumo vía batería sea mucho más valioso que la exportación) y
fue verificado independientemente antes de proceder — no es un error.

## 3. Estrategia de rendimiento: relajación LP + paralelización (validada empíricamente)

**Relajación LP**: se probó reemplazar las variables binarias `w1`/`w3` (exclusión mutua
carga/descarga y compra/venta) por variables continuas en [0,1], en 2 datasets reales distintos
(Bogotá/2020/datacenter y el caso de referencia de España):

| Dataset | NPV (MILP) | NPV (LP relajado) | Diferencia | Ppvinst/C (ambos) | Velocidad |
|---|---|---|---|---|---|
| Bogotá 2020 | 3,023,010.65 | 3,023,010.65 | 0.00% | idénticos | 130s→26s (5.0×) |
| España (ref.) | 1,591,547.11 | 1,591,547.11 | 0.00% | idénticos | 146s→24s (6.1×) |

Las variables de dimensionamiento y las métricas financieras (que son lo que reportamos) salen
**idénticas**. La única diferencia observada: en un caso, la relajación permite carga y descarga
simultánea en una hora puntual (un artefacto degenerado de la LP, sin costo en la función objetivo,
ya que `Pc`/`Pd` no entran directamente al costo). Esto no afecta VPN, LCOE, ni el dimensionamiento —
solo afectaría un gráfico de despacho horario detallado hora por hora, que no es parte del entregable
de este plan (se reserva el MILP completo para los casos ilustrativos puntuales, si se necesitan más
adelante).

**Decisión**: usar la relajación LP por defecto para las 684 corridas de este plan.

**Paralelización**: además de la relajación LP (~5-6×), se paraleliza entre núcleos de CPU usando
`multiprocessing` de Python (cada corrida `(ubicación, año, curva)` es independiente — problema
"embarazosamente paralelo"). Con ambas mejoras combinadas, el tiempo total esperado baja de las
~26.6 horas secuenciales originales (MILP completo, sin paralelizar) a un estimado de **30-90
minutos**, dependiendo de los núcleos disponibles. Se mide el tiempo real de un lote pequeño (ver
sección 6) antes de comprometerse a correr las 684 completas, como validación de esta proyección.

## 4. Arquitectura

### 4.1 Nuevo módulo: `src/run_scenarios.py`

Orquesta el barrido completo. Responsabilidades:
- Generar la lista de las 684 combinaciones `(location, year, load_curve_name)`.
- Para cada combinación: obtener datos (reusando `pvgis_client`, `xm_prices`, `creg_tariffs`,
  `load_curves` — todos ya cacheados en disco desde el plan anterior, así que solo Bogotá/2020 tiene
  caché; las demás 683 combinaciones necesitan descargas reales nuevas de PVGIS/XM), resolver
  (usando `dispatch_model.solve_sizing_dispatch` con un nuevo parámetro `relax_binaries: bool =
  False` — ver 4.2), calcular LCOE, y escribir una fila de resultado.
- **Cacheable y resumible**: cada combinación se escribe como un archivo CSV individual bajo
  `data/results/` (ej. `data/results/Bogota_2020_datacenter.csv`), no un único archivo append-only —
  así un rerun simplemente revisa qué archivos ya existen y salta esas combinaciones, sin necesidad
  de parsear/bloquear un archivo compartido entre workers paralelos. Un paso final concatena todos
  los CSV individuales en la tabla consolidada de la sección 4.3. CSV (no Parquet) por simplicidad —
  684 filas es un volumen trivial, no se necesita el formato columnar/comprimido de Parquet.
- Paraleliza el trabajo usando `multiprocessing.Pool` (o `concurrent.futures.ProcessPoolExecutor`),
  con el número de workers como parámetro configurable (default: núcleos disponibles - 1).

### 4.2 Cambio necesario en `src/dispatch_model.py`

Agregar un parámetro `relax_binaries: bool = False` a `solve_sizing_dispatch`: cuando es `True`, las
variables `w1`/`w3` se crean como `Continuous` con `upBound=1` en vez de `Binary` (exactamente como
se probó en el experimento de la sección 3). Cuando es `False` (default), el comportamiento es
idéntico al ya validado y revisado en el plan anterior — este cambio no debe alterar ningún test
existente.

### 4.3 Formato de salida

Una tabla consolidada (`data/results/version_a_results.csv`, concatenando los CSV individuales) con columnas:
`location, region, sdl, year, load_curve, status, Ppvinst_kw, C_kwh, PinverterBESS_kw,
lcoe_gross_usd_per_mwh, lcoe_net_usd_per_mwh, solve_time_s`. Esta tabla es el insumo directo para
los mapas y el análisis de sensibilidad de planes posteriores.

## 5. Fuera de alcance (explícito, sin cambios respecto al plan anterior)

Versión B (clima), mapas, análisis de sensibilidad, validación contra literatura, informe ejecutivo
— todos quedan para planes posteriores, tal como ya estaba previsto.

## 6. Validación antes de comprometerse a las 684 corridas completas

Antes de lanzar el barrido completo, correr un lote piloto pequeño (ej. 1 ubicación × 3 años × 3
curvas = 9 corridas) con la relajación LP y paralelización activadas, para:
- Confirmar que el tiempo real por corrida y el speedup de paralelización coinciden con lo esperado.
- Confirmar que el mecanismo de cacheo/resumibilidad funciona (interrumpir a mitad de camino y
  confirmar que un rerun retoma correctamente).

Si el lote piloto revela que el tiempo total proyectado excede ~2 horas, revisar antes de continuar
(podría requerir reducir el número de workers en uso simultáneo por límites de la API de XM/PVGIS, u
otras mitigaciones).
