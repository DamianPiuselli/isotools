# Workflow Recipes & Public API Reference

This document provides copy-pasteable, production-ready workflow recipes for common CF-IRMS analytical scenarios alongside a structured public API reference.

---

## Part 1: Workflow Recipes

### Recipe 1: Dual-Isotope Water Analysis ($\delta^{2}\text{H}$ & $\delta^{18}\text{O}$)

This recipe processes a dual-isotope liquid water sequence (e.g. TC/EA, equilibration, or laser spectroscopy) stored in an Excel workbook with separate sheets for `2H` and `18O`. It excludes early carryover injections, evaluates and applies linear drift correction, calibrates to the VSMOW-SLAP scale using `MultiPointLinear`, and exports single and dual-isotope HTML and Excel reports with deuterium excess ($d\text{-excess}$).

```python
from isotools import (
    Batch,
    WATER_H,
    WATER_O,
    MultiPointLinear,
    generate_dual_isotope_html_report,
)

EXCEL_PATH = "run_2026_water.xlsx"

# 1. Instantiate Batches for Hydrogen and Oxygen
batch_h = Batch(EXCEL_PATH, config=WATER_H, sheet_name="2H.wke")
batch_o = Batch(EXCEL_PATH, config=WATER_O, sheet_name="18O.wke")

# 2. Register International / Working Standards
anchors_h = ["Mar_H", "Buenos Aires_H", "Mendoza_H", "Antartida_H"]
anchors_o = ["Mar_O", "Buenos Aires_O", "Mendoza_O", "Antartida_O"]

batch_h.set_anchors(anchors_h)
batch_o.set_anchors(anchors_o)

batch_h.set_drift_monitors(["Buenos Aires_H"])
batch_o.set_drift_monitors(["Buenos Aires_O"])

# 3. Handle Carryover / Memory
# Option A: Exclude the first 2 injections of each vial block
batch_h.exclude_first_injections(2)
batch_o.exclude_first_injections(2)

# Option B: Or apply Gröning memory carryover correction
# batch_h.apply_memory_correction(coefficients=[0.08, 0.02])
# batch_o.apply_memory_correction(coefficients=[0.06, 0.015])

# 4. Triage Outliers & Apply Manual Row Exclusions
print("2H Alerts:\n", batch_h.alerts)
print("18O Alerts:\n", batch_o.alerts)
batch_h.exclude_rows([22])  # e.g., row 22 had an autosampler leak
batch_o.exclude_rows([16])  # e.g., row 16 had an anomalous peak area

# 5. Evaluate and Apply Linear Drift Correction
print("2H Drift Stats:\n", batch_h.check_drift())
batch_h.apply_drift_correction("Buenos Aires_H")
batch_o.apply_drift_correction("Buenos Aires_O")

# 6. Normalize Scales & Propagate Full Uncertainty
strat_h = MultiPointLinear()
strat_o = MultiPointLinear()

batch_h.process(strategy=strat_h)
batch_o.process(strategy=strat_o)

# 7. Export Single-Isotope Excel and Interactive HTML Reports
batch_h.save_report("Water_2H_Report.xlsx")
batch_h.save_html_report("Water_2H_Report.html", offline=True)

batch_o.save_report("Water_18O_Report.xlsx")
batch_o.save_html_report("Water_18O_Report.html", offline=True)

# 8. Export Unified Dual-Isotope Report (with d-excess and LMWL/GMWL)
generate_dual_isotope_html_report(
    batch_h,
    batch_o,
    "Water_Dual_Isotope_Report.html",
    title="Hydrology Dual Isotope Report",
    offline=True,
)
```

---

### Recipe 2: Solid EA-IRMS ($\delta^{13}\text{C}$ & $\delta^{15}\text{N}$) with Blanks, Linearity, Elemental $\%C$/$\%N$, and Metadata

This recipe processes solid organic or sediment samples analyzed by EA-IRMS. It applies mass-balance blank correction for tin capsules, corrects for peak-area linearity dependence, calibrates elemental mass fractions ($\text{\%C}$ and $\text{\%N}$), merges external field sample metadata, and exports dual $\text{C/N}$ atomic ratio reports.

```python
import pandas as pd
from isotools import (
    Batch,
    CARBON_13C,
    NITROGEN,
    TwoPointLinear,
    generate_dual_isotope_html_report,
)

EXCEL_PATH = "ea_sequence_cn.xlsx"

# 1. Initialize Batches
batch_c = Batch(EXCEL_PATH, config=CARBON_13C, sheet_name="Carbon")
batch_n = Batch(EXCEL_PATH, config=NITROGEN, sheet_name="Nitrogen")

# 2. Register Anchors and Quality Control Standards
batch_c.set_anchors(["USGS40_C", "USGS41a_C"])
batch_c.set_controls(["Acetanilide_C"])

batch_n.set_anchors(["USGS40_N", "USGS41a_N"])
batch_n.set_controls(["Acetanilide_N"])

# 3. Apply Mass-Balance Blank Correction (Tin capsule blanks labeled 'Blank')
batch_c.apply_blank_correction(blank_identifier="Blank")
batch_n.apply_blank_correction(blank_identifier="Blank")

# 4. Check & Apply Linearity Correction
# Linearity can be inferred from variable-size Acetanilide or transferred directly
lin_stats_c = batch_c.check_linearity(substance_name="Acetanilide")
print("Carbon Linearity Regression:\n", lin_stats_c)
if not lin_stats_c.empty and lin_stats_c.loc["Acetanilide_C", "p_value"] < 0.05:
    batch_c.apply_linearity_correction(substance_name="Acetanilide")

# 5. Calibrate Elemental Composition (%C and %N)
# Uses sample weights ('Amount') and reference standards with known mass_fraction
batch_c.calibrate_elemental_composition()
batch_n.calibrate_elemental_composition()

# 6. Normalize Isotope Scales
batch_c.process(strategy=TwoPointLinear())
batch_n.process(strategy=TwoPointLinear())

# 7. Merge Contextual Field Sample Metadata
metadata_df = pd.DataFrame({
    "sample_name": ["Soil_Core_A", "Soil_Core_B", "Sediment_01"],
    "Transect": ["North", "North", "Estuary"],
    "Horizon": ["A", "B", "Surface"],
    "Elevation_m": [1240, 1235, 12],
})
batch_c.join_metadata(metadata_df, on="sample_name")
batch_n.join_metadata(metadata_df, on="sample_name")

# 8. Export Single and Dual-Isotope C/N Reports
batch_c.save_report("EA_Carbon_Results.xlsx")
batch_n.save_report("EA_Nitrogen_Results.xlsx")

generate_dual_isotope_html_report(
    batch_c,
    batch_n,
    "EA_Dual_CN_Report.html",
    title="Ecosystem Carbon/Nitrogen Isotope and Stoichiometry Report",
    offline=True,
)
```

---

### Recipe 3: Long-Term Laboratory QA/QC Logging & Shewhart Control Charts

This recipe logs quality control monitor standard performance across multiple analytical batches to track longitudinal instrument stability under ISO/IEC 17025.

```python
import os
from isotools import Batch, NITROGEN, TwoPointLinear, QualityControlLog

QC_LOG_PATH = "laboratory_qc_log.csv"
qc_log = QualityControlLog(QC_LOG_PATH)

# Simulate processing of analytical batches over successive weeks
for batch_file in ["run_week1.xlsx", "run_week2.xlsx", "run_week3.xlsx"]:
    if not os.path.exists(batch_file):
        continue

    batch = Batch(batch_file, config=NITROGEN)
    batch.set_anchors(["USGS34", "USGS32"])
    batch.set_controls(["USGS35"])  # True delta = +2.70 ‰, u_true = 0.20 ‰
    batch.process(strategy=TwoPointLinear())

    # Record control standard measurements and En scores into persistent CSV
    qc_log.record_batch(batch)

# Inspect historical performance of USGS35
history = qc_log.get_control_history("USGS35", target_column="d15n")
print(history[["batch_id", "corrected_d15n", "bias", "en_score", "within_unc"]])

# Generate Matplotlib Shewhart Chart (+/- 2s warning and +/- 3s action limits)
ax = qc_log.plot_shewhart("USGS35", target_column="d15n")

# Export Standalone Interactive HTML Shewhart Dashboard
qc_log.save_shewhart_html(
    control_name="USGS35",
    output_path="USGS35_Shewhart_Dashboard.html",
    target_column="d15n",
    offline=True,
)
```

---

## Part 2: Public API Reference

### `Batch` (`isotools.core`)

The primary object representing an analytical sequence.

| Method / Property | Arguments | Description |
| :--- | :--- | :--- |
| `Batch(...)` | `filepath`, `config=NITROGEN`, `sheet_name=0`, `exclude_rows=None` | Initializes and cleans the dataset via `IsodatReader`. |
| `set_anchors(names)` | `List[str \| ReferenceMaterial]` | Registers standards used to fit the calibration curve. |
| `set_controls(names)` | `List[str \| ReferenceMaterial]` | Registers standards used for QC accuracy/trueness verification. |
| `set_drift_monitors(names)` | `List[str \| ReferenceMaterial]` | Registers standards used to monitor instrumental drift. |
| `exclude_rows(rows)` | `List[int]` | Excludes specific injection row numbers from all calculations. |
| `exclude_first_injections(n_skip)` | `int` | Automatically excludes the first $k$ injections of each contiguous vial run. |
| `apply_memory_correction(...)` | `coefficients=None`, `max_injections=3` | Applies Gröning carryover correction. Auto-estimates or uses manual coefficients. |
| `apply_blank_correction(...)` | `blank_identifier="bco cap"`, `area_column=None` | Subtracts blank mass-balance contribution from area and delta values. |
| `check_linearity(...)` | `substance_name=None`, `area_column=None` | Runs OLS regression of delta vs peak area/amplitude. |
| `apply_linearity_correction(...)` | `substance_name=None`, `slope=None` | Incurs peak-size linearity correction relative to $A_{\text{ref}}$. |
| `check_drift(...)` | `use_working=True` | Evaluates linear drift rate (‰ per row) for registered drift monitors. |
| `apply_drift_correction(monitor_name)` | `str` | Subtracts linear drift slope based on the specified drift monitor. |
| `calibrate_elemental_composition(...)` | `standards=None`, `area_column=None` | Calibrates elemental weight percent (`%C`, `%N`) using sample weight (`Amount`). |
| `join_metadata(...)` | `metadata`, `on="sample_name"` | Joins external DataFrame or CSV/Excel metadata to replicates and summary reports. |
| `process(strategy, ...)` | `strategy`, `use_method_precision=False` | Fits calibration strategy, normalizes all samples, and propagates uncertainty. |
| `report` | *Property* | Returns client results table rounded to 2 decimal places. |
| `get_report(round_decimals=None)` | `Optional[int]` | Returns client results table with configurable (or unrounded) precision. |
| `qaqc` | *Property* | Returns Control trueness summary with $E_n$ scores (rounded to 2 decimals). |
| `get_qaqc(round_decimals=None)` | `Optional[int]` | Returns Control trueness summary with configurable (or unrounded) precision. |
| `uncertainty_budget` | *Property* | Returns percentage breakdown of combined uncertainty variance sources. |
| `alerts` | *Property* | DataFrame listing all flagged outlier diagnostic notices and failure modes. |
| `save_report(filepath)` | `str` | Exports multi-sheet Excel file (`Results`, `QAQC`, `Uncertainty_Budget`, `Parameters`). |
| `save_html_report(filepath, ...)` | `str`, `offline=False` | Generates standalone interactive ISO 17025 HTML report. |

---

### Calibration Strategies (`isotools.strategies`)

All strategies inherit from `CalibrationStrategy` and implement `.fit()` and `.propagate()`.

| Class | Optimal Use Case | Uncertainty Propagation Details |
| :--- | :--- | :--- |
| `SinglePointOffset` | Single anchor available ($K = 1$). Assumes unit slope $m = 1$. | Propagates anchor replicate SEM and certificate uncertainty $u_{\text{true}}$ via Kragten perturbation. |
| `TwoPointLinear` | Standard IUPAC/IAEA 2-anchor bracketing ($K = 2$). | Propagates measured SEM and certificate uncertainties of both anchors via Kragten perturbation. |
| `MultiPointLinear` | 3 or more anchors ($K \ge 3$). Ordinary Least Squares regression. | Evaluates orthogonal excess lack-of-fit variance ($s_{\text{excess}}^2$) with inverse-regression leverage to avoid double-counting anchor uncertainties. |

---

### `QualityControlLog` (`isotools.qaqc_log`)

Manages longitudinal laboratory QA/QC tracking.

| Method | Arguments | Description |
| :--- | :--- | :--- |
| `QualityControlLog(csv_path)` | `str` | Initializes or loads the historical CSV control database. |
| `record_batch(batch)` | `Batch` | Appends all Control standard measurements from a processed batch. |
| `get_control_history(...)` | `control_name`, `target_column=None` | Returns historical DataFrame of measurements for a control standard. |
| `plot_shewhart(...)` | `control_name`, `target_column=None` | Plots a Matplotlib Shewhart chart with $\pm 2s$ warning and $\pm 3s$ action limits. |
| `save_shewhart_html(...)` | `control_name`, `output_path`, `offline=False` | Exports a standalone interactive Plotly HTML Shewhart dashboard. |

---

### Standards Registry (`isotools.standards`)

| Function / Model | Arguments | Description |
| :--- | :--- | :--- |
| `ReferenceMaterial(...)` | `name`, `d_true`, `u_true`, `aliases`, `target_column`, `mass_fraction`, `u_mass_fraction` | Dataclass representing certified standard properties. |
| `get_standard(...)` | `name`, `target_column=None` | Searches registry for a standard matching `name` or its aliases. |
| `register_standard(std)` | `ReferenceMaterial` | Registers a custom working reference material in the active registry. |

---

### Pre-defined Configurations (`isotools.config`)

| Configuration | Target Column | Element Symbol | Default Scale | Mapped Amplitude / Area Columns |
| :--- | :--- | :--- | :--- | :--- |
| `NITROGEN` | `d15n` | `N` | `AIR-N2` | `Ampl 28` / `Area 28` |
| `WATER_H` | `d2h` | `H` | `VSMOW-SLAP` | `Ampl 2` / `Area 2` |
| `WATER_O` | `d18o` | `O` | `VSMOW-SLAP` | `Ampl 28` / `Area 28` |
| `CARBON_13C` | `d13c` | `C` | `VPDB` | `Ampl 44` / `Area 44` |
