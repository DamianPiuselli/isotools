[![Pylint](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml/badge.svg)](https://github.com/DamianPiuselli/IRMS/actions/workflows/pylint.yml)

# isotools

**isotools** is a Python library designed for the automated processing, normalization, and uncertainty propagation of Stable Isotope Ratio Mass Spectrometry (IRMS) data.

## Key Features

*   **Batch-Centric Workflow:** Manage an entire analytical run as a single `Batch` object.
*   **Rigorous Uncertainty:** Uses the **Kragten method** for numerical error propagation.
*   **Automated QA/QC:** Built-in outlier detection, drift correction, and trueness checks.
*   **Standards Registry:** Automatic matching of sample names to certified values (USGS/IAEA).

## Installation

```bash
pip install git+https://github.com/DamianPiuselli/isotools.git
```

## Quickstart

```python
from isotools.core import Batch
from isotools.config import Water_O
from isotools.strategies.normalization import TwoPointLinear

# 1. Load data and register standards
run = Batch("DATA/water_run.xls", config=Water_O)
run.set_anchors(["VSMOW2", "SLAP2"])
run.set_drift_monitors(["VSMOW2"])

# 2. Correct drift and process
run.apply_drift_correction("VSMOW2")
run.process(strategy=TwoPointLinear())

# 3. Export results
run.save_report("Report.xlsx")
```

## Documentation

For detailed information, see:

1.  **[Concepts and Workflow](docs/concepts_and_workflow.md):** Understanding the `Batch` lifecycle.
2.  **[Calibration and Uncertainty](docs/calibration_and_uncertainty.md):** Mathematical details and the Kragten method.
3.  **[Managing Standards](docs/managing_standards.md):** How the registry and aliasing work.
4.  **[Interactive Examples](examples/):** Jupyter notebooks with real-world data processing.

---
*Developed for stable isotope researchers who want to move from spreadsheets to reproducible code.*
