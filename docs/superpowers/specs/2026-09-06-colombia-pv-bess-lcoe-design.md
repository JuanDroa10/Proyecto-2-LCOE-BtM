# Mapas de LCOE para sistemas PV+BESS BtM en Colombia — Diseño

Fecha: 2026-09-06

## 1. Contexto y fuentes

El encargo original ("Proyecto II", `Proyecto 2.pdf`) pide adaptar un modelo de dimensionamiento/despacho
óptimo de sistemas fotovoltaicos + BESS *behind-the-meter* (BtM), desarrollado originalmente para España,
al contexto colombiano de Autogeneradores a Gran Escala (AGGE, CREG 174/2021, 1-5 MW), y producir mapas
de LCOE (bruto y neto) para Colombia bajo un escenario histórico (Versión A) y bajo escenarios de cambio
climático (Versión B, SSP1-2.6 / SSP5-8.5).

Se revisaron los 4 PDFs adjuntos al proyecto y el repositorio de GitHub referenciado
(`pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing`). Hallazgos clave que cambian el alcance
literal del brief extendido:

- El paper "Optimal Dispatch/Sizing PV and BESS systems" (caso España) **no estaba entre los PDFs
  adjuntos**, pero su implementación real sí está en el repo de GitHub (`PV_BESS_sizing_model.py`,
  Gurobi). Este archivo es la fuente de verdad para la metodología — se usa en vez de reconstruir el
  modelo desde cero.
- El paper "LCOE Colombia EAFIT" tampoco estaba adjunto. El PDF `1-s2.0-S0973082623000297-main.pdf`
  resultó ser Ángel-Sanint et al. 2023 (*Energy for Sustainable Development*, Colombia, PV/eólica,
  sin BESS, sin distinción ZNI/SIN) — un sustituto razonable para validación de orden de magnitud, no
  el paper original (que parece ser Castillo-Ramírez et al. 2015, "GeoLCOE", no disponible).
- El PDF `1-s2.0-S2666278726000322-main.pdf` es Ramírez-Ruiz, Cabrales & Valencia (2026, *Energy and
  Climate Change*): CMIP6, SSP1-2.6/SSP5-8.5, específico de Colombia, pero **excluye explícitamente
  Amazonía y Orinoquía** y solo cubre el horizonte 2051-2060 (no near-future).
- El PDF `Narvaez_2023...pdf` es Narváez et al. 2023 (*Environmental Research Communications*):
  CMIP5/RCP (no CMIP6/SSP), Sudamérica completa (no regiones colombianas), horizonte 2070-2099.
- Ninguno de los dos papers de clima permite construir Versión B con datos literales para las 5
  regiones naturales en el horizonte 2026-2050 pedido. Se usa NASA NEX-GDDP-CMIP6 (confirmado accesible
  vía AWS S3 y Microsoft Planetary Computer) como fuente primaria real, con los dos papers como
  chequeo de consistencia narrativo.
- No hay licencia de Gurobi disponible en este entorno. Se sustituye por PuLP+CBC (open source),
  con HiGHS (`scipy.optimize.milp`, ya instalado) como respaldo si el rendimiento lo exige.

Estas decisiones fueron discutidas y aprobadas con el usuario el 2026-09-06 (selección de ~10-12
ciudades representativas, NEX-GDDP-CMIP6 + papers como validación cruzada, horizonte near-future
2026-2050).

## 2. Ubicaciones representativas

Un raster nacional real a ~5 km con optimización horaria de 17 años por celda no es computacionalmente
viable en esta sesión (implicaría miles de resoluciones MILP). Se usan 12 ubicaciones reales,
interpoladas espacialmente (IDW) para producir los mapas continuos. Los mapas resultantes se rotulan
explícitamente como "interpolado de 12 ubicaciones", no como raster satelital de 5 km.

| Región natural | Ciudad | SDL (tarifa N2) | Nota |
|---|---|---|---|
| Andina | Bogotá | Enel-Codensa | |
| Andina | Medellín | EPM | |
| Andina | Cali | CELSIA/EMCALI | |
| Caribe | Barranquilla | Air-e | |
| Caribe | Cartagena | Afinia | |
| Caribe | Riohacha | Air-e | mayor irradiancia esperada (Guajira) |
| Pacífica | Quibdó | DISPAC | zona con alta proporción de ZNI alrededor de la capital |
| Pacífica | Buenaventura | CELSIA/EPSA | |
| Orinoquía | Villavicencio | EMSA | |
| Orinoquía | Yopal | Enerca | |
| Amazonía | Florencia (Caquetá) | vía SIN | se usa en vez de Leticia |
| Amazonía | Mocoa (Putumayo) | vía SIN | se usa en vez de Leticia |

**Nota metodológica**: Leticia (Amazonas) se descarta como representante de Amazonía porque es zona
ZNI pura (sin mercado spot XM, sin marco tarifario T+D+Pr+R+Cv, sin aplicabilidad real del esquema
AGGE). Florencia y Mocoa están conectadas al SIN y sí permiten aplicar el marco regulatorio completo.
Esto se documenta como limitación: la Amazonía profunda (mayoritariamente ZNI) queda subrepresentada.

## 3. Modelo de optimización (dimensionamiento + despacho)

Puerto fiel de `PV_BESS_sizing_model.py` (Gurobi → PuLP/CBC, con HiGHS como respaldo si el
rendimiento con CBC no es aceptable). Un año representativo por corrida (8760 h).

### 3.1 Variables de decisión

- Dimensionamiento: `Ppvinst` (kWp PV), `C` (kWh BESS), `PinverterBESS` (kW), `PinverterPV` (kW,
  derivado), `Pbmax[p]` (potencia contratada — ver adaptación en 3.3).
- Despacho horario (t = 1..8760): `Ppv[t]`, `Ppvmx[t]`, `Pb[t]` (comprado), `Ps[t]` (vendido),
  `Pc[t]` (carga BESS), `Pd[t]` (descarga BESS), `SOC[t]`, binarios `w1[t]` (exclusión carga/descarga),
  `w3[t]` (exclusión compra/venta).

### 3.2 Restricciones principales

- Balance horario: `Pd[t] + Pb[t] + Ppv[t] = Pc[t] + Ps[t] + Plinst·Plu[t]`
- PV disponible: `Ppvmx[t] = Ppvinst · Ppvu[t]`, `Ppv[t] ≤ Ppvmx[t]` (permite clipping/curtailment)
- SOC: `SOC[t] = SOC[t-1] + Pc[t]·eff_c − Pd[t]/eff_d`, acotado por profundidad de descarga (DoD)
- Exclusión mutua carga/descarga y compra/venta vía `w1[t]`, `w3[t]`
- C-rate del inversor BESS: `0.1·C ≤ PinverterBESS ≤ 2.0·C`
- **Nueva restricción para Colombia**: `1000 ≤ Ppvinst ≤ 5000` kWp (rango AGGE, CREG 174/2021, 1-5 MW)
- La batería puede cargarse tanto desde PV como comprando de la red — este es el mecanismo de
  arbitraje que da lugar a la diferencia entre LCOE_bruto y LCOE_neto.

### 3.3 Adaptación estructural España → Colombia (no es solo "cambiar series de tiempo")

1. **Cargos de potencia por período**: España usa 6 períodos tarifarios de potencia contratada
   (`Pbmax[1..6]`, cargos `kappa`). Por instrucción explícita del brief ("no tomar en cuenta los
   cargos de potencia horarios"), esta sub-estructura se **elimina completamente** y se reemplaza por
   un **cargo fijo único de respaldo AGGE** (CREG 174/2021), aplicado como término constante en el
   OPEX. El valor exacto se busca durante la implementación en la resolución CREG correspondiente;
   si no se encuentra un valor publicado con suficiente claridad, se documenta el supuesto usado.
2. **`psi[t]`** (tarifa de red española, horaria) se reemplaza por la tarifa colombiana
   **N2 = T + D + Pr + R + Cv**, que en la práctica es casi-constante dentro de un año (actualización
   mensual, no horaria), y varía por SDL según la ubicación.
3. **"Frontera de conexión: 1000 MW"** del brief original se interpreta como error de unidades
   (debería ser 1000 **kW**, coherente con `PmaxF = Plinst` en el código de referencia — un AGGE de
   1-5 MW no tendría sentido con una frontera de conexión 200-1000× mayor que su propio tamaño). Se
   sigue la convención del modelo de referencia (`PmaxF = Plinst`, la frontera de importación/
   exportación es el pico de la carga). Este supuesto queda marcado explícitamente para que el
   usuario lo confirme o corrija.

### 3.4 Función objetivo y fórmulas de LCOE (verbatim del código de referencia)

Objetivo: `maximizar VPN`, donde `VPN = CashFlow/crfe − CAPEX` (matemáticamente equivalente a
minimizar LCOE_neto, verificado algebraicamente).

```
LCOE_gross = 1000 · (CAPEX + OPEX_gross/crfe) / (E_carga_anual/crf)
LCOE_net   = 1000 · (CAPEX + (OPEX − OPEX0 − Es)/crfe) / (E_carga_anual/crf)
```

- `crf` = factor de recuperación de capital simple; `crfe` = factor de recuperación de capital
  ajustado por escalación de costos.
- `OPEX0` = costo de comprar toda la carga de la red (caso base, sin proyecto).
- `Es` = ingreso por energía vendida a la red.
- El denominador es la **energía de carga anual** (no la generación PV) — así está definido en el
  modelo de referencia, y se mantiene para ser fieles a la metodología que se pidió adaptar.
- Degradación de batería: se modela como una reducción promedio de capacidad/eficiencia aplicada
  dentro de la matemática de la anualidad de 20 años (simplificación explícita; una simulación
  dinámica año a año de degradación queda fuera de alcance de esta primera versión).

### 3.5 Parámetros financieros por defecto

Tomados del modelo de referencia (ya calibrados con fuentes como Lazard/IRENA vía el reporte Ember
revisado): `CAPEX_pv=388 USD/kWp`, `CAPEX_BESS=185 USD/kWh`, `CAPEX_inverter=48 USD/kWp`,
`OyM_pv=12.5 USD/kWp-año`, `OyM_BESS=5.9 USD/kWh-año`, tasa de descuento `i=7.7%`, vida útil
`n=20 años`, escalación `e=2.5%`. Estos son los valores base; la tasa de descuento se barre en el
análisis de sensibilidad (6/8/10/12%).

## 4. Versión A (histórica) vs Versión B (futura)

- **Versión A**: para cada ubicación × cada uno de los 17 años (2005-2023) × 3 curvas de carga, se
  resuelve el MILP de forma independiente, usando el perfil PV real de PVGIS de ese año específico y
  los precios de bolsa reales (XM) de ese mismo año. Esto produce una **distribución de 17 resultados**
  por ubicación/curva (no una única corrida conjunta de 149 000 horas), de la cual se reporta
  media/mediana/P10-P90. Esta distribución es la base para comparar "incertidumbre" entre Versión A y B.
- **Versión B**: se toman los perfiles horarios reales de PVGIS (los mismos de Versión A) y se les
  aplica un **factor de cambio mensual** derivado de NASA NEX-GDDP-CMIP6 (variables `rsds` y `tas`),
  comparando el período histórico del modelo climático (~2005-2014) contra 2026-2050 bajo SSP1-2.6 y
  SSP5-8.5 (método delta-change/change-factor, estándar en literatura de impacto climático). Esto
  preserva la variabilidad horaria real observada y solo ajusta el nivel según la señal climática.
  Se reporta si esto es consistente con lo narrado por Narváez et al. 2023 y Ramírez-Ruiz et al. 2026
  (chequeo cruzado, no fuente primaria de datos).
- Horizonte usado para los 4 mapas de Versión B: **near-future / mediano plazo (2026-2050)**, alineado
  con la vida útil de 20 años del proyecto (n=20).

## 5. Datos de mercado y tarifas

- **XM**: precios de bolsa horarios 2005-2023 vía `pydataxm` (SDK público de XM), deflactados a
  precios constantes usando IPC de Colombia (DANE), para cumplir el requisito de "precios constantes".
- **CREG N2 (T+D+Pr+R+Cv)** por SDL: valores desde resoluciones CREG/SUI públicas. Si no se logra
  granularidad exacta por SDL para todo 2005-2023, se usa el promedio nacional N2 más reciente como
  aproximación razonable, documentada como tal.
- **Cargo fijo de respaldo AGGE**: según CREG 174/2021 — buscado durante implementación; si no hay
  valor exhaustivamente claro, se documenta el supuesto adoptado.
- **Curvas de carga (PLu)**: las 3 del repositorio GitHub (`Plu.inc` = industria1, `Plu2.inc` =
  industria2, `PluDataCenter.inc` = datacenter), ya descargadas.
- **PV histórico**: PVGIS 5.3 (ERA5), API pública confirmada accesible, 2005-2023 por ubicación.

## 6. Arquitectura del código

```
JUANCHO 2/
├── data/{raw,processed}/          # cache de descargas (PVGIS, XM, CMIP6, tarifas)
├── src/
│   ├── locations.py               # las 12 ubicaciones + SDL
│   ├── pvgis_client.py            # descarga/cachea PV horario 2005-2023 por ubicación
│   ├── xm_prices.py               # precios de bolsa vía pydataxm + deflactor IPC
│   ├── creg_tariffs.py            # T+D+Pr+R+Cv por SDL + cargo de respaldo AGGE
│   ├── climate_future.py          # NEX-GDDP-CMIP6 + método delta-change → Versión B
│   ├── load_curves.py             # carga las 3 curvas Plu
│   ├── dispatch_model.py          # el MILP (PuLP), puerto fiel del modelo de referencia
│   ├── lcoe.py                    # LCOE_gross/net desde resultados del solver
│   ├── run_scenarios.py           # orquesta todas las corridas, cachea resultados (resumable)
│   ├── mapping.py                 # interpolación IDW + mapas (matplotlib/geopandas)
│   └── sensitivity.py             # barridos de tasa de descuento / costo BESS / curva de carga
├── outputs/{maps,tables}/
└── README.md
```

Cada módulo se puede entender y probar de forma aislada: `dispatch_model.py` no sabe de dónde vienen
los datos (recibe series ya alineadas), `run_scenarios.py` no sabe cómo se resuelve el MILP (solo
orquesta), y los clientes de datos (`pvgis_client.py`, `xm_prices.py`, etc.) cachean en disco para que
una corrida interrumpida no obligue a re-descargar todo.

## 7. Validación

- Se compara LCOE_gross (aislando el componente PV, sin BESS) contra el rango 53-93 USD/MWh reportado
  por Ángel-Sanint et al. 2023 (Colombia, PV utility-scale, sin storage) como chequeo de orden de
  magnitud. No es el paper "EAFIT" original del brief corto (ese parece ser Castillo-Ramírez et al.
  2015, "GeoLCOE", no disponible en los adjuntos) — se documenta como sustituto razonable, no
  equivalente exacto.
- Se compara la dirección/magnitud del cambio climático resultante (Versión B vs A) contra lo narrado
  por Narváez et al. 2023 y Ramírez-Ruiz et al. 2026, por región, como chequeo de consistencia.

## 8. Riesgo de rendimiento y mitigación

~12 ubicaciones × 17 años × 3 curvas (histórico) + 12 × 2 escenarios × 3 curvas (futuro) ≈ **684
resoluciones del MILP**. Antes de ejecutar el conjunto completo, se valida el tiempo real de una sola
corrida. Si CBC resulta lento por los binarios de exclusión mutua (`w1`, `w3`), se prueba si la
relajación LP (sin binarios) da la misma solución — económicamente, cargar y descargar simultáneamente,
o comprar y vender simultáneamente al mismo precio+peaje, nunca es óptimo, por lo que la relajación LP
podría ser válida y drásticamente más rápida. Solo se adopta si se verifica empíricamente que coincide
con la solución del MILP completo en un conjunto de casos de prueba.

## 9. Fuera de alcance (explícito)

- Raster nacional real a ~5 km (se usan 12 ubicaciones interpoladas).
- Simulación dinámica de degradación de batería año a año (se usa una simplificación promedio dentro
  de la anualidad de 20 años).
- Horizonte "far-future" (2051-2100) para los 6 mapas principales (se usa near-future 2026-2050; se
  puede agregar como extensión posterior si hay tiempo).
- Cobertura ZNI (Leticia y zonas no interconectadas similares) bajo el marco AGGE, que no les aplica
  regulatoriamente.
