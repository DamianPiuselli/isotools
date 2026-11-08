# Calibration and Uncertainty

`isotools` prioritizes rigorous error propagation to ensure that reported isotope values are scientifically defensible and compliant with ISO/IEC 17025 and GUM (JCGM 100:2008) traceability principles.

## Calibration Strategies

The library supports three calibration models (subclassing `CalibrationStrategy` in `isotools.strategies`) to normalize pre-calibrated working delta values ($\delta_{\text{meas}}$) to international reference scales (e.g., VSMOW-SLAP, VPDB, AIR-N2).

All strategies model the instrument response as:

$$
\delta_{\text{meas}} = m \times \delta_{\text{true}} + b
$$

and invert the relationship to normalize sample measurements:

$$
\delta_{\text{corrected}} = \frac{\delta_{\text{meas}} - b}{m}
$$

### 1. Single-Point Offset (`SinglePointOffset`)
Used when a single anchor reference material is available (assumes unit scale factor $m = 1$ and corrects for an additive offset $b$):

$$
\delta_{\text{corrected}} = \delta_{\text{meas}} - (\bar{\delta}_{\text{anchor,meas}} - \delta_{\text{anchor,true}})
$$

### 2. Two-Point Linear Normalization (`TwoPointLinear`)
The standard two-anchor normalization technique recommended by IUPAC/IAEA. It uses two reference materials spanning the expected isotopic range of the samples to solve exactly for scale compression/expansion ($m$) and offset ($b$):

$$
m = \frac{\bar{\delta}_{\text{meas,2}} - \bar{\delta}_{\text{meas,1}}}{\delta_{\text{true,2}} - \delta_{\text{true,1}}}, \quad b = \bar{\delta}_{\text{meas,1}} - m \times \delta_{\text{true,1}}
$$

### 3. Multi-Point Linear OLS (`MultiPointLinear`)
For analytical sequences with $K \ge 3$ anchor standards, Ordinary Least Squares (OLS) regression is used to fit measured working values against certified anchor delta values across all registered anchors.

In addition to propagating the measurement and certified uncertainties of the anchors via Kragten perturbation, `MultiPointLinear` evaluates the **OLS calibration fit residual standard error** ($s_{y/x}$) with $K - 2$ degrees of freedom:

$$
s_{y/x} = \sqrt{\frac{\sum_{i=1}^{K} \left(\bar{\delta}_{\text{meas},i} - (m \times \delta_{\text{true},i} + b)\right)^2}{K - 2}}
$$

To prevent double-counting the known anchor measurement and certificate uncertainties already propagated through the Kragten perturbations, `MultiPointLinear` extracts the **orthogonal excess lack-of-fit variance** ($s_{\text{excess}}^2$, Birge / DerSimonian-Laird estimator):

$$
s_{\text{excess}}^2 = \max\left(0,\; s_{y/x}^2 - \frac{1}{K}\sum_{i=1}^{K}\left(u^2(\bar{\delta}_{\text{meas},i}) + m^2 \times u^2(\delta_{\text{true},i})\right)\right)
$$

This excess lack-of-fit variance is then scaled by the inverse-regression calibration leverage at the sample's normalized value $\hat{\delta}_{\text{sample}}$:

$$
u_{\text{fit}}^2(\hat{\delta}_{\text{sample}}) = \frac{s_{\text{excess}}^2}{m^2} \times \left(\frac{1}{K} + \frac{\left(\hat{\delta}_{\text{sample}} - \bar{\delta}_{\text{true}}\right)^2}{\sum_{i=1}^{K}\left(\delta_{\text{true},i} - \bar{\delta}_{\text{true}}\right)^2}\right)
$$

When the anchors are mutually consistent within their certified and measurement uncertainties, $s_{\text{excess}}^2 = 0$ and no artificial variance is added.

When genuine matrix mismatch or detector non-linearity exists beyond the anchor uncertainties, the fit variance $u_{\text{fit}}^2$ captures the excess scatter and scales with distance from the calibration centroid.

## Full-Pipeline Uncertainty Propagation (The Kragten Method)

Analytical partial-derivative formulas for error propagation become cumbersome and error-prone in multi-stage CF-IRMS pipelines. `isotools` uses the **Kragten Numerical Differentiation** method (`isotools.utils.kragten.propagate_kragten` and `propagate_kragten_budget`).

### How It Works
1.  **Identify Inputs:** For each sample, the model collects all uncertain input quantities ($x_i$):
    *   Sample replicate measurement uncertainty $u(\bar{\delta}_{\text{sample}})$ (empirical SEM or instrumental method precision).
    *   Anchor measured uncertainties $u(\bar{\delta})$ and certified uncertainties $u(\delta_{\text{true}})$.
    *   OLS calibration fit residual scatter $s_{y/x}$ (for `MultiPointLinear` when $K \ge 3$).
    *   **Pre-calibration correction uncertainties** (`u_blank`, `u_linearity`, `u_drift`) when those corrections are active.
2.  **Numerical Perturbation:** Each calibration input is perturbed one at a time by its standard uncertainty $u(x_i)$, and the calibration model is re-evaluated to compute individual sensitivity shifts:

$$
\Delta y_i = f(x_1, \dots, x_i + u(x_i), \dots) - f(x_1, \dots, x_k)
$$

Pre-calibration working-scale uncertainties (`u_blank`, `u_linearity`, `u_drift`) are scaled to the normalized scale by $1 / |m|$.
3.  **Quadrature Combination:** The resulting variance contributions are combined in quadrature to obtain the combined standard uncertainty $u_c$:

$$
u_c(y) = \sqrt{\sum_{i=1}^{k} (\Delta y_i)^2}
$$

### Pre-Calibration Uncertainty Components
When pre-calibration stages are active on a `Batch`, `Batch._compute_precalibration_uncertainties()` quantifies their standard uncertainties before scale normalization:
-   **Blank Correction (`u_blank`):** Propagates the standard error of the mean blank peak area $u(\bar{A})$ and mean blank delta $u(\bar{\delta})$ through the mass-balance equation via Kragten perturbation.
-   **Linearity Correction (`u_linearity`):** Propagates the OLS slope standard error $s_m$ scaled by the sample's area leverage relative to the reference area:

$$
u_{\text{lin}} = |\bar{A}_{\text{sample}} - A_{\text{ref}}| \times s_{m_{\text{lin}}}
$$

-   **Drift Correction (`u_drift`):** Propagates the drift regression slope standard error $s_m$ scaled by the sample's sequence position distance from the mean anchor position:

$$
u_{\text{drift}} = |\overline{\text{row}}_{\text{sample}} - \overline{\text{row}}_{\text{anchors}}| \times s_{m_{\text{drift}}}
$$

### Uncertainty Budget Decomposition (`batch.uncertainty_budget`)
`propagate_kragten_budget()` records the squared percentage variance contribution of each error category:

$$
\frac{(\Delta y_i)^2}{u_c^2} \times 100\%
$$

After calling `batch.process()`, inspect `batch.uncertainty_budget` (also exported to the `Uncertainty_Budget` Excel sheet and HTML report) to view the percentage breakdown across:
-   `pct_measurement`: Sample replicate scatter (`SEM` or $\sigma_{\text{method}} / \sqrt{n}$)
-   `pct_anchors`: Reference material certified and measured uncertainties
-   `pct_fit_residual`: Multi-point OLS calibration curve residual scatter ($s_{y/x}$)
-   `pct_blank`: Blank mass-balance correction uncertainty
-   `pct_linearity`: Peak-size linearity slope uncertainty
-   `pct_drift`: Temporal drift slope uncertainty

### Sample Measurement Uncertainty Basis
By default (`batch.process(strategy, use_method_precision=False)`):
-   Sample and anchor measurement uncertainties are taken as the empirical **Standard Error of the Mean (SEM)** of their replicates ($s / \sqrt{n}$).
-   If a sample has only a single replicate ($n = 1$), `isotools` automatically falls back to the configured instrumental repeatability (`config.method_precision`) and logs a diagnostic notice in `batch.alerts`.
-   If `use_method_precision=True` is passed to `batch.process()`, all sample and anchor measurement uncertainties use $\sigma_{\text{method}} / \sqrt{n}$.

## Elemental Composition Uncertainty (`calibrate_elemental_composition`)

For weighed solid samples analyzed by EA-IRMS, `batch.calibrate_elemental_composition()` calculates the instrumental response factor $k$ (mg of element per $\text{V s}$ of peak area) by fitting standard elemental mass against integrated peak area through the origin:

$$
k = \frac{\sum_{i=1}^{N_{\text{std}}} A_i \times M_i}{\sum_{i=1}^{N_{\text{std}}} A_i^2}
$$

where the certified elemental mass for standard $i$ is:

$$
M_i = \text{Amount}_i \times \frac{w_i}{100}
$$

The total relative uncertainty of the response factor $u_{\text{rel}}(k)$ combines replicate variation across standards and the certified uncertainty of the reference material's mass fraction (`ReferenceMaterial.u_mass_fraction`) in quadrature:

$$
u_{\text{rel}}(k) = \sqrt{u_{\text{rel,rep}}^2 + u_{\text{rel,cert}}^2}
$$

For each sample group, the combined standard uncertainty of the elemental weight percent $u(w_{\text{sample}})$ combines the empirical sample replicate SEM and calibration response factor uncertainty:

$$
u(w_{\text{sample}}) = \sqrt{\text{SEM}^2(w) + \left(w_{\text{sample}} \times u_{\text{rel}}(k)\right)^2}
$$

## Dual-Isotope Derived Uncertainties

When combining two isotopic dimensions in `generate_dual_isotope_html_report()`, secondary geochemical tracers are calculated with full first-order Taylor series error propagation:

### 1. Deuterium Excess ($d\text{-excess}$)
In meteoric water analysis ($\delta^{2}\text{H}$ and $\delta^{18}\text{O}$):

$$
d = \delta^{2}\text{H} - 8 \times \delta^{18}\text{O}
$$

Assuming covariance between independently normalized hydrogen and oxygen analytical batches is negligible ($\text{cov} \approx 0$):

$$
u(d) = \sqrt{u^2(\delta^{2}\text{H}) + 64 \times u^2(\delta^{18}\text{O})}
$$

### 2. Atomic $\text{C/N}$ Ratio ($\text{C/N}_{\text{atomic}}$)
In organic matter and particulate ecology ($\text{\%C}$ and $\text{\%N}$):

$$
\text{C/N}_{\text{mass}} = \frac{w_{\text{C}}}{w_{\text{N}}}, \quad \text{C/N}_{\text{atomic}} = \frac{w_{\text{C}}}{w_{\text{N}}} \times \frac{14.0067}{12.011}
$$

Propagating the elemental uncertainties:

$$
u(\text{C/N}_{\text{atomic}}) = \text{C/N}_{\text{atomic}} \times \sqrt{\left(\frac{u(w_{\text{C}})}{w_{\text{C}}}\right)^2 + \left(\frac{u(w_{\text{N}})}{w_{\text{N}}}\right)^2}
$$
