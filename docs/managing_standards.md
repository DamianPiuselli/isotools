# Managing Standards

One of the most tedious parts of IRMS data processing is matching raw sample identifiers from the mass spectrometer sequence (e.g., `KN032`, `BSAS`, `8541`) to their certified reference values. `isotools` automates this through a built-in standards registry and case-insensitive alias system.

## Built-in Standards Registry

`isotools` comes pre-loaded with reference materials in `isotools.standards`:

-   **Nitrogen ($\delta^{15}\text{N}$, `target_column="d15n"`):** `USGS32`, `USGS34`, `USGS35`
-   **Water Hydrogen ($\delta^2\text{H}$, `target_column="d2h"`):** `MAR_H` (`Mar_H`), `BUENOS_AIRES_H` (`Buenos Aires_H`), `MENDOZA_H` (`Mendoza_H`), `ANTARTIDA_H` (`Antartida_H`)
-   **Water Oxygen ($\delta^{18}\text{O}$, `target_column="d18o"`):** `MAR_O` (`Mar_O`), `BUENOS_AIRES_O` (`Buenos Aires_O`), `MENDOZA_O` (`Mendoza_O`), `ANTARTIDA_O` (`Antartida_O`)
-   **Carbon ($\delta^{13}\text{C}$, `target_column="d13c"`):** `NIST8541`, `SRM1649A` (`1649a`)

Each `ReferenceMaterial` is defined with:
-   `name`: The canonical identifier (e.g., `"USGS32"`).
-   `d_true`: Certified delta value ($\text{‰}$).
-   `u_true`: Certified 1-$\sigma$ standard uncertainty ($\text{‰}$).
-   `aliases`: List of alternative names recognized in raw sequence files.
-   `target_column`: Associated isotope target column (e.g., `"d15n"`, `"d2h"`, `"d18o"`, `"d13c"`), allowing `get_standard()` to disambiguate standards that share an alias across different isotopes (such as `"Mar"` or `"Buenos Aires"` for $\delta^2\text{H}$ vs $\delta^{18}\text{O}$).

## Aliasing and Matching

When you register standards on a `Batch` (e.g., `batch.set_anchors(["USGS32", "USGS34"])`), `isotools` resolves each name against the registry for the batch's `config.target_column`. During processing, `ReferenceMaterial.matches()` performs a case-insensitive, whitespace-trimmed lookup against the standard's canonical `name` and all of its `aliases`, grouping all matching rows under the canonical name.

## Roles of Standards in a Batch

A reference material can play three distinct roles in a `Batch`:

1.  **Anchors (`batch.set_anchors`):** Used to fit the calibration curve (`SinglePointOffset`, `TwoPointLinear`, or `MultiPointLinear`).
2.  **Controls (`batch.set_controls`):** Treated as unknowns during calibration. Afterward, `batch.qaqc` compares their calibrated mean against `d_true` to evaluate analytical **bias (trueness)** and check whether $|\text{Bias}| < 2 \times u_c$.
3.  **Drift Monitors (`batch.set_drift_monitors`):** Replicates of a homogeneous standard spaced throughout the sequence used by `batch.check_drift()` and `batch.apply_drift_correction()` to quantify and remove temporal instrument drift.

## Adding Custom Standards

You can register your own internal laboratory standards using `ReferenceMaterial` and `register_standard()`:

```python
from isotools import ReferenceMaterial, register_standard

my_std = ReferenceMaterial(
    name="Lab-Water-1",
    d_true=-10.5,
    u_true=0.1,
    aliases=["lab1", "water1"],
    target_column="d18o",
)

register_standard(my_std)
```

Once registered, `"Lab-Water-1"` (and its aliases `"lab1"`, `"water1"`) can be passed directly to `batch.set_anchors()`, `batch.set_controls()`, or `batch.set_drift_monitors()`.
