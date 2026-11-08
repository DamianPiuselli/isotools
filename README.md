[![Tests](https://github.com/DamianPiuselli/isotools/actions/workflows/main.yml/badge.svg)](https://github.com/DamianPiuselli/isotools/actions/workflows/main.yml)
[![Pylint](https://github.com/DamianPiuselli/isotools/actions/workflows/pylint.yml/badge.svg)](https://github.com/DamianPiuselli/isotools/actions/workflows/pylint.yml)

# isotools

**isotools** is a Python library designed for the automated processing, normalization, and uncertainty propagation of Continuous-Flow Stable Isotope Ratio Mass Spectrometry (CF-IRMS) data.

## Key Features

- **Batch-Centric Architecture**  
  Encapsulates raw data, sequence corrections, and diagnostic audits in a single reproducible `Batch` object.

- **Canonical CF-IRMS Correction Pipeline**  
  Enforces the physical order of operations deterministically regardless of execution order:  
  `Exclusions` $\rightarrow$ `Memory` $\rightarrow$ `Blank` $\rightarrow$ `Linearity` $\rightarrow$ `Linear Drift` $\rightarrow$ `Scale Normalization`.

- **Rigorous Kragten Uncertainty Propagation**  
  Propagates sample repeatability, certified anchor uncertainties, multi-point calibration lack-of-fit leverage ($s_{\text{excess}}$), and pre-calibration variance into a full percentage budget (`batch.uncertainty_budget`).

- **Automated QA/QC & Trueness Diagnostics**  
  Automated detection for missing sample peaks, autosampler double drops, peak-area anomalies, and small-$N$ replicate flyer pinpointing, alongside ISO 17025 $E_n$ scores and longitudinal Shewhart control charts (`QualityControlLog`).

- **Water Isotope & Elemental Models**  
  Gröning memory carryover correction and first-$k$ injection filtering for water ($\delta^2\text{H}$, $\delta^{18}\text{O}$), plus elemental %C, %N, and atomic C/N calibration for solid EA-IRMS.

- **Standards Registry & Metadata Integration**  
  Pre-loaded IAEA, USGS, and NIST standards database with case-insensitive alias matching and seamless external field metadata joining (`batch.join_metadata()`).

- **ISO 17025 Audit Reporting**  
  Generates multi-sheet Excel workbooks (`.save_report()`) and standalone interactive Plotly HTML dashboards for single- and dual-isotope workflows with offline air-gapped support (`offline=True`).

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

1.  **[Concepts and Workflow](docs/concepts_and_workflow.md):** Understanding the `Batch` lifecycle, the canonical CF-IRMS order of operations, small-$N$ outlier philosophy, metadata integration, and `QualityControlLog` Shewhart charts.
2.  **[Calibration and Uncertainty](docs/calibration_and_uncertainty.md):** Mathematical details of calibration strategies (`SinglePointOffset`, `TwoPointLinear`, `MultiPointLinear`), lack-of-fit leverage formulation, full-pipeline Kragten propagation, and `batch.uncertainty_budget`.
3.  **[Managing Standards](docs/managing_standards.md):** Built-in IAEA/USGS/NIST standards registry, elemental mass fractions, isotope disambiguation, and custom registration.
4.  **[Workflow Recipes & API Reference](docs/recipes_and_api_reference.md):** Copy-pasteable workflow recipes (Dual-Isotope Water, Weighed Solid C/N with elemental `%C`/`%N`, Long-Term QA/QC) and comprehensive public API reference.
5.  **[AI Agent Data-Processing Skill](.agents/skills/isotools-data-processing/SKILL.md):** Procedural runbook for AI agents assisting laboratory analysts with data ingestion, outlier triage, calibration, and report generation.
6.  **[Worked Examples](examples/dual_isotope_water/):** Complete synthetic dual-isotope water ($\delta^{2}\text{H}$ and $\delta^{18}\text{O}$) generator and ISO 17025 report pipeline.

---
*Developed for stable isotope researchers who want to move from spreadsheets to reproducible code.*
