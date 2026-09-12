# Colombia PV+BESS BtM LCOE

Modelo de dimensionamiento/despacho óptimo y cálculo de LCOE (bruto y neto) para sistemas
fotovoltaicos + almacenamiento en baterías (PV+BESS) *behind-the-meter* en Colombia, para proyectos
AGGE (Autogeneradores a Gran Escala, CREG 174/2021, 1-5 MW). Adaptado del modelo de referencia
[pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing](https://github.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing)
(desarrollado originalmente para España).

**Resultado final del proyecto**: 684 corridas de optimización (12 ubicaciones × 19 años × 3 curvas
de carga) con datos reales de PVGIS-ERA5, XM y CREG, y mapas de LCOE bruto y neto para Colombia con
el contorno del territorio nacional.

---

## 📊 Resultados principales

| Métrica | Valor |
|---------|-------|
| Total de corridas | 684 |
| Corridas exitosas | 684 (100% `Optimal`) |
| LCOE bruto promedio | 75,92 USD/MWh |
| LCOE neto promedio | −68,81 USD/MWh |
| Rango LCOE bruto | 8,32 – 367,79 USD/MWh |
| PV óptimo (rango) | 1.000 – 5.000 kWp |
| BESS óptimo (rango) | 0 – 12.716 kWh |

### Tipologías regionales identificadas

1. **Caribe** (Barranquilla, Riohacha): mayor LCOE bruto (~107 USD/MWh) pero mayor valor de arbitraje (neto < −120 USD/MWh).
2. **Centro** (Bogotá, Medellín, Cartagena): economías balanceadas (~72 USD/MWh bruto, ~−66 USD/MWh neto).
3. **Pacífico/Sur** (Cali, Buenaventura, Mocoa): menor LCOE bruto nacional (29,6 – 66,2 USD/MWh).
4. **Orinoquía/Amazonía** (Yopal, Villavicencio, Florencia): desempeño intermedio.

### Mejor y peor curva de carga

- **datacenter**: 52,23 USD/MWh (mejor desempeño — perfil plano 24/7 que maximiza autoconsumo).
- **industria1**: 95,57 USD/MWh (peor desempeño — perfil concentrado en horas de bajo valor energético).

---

## 📚 Documentación de diseño

- [`docs/superpowers/specs/2026-09-06-colombia-pv-bess-lcoe-design.md`](docs/superpowers/specs/2026-09-06-colombia-pv-bess-lcoe-design.md) — diseño general del proyecto
- [`docs/superpowers/specs/2026-09-07-creg-tariff-research-notes.md`](docs/superpowers/specs/2026-09-07-creg-tariff-research-notes.md) — fuentes y niveles de confianza de las tarifas CREG reales usadas
- [`docs/superpowers/specs/2026-09-07-colombia-pv-bess-scaling-design.md`](docs/superpowers/specs/2026-09-07-colombia-pv-bess-scaling-design.md) — diseño del escalamiento a las 684 corridas
- [`docs/superpowers/plans/2026-09-06-colombia-pv-bess-foundation.md`](docs/superpowers/plans/2026-09-06-colombia-pv-bess-foundation.md) — plan de implementación

---

## ⚙️ Setup

```bash
pip install -r requirements.txt
pytest          # corre todo el suite de tests (~5-6 min: hace llamadas reales a PVGIS/XM
                 # y resuelve el modelo de optimización a escala completa)
python scripts/run_single_case.py   # corre un caso real de punta a punta e imprime el resultado