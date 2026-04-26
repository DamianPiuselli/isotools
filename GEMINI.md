# isotools: IRMS Data Processing Library

`isotools` is a Python library designed for the automated processing, normalization, and uncertainty propagation of Stable Isotope Ratio Mass Spectrometry (IRMS) data. It replaces procedural scripts with a robust, object-oriented **Batch-Centric** workflow.

## Project Overview

- **Core Objective:** Simplify and standardize the processing of IRMS analytical runs, ensuring rigorous uncertainty propagation and consistent calibration.
- **Key Concepts:**
    - **`Batch`**: The central controller managing a single analytical run's data, configuration, and state.
    - **`SystemConfig`**: Encapsulates gas-specific logic (e.g., Nitrogen, Carbon) including column mappings and filtering rules.
    - **`ReferenceMaterial`**: Models for standards (e.g., USGS32) with support for aliases.
    - **`CalibrationStrategy`**: Modular normalization math (e.g., `TwoPointLinear`) and uncertainty propagation.
- **Uncertainty:** Uses **Kragten numerical differentiation** to propagate systematic calibration error and random measurement noise.

## Technical Stack

- **Language:** Python 3.10+
- **Data:** `pandas`, `numpy`, `openpyxl`
- **Visualization:** `matplotlib`, `seaborn`
- **Testing:** `pytest`
- **Linting:** `pylint`

## Building and Running

### Development Setup
```bash
# Clone the repository and install dev dependencies
pip install -r requirements-dev.txt
```

### Running Tests
```bash
pytest
```

### Linting
```bash
pylint isotools
```

## Development Conventions

### 1. Batch-Centric Workflow
Always interact with data through the `Batch` object. Avoid manual pandas manipulation of raw dataframes outside the `Batch` lifecycle.
1. **Initialize:** `run = Batch("data.xls", config=Nitrogen)`
2. **Clean:** `run.exclude_rows([1, 5, 10])`
3. **Configure:** `run.set_anchors([...])`, `run.set_controls([...])`
4. **Process:** `run.process(strategy=TwoPointLinear())` (Triggers automatic outlier detection)
5. **Inspect Alerts:** `print(run.alerts)` (If warnings were emitted during process)
6. **Output:** `run.report`, `run.qaqc`

### 2. Uncertainty Propagation
The `CalibrationStrategy.propagate()` method must implement Kragten propagation (via `isotools.utils.kragten`) to ensure all sources of error (standard uncertainty, measurement SEM, calibration fit) are combined correctly.

### 3. Data Integrity
- **Immutability:** Use `.copy()` when performing transformations in strategies or readers to avoid side effects on the `Batch` state.
- **Aliases:** Leverage the `ReferenceMaterial.matches()` method for case-insensitive, alias-aware standard identification.
- **System Specifics:** New gas systems should be added as `SystemConfig` instances in `isotools/config.py`.

## Directory Structure

- `isotools/`: Main package.
    - `core.py`: `Batch` class and main workflow.
    - `models.py`: `ReferenceMaterial` and base data models.
    - `config.py`: `SystemConfig` definitions for different isotope systems.
    - `standards.py`: Registry of known reference materials.
    - `strategies/`: Normalization logic (Abstract base + implementations).
    - `utils/`: `IsodatReader` for I/O and `kragten` for math.
- `tests/`: Comprehensive test suite reflecting the core workflow.
- `DATA/`: Example raw data files (e.g., Isodat Excel exports).
