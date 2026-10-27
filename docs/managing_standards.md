# Managing Standards

One of the most tedious parts of IRMS data processing is matching raw sample identifiers from the mass spectrometer sequence (e.g., `KN032`, `BSAS`, `8541`, `ac benzoico`) to their certified reference values. `isotools` automates this through a built-in standards registry and case-insensitive alias system.

## Built-in Standards Registry

`isotools` comes pre-loaded with international IAEA, USGS, and NIST reference materials as well as regional working standards in `isotools.standards`:

### 1. Nitrogen ($\delta^{15}\text{N}$ vs. AIR-N2, `target_column="d15n"`)
-   **Nitrates & Ammonium Salts (with $\text{\%N}$ `mass_fraction`):**
    -   `USGS32` ($+180.0\,\text{‰}$, $13.85\,\text{\%N}$)
    -   `USGS34` ($-1.8\,\text{‰}$, $13.85\,\text{\%N}$)
    -   `USGS35` ($+2.7\,\text{‰}$, $16.47\,\text{\%N}$)
    -   `IAEA_N1` (`IAEA-N-1`, $+0.4\,\text{‰}$, $21.20\,\text{\%N}$)
    -   `IAEA_N2` (`IAEA-N-2`, $+20.3\,\text{‰}$, $21.20\,\text{\%N}$)
    -   `IAEA_NO3` (`IAEA-NO-3`, $+4.7\,\text{‰}$, $13.85\,\text{\%N}$)
-   **Organic & Amino Acid Standards (with $\text{\%N}$ `mass_fraction`):**
    -   `IAEA600_N` (`IAEA-600_N`, Caffeine, $+1.0\,\text{‰}$, $28.85\,\text{\%N}$)
    -   `USGS40_N` (L-glutamic acid, $-4.52\,\text{‰}$, $9.52\,\text{\%N}$)
    -   `USGS41A_N` (`USGS41a_N`, L-glutamic acid enriched, $+47.55\,\text{‰}$, $9.52\,\text{\%N}$)
    -   `USGS61_N` ($-2.87\,\text{‰}$), `USGS62_N` ($+20.17\,\text{‰}$), `USGS63_N` ($+37.83\,\text{‰}$) (Caffeines, $28.85\,\text{\%N}$)
    -   `ACETANILIDE_N` (`Acetanilide_N`, $+1.18\,\text{‰}$, $10.36\,\text{\%N}$)

### 2. Water Hydrogen ($\delta^{2}\text{H}$ vs. VSMOW-SLAP, `target_column="d2h"`)
-   **Primary & International Reference Waters:** `VSMOW2_H` ($0.0\,\text{‰}$), `SLAP2_H` ($-427.5\,\text{‰}$), `GISP_H` ($-189.5\,\text{‰}$), `USGS45_H` ($-10.3\,\text{‰}$), `USGS46_H` ($-235.8\,\text{‰}$), `USGS47_H` ($-150.2\,\text{‰}$), `USGS48_H` ($-2.0\,\text{‰}$)
-   **Laboratory Working Standards:** `MAR_H` (`Mar_H`, $-0.49\,\text{‰}$), `BUENOS_AIRES_H` (`Buenos Aires_H`, $-36.92\,\text{‰}$), `MENDOZA_H` (`Mendoza_H`, $-72.07\,\text{‰}$), `ANTARTIDA_H` (`Antartida_H`, $-94.89\,\text{‰}$)

### 3. Water Oxygen ($\delta^{18}\text{O}$ vs. VSMOW-SLAP, `target_column="d18o"`)
-   **Primary & International Reference Waters:** `VSMOW2_O` ($0.0\,\text{‰}$), `SLAP2_O` ($-55.5\,\text{‰}$), `GISP_O` ($-24.76\,\text{‰}$), `USGS45_O` ($-2.238\,\text{‰}$), `USGS46_O` ($-29.80\,\text{‰}$), `USGS47_O` ($-19.80\,\text{‰}$), `USGS48_O` ($-2.224\,\text{‰}$)
-   **Laboratory Working Standards:** `MAR_O` (`Mar_O`, $-0.027\,\text{‰}$), `BUENOS_AIRES_O` (`Buenos Aires_O`, $-5.442\,\text{‰}$), `MENDOZA_O` (`Mendoza_O`, $-11.362\,\text{‰}$), `ANTARTIDA_O` (`Antartida_O`, $-12.78\,\text{‰}$)

### 4. Carbon ($\delta^{13}\text{C}$ vs. VPDB, `target_column="d13c"`)
-   **Carbonates, Graphites & Sugars (with $\text{\%C}$ `mass_fraction`):**
    -   `NBS19_C` (`NBS19`, $+1.95\,\text{‰}$, $12.00\,\text{\%C}$)
    -   `NBS18_C` (`NBS18`, $-5.014\,\text{‰}$, $12.00\,\text{\%C}$)
    -   `IAEA603_C` (`IAEA-603`, $+2.46\,\text{‰}$, $12.00\,\text{\%C}$)
    -   `IAEA_CH6` (`IAEA-CH-6`, Sucrose, $-10.449\,\text{‰}$, $42.10\,\text{\%C}$)
    -   `NIST8541` (USGS24 Graphite, $-16.05\,\text{‰}$, $100.0\,\text{\%C}$)
    -   `SRM1649A` (`1649a`, Urban Dust, $-25.60\,\text{‰}$, $17.68\,\text{\%C}$)
-   **Organic & Amino Acid Standards (with $\text{\%C}$ `mass_fraction`):**
    -   `IAEA600_C` (`IAEA-600_C`, Caffeine, $-27.771\,\text{‰}$, $49.48\,\text{\%C}$)
    -   `USGS40_C` (L-glutamic acid, $-26.39\,\text{‰}$, $40.82\,\text{\%C}$)
    -   `USGS41A_C` (`USGS41a_C`, L-glutamic acid enriched, $+36.55\,\text{‰}$, $40.82\,\text{\%C}$)
    -   `USGS61_C` ($-35.05\,\text{‰}$), `USGS62_C` ($-14.79\,\text{‰}$), `USGS63_C` ($-1.17\,\text{‰}$) (Caffeines, $49.48\,\text{\%C}$)
    -   `BENZOIC_ACID_C` (`Benzoic Acid` / `ac benzoico`, $-28.80\,\text{‰}$, $68.85\,\text{\%C}$)
    -   `ACETANILIDE_C` (`Acetanilide_C`, $-29.53\,\text{‰}$, $71.09\,\text{\%C}$)

## The `ReferenceMaterial` Model

Each `ReferenceMaterial` is defined with:
-   `name`: The canonical identifier (e.g., `"USGS40_C"`).
-   `d_true`: Certified delta value ($\text{‰}$).
-   `u_true`: Certified 1-$\sigma$ standard uncertainty ($\text{‰}$).
-   `aliases`: List of alternative names recognized in raw sequence files.
-   `target_column`: Associated isotope target column (`"d15n"`, `"d2h"`, `"d18o"`, `"d13c"`), allowing `get_standard()` to disambiguate dual-isotope standards that share aliases (such as `"USGS40"`, `"IAEA-600"`, `"VSMOW2"`, or `"Mar"`).
-   `mass_fraction`: Optional elemental weight percentage (e.g., $40.82$ for $40.82\,\text{\%C}$ in USGS40) used by `batch.calibrate_elemental_composition()`.
-   `u_mass_fraction`: Optional 1-$\sigma$ uncertainty on `mass_fraction`.

## Aliasing and Matching

When you register standards on a `Batch` (e.g., `batch.set_anchors(["USGS40", "USGS41a"])`), `isotools` resolves each name against the registry for the batch's `config.target_column`. During processing, `ReferenceMaterial.matches()` performs a case-insensitive, whitespace-trimmed lookup against the standard's canonical `name` and all of its `aliases`, grouping all matching rows under the canonical name.

## Roles of Standards in a Batch

A reference material can play three distinct roles in a `Batch`:

1.  **Anchors (`batch.set_anchors`):** Used to fit the calibration curve (`SinglePointOffset`, `TwoPointLinear`, or `MultiPointLinear`).
2.  **Controls (`batch.set_controls`):** Treated as unknowns during calibration. Afterward, `batch.qaqc` compares their calibrated mean against `d_true` to evaluate analytical **bias (trueness)**, calculate the normalized error score $E_n$, and verify whether $E_n \le 1.0$ (`Within_Unc`).
3.  **Drift Monitors (`batch.set_drift_monitors`):** Replicates of a homogeneous standard spaced throughout the sequence used by `batch.check_drift()` and `batch.apply_drift_correction()` to quantify and remove temporal instrument drift.

## Adding Custom Standards

You can register your own internal laboratory standards using `ReferenceMaterial` and `register_standard()`:

```python
from isotools import ReferenceMaterial, register_standard

my_std = ReferenceMaterial(
    name="Lab-Soil-1",
    d_true=-25.40,
    u_true=0.08,
    aliases=["soil1", "inhouse_soil"],
    target_column="d13c",
    mass_fraction=3.45,
    u_mass_fraction=0.05,
)

register_standard(my_std)
```

Once registered, `"Lab-Soil-1"` (and its aliases `"soil1"`, `"inhouse_soil"`) can be passed directly to `batch.set_anchors()`, `batch.set_controls()`, or `batch.set_drift_monitors()`.
