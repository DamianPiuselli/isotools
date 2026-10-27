[![Pylint](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml/badge.svg)](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml)

# isotools

**isotools** is a Python library designed for the automated processing, normalization, and uncertainty propagation of Continuous-Flow Stable Isotope Ratio Mass Spectrometry (CF-IRMS) data.

## Key Features

*   **Batch-Centric Workflow:** Manage an entire analytical sequence as a single `Batch` object.
*   **Canonical CF-IRMS Order of Operations:** Automatically enforces the metrologically sound sequence of pre-calibration corrections (**Exclusions → Memory Correction → Blank Correction → Linearity Correction → Drift Correction → Scale Normalization**), regardless of the order in which methods are invoked.
*   **Full-Pipeline Kragten Uncertainty & Budget Breakdown:** Propagates replicate repeatability (or instrumental method precision), reference material uncertainties, multi-point OLS fit residuals ($s_{y/x}$), and pre-calibration uncertainties (`u_blank`, `u_linearity`, `u_drift`) with a complete variance percentage breakdown (`batch.uncertainty_budget`).
*   **Water Carryover & Elemental Composition ($\text{\%C}$, $\text{\%N}$, $\text{C/N}_{\text{atomic}}$):** Built-in Gröning (2011) sample-to-sample memory correction (`apply_memory_correction`), first-$k$ injection filtering (`exclude_first_injections`), and elemental mass fraction calibration (`calibrate_elemental_composition`).
*   **Rigorous QA/QC & Long-Term Shewhart Control Charts:** Automated checks for missing sample peaks, double drops, small-$N$ median-based flyer pinpointing, scale extrapolation alerts, ISO 17025 $E_n$ trueness scores, and longitudinal laboratory QC tracking (`QualityControlLog`).
*   **Comprehensive Standards Registry:** Pre-loaded IAEA, USGS, and NIST reference materials (VSMOW2, SLAP2, GISP, USGS32/34/35/40/41a/45–48/61–63, IAEA-N-1/N-2/NO-3/600/603/CH-6, NBS18/19, NIST8541, SRM1649a, Benzoic Acid, Acetanilide) with case-insensitive alias matching and custom registration via `register_standard()`.
*   **ISO 17025 Audit Reporting:** Export multi-sheet Excel workbooks (`.save_report()`) and standalone interactive Plotly HTML audit reports for single-isotope (`.save_html_report()`), dual-isotope (`generate_dual_isotope_html_report()`), and Shewhart control chart (`save_shewhart_html()`) workflows.

## Installation

```bash
pip install git+https://github.com/DamianPiuselli/isotools.git
```

For local development (using `uv` or `pip`):

```bash
uv sync --dev
# or: pip install -e ".[dev]"
```

## Quickstart

```python
from isotools import Batch, WATER_O, MultiPointLinear

# 1. Load data and register standards
run = Batch("water_run.xlsx", config=WATER_O, sheet_name="18O.wke")
run.set_anchors(["Mar_O", "Buenos Aires_O", "Mendoza_O", "Antartida_O"])
run.set_drift_monitors(["Buenos Aires_O"])

# 2. Inspect alerts, exclude bad rows, and apply pre-calibration corrections
run.exclude_rows([16])
run.apply_drift_correction("Buenos Aires_O")

# 3. Calibrate to international scale and propagate uncertainty
run.process(strategy=MultiPointLinear())

# 4. Inspect uncertainty budget and export Excel / interactive HTML reports
print(run.uncertainty_budget)
run.save_report("Water_18O_Report.xlsx")
run.save_html_report("Water_18O_Report.html")
```

## Documentation

For detailed information, see:

1.  **[Concepts and Workflow](docs/concepts_and_workflow.md):** Understanding the `Batch` lifecycle, the canonical CF-IRMS order of operations, small-$N$ outlier philosophy, and `QualityControlLog` Shewhart charts.
2.  **[Calibration and Uncertainty](docs/calibration_and_uncertainty.md):** Mathematical details of calibration strategies (`SinglePointOffset`, `TwoPointLinear`, `MultiPointLinear`), full-pipeline Kragten propagation, and `batch.uncertainty_budget`.
3.  **[Managing Standards](docs/managing_standards.md):** Built-in IAEA/USGS/NIST standards registry, elemental mass fractions, isotope disambiguation, and custom registration.
4.  **[Worked Examples](examples/dual_isotope_water/):** Complete synthetic dual-isotope water ($\delta^2\text{H}$ and $\delta^{18}\text{O}$) generator and ISO 17025 report pipeline.

---
*Developed for stable isotope researchers who want to move from spreadsheets to reproducible code.*
