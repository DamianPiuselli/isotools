# Managing Standards

One of the most tedious parts of IRMS data processing is matching machine-specific sample names (e.g., `st-USGS40-A`) to their certified values. `isotools` automates this through a standard registry and aliasing system.

## The Standard Registry

`isotools` comes pre-loaded with common international standards from the USGS and IAEA. Each standard is defined with:
-   **Name:** The canonical name (e.g., `USGS40`).
-   **Value:** Its certified isotopic value.
-   **Uncertainty:** Its certified 1-sigma uncertainty.
-   **Aliases:** Common variations of the name used in different labs.

## Aliasing and Matching

When you call `batch.set_anchors(["USGS40", "USGS41"])`, the library uses a fuzzy matching system. If your Excel file has a sample named `st_usgs_40`, the library will:
1.  Check the alias list for `USGS40`.
2.  Clean the name (lower-case, remove special characters).
3.  Automatically link the raw machine data to the correct certified value.

## Roles of Standards

In `isotools`, a standard can play three distinct roles in a batch:

1.  **Anchors (`set_anchors`):** These define the calibration curve. They must cover the range of your samples.
2.  **Controls (`set_controls`):** These are treated as unknowns during processing. After calibration, the library compares their measured value against their certified value to check for **trueness**.
3.  **Drift Monitors (`set_drift_monitors`):** These are replicates of the same material spaced throughout the run. The library uses them to check if the instrument response changed over time.

## Adding Custom Standards

You can easily add your own internal lab standards to the registry:

```python
from isotools.standards import register_standard
from isotools.models import ReferenceMaterial

my_std = ReferenceMaterial(
    name="Lab-Water-1",
    true_value=-10.5,
    uncertainty=0.1,
    aliases=["lab1", "water1"]
)

register_standard(my_std)
```
