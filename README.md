[![Pylint](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml/badge.svg)](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml)

# isotools

**isotools** is a Python library designed for the automated processing, normalization, and uncertainty propagation of Continuous-Flow Stable Isotope Ratio Mass Spectrometry (CF-IRMS) data.

## Key Features

*   **Batch-Centric Workflow:** Manage an entire analytical sequence as a single `Batch` object.
*   **Canonical CF-IRMS Order of Operations:** Automatically enforces the metrologically sound sequence of pre-calibration corrections (**Exclusions → Blank Correction → Linearity Correction → Drift Correction → Scale Normalization**), regardless of the order in which methods are invoked.
*   **Rigorous Uncertainty Propagation:** Uses the **Kragten numerical differentiation method** to combine replicate repeatability (or instrumental method precision), reference material uncertainties, and calibration curve fit uncertainties.
*   **Automated QA/QC Diagnostics:** Built-in checks for missing sample peaks (autosampler drop failures), double drops / abnormal response factors, replicate variance, signal amplitude anomalies, environmental range bounds, and control standard trueness.
*   **Standards Registry:** Pre-loaded reference materials (Nitrogen $\delta^{15}\text{N}$, Water $\delta^2\text{H}$ & $\delta^{18}\text{O}$, Carbon $\delta^{13}\text{C}$) with case-insensitive alias matching and custom standard registration via `register_standard()`.
*   **ISO 17025 Audit Reporting:** Export multi-sheet Excel workbooks (`.save_report()`) and standalone interactive Plotly HTML audit reports for single-isotope (`.save_html_report()`) and dual-isotope (`generate_dual_isotope_html_report()`) runs.

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

# 4. Export Excel and interactive HTML reports
run.save_report("Water_18O_Report.xlsx")
run.save_html_report("Water_18O_Report.html")
```

## Documentation

For detailed information, see:

1.  **[Concepts and Workflow](docs/concepts_and_workflow.md):** Understanding the `Batch` lifecycle and the canonical CF-IRMS order of operations.
2.  **[Calibration and Uncertainty](docs/calibration_and_uncertainty.md):** Mathematical details of calibration strategies (`SinglePointOffset`, `TwoPointLinear`, `MultiPointLinear`) and the Kragten method.
3.  **[Managing Standards](docs/managing_standards.md):** How the standards registry, isotope disambiguation, and custom registration work.
4.  **[Worked Examples](examples/dual_isotope_water/):** Complete synthetic dual-isotope water ($\delta^2\text{H}$ and $\delta^{18}\text{O}$) generator and ISO 17025 report pipeline.

---
*Developed for stable isotope researchers who want to move from spreadsheets to reproducible code.*
