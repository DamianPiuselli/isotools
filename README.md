[![Pylint](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml/badge.svg)](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml)

# isotools

**isotools** is a Python library designed for the automated processing, normalization, and uncertainty propagation of Stable Isotope Ratio Mass Spectrometry (IRMS) data.

It moves away from procedural scripts to a **Batch-Centric** workflow, where data, configuration, and calibration logic are encapsulated in a single, robust object.

## Key Features

* **Batch-Centric Workflow:** Manage an entire analytical run as a single object (`Batch`) that handles data state from raw import to final reporting.
* **Rigorous Uncertainty:** Implements **Kragten numerical differentiation** to propagate uncertainty from standards to samples, combining both systematic calibration error and random measurement noise.
* **Outlier Detection:** Automatic flagging of suspicious data based on environmental ranges, analytical precision, and signal amplitude.
* **Drift Correction:** Built-in tools to monitor and correct for linear analytical drift using specialized monitor standards.
* **Flexible Standards:** Database of Reference Materials (USGS, IAEA, and internal lab standards) with support for **aliasing** (e.g., automatically recognizes "USGS-32", "st_usgs32").
* **Configurable Systems:** Easily extensible to different gas systems ($N_2$, $CO_2$, $SO_2$, $H_2O$) via `SystemConfig` objects.
* **Modular Strategies:** Switch calibration math (e.g., 2-Point Linear, Multi-Point OLS) without rewriting your workflow.

## Installation

The easiest way to install **isotools** (especially in Google Colab or similar environments) is directly from GitHub:

```bash
pip install git+https://github.com/DamianPiuselli/isotools.git
```

For local development:

```bash
git clone https://github.com/DamianPiuselli/isotools.git
cd isotools
pip install -e .
```

For development dependencies (testing and linting):
```bash
pip install -r requirements-dev.txt
```

## Tutorial: Water $\delta^{18}O$ Processing

This example demonstrates how to process a run of water samples for $\delta^{18}$O using a two-point linear normalization.

```python
import pandas as pd
from isotools.core import Batch
from isotools.config import Water_O
from isotools.strategies.normalization import TwoPointLinear

# 1. Initialize the Batch
# Point to your Isodat Excel export
run = Batch("DATA/water_run_2024.xls", config=Water_O)

# 2. Register Standards
# 'Anchors' are used to build the calibration curve
run.set_anchors(["Mar", "Antartida"])

# 'Controls' are used for QAQC (checking trueness)
run.set_controls(["Buenos Aires"])

# 'Drift Monitors' are used to check for analytical stability
run.set_drift_monitors(["Mar"])

# 3. Handle Outliers and Drift (Optional)
# Check for drift using the 'Mar' standard replicates
drift_stats = run.check_drift()
print(drift_stats)

# If drift is significant (p < 0.05), apply correction
run.apply_drift_correction("Mar")

# Manually exclude problematic rows (e.g., injection error at row 15)
run.exclude_rows([15])

# 4. Process the Run
# This fits the calibration curve and propagates uncertainty
run.process(strategy=TwoPointLinear())

# 5. Inspect Results
print("--- FINAL REPORT ---")
print(run.report.head())

print("\n--- QAQC TRUENESS ---")
print(run.qaqc)

# 6. Export to Excel
run.save_report("Water_18O_Final_Report.xlsx")
```

## Advanced Workflow Components

### Outlier Diagnostics
When a `Batch` is initialized or processed, it automatically runs diagnostics. Flags are stored in the `.alerts` property:
- **Range Check:** Values outside environmental bounds (e.g., $<-60$ or $>20$ for $\delta^{18}O$).
- **Precision Check:** Sample standard deviation > 3x method precision.
- **Amplitude Check:** Signal intensity far from the run median.

### Uncertainty Propagation
`isotools` uses the **Kragten Method**. This approach calculates the partial derivatives of the calibration equation numerically, allowing it to combine:
1.  **Standard Uncertainty:** The known error of the reference material.
2.  **Measurement Error (SEM):** The repeatability of your replicates.
3.  **Calibration Error:** The uncertainty in the slope and intercept of the fit.

### Data Cleaning
The `.exclude_rows([ids])` method allows you to remove specific injections. **Note:** If you exclude rows after calling `.process()`, you must re-run `.process()` to update the calibration and summary statistics.

---
*For more detailed information on specific gas configurations, see `isotools/config.py`.*
