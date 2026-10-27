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
Used when a single anchor reference material is available (assumes unit scale factor $m = 1$ and corrects for additive offset $b = \bar{\delta}_{\text{anchor,meas}} - \delta_{\text{anchor,true}}$):

$$
\delta_{\text{corrected}} = \delta_{\text{meas}} - (\bar{\delta}_{\text{anchor,meas}} - \delta_{\text{anchor,true}})
$$

### 2. Two-Point Linear Normalization (`TwoPointLinear`)
The standard two-anchor normalization technique recommended by IUPAC/IAEA. It uses two reference materials spanning the expected isotopic range of the samples to solve exactly for scale compression/expansion ($m$) and offset ($b$):

$$
m = \frac{\bar{\delta}_{\text{meas,2}} - \bar{\delta}_{\text{meas,1}}}{\delta_{\text{true,2}} - \delta_{\text{true,1}}}, \quad b = \bar{\delta}_{\text{meas,1}} - m \times \delta_{\text{true,1}}
$$

### 3. Multi-Point Linear OLS (`MultiPointLinear`)
For analytical sequences with $K \ge 3$ anchor standards, Ordinary Least Squares (OLS) regression is used to fit $\delta_{\text{meas}}$ against $\delta_{\text{true}}$ across all registered anchors.

In addition to the measurement and certified uncertainties of the anchors, `MultiPointLinear` incorporates the **OLS calibration fit residual standard error** ($s_{y/x}$) with $K - 2$ degrees of freedom:

$$
s_{y/x} = \sqrt{\frac{\sum_{i=1}^{K} \left(\bar{\delta}_{\text{meas},i} - (m \times \delta_{\text{true},i} + b)\right)^2}{K - 2}}
$$

Propagating $s_{y/x} / |m|$ ensures that any non-linearity or matrix mismatch among the calibration anchors is reflected in the final uncertainty budget.

## Full-Pipeline Uncertainty Propagation (The Kragten Method)

Analytical partial-derivative formulas for error propagation become cumbersome and error-prone in multi-stage CF-IRMS pipelines. `isotools` uses the **Kragten Numerical Differentiation** method (`isotools.utils.kragten.propagate_kragten` and `propagate_kragten_budget`).

### How It Works
1.  **Identify Inputs:** For each sample, the model collects all uncertain input quantities $x_1, x_2, \dots, x_k$:
    *   Sample replicate measurement uncertainty $u(\bar{\delta}_{\text{sample}})$ (`SEM` or $\sigma_{\text{method}} / \sqrt{n}$).
    *   Anchor measured uncertainties $u(\bar{\delta}_{\text{anchor},i})$ and certified uncertainties $u(\delta_{\text{true},i})$.
    *   OLS calibration fit residual scatter $s_{y/x}$ (for `MultiPointLinear` when $K \ge 3$).
    *   **Pre-calibration correction uncertainties** (`u_blank`, `u_linearity`, `u_drift`) when those corrections are active.
2.  **Numerical Perturbation:** Each input $x_i$ is perturbed one at a time by its 1-$\sigma$ standard uncertainty $u(x_i)$, and the calibration model is re-evaluated to compute individual sensitivity shifts $\Delta y_i = f(x_1, \dots, x_i + u(x_i), \dots) - f(x_1, \dots, x_k)$.
3.  **Quadrature Combination:** The resulting shifts are combined in quadrature to obtain the combined standard uncertainty $u_c$:

$$
u_c(y) = \sqrt{\sum_{i=1}^{k} (\Delta y_i)^2}
$$

### Pre-Calibration Uncertainty Components
When pre-calibration stages are active on a `Batch`, `Batch._compute_precalibration_uncertainties()` quantifies their standard uncertainties before scale normalization:
-   **Blank Correction (`u_blank`):** Propagates the standard error of the mean blank peak area $u(\bar{A}_{\text{blk}})$ and mean blank delta $u(\bar{\delta}_{\text{blk}})$ through the mass-balance equation via Kragten perturbation.
-   **Linearity Correction (`u_linearity`):** Propagates the OLS slope standard error $s_{m_{\text{lin}}}$ scaled by the sample's area leverage relative to the reference area:

$$
u_{\text{lin}} = |\bar{A}_{\text{sample}} - A_{\text{ref}}| \times s_{m_{\text{lin}}}
$$

-   **Drift Correction (`u_drift`):** Propagates the drift regression slope standard error $s_{m_{\text{drift}}}$ scaled by the sample's sequence position distance from the mean anchor position:

$$
u_{\text{drift}} = |\overline{\text{row}}_{\text{sample}} - \overline{\text{row}}_{\text{anchors}}| \times s_{m_{\text{drift}}}
$$

### Uncertainty Budget Decomposition (`batch.uncertainty_budget`)
`propagate_kragten_budget()` records the squared variance contribution $(\Delta y_i)^2 / u_c^2 \times 100\%$ of each error category. After calling `batch.process()`, inspect `batch.uncertainty_budget` (also exported to the `Uncertainty_Budget` Excel sheet and HTML report) to view the percentage breakdown across:
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
