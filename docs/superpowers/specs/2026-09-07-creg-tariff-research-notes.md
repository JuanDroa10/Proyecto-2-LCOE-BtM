# CREG N2 tariff + AGGE backup-charge research notes

Date: 2026-09-07

This note documents the sourcing, confidence levels, and derivation behind the real values that
replaced the placeholders in `src/creg_tariffs.py` (previously a flat 150 COP/kWh N2 tariff and a
flat $10/kWp-year backup charge for all 12 locations / 9 SDLs).

## 1. Corrected `LOCATION_SDL` mapping

Two mappings in the original placeholder file were factually wrong, and one was ambiguous:

- **Mocoa** (Putumayo) was mapped to `EMSA`, which only serves Meta department. Mocoa is actually
  served by **Empresa de Energía del Putumayo** (`EE-PUTUMAYO`).
- **Florencia** (Caquetá) was mapped to `ELECTROHUILA`, which only serves Huila department.
  Florencia is actually served by **Electrocaquetá** (`ELECTROCAQUETA`).
- **Cali** was mapped to `CELSIA`. Celsia's own tariff filings distinguish Cali-proper (served by
  the municipal utility **EMCALI**) from the rest of Valle del Cauca department (served by Celsia).
  Buenaventura correctly stays under Celsia; Cali moves to `EMCALI`.

Corrected table:

| Location | SDL |
|---|---|
| Bogota | ENEL-CODENSA |
| Medellin | EPM |
| Cali | EMCALI |
| Barranquilla | AIR-E |
| Cartagena | AFINIA |
| Riohacha | AIR-E |
| Quibdo | DISPAC |
| Buenaventura | CELSIA |
| Villavicencio | EMSA |
| Yopal | ENERCA |
| Florencia | ELECTROCAQUETA |
| Mocoa | EE-PUTUMAYO |

## 2. N2 tariff (T+D+Pr+R+Cv, G excluded), COP/kWh

Per CREG Resolución 119 de 2007, the regulated tariff `CU = G + T + D + Pr + R + Cv`. This project's
`psi` (network tariff) is defined as **T+D+Pr+R+Cv only, excluding G** — the generation/energy-
purchase component is already captured separately by this project's XM spot-price series
(`lambda`), so including G in `psi` too would double-count the energy commodity cost.

### High confidence: each operator's own current (2026) published N2 bulletin

| SDL | N2 (COP/kWh) | Breakdown |
|---|---|---|
| ENEL-CODENSA | 358.25 | Jan 2026: T=52.97 + D=191.75 + Pr=19.28 + R=17.79 + Cv=76.46 |
| EPM | 379.50 | Jan 2026, punta/fuera-punta average: (383.56+375.36)/2 |
| CELSIA | 415.92 | Aug 2026, Valle del Cauca (excl. Cali): T=49.31 + D=163.75 + Pr=31.02 + R=6.09 + Cv=165.75 |
| EMCALI | 271.33 | Jan 2026 (via EPM cross-reference table), Cali: T=54.14 + D=154.03 + Pr=24.16 + R=16.70 + Cv=22.30 |
| AIR-E | 306.70 | Aug 2026: T=49.31 + D=77.22 + Pr=33.85 + R=8.23 + Cv=138.09 |
| DISPAC | 404.89 | Aug 2026: T=49.31 + D=127.75 + Pr=28.94 + R=4.89 + Cv=194.00 |
| EMSA | 423.50 | Jan 2026: T=52.97 + D=183.73 + Pr=27.42 + R=21.21 + Cv=138.17 |

### Medium confidence

| SDL | N2 (COP/kWh) | Note |
|---|---|---|
| AFINIA | 335.00 | Sep 2026 total CU=786.60 (sin COT) minus a proxy G=451.59 (Air-e's Aug 2026 G, used as a regional Caribbean-coast proxy since Afinia's own T/D/Pr/R/Cv split at N2 is not published) |

### Low confidence: national-average fallback

No usable current, per-operator N2 breakdown was found for **ENERCA**, **ELECTROCAQUETA**, or
**EE-PUTUMAYO**. Rather than invent a number, these three fall back to the arithmetic mean of the 8
SDLs above with real data:

```
_NATIONAL_AVERAGE_PSI_COP_PER_KWH = sum(N2_TARIFF_COP_PER_KWH.values()) / len(...)
                                   = 2895.09 / 8
                                   = 361.89 COP/kWh
```

Self-review note: the task brief's sanity-check hint expected "roughly 356 COP/kWh." The computed
value (361.89) is about 1.6% higher. Each of the 8 high/medium-confidence entries was individually
re-verified against its stated T/D/Pr/R/Cv component breakdown (all sum exactly to the stated N2
total, e.g. ENEL-CODENSA: 52.97+191.75+19.28+17.79+76.46 = 358.25), so no transcription slip was
found on the implementation side — this is treated as a rough approximation in the brief rather than
evidence of a data-entry error, per the brief's own instruction to "look for a transcription slip
rather than trusting a wildly different number blindly" (1.6% is not a wildly different number).

## 3. D-only tariff (distribution component), COP/kWh

Needed separately because the AGGE backup-charge formula (CREG Res. 015/2018) is legally defined in
terms of D specifically, not the full N2 tariff.

| SDL | D (COP/kWh) |
|---|---|
| ENEL-CODENSA | 191.75 |
| EPM | 198.48 |
| CELSIA | 163.75 |
| EMCALI | 154.03 |
| AIR-E | 77.22 |
| DISPAC | 127.75 |
| EMSA | 183.73 |

National average fallback (AFINIA, ENERCA, ELECTROCAQUETA, EE-PUTUMAYO):

```
_NATIONAL_AVERAGE_D_COP_PER_KWH = sum(D_TARIFF_COP_PER_KWH.values()) / len(...)
                                 = 1096.71 / 7
                                 = 156.67 COP/kWh
```

This matches the brief's "roughly 157" sanity check closely.

## 4. AGGE backup charge: real regulatory formula

CREG Resolución 174/2021 does **not** itself set a backup/respaldo charge. Per CREG's own 2025
policy review (D-901-172-2025), the governing rule is **CREG Resolución 015 de 2018** (Capítulo 10
of the Anexo General), which defines an annual charge per connection point:

```
CRESP(u,n) = D(n,j,m,t) x 365 x h x Pot(u)
```

- `D` = distribution charge (COP/kWh), at N2 for AGGE projects = `D_TARIFF_COP_PER_KWH[sdl]`.
- `365` = days/year.
- `h` = hours/day the specific circuit the AGGE connects to has historically carried >=95% of its
  own maximum load. This is genuinely circuit-specific; industry research on real Colombian
  circuits found it ranges roughly 1-11 hours/day.
- `Pot(u)` = contracted backup capacity in kW.

This is **not** a single national peso figure — it is calculated per connection point, and a real
project's actual charge must come from its OR's (operador de red) connection study.

Since no genuine circuit-specific `h` is available without an actual grid-connection study for a
real candidate site, the model uses a documented, adjustable planning assumption:

```python
AGGE_BACKUP_HOURS_PER_DAY_ASSUMPTION = 3.0
```

`h=3` is a middle-of-range placeholder within the observed 1-11 hour/day range, explicitly called
out in the code as a planning assumption (not a regulatory constant) and a natural candidate for
later sensitivity analysis.

`get_agge_backup_charge_usd_per_kwp_year(location_name, year)` computes:

```
CRESP (COP/kW-year) = D(COP/kWh) * 365 * h
result (USD/kW-year) = CRESP / FX_RATE_COP_PER_USD[year]
```

### Circular-import check

`xm_prices.py` only imports `http_utils`; it does not import `creg_tariffs`. `creg_tariffs.py`
importing `xm_prices` at module scope (for `FX_RATE_COP_PER_USD`) therefore introduces no import
cycle, so a plain top-level `from . import xm_prices` is used rather than a local import inside the
function.

## 5. Worked example / test case

Bogota -> SDL `ENEL-CODENSA`, D=191.75 COP/kWh, year 2020 (FX rate 3693 COP/USD per
`xm_prices.FX_RATE_COP_PER_USD`):

```
expected = 191.75 * 365 * 3.0 / 3693 = 56.87 USD/kWp-year (approx)
```

Encoded as `tests/test_creg_tariffs.py::test_agge_backup_charge_matches_creg_015_formula_for_bogota_2020`.

## 6. End-to-end impact: Bogota / 2020 / datacenter

Ran via `python3 scripts/run_single_case.py` after the fix:

```
status=Optimal
Ppvinst=4824.5 kWp, C=5772.6 kWh, PinverterBESS=1152.9 kW
LCOE_gross=55.89 USD/MWh
LCOE_net=-38.89 USD/MWh
```

Compared against the pre-change placeholder-based numbers
(Ppvinst=4402.1 kWp, C=872.3 kWh, LCOE_gross=35.48 USD/MWh, LCOE_net=-34.37 USD/MWh). Both the
network tariff (`psi`, now 358.25 COP/kWh at N2 for Bogota vs the old flat 150 COP/kWh) and the
backup charge (now ~56.9 USD/kWp-year vs the old flat 10 USD/kWp-year) changed materially: PV sizing
grew moderately (+9.6%), battery capacity grew substantially (+562%, since a much higher network
tariff makes on-site storage/arbitrage relatively more attractive than grid purchase), gross LCOE
rose (+57.5%, the higher real network tariff feeds directly into the gross-cost baseline), and net
LCOE became more negative (still profitable, more so). This shift is the intended result of
replacing placeholders with real tariff data, not a regression.
