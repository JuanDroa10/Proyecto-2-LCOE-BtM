# Colombia PV+BESS BtM LCOE — Foundation (Walking Skeleton) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate, end-to-end for one location/year/load-curve, the full data-to-LCOE
pipeline (PVGIS PV data, XM spot prices, CREG N2 tariffs, the ported PuLP dispatch/sizing MILP, and
LCOE_gross/LCOE_net calculation) so the foundation is proven correct before scaling out to all 12
locations × 17 years × 3 load curves (Version A) and the climate-adjusted Version B in follow-on plans.

**Architecture:** A `src/` package of small, independently testable modules (locations, load curves,
PVGIS client, XM client, CREG tariffs, the MILP dispatch/sizing model, LCOE calculator), wired together
by a thin orchestration script. Each external data source is fetched via `requests`/`pydataxm` through a
shared HTTP-session helper (needed because this environment's outbound HTTPS traffic is intercepted by
a corporate TLS proxy — see Task 5) and cached to disk. The MILP model is a faithful PuLP/CBC port of
the reference Gurobi model at `github.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing`,
adapted per the approved design spec.

**Tech Stack:** Python 3.10, `pandas`, `pulp` (CBC solver, bundled), `requests`, `pydataxm` (XM Colombia
SDK), `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-06-colombia-pv-bess-lcoe-design.md`

## Global Constraints

- AGGE sizing range (CREG 174/2021): `1000 <= Ppvinst_kw <= 5000`.
- No hourly/periodic power-capacity charges (explicit brief instruction) — replaced by a flat CREG AGGE
  backup charge, applied only when the PV+BESS project exists (not in the no-project baseline).
- Every hourly series is exactly 8760 values, index `0..8759`. Leap-day (Feb 29) is dropped from any
  source that includes it, so every calendar year lines up to the same 8760-hour convention.
- Currency: all internal financial calculations are in USD. Colombian inputs (XM prices in COP/kWh,
  CREG tariffs in COP/kWh) are converted to USD upstream, using annual-average COP/USD rates — the
  dispatch model itself never does currency conversion (no `er` factor, unlike the Spain reference).
- Solver: PuLP with the bundled CBC backend (`pulp.PULP_CBC_CMD`) — no Gurobi (no license available in
  this environment).
- All HTTP calls use the shared `src/http_utils.py` session helper, not bare `requests`/`urllib`
  (see Task 5 for why).
- Financial parameters default to the reference model's own values unless the Colombia design doc says
  otherwise: `i=0.077`, `n=20`, `e=0.025`, `CAPEX_pv=388 USD/kWp`, `CAPEX_BESS=185 USD/kWh`,
  `CAPEX_inverter=48 USD/kWp`, `OaM_pv=12.5 USD/kWp-yr`, `OaM_BESS=5.9 USD/kWh-yr`, `DoD=0.90`,
  `eff_charge=eff_discharge=0.9624`.

---

### Task 0: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `README.md`

**Interfaces:**
- Produces: the `src` package (importable), a `tests/` directory pytest will discover, and
  `data/{raw,cache}/` directories later tasks write into.

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p src tests scripts
mkdir -p data/raw/load_curves data/raw/reference_spain
mkdir -p data/cache/pvgis data/cache/xm
touch src/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
pandas
numpy
requests
certifi
aiohttp
nest_asyncio
pydataxm
pulp
pytest
```

- [ ] **Step 3: Write `pytest.ini`**

```ini
[pytest]
pythonpath = .
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
data/cache/
data/ca_bundle.pem
```

- [ ] **Step 5: Write a minimal `README.md`**

```markdown
# Colombia PV+BESS BtM LCOE

Optimal sizing/dispatch and LCOE (gross/net) for behind-the-meter PV+BESS systems in Colombia,
adapted from github.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing for CREG 174/2021
AGGE (1-5 MW) projects.

See `docs/superpowers/specs/2026-09-06-colombia-pv-bess-lcoe-design.md` for the design and
`docs/superpowers/plans/` for implementation plans.

## Setup

    pip install -r requirements.txt
    pytest
```

- [ ] **Step 6: Install dependencies and verify**

Run: `pip3 install -r requirements.txt`
Expected: completes with no errors (pydataxm/pulp/aiohttp all install cleanly from PyPI).

- [ ] **Step 7: Verify pytest can discover the (currently-empty) test suite**

Run: `python3 -m pytest --collect-only`
Expected: `no tests ran` (not an import/config error) — confirms `pytest.ini`'s `pythonpath = .` is valid.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini .gitignore README.md src/__init__.py
git commit -m "chore: project scaffolding for PV+BESS LCOE foundation"
```

---

### Task 1: Financial helper functions

**Files:**
- Create: `src/finance.py`
- Test: `tests/test_finance.py`

**Interfaces:**
- Produces: `capital_recovery_factor(i: float, n: int) -> float`,
  `escalated_capital_recovery_factor(i: float, n: int, e: float) -> float`. Consumed by
  `src/dispatch_model.py` (Task 9) and `src/lcoe.py` (Task 10).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_finance.py
import pytest

from src import finance


def test_capital_recovery_factor_matches_reference_parameters():
    # i=7.7%, n=20 — the reference model's own values.
    crf = finance.capital_recovery_factor(0.077, 20)
    assert crf == pytest.approx(0.0995890201914585, rel=1e-9)


def test_escalated_capital_recovery_factor_matches_reference_parameters():
    # i=7.7%, n=20, e=2.5% — the reference model's own values.
    crfe = finance.escalated_capital_recovery_factor(0.077, 20, 0.025)
    assert crfe == pytest.approx(0.08275970609929227, rel=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_finance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.finance'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/finance.py
"""Capital-recovery-factor helpers shared by the dispatch model and LCOE calculator.

Mirrors the reference model's own annuity math: a single representative
year's cash flow is annuitized over the project life to get an NPV, using
crf (no cost escalation) or crfe (with escalation) as the annuity factor.
"""


def capital_recovery_factor(i: float, n: int) -> float:
    """Standard capital recovery factor: i(1+i)^n / ((1+i)^n - 1)."""
    return (i * (1 + i) ** n) / ((1 + i) ** n - 1)


def escalated_capital_recovery_factor(i: float, n: int, e: float) -> float:
    """Capital recovery factor adjusted for a constant annual cost escalation e."""
    ir = (i - e) / (1 + e)
    return (1 + e) * (ir * (1 + ir) ** n) / ((1 + ir) ** n - 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_finance.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/finance.py tests/test_finance.py
git commit -m "feat: add capital recovery factor helpers"
```

---

### Task 2: Locations module

**Files:**
- Create: `src/locations.py`
- Test: `tests/test_locations.py`

**Interfaces:**
- Produces: `Location` dataclass (`name`, `region`, `lat`, `lon`), `LOCATIONS` tuple (12 entries),
  `REGIONS` tuple, `get_location(name: str) -> Location`. Consumed by `scripts/run_single_case.py`
  (Task 11) and by `src/creg_tariffs.py` (Task 7, for the location→SDL mapping).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_locations.py
import pytest

from src import locations


def test_has_exactly_twelve_locations_covering_all_five_regions():
    assert len(locations.LOCATIONS) == 12
    assert {loc.region for loc in locations.LOCATIONS} == set(locations.REGIONS)


def test_all_coordinates_are_within_continental_colombia_bounding_box():
    for loc in locations.LOCATIONS:
        assert -4.5 <= loc.lat <= 13.0, f"{loc.name} latitude out of range"
        assert -80.0 <= loc.lon <= -66.5, f"{loc.name} longitude out of range"


def test_get_location_returns_expected_entry():
    bogota = locations.get_location("Bogota")
    assert bogota.region == "Andina"


def test_get_location_raises_for_unknown_name():
    with pytest.raises(KeyError):
        locations.get_location("Not A Real City")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_locations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.locations'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/locations.py
"""The 12 representative locations used to build interpolated LCOE maps.

See design doc section 2 for the rationale (a true 5 km national raster is
not computationally tractable; these 12 points, one-to-three per natural
region, are interpolated instead). Leticia (Amazonas) is deliberately
excluded in favor of Florencia/Mocoa — Leticia is pure ZNI (no spot market,
no AGGE applicability); Florencia and Mocoa are SIN-connected.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    name: str
    region: str  # one of REGIONS
    lat: float
    lon: float


REGIONS = ("Andina", "Caribe", "Pacifica", "Orinoquia", "Amazonia")

LOCATIONS: tuple[Location, ...] = (
    Location("Bogota", "Andina", 4.7110, -74.0721),
    Location("Medellin", "Andina", 6.2442, -75.5812),
    Location("Cali", "Andina", 3.4516, -76.5320),
    Location("Barranquilla", "Caribe", 10.9685, -74.7813),
    Location("Cartagena", "Caribe", 10.3910, -75.4794),
    Location("Riohacha", "Caribe", 11.5444, -72.9072),
    Location("Quibdo", "Pacifica", 5.6947, -76.6611),
    Location("Buenaventura", "Pacifica", 3.8801, -77.0312),
    Location("Villavicencio", "Orinoquia", 4.1420, -73.6266),
    Location("Yopal", "Orinoquia", 5.3378, -72.3959),
    Location("Florencia", "Amazonia", 1.6144, -75.6062),
    Location("Mocoa", "Amazonia", 1.1466, -76.6486),
)


def get_location(name: str) -> Location:
    for loc in LOCATIONS:
        if loc.name == name:
            return loc
    raise KeyError(f"Unknown location: {name}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_locations.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/locations.py tests/test_locations.py
git commit -m "feat: add the 12 representative locations"
```

---

### Task 3: GAMS `.inc` file parser

**Files:**
- Create: `src/gams_inc_parser.py`
- Test: `tests/test_gams_inc_parser.py`

**Interfaces:**
- Produces: `parse_inc_series(text: str) -> dict[int, float]`,
  `load_inc_as_series(path: Path) -> pd.Series` (0-indexed, `0..8759`). Consumed by
  `src/load_curves.py` (Task 4) and the Task 9 dispatch-model validation step.
- Rationale: the reference repo's `.inc` files are inconsistent in formatting — some have one
  `t<hour>\t<value>` pair per line (8763 lines total, including 3 header lines), others have the
  entire table flattened onto a single line with no newlines at all (confirmed by inspecting
  `PpvuMadridSarah20052023_localtime.inc`, which has zero newlines). A regex that scans the whole
  file content — rather than iterating line by line — handles both formats identically.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gams_inc_parser.py
from pathlib import Path

import pandas as pd
import pytest

from src import gams_inc_parser


def test_parse_inc_series_handles_normal_multiline_format():
    text = "Table data4(t,*)\n\tPlu\nt1\t0.5\nt2\t0.75\nt3\t1.0\n"
    result = gams_inc_parser.parse_inc_series(text)
    assert result == {1: 0.5, 2: 0.75, 3: 1.0}


def test_parse_inc_series_handles_flattened_single_line_format():
    text = "Table data3(t,*)Ppvut1\t0t2\t0.0848t3\t0.259"
    result = gams_inc_parser.parse_inc_series(text)
    assert result == {1: 0.0, 2: 0.0848, 3: 0.259}


def test_load_inc_as_series_returns_zero_indexed_series(tmp_path):
    p = tmp_path / "sample.inc"
    p.write_text("Table data4(t,*)\n\tX\nt1\t10.0\nt2\t20.0\n")
    series = gams_inc_parser.load_inc_as_series(p)
    assert series.index.tolist() == [0, 1]
    assert series.tolist() == [10.0, 20.0]


def test_load_inc_as_series_raises_on_missing_hours():
    with pytest.raises(FileNotFoundError):
        gams_inc_parser.load_inc_as_series(Path("/no/such/file.inc"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_gams_inc_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.gams_inc_parser'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/gams_inc_parser.py
"""Parser for the GAMS-style `.inc` table files used by the reference repo.

Handles both the normal one-pair-per-line format and the flattened
single-line format (see PpvuMadridSarah20052023_localtime.inc, which has
zero newlines) by matching `t<digits><whitespace><number>` across the whole
file content rather than iterating line by line.
"""
import re
from pathlib import Path

import pandas as pd

_TOKEN_RE = re.compile(r"t(\d+)\s+([-+0-9.eE]+)")


def parse_inc_series(text: str) -> dict[int, float]:
    return {int(hour): float(value) for hour, value in _TOKEN_RE.findall(text)}


def load_inc_as_series(path: Path) -> pd.Series:
    """Load an `.inc` file into a 0-indexed (0..N-1) hourly Series."""
    text = Path(path).read_text(encoding="utf-8")
    values = parse_inc_series(text)
    series = pd.Series(values).sort_index()
    series.index = series.index - 1
    return series
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_gams_inc_parser.py -v`
Expected: PASS (4 tests) — note `Path.read_text` on a missing file already raises
`FileNotFoundError` naturally, so no special-casing is needed for the last test.

- [ ] **Step 5: Commit**

```bash
git add src/gams_inc_parser.py tests/test_gams_inc_parser.py
git commit -m "feat: add regex-based GAMS .inc file parser"
```

---

### Task 4: Load curve loader

**Files:**
- Create: `src/load_curves.py`
- Test: `tests/test_load_curves.py`

**Interfaces:**
- Consumes: `src.gams_inc_parser.load_inc_as_series` (Task 3).
- Produces: `load_all_curves(data_dir: Path) -> dict[str, pd.Series]` with keys
  `"industria1"`, `"industria2"`, `"datacenter"`, each an 8760-length, 0-indexed `pd.Series` of
  per-unit load factors. Consumed by `scripts/run_single_case.py` (Task 11).

- [ ] **Step 1: Download the 3 real load-curve files into `data/raw/load_curves/`**

```bash
curl -s -o data/raw/load_curves/Plu.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/Plu.inc"
curl -s -o data/raw/load_curves/Plu2.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/Plu2.inc"
curl -s -o data/raw/load_curves/PluDataCenter.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/PluDataCenter.inc"
```

Verify: `wc -l data/raw/load_curves/*.inc` should show 8763 lines for each (8760 data rows + 3 header
rows: `Table data4(t,*)`, a blank/column-name line, and the trailing newline accounting is approximate —
the important check is that Task 4's test below successfully parses exactly 8760 hours from each).

- [ ] **Step 2: Write the failing test**

```python
# tests/test_load_curves.py
from pathlib import Path

from src import load_curves

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "load_curves"


def test_load_all_curves_returns_the_three_expected_curves():
    curves = load_curves.load_all_curves(DATA_DIR)
    assert set(curves.keys()) == {"industria1", "industria2", "datacenter"}


def test_each_curve_has_exactly_8760_hours_indexed_from_zero():
    curves = load_curves.load_all_curves(DATA_DIR)
    for name, series in curves.items():
        assert len(series) == 8760, f"{name} has {len(series)} hours, expected 8760"
        assert series.index.min() == 0
        assert series.index.max() == 8759


def test_load_factors_are_non_negative_and_plausibly_bounded():
    curves = load_curves.load_all_curves(DATA_DIR)
    for name, series in curves.items():
        assert (series >= 0).all(), f"{name} has negative load factors"
        assert (series <= 1.5).all(), f"{name} has implausibly large load factors"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_load_curves.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.load_curves'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/load_curves.py
"""Loads the three 1 MW load curves (industria1, industria2, datacenter)."""
from pathlib import Path

import pandas as pd

from . import gams_inc_parser

LOAD_CURVE_FILES = {
    "industria1": "Plu.inc",
    "industria2": "Plu2.inc",
    "datacenter": "PluDataCenter.inc",
}


def load_all_curves(data_dir: Path) -> dict[str, pd.Series]:
    data_dir = Path(data_dir)
    curves = {}
    for name, filename in LOAD_CURVE_FILES.items():
        series = gams_inc_parser.load_inc_as_series(data_dir / filename)
        if len(series) != 8760:
            raise ValueError(f"{filename}: expected 8760 hours, got {len(series)}")
        curves[name] = series
    return curves
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_load_curves.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add data/raw/load_curves src/load_curves.py tests/test_load_curves.py
git commit -m "feat: add load curve loader for the 3 reference load profiles"
```

---

### Task 5: HTTP session / CA trust helper

**Why this task exists:** this environment routes outbound HTTPS through a corporate TLS-inspecting
proxy (Zscaler) that re-signs certificates with a private CA. That CA is trusted by the OS (macOS
System keychain — confirmed via `security find-certificate`) but not by Python's bundled `certifi`
trust store. Plain `requests` calls to some hosts fail with `CERTIFICATE_VERIFY_FAILED` even though
the same host is reachable via `curl` — confirmed concretely against XM's API (`servapibi.xm.com.co`),
which curl reaches fine but Python's `requests`/`aiohttp` reject out of the box. This builds a combined
CA bundle (certifi + the OS's extra trusted roots) so Python trusts exactly what the OS trusts, without
disabling verification. PVGIS and NEX-GDDP-CMIP6 happened to work without this fix in ad-hoc testing
(their domains are apparently not intercepted), but every client in this project routes through this
helper anyway so a future change in the proxy's intercept list doesn't silently break things.

**Files:**
- Create: `src/http_utils.py`
- Test: `tests/test_http_utils.py`

**Interfaces:**
- Produces: `build_ca_bundle(force: bool = False) -> Path`, `ensure_ca_trust() -> Path`,
  `get_session() -> requests.Session`. Consumed by `src/pvgis_client.py` (Task 6) and
  `src/xm_prices.py` (Task 8).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_http_utils.py
from pathlib import Path

import certifi

from src import http_utils


def test_build_ca_bundle_creates_a_file_at_least_as_large_as_certifi_alone():
    path = http_utils.build_ca_bundle(force=True)
    assert path.exists()
    assert path.stat().st_size >= Path(certifi.where()).stat().st_size


def test_ensure_ca_trust_sets_expected_environment_variables(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    bundle = http_utils.ensure_ca_trust()
    import os
    assert os.environ["SSL_CERT_FILE"] == str(bundle)
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(bundle)


def test_get_session_can_reach_a_known_https_endpoint():
    session = http_utils.get_session()
    r = session.get(
        "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc",
        params={"lat": 4.71, "lon": -74.07, "outputformat": "json",
                "startyear": 2020, "endyear": 2020},
        timeout=30,
    )
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_http_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.http_utils'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/http_utils.py
"""Shared HTTP session setup.

See the Task 5 docstring in the implementation plan for why this exists:
this environment's outbound HTTPS traffic is intercepted by a corporate
TLS-inspecting proxy whose CA is trusted by the OS but not by Python's
bundled certifi trust store.
"""
import os
import subprocess
from pathlib import Path

import certifi
import requests

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CA_BUNDLE_PATH = _DATA_DIR / "ca_bundle.pem"


def build_ca_bundle(force: bool = False) -> Path:
    """Combine certifi's CA bundle with extra roots trusted by the OS keychain.

    Safe to call repeatedly: corporate proxy intermediate certs can rotate on
    a short cycle, so re-running this regenerates the bundle from whatever
    the keychain currently trusts.
    """
    if CA_BUNDLE_PATH.exists() and not force:
        return CA_BUNDLE_PATH
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    base = Path(certifi.where()).read_bytes()
    extra = b""
    try:
        extra = subprocess.run(
            ["security", "find-certificate", "-a", "-p", "/Library/Keychains/System.keychain"],
            capture_output=True, check=True, timeout=15,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass  # not on macOS, or keychain unavailable — fall back to certifi alone
    CA_BUNDLE_PATH.write_bytes(base + b"\n" + extra)
    return CA_BUNDLE_PATH


def ensure_ca_trust() -> Path:
    """Point the standard OpenSSL/requests env vars at the combined bundle.

    Needed for libraries (e.g. aiohttp, used internally by pydataxm) that
    build their own SSL context from SSL_CERT_FILE rather than accepting an
    explicit `verify=` argument.
    """
    bundle = build_ca_bundle()
    os.environ["SSL_CERT_FILE"] = str(bundle)
    os.environ["REQUESTS_CA_BUNDLE"] = str(bundle)
    return bundle


def get_session() -> requests.Session:
    bundle = ensure_ca_trust()
    session = requests.Session()
    session.verify = str(bundle)
    return session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_http_utils.py -v`
Expected: PASS (3 tests). Requires network access to `re.jrc.ec.europa.eu`.

- [ ] **Step 5: Commit**

```bash
git add src/http_utils.py tests/test_http_utils.py
git commit -m "feat: add CA-trust-aware HTTP session helper (Zscaler workaround)"
```

---

### Task 6: PVGIS client

**Files:**
- Create: `src/pvgis_client.py`
- Test: `tests/test_pvgis_client.py`

**Interfaces:**
- Consumes: `src.http_utils.get_session` (Task 5).
- Produces: `fetch_pv_profile(lat: float, lon: float, year: int, cache_dir: Path) -> pd.Series`
  (0-indexed, 8760 hours, per-unit kW-output-per-kWp). Consumed by `scripts/run_single_case.py`
  (Task 11).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pvgis_client.py
from pathlib import Path

from src import pvgis_client


def test_fetch_pv_profile_returns_8760_plausible_values(tmp_path):
    series = pvgis_client.fetch_pv_profile(lat=4.7110, lon=-74.0721, year=2020, cache_dir=tmp_path)
    assert len(series) == 8760
    assert series.index.min() == 0
    assert series.index.max() == 8759
    assert (series >= 0).all()
    assert (series <= 1.5).all()
    # Plausible annual specific yield range for a fixed-tilt system in Colombia (kWh/kWp/year).
    assert 800 < series.sum() < 2500


def test_fetch_pv_profile_uses_cache_on_second_call(tmp_path):
    first = pvgis_client.fetch_pv_profile(lat=4.7110, lon=-74.0721, year=2020, cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("*.csv"))
    assert len(cache_files) == 1
    second = pvgis_client.fetch_pv_profile(lat=4.7110, lon=-74.0721, year=2020, cache_dir=tmp_path)
    assert first.equals(second)
    assert len(list(tmp_path.glob("*.csv"))) == 1  # no new file written
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pvgis_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pvgis_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/pvgis_client.py
"""PVGIS 5.3 (ERA5) hourly PV output client.

Uses PVGIS's own PV simulation (pvcalculation=1), which already accounts for
module temperature de-rating and system losses, so no separate cell-
temperature model is needed for the historical (Version A) case.
"""
from pathlib import Path

import pandas as pd

from . import http_utils

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"


def fetch_pv_profile(lat: float, lon: float, year: int, cache_dir: Path) -> pd.Series:
    """Hourly per-unit PV output (kW per kWp installed) for one calendar year.

    Index 0..8759 — Feb 29 is dropped on leap years so every year lines up
    to the same 8760-hour convention used throughout this project.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"pvgis_{lat:.4f}_{lon:.4f}_{year}.csv"
    if cache_file.exists():
        return pd.read_csv(cache_file, index_col=0).iloc[:, 0]

    session = http_utils.get_session()
    params = {
        "lat": lat, "lon": lon, "outputformat": "json",
        "startyear": year, "endyear": year,
        "pvcalculation": 1, "peakpower": 1, "loss": 14,
        "pvtechchoice": "crystSi", "optimalangles": 1,
    }
    r = session.get(PVGIS_URL, params=params, timeout=60)
    r.raise_for_status()
    hourly = r.json()["outputs"]["hourly"]

    values = []
    for rec in hourly:
        date_part = rec["time"].split(":")[0]  # e.g. '20200101'
        month, day = int(date_part[4:6]), int(date_part[6:8])
        if month == 2 and day == 29:
            continue
        values.append(rec["P"] / 1000.0)  # W for a 1 kWp system -> per-unit kW/kWp

    if len(values) != 8760:
        raise ValueError(
            f"Expected 8760 hourly PV values for ({lat},{lon},{year}), got {len(values)}"
        )

    series = pd.Series(values, index=range(8760), name="pv_per_unit")
    series.to_csv(cache_file)
    return series
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pvgis_client.py -v`
Expected: PASS (2 tests). Requires network access to PVGIS.

- [ ] **Step 5: Commit**

```bash
git add src/pvgis_client.py tests/test_pvgis_client.py
git commit -m "feat: add PVGIS hourly PV output client with disk caching"
```

---

### Task 7: CREG N2 tariff + AGGE backup charge module

**Files:**
- Create: `src/creg_tariffs.py`
- Test: `tests/test_creg_tariffs.py`

**Interfaces:**
- Consumes: `src.locations.LOCATIONS` (Task 2, for coverage validation only).
- Produces: `get_n2_tariff_cop_per_kwh(location_name: str) -> float`,
  `AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR: float`. Consumed by `scripts/run_single_case.py` (Task 11).

**Known limitation, documented rather than hidden:** the N2 (T+D+Pr+R+Cv) values below are an
order-of-magnitude placeholder (a single flat value applied to every SDL), not sourced from a specific
CREG/SUI resolution yet. Same for the AGGE backup charge. Both are concrete, defensible starting
numbers (see comments in the code) — replace with real per-SDL published figures in a follow-on plan
before treating absolute LCOE levels (as opposed to relative comparisons across locations) as final.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_creg_tariffs.py
from src import creg_tariffs, locations


def test_every_location_has_an_sdl_mapping():
    for loc in locations.LOCATIONS:
        assert loc.name in creg_tariffs.LOCATION_SDL, f"{loc.name} missing from LOCATION_SDL"


def test_get_n2_tariff_returns_a_positive_value_for_every_location():
    for loc in locations.LOCATIONS:
        tariff = creg_tariffs.get_n2_tariff_cop_per_kwh(loc.name)
        assert tariff > 0


def test_agge_backup_charge_is_positive():
    assert creg_tariffs.AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_creg_tariffs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.creg_tariffs'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/creg_tariffs.py
"""Colombian N2 tariff (T+D+Pr+R+Cv) and CREG 174/2021 AGGE backup charge.

PLACEHOLDER VALUES: order-of-magnitude defaults, not yet sourced from a
specific CREG/SUI resolution. N2_TARIFF_COP_PER_KWH uses one flat value for
every SDL. Replace with real per-SDL published figures in a follow-on plan.
"""

# Location name (see src/locations.py) -> SDL (regional distribution utility) code.
LOCATION_SDL = {
    "Bogota": "ENEL-CODENSA",
    "Medellin": "EPM",
    "Cali": "CELSIA",
    "Barranquilla": "AIR-E",
    "Cartagena": "AFINIA",
    "Riohacha": "AIR-E",
    "Quibdo": "DISPAC",
    "Buenaventura": "CELSIA",
    "Villavicencio": "EMSA",
    "Yopal": "ENERCA",
    "Florencia": "ELECTROHUILA",
    "Mocoa": "EMSA",
}

# Flat representative N2 = T+D+Pr+R+Cv total, COP/kWh. Placeholder: same value
# for every SDL (~ typical published range for Colombian medium-voltage
# tariffs) pending a real per-SDL CREG/SUI lookup.
_DEFAULT_N2_COP_PER_KWH = 150.0
N2_TARIFF_COP_PER_KWH = {sdl: _DEFAULT_N2_COP_PER_KWH for sdl in set(LOCATION_SDL.values())}

# CREG 174/2021 AGGE backup/respaldo charge (USD per kWp of installed PV
# capacity per year). Applied only when the PV+BESS project exists — an
# AGGE customer without self-generation pays no backup charge, so this does
# NOT appear in the no-project baseline (OPEX0).
AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR = 10.0


def get_n2_tariff_cop_per_kwh(location_name: str) -> float:
    sdl = LOCATION_SDL[location_name]
    return N2_TARIFF_COP_PER_KWH[sdl]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_creg_tariffs.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/creg_tariffs.py tests/test_creg_tariffs.py
git commit -m "feat: add CREG N2 tariff and AGGE backup charge module (placeholder values)"
```

---

### Task 8: XM spot price client

**Files:**
- Create: `src/xm_prices.py`
- Test: `tests/test_xm_prices.py`

**Interfaces:**
- Consumes: `src.http_utils.ensure_ca_trust` (Task 5), `pydataxm.pydataxm.ReadDB`.
- Produces: `fetch_spot_prices_cop_per_kwh(year: int, cache_dir: Path) -> pd.Series` (0-indexed, 8760
  hours), `FX_RATE_COP_PER_USD: dict[int, float]` (2005-2023), `to_usd_per_kwh(series, year) -> pd.Series`.
  Consumed by `scripts/run_single_case.py` (Task 11).

**Verified real call:** `ReadDB().request_data("PrecBolsNaci", "Sistema", start_date, end_date)` is
XM's own documented example (see `pydataxm/pydataxm.py`'s `__main__` block) for the national spot
price, returning one row per day with columns `Values_Hour01`..`Values_Hour24` (COP/kWh). Confirmed
working end-to-end against the real API for January 2023 (values ~500 COP/kWh, a plausible order of
magnitude) once the Task 5 CA-trust fix is applied.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xm_prices.py
import pandas as pd
import pytest

from src import xm_prices


def test_fetch_spot_prices_returns_8760_plausible_values(tmp_path):
    series = xm_prices.fetch_spot_prices_cop_per_kwh(year=2023, cache_dir=tmp_path)
    assert len(series) == 8760
    assert series.index.min() == 0
    assert series.index.max() == 8759
    assert (series > 0).all()
    assert (series < 5000).all()  # COP/kWh — generous upper bound


def test_fetch_spot_prices_uses_cache_on_second_call(tmp_path):
    first = xm_prices.fetch_spot_prices_cop_per_kwh(year=2023, cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("*.csv"))
    assert len(cache_files) == 1
    second = xm_prices.fetch_spot_prices_cop_per_kwh(year=2023, cache_dir=tmp_path)
    assert first.equals(second)


def test_to_usd_per_kwh_divides_by_the_correct_annual_fx_rate():
    series_cop = pd.Series([4325.0, 8650.0])  # chosen to be exact multiples of the 2023 rate
    series_usd = xm_prices.to_usd_per_kwh(series_cop, year=2023)
    assert series_usd.iloc[0] == pytest.approx(1.0, rel=1e-6)
    assert series_usd.iloc[1] == pytest.approx(2.0, rel=1e-6)


def test_to_usd_per_kwh_raises_for_unconfigured_year():
    with pytest.raises(KeyError):
        xm_prices.to_usd_per_kwh(pd.Series([100.0]), year=1999)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_xm_prices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.xm_prices'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/xm_prices.py
"""XM Sinergox hourly national spot price client + COP->USD conversion.

Uses pydataxm (XM's own public SDK). Requires the Task 5 CA-trust fix:
pydataxm's constructor makes an unconditional `requests.post` call, and its
`request_data()` uses `aiohttp` internally for the actual data fetch — both
need the combined CA bundle (aiohttp reads it via the SSL_CERT_FILE env var;
requests via REQUESTS_CA_BUNDLE), which `http_utils.ensure_ca_trust()` sets.
"""
import datetime as dt
from pathlib import Path

import pandas as pd

from . import http_utils

_client = None


def _get_client():
    global _client
    if _client is None:
        http_utils.ensure_ca_trust()
        from pydataxm.pydataxm import ReadDB
        _client = ReadDB()
    return _client


def fetch_spot_prices_cop_per_kwh(year: int, cache_dir: Path) -> pd.Series:
    """Hourly national spot price (COP/kWh) for the given year, index 0..8759.

    Feb 29 is dropped on leap years to keep exactly 8760 hours/year.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"xm_prices_{year}.csv"
    if cache_file.exists():
        return pd.read_csv(cache_file, index_col=0).iloc[:, 0]

    client = _get_client()
    df = client.request_data("PrecBolsNaci", "Sistema", dt.date(year, 1, 1), dt.date(year, 12, 31))
    if df.empty:
        raise ValueError(f"XM returned no data for {year}")
    df = df.sort_values("Date").reset_index(drop=True)

    hour_cols = [f"Values_Hour{h:02d}" for h in range(1, 25)]
    values = []
    for _, row in df.iterrows():
        date = row["Date"]
        if date.month == 2 and date.day == 29:
            continue
        values.extend(float(row[c]) for c in hour_cols)

    if len(values) != 8760:
        raise ValueError(f"Expected 8760 hourly prices for {year}, got {len(values)}")

    series = pd.Series(values, index=range(8760), name="cop_per_kwh")
    series.to_csv(cache_file)
    return series


# Banco de la República annual-average COP/USD rates. Approximate — verify
# against BanRep's official "TRM promedio anual" series before using for
# anything beyond order-of-magnitude currency conversion.
FX_RATE_COP_PER_USD = {
    2005: 2321, 2006: 2358, 2007: 2078, 2008: 1967, 2009: 2153,
    2010: 1898, 2011: 1848, 2012: 1798, 2013: 1869, 2014: 2001,
    2015: 2743, 2016: 3055, 2017: 2951, 2018: 2957, 2019: 3281,
    2020: 3693, 2021: 3744, 2022: 4256, 2023: 4325,
}


def to_usd_per_kwh(series_cop_per_kwh: pd.Series, year: int) -> pd.Series:
    if year not in FX_RATE_COP_PER_USD:
        raise KeyError(f"No FX rate configured for year {year}")
    return series_cop_per_kwh / FX_RATE_COP_PER_USD[year]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_xm_prices.py -v`
Expected: PASS (4 tests). Requires network access to XM's API (`servapibi.xm.com.co`).

- [ ] **Step 5: Commit**

```bash
git add src/xm_prices.py tests/test_xm_prices.py
git commit -m "feat: add XM spot price client with COP->USD conversion"
```

---

### Task 9: Dispatch/sizing MILP model

**Files:**
- Create: `src/dispatch_model.py`
- Test: `tests/test_dispatch_model.py`

**Interfaces:**
- Consumes: `src.finance.capital_recovery_factor`, `src.finance.escalated_capital_recovery_factor`
  (Task 1); `src.gams_inc_parser.load_inc_as_series` (Task 3, validation step only).
- Produces: `SizingParams` dataclass, `SizingResult` dataclass, `solve_sizing_dispatch(Plu, Ppvu,
  lambda_usd_per_kwh, psi_usd_per_kwh, params) -> SizingResult`. Consumed by `src/lcoe.py` (Task 10)
  and `scripts/run_single_case.py` (Task 11).

This is a PuLP/CBC port of `PV_BESS_sizing_model.py` (Gurobi) from the reference repo, adapted per
design doc section 3: the Spain 6-period contracted-power capacity charge is dropped and replaced by a
flat AGGE backup charge (see `CapacityP`/`CapacityP0` below — asymmetric: the charge exists only with
the project); no `er` EUR/USD conversion (inputs already USD); a new `[Ppv_min_kw, Ppv_max_kw]` bound
enforces the CREG 174/2021 AGGE range. `T` is derived from the input series length rather than
hardcoded to 8760, so the same function supports both a fast small-scale unit test and the full
8760-hour case.

- [ ] **Step 1: Write the failing test (fast, synthetic 48-hour scenario)**

```python
# tests/test_dispatch_model.py
import pandas as pd

from src import dispatch_model as dm


def _toy_two_day_scenario():
    """48 hours, 2 identical days: PV only 06:00-18:00, cheap price during
    that PV window, expensive price at night — a clear arbitrage incentive
    for the optimizer to charge from PV by day and discharge by night."""
    n = 48
    Plu = pd.Series([1.0] * n)
    Ppvu = pd.Series([1.0 if 6 <= (h % 24) < 18 else 0.0 for h in range(n)])
    lam = pd.Series([0.05 if 6 <= (h % 24) < 18 else 0.20 for h in range(n)])
    psi = pd.Series([0.01] * n)
    return Plu, Ppvu, lam, psi


def test_solve_sizing_dispatch_is_optimal_and_energy_balanced():
    Plu, Ppvu, lam, psi = _toy_two_day_scenario()
    params = dm.SizingParams(Plinst_kw=1000.0)
    result = dm.solve_sizing_dispatch(Plu, Ppvu, lam, psi, params)

    assert result.status == "Optimal"
    assert params.Ppv_min_kw - 1e-6 <= result.Ppvinst_kw <= params.Ppv_max_kw + 1e-6
    assert result.C_kwh >= 0

    for t in range(len(Plu)):
        supply = result.Pd[t] + result.Pb[t] + result.Ppv[t]
        use = result.Pc[t] + result.Ps[t] + params.Plinst_kw * Plu.iloc[t]
        assert abs(supply - use) < 1e-3, f"energy balance violated at hour {t}"

        floor = ((1 - params.depth_of_discharge) / 2) * result.C_kwh
        ceiling = ((1 - params.depth_of_discharge) / 2 + params.depth_of_discharge) * result.C_kwh
        assert floor - 1e-3 <= result.SOC[t] <= ceiling + 1e-3, f"SOC out of bounds at hour {t}"


def test_solve_sizing_dispatch_rejects_mismatched_series_lengths():
    import pytest
    Plu, Ppvu, lam, psi = _toy_two_day_scenario()
    params = dm.SizingParams(Plinst_kw=1000.0)
    with pytest.raises(ValueError):
        dm.solve_sizing_dispatch(Plu, Ppvu.iloc[:24], lam, psi, params)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.dispatch_model'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/dispatch_model.py
"""PV+BESS behind-the-meter optimal sizing + dispatch (Colombia AGGE adaptation).

Ports the reference Spain model (Gurobi; see
github.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing) to PuLP/CBC.

Two structural changes from the Spain original (see design doc section 3.3):
1. Spain's 6-period contracted-power capacity charge is dropped (the brief
   says not to model hourly/periodic power charges); replaced by a flat CREG
   AGGE backup charge that applies only when the PV+BESS project exists
   (CapacityP0 = 0 in the no-project baseline).
2. Currency: inputs are already USD/kWh (converted upstream from COP); no
   internal EUR->USD exchange-rate factor.
"""
from dataclasses import dataclass

import pandas as pd
import pulp

from . import finance


@dataclass
class SizingParams:
    Plinst_kw: float
    depth_of_discharge: float = 0.90
    eff_charge: float = 0.9624
    eff_discharge: float = 0.9624
    Ppv_min_kw: float = 1000.0   # CREG 174/2021 AGGE floor (1 MW)
    Ppv_max_kw: float = 5000.0   # CREG 174/2021 AGGE ceiling (5 MW)
    oam_pv_usd_per_kwp_year: float = 12.5
    oam_bess_usd_per_kwh_year: float = 5.9
    capex_pv_usd_per_kwp: float = 388.0
    capex_bess_usd_per_kwh: float = 185.0
    capex_inverter_usd_per_kw: float = 48.0
    balance_of_plant_usd: float = 0.0
    soft_cost_multiplier: float = 1.2
    discount_rate: float = 0.077
    project_life_years: int = 20
    escalation_rate: float = 0.025
    agge_backup_charge_usd_per_kwp_year: float = 10.0

    @property
    def PmaxF_kw(self) -> float:
        """Grid import/export frontier. Interpreted as the load's own peak,
        matching the reference model's own convention (PmaxF = Plinst) — see
        design doc section 3.3 for why the brief's '1000 MW' is read as a
        units slip rather than taken literally."""
        return self.Plinst_kw


@dataclass
class SizingResult:
    status: str
    Ppvinst_kw: float
    C_kwh: float
    PinverterBESS_kw: float
    PinverterPV_kw: float
    Investment0_usd: float
    OPEX_usd_per_year: float
    OPEX0_usd_per_year: float
    OPEXgross_usd_per_year: float
    Es_usd_per_year: float
    Wl_kwh_per_year: float
    crf: float
    crfe: float
    Ppv: list
    Pb: list
    Ps: list
    Pc: list
    Pd: list
    SOC: list


def solve_sizing_dispatch(
    Plu: pd.Series,
    Ppvu: pd.Series,
    lambda_usd_per_kwh: pd.Series,
    psi_usd_per_kwh: pd.Series,
    params: SizingParams,
) -> SizingResult:
    n_hours = len(Plu)
    if not (len(Ppvu) == len(lambda_usd_per_kwh) == len(psi_usd_per_kwh) == n_hours):
        raise ValueError("All hourly series must have the same length")

    T = range(n_hours)
    Plu_v = Plu.to_numpy()
    Ppvu_v = Ppvu.to_numpy()
    lam_v = lambda_usd_per_kwh.to_numpy()
    psi_v = psi_usd_per_kwh.to_numpy()

    prob = pulp.LpProblem("PV_BESS_Sizing_Colombia", pulp.LpMaximize)

    Ppvinst = pulp.LpVariable("Ppvinst", lowBound=params.Ppv_min_kw, upBound=params.Ppv_max_kw)
    C = pulp.LpVariable("C", lowBound=0)
    PinverterBESS = pulp.LpVariable("PinverterBESS", lowBound=0)
    PinverterPV = pulp.LpVariable("PinverterPV", lowBound=0)
    SOC0 = pulp.LpVariable("SOC0", lowBound=0)

    Ppv = pulp.LpVariable.dicts("Ppv", T, lowBound=0)
    Ppvmx = pulp.LpVariable.dicts("Ppvmx", T, lowBound=0)
    Pd = pulp.LpVariable.dicts("Pd", T, lowBound=0)
    Pc = pulp.LpVariable.dicts("Pc", T, lowBound=0)
    Pb = pulp.LpVariable.dicts("Pb", T, lowBound=0)
    Ps = pulp.LpVariable.dicts("Ps", T, lowBound=0)
    SOC = pulp.LpVariable.dicts("SOC", T, lowBound=0)
    w1 = pulp.LpVariable.dicts("w1", T, cat="Binary")
    w3 = pulp.LpVariable.dicts("w3", T, cat="Binary")

    PmaxF = params.PmaxF_kw
    DoD = params.depth_of_discharge
    Plinst = params.Plinst_kw

    Es = pulp.lpSum(lam_v[t] * Ps[t] for t in T)
    Eb = pulp.lpSum((lam_v[t] + psi_v[t]) * Pb[t] for t in T)
    Eb0 = pulp.lpSum((lam_v[t] + psi_v[t]) * Plinst * Plu_v[t] for t in T)

    CapacityP = params.agge_backup_charge_usd_per_kwp_year * Ppvinst
    CapacityP0 = 0.0  # no backup charge without self-generation

    OPEX = CapacityP + Eb + params.oam_pv_usd_per_kwp_year * Ppvinst + params.oam_bess_usd_per_kwh_year * C
    OPEX0 = Eb0 + CapacityP0
    OPEXgross = params.oam_pv_usd_per_kwp_year * Ppvinst + params.oam_bess_usd_per_kwh_year * C

    Investment0 = params.balance_of_plant_usd + params.soft_cost_multiplier * (
        params.capex_pv_usd_per_kwp * Ppvinst
        + params.capex_bess_usd_per_kwh * C
        + params.capex_inverter_usd_per_kw * (PinverterBESS + PinverterPV)
    )

    CashFlow = Es + OPEX0 - OPEX
    crfe = finance.escalated_capital_recovery_factor(
        params.discount_rate, params.project_life_years, params.escalation_rate
    )
    npv = CashFlow * (1.0 / crfe) - Investment0
    prob += npv  # objective: maximize NPV == minimize LCOE_net (see design doc section 3.4)

    for t in T:
        prob += Pd[t] + Pb[t] + Ppv[t] == Pc[t] + Ps[t] + Plinst * Plu_v[t], f"balance_{t}"
        prob += Ppvmx[t] == Ppvinst * Ppvu_v[t], f"pv_avail_{t}"
        prob += Ppv[t] <= Ppvmx[t], f"pv_curtail_{t}"
        if t == 0:
            prob += SOC[t] == SOC0 + Pc[t] * params.eff_charge - Pd[t] / params.eff_discharge, f"soc_{t}"
        else:
            prob += SOC[t] == SOC[t - 1] + Pc[t] * params.eff_charge - Pd[t] / params.eff_discharge, f"soc_{t}"
        prob += Pc[t] <= PinverterBESS * w1[t], f"charge_excl_{t}"
        prob += Pd[t] <= PinverterBESS * (1 - w1[t]), f"discharge_excl_{t}"
        prob += Pb[t] <= PmaxF * w3[t], f"buy_excl_{t}"
        prob += Ps[t] <= PmaxF * (1 - w3[t]), f"sell_excl_{t}"
        prob += SOC[t] <= ((1 - DoD) / 2 + DoD) * C, f"soc_ub_{t}"
        prob += SOC[t] >= ((1 - DoD) / 2) * C, f"soc_lb_{t}"

    prob += SOC0 <= ((1 - DoD) / 2 + DoD) * C, "soc0_ub"
    prob += SOC0 >= ((1 - DoD) / 2) * C, "soc0_lb"
    prob += PinverterBESS <= C * 2.0, "bess_crate_ub"
    prob += PinverterBESS >= C * 0.1, "bess_crate_lb"
    prob += PinverterPV == Plinst + PmaxF + PinverterBESS, "pv_inverter_size"

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]

    Wl = float(sum(Plinst * Plu_v[t] for t in T))
    crf = finance.capital_recovery_factor(params.discount_rate, params.project_life_years)

    return SizingResult(
        status=status,
        Ppvinst_kw=Ppvinst.varValue,
        C_kwh=C.varValue,
        PinverterBESS_kw=PinverterBESS.varValue,
        PinverterPV_kw=PinverterPV.varValue,
        Investment0_usd=pulp.value(Investment0),
        OPEX_usd_per_year=pulp.value(OPEX),
        OPEX0_usd_per_year=pulp.value(OPEX0),
        OPEXgross_usd_per_year=pulp.value(OPEXgross),
        Es_usd_per_year=pulp.value(Es),
        Wl_kwh_per_year=Wl,
        crf=crf,
        crfe=crfe,
        Ppv=[Ppv[t].varValue for t in T],
        Pb=[Pb[t].varValue for t in T],
        Ps=[Ps[t].varValue for t in T],
        Pc=[Pc[t].varValue for t in T],
        Pd=[Pd[t].varValue for t in T],
        SOC=[SOC[t].varValue for t in T],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch_model.py -v`
Expected: PASS (2 tests). Solves in well under a second (48 hours × 2 binaries = 96 binary variables).

- [ ] **Step 5: Commit**

```bash
git add src/dispatch_model.py tests/test_dispatch_model.py
git commit -m "feat: add PuLP/CBC port of the PV+BESS sizing/dispatch MILP"
```

- [ ] **Step 6: Download the Spain reference data files for a full-scale (8760h) validation test**

```bash
curl -s -o data/raw/reference_spain/PpvuMadridSarah20052023_localtime.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/PpvuMadridSarah20052023_localtime.inc"
curl -s -o data/raw/reference_spain/lambda_spain_localtime.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/lambda_spain_localtime.inc"
curl -s -o data/raw/reference_spain/psi.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/psi.inc"
curl -s -o data/raw/reference_spain/PluDataCenter.inc "https://raw.githubusercontent.com/pmdeoliveiradejesus/SelfGeneration_PV_BESS_BTM_Sizing/main/PluDataCenter.inc"
```

Note: `PpvuMadridSarah20052023_localtime.inc` has zero newlines (the whole table is on one line) —
this is exactly why Task 3's parser scans the whole file content with a regex instead of iterating
line by line. Confirmed by direct inspection: it contains exactly 8760 unique hour keys with values in
`[0, 0.726]`; `lambda_spain_localtime.inc` and `psi.inc` are normal multi-line files, 8760 values each,
in `[-0.002, 0.193]` and `[0.021, 0.072]` respectively — both already effectively EUR/kWh despite a
misleading "Eur/MWh" comment in the original reference script.

- [ ] **Step 7: Write the failing full-scale validation test**

```python
# tests/test_dispatch_model_full_scale.py (separate file: this test is slow — full 8760h MILP solve)
from pathlib import Path

from src import dispatch_model as dm
from src import gams_inc_parser

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "reference_spain"


def test_full_scale_solve_on_real_spain_reference_data_is_optimal_and_balanced():
    Ppvu = gams_inc_parser.load_inc_as_series(DATA_DIR / "PpvuMadridSarah20052023_localtime.inc")
    lam = gams_inc_parser.load_inc_as_series(DATA_DIR / "lambda_spain_localtime.inc")
    psi = gams_inc_parser.load_inc_as_series(DATA_DIR / "psi.inc")
    Plu = gams_inc_parser.load_inc_as_series(DATA_DIR / "PluDataCenter.inc")
    assert len(Ppvu) == len(lam) == len(psi) == len(Plu) == 8760

    params = dm.SizingParams(Plinst_kw=1000.0)
    result = dm.solve_sizing_dispatch(Plu, Ppvu, lam, psi, params)

    assert result.status == "Optimal"
    assert params.Ppv_min_kw - 1e-6 <= result.Ppvinst_kw <= params.Ppv_max_kw + 1e-6

    total_supply = sum(result.Pd) + sum(result.Pb) + sum(result.Ppv)
    total_use = sum(result.Pc) + sum(result.Ps) + result.Wl_kwh_per_year
    assert abs(total_supply - total_use) < 1.0  # kWh, over a full year — tight tolerance
```

- [ ] **Step 8: Run test to verify it fails, then run again after no code changes are needed**

Run: `python3 -m pytest tests/test_dispatch_model_full_scale.py -v`
Expected: since `dispatch_model.py` and `gams_inc_parser.py` already exist from prior steps, this
should PASS immediately without further implementation changes. Record the wall-clock solve time
reported by `-v`'s duration (or wrap with `time python3 -m pytest ...`) — this is the performance
benchmark referenced in the design doc's risk section (~684 solves needed for the full Version A+B
run). If this single 8760-hour solve takes more than ~30 seconds, flag it before any follow-on plan
attempts the full location × year × load-curve sweep, and investigate the LP-relaxation shortcut noted
in the design doc (dropping the `w1`/`w3` binaries) as a mitigation.

- [ ] **Step 9: Commit**

```bash
git add data/raw/reference_spain tests/test_dispatch_model_full_scale.py
git commit -m "test: validate dispatch_model at full 8760h scale against real Spain reference data"
```

---

### Task 10: LCOE calculator

**Files:**
- Create: `src/lcoe.py`
- Test: `tests/test_lcoe.py`

**Interfaces:**
- Consumes: `src.dispatch_model.SizingResult` (Task 9, structurally — this module does not import
  `dispatch_model` itself, it just accepts objects with matching fields, but the test constructs a
  real `SizingResult`).
- Produces: `LCOEResult` dataclass (`lcoe_gross_usd_per_mwh`, `lcoe_net_usd_per_mwh`),
  `compute_lcoe(result: SizingResult) -> LCOEResult`. Consumed by `scripts/run_single_case.py`
  (Task 11).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lcoe.py
import pytest

from src import lcoe
from src.dispatch_model import SizingResult


def _make_result(**overrides) -> SizingResult:
    defaults = dict(
        status="Optimal", Ppvinst_kw=2000.0, C_kwh=1000.0, PinverterBESS_kw=200.0,
        PinverterPV_kw=3000.0, Investment0_usd=1_000_000.0, OPEX_usd_per_year=50_000.0,
        OPEX0_usd_per_year=80_000.0, OPEXgross_usd_per_year=30_000.0, Es_usd_per_year=10_000.0,
        Wl_kwh_per_year=2_000_000.0, crf=0.0995890201914585, crfe=0.08275970609929227,
        Ppv=[], Pb=[], Ps=[], Pc=[], Pd=[], SOC=[],
    )
    defaults.update(overrides)
    return SizingResult(**defaults)


def test_compute_lcoe_matches_the_reference_formula_exactly():
    result = _make_result()
    out = lcoe.compute_lcoe(result)

    expected_gross = 1000 * (result.Investment0_usd + result.OPEXgross_usd_per_year / result.crfe) / (
        result.Wl_kwh_per_year / result.crf
    )
    expected_net = 1000 * (
        result.Investment0_usd
        + (result.OPEX_usd_per_year - result.OPEX0_usd_per_year - result.Es_usd_per_year) / result.crfe
    ) / (result.Wl_kwh_per_year / result.crf)

    assert out.lcoe_gross_usd_per_mwh == pytest.approx(expected_gross, rel=1e-9)
    assert out.lcoe_net_usd_per_mwh == pytest.approx(expected_net, rel=1e-9)


def test_compute_lcoe_raises_when_load_energy_is_zero():
    result = _make_result(Wl_kwh_per_year=0.0)
    with pytest.raises(ValueError):
        lcoe.compute_lcoe(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_lcoe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lcoe'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/lcoe.py
"""LCOE_gross and LCOE_net, exactly as defined in the reference model.

The denominator is the annual LOAD energy (Wl), not PV generation — this
matches the reference model's own definition (see design doc section 3.4),
kept as-is to stay faithful to the methodology being adapted.
"""
from dataclasses import dataclass

from .dispatch_model import SizingResult


@dataclass
class LCOEResult:
    lcoe_gross_usd_per_mwh: float
    lcoe_net_usd_per_mwh: float


def compute_lcoe(result: SizingResult) -> LCOEResult:
    if result.Wl_kwh_per_year <= 0:
        raise ValueError("Wl_kwh_per_year (annual load energy) must be positive")

    annuitized_load = result.Wl_kwh_per_year / result.crf

    lcoe_gross = 1000 * (
        result.Investment0_usd + result.OPEXgross_usd_per_year / result.crfe
    ) / annuitized_load

    lcoe_net = 1000 * (
        result.Investment0_usd
        + (result.OPEX_usd_per_year - result.OPEX0_usd_per_year - result.Es_usd_per_year) / result.crfe
    ) / annuitized_load

    return LCOEResult(lcoe_gross_usd_per_mwh=lcoe_gross, lcoe_net_usd_per_mwh=lcoe_net)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_lcoe.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lcoe.py tests/test_lcoe.py
git commit -m "feat: add LCOE_gross/LCOE_net calculator"
```

---

### Task 11: End-to-end single-case integration

**Files:**
- Create: `scripts/run_single_case.py`
- Test: `tests/test_integration_single_case.py`

**Interfaces:**
- Consumes: every module from Tasks 2, 4, 6, 7, 8, 9, 10.
- Produces: `run(location_name: str, year: int, load_curve_name: str) -> tuple[SizingResult, LCOEResult]`.
  This is the final proof that the whole pipeline works together; no later task consumes this one — it
  is the deliverable of this plan.

This test is slow (real PVGIS + XM network calls, plus a full 8760-hour MILP solve) and requires
network access. That is expected and correct for an end-to-end integration test — it is intentionally
the one test in this plan that exercises every module together against real external data.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration_single_case.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_single_case import run


def test_bogota_2020_datacenter_end_to_end():
    result, lcoe_result = run("Bogota", 2020, "datacenter")

    assert result.status == "Optimal"
    assert 1000.0 - 1e-6 <= result.Ppvinst_kw <= 5000.0 + 1e-6
    assert result.C_kwh >= 0

    # Broad sanity bounds — plausible order of magnitude for USD/MWh, not a
    # tight expected value (real market/PV data varies year to year).
    assert 10.0 < lcoe_result.lcoe_gross_usd_per_mwh < 2000.0
    assert 10.0 < lcoe_result.lcoe_net_usd_per_mwh < 2000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_integration_single_case.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_single_case'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/run_single_case.py
"""End-to-end smoke run: one location, one year, one load curve."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import creg_tariffs, dispatch_model, lcoe, load_curves, locations, pvgis_client, xm_prices

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def run(location_name: str, year: int, load_curve_name: str):
    loc = locations.get_location(location_name)

    pv_per_unit = pvgis_client.fetch_pv_profile(loc.lat, loc.lon, year, DATA_DIR / "cache" / "pvgis")

    prices_cop = xm_prices.fetch_spot_prices_cop_per_kwh(year, DATA_DIR / "cache" / "xm")
    prices_usd = xm_prices.to_usd_per_kwh(prices_cop, year)

    n2_cop_series = pd.Series([creg_tariffs.get_n2_tariff_cop_per_kwh(location_name)] * 8760)
    n2_usd_series = xm_prices.to_usd_per_kwh(n2_cop_series, year)

    curves = load_curves.load_all_curves(DATA_DIR / "raw" / "load_curves")
    plu = curves[load_curve_name]

    params = dispatch_model.SizingParams(
        Plinst_kw=1000.0,
        agge_backup_charge_usd_per_kwp_year=creg_tariffs.AGGE_BACKUP_CHARGE_USD_PER_KWP_YEAR,
    )
    result = dispatch_model.solve_sizing_dispatch(plu, pv_per_unit, prices_usd, n2_usd_series, params)
    lcoe_result = lcoe.compute_lcoe(result)
    return result, lcoe_result


if __name__ == "__main__":
    r, l = run("Bogota", 2020, "datacenter")
    print(f"status={r.status}")
    print(f"Ppvinst={r.Ppvinst_kw:.1f} kWp, C={r.C_kwh:.1f} kWh, PinverterBESS={r.PinverterBESS_kw:.1f} kW")
    print(f"LCOE_gross={l.lcoe_gross_usd_per_mwh:.2f} USD/MWh")
    print(f"LCOE_net={l.lcoe_net_usd_per_mwh:.2f} USD/MWh")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_integration_single_case.py -v`
Expected: PASS. Also run directly to see the printed summary: `python3 scripts/run_single_case.py`

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

Run: `python3 -m pytest -v`
Expected: all tests from Tasks 1-11 PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_single_case.py tests/test_integration_single_case.py
git commit -m "feat: wire up end-to-end single-case run (Bogota/2020/datacenter)"
```

---

## What this plan deliberately leaves out (for follow-on plans)

- Scaling Version A to all 12 locations × 17 years × 3 load curves, with disk-cached/resumable
  orchestration (`src/run_scenarios.py` in the design doc's architecture).
- Version B (NEX-GDDP-CMIP6 delta-change climate adjustment).
- Mapping/interpolation (`src/mapping.py`) and the 6 headline LCOE maps.
- Sensitivity analysis (discount rate, battery cost, load curve).
- Validation against Ángel-Sanint et al. 2023 and the two climate papers.
- Replacing the placeholder CREG N2/AGGE backup charge values with real per-SDL CREG/SUI figures.
- The executive report and README expansion.

Each of these should be its own plan once this foundation is confirmed working, per the writing-plans
skill's guidance to split multi-subsystem specs into separate plans rather than one monolithic one.
