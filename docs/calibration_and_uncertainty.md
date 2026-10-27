# Calibration and Uncertainty

`isotools` prioritizes rigorous error propagation to ensure that reported isotope values are scientifically defensible and compliant with ISO/IEC 17025 traceability principles.

## Calibration Strategies

The library supports three calibration models (subclassing `CalibrationStrategy` in `isotools.strategies`) to normalize pre-calibrated working delta values ($\delta_{\text{meas}}$) to international reference scales (e.g., VSMOW-SLAP, VPDB, AIR).

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
For analytical sequences with 3 or more anchor standards, Ordinary Least Squares (OLS) regression is used to fit $\delta_{\text{meas}}$ against $\delta_{\text{true}}$ across all registered anchors.

## Uncertainty Propagation (The Kragten Method)

Analytical partial-derivative formulas for error propagation become cumbersome and error-prone in multi-point regressions. `isotools` uses the **Kragten Numerical Differentiation** method (`isotools.utils.kragten.propagate_kragten`).

### How It Works
1.  **Identify Inputs:** For each sample, the model collects all uncertain input quantities $x_1, x_2, \dots, x_k$—specifically the sample's measured mean ($\bar{\delta}_{\text{sample}}$), each anchor standard's measured mean ($\bar{\delta}_{\text{anchor},i}$), and each anchor standard's certified value ($\delta_{\text{true},i}$).
2.  **Numerical Perturbation:** Each input $x_i$ is perturbed one at a time by its 1-$\sigma$ standard uncertainty $u(x_i)$, and the entire calibration model (including re-fitting the OLS regression in `MultiPointLinear`) is re-evaluated.
3.  **Quadrature Combination:** The resulting shifts $\Delta y_i = f(x_1, \dots, x_i + u(x_i), \dots) - f(x_1, \dots, x_k)$ are combined in quadrature to obtain the combined standard uncertainty $u_c$:

$$
u_c(y) = \sqrt{\sum_{i=1}^{k} \left( f(x_1, \dots, x_i + u(x_i), \dots, x_k) - f(x_1, \dots, x_k) \right)^2}
$$

### Sample Measurement Uncertainty Basis
By default (`batch.process(strategy, use_method_precision=False)`):
-   Sample and anchor measurement uncertainties are taken as the empirical **Standard Error of the Mean (SEM)** of their replicates ($s / \sqrt{n}$).
-   If a sample has only a single replicate ($n = 1$), `isotools` automatically falls back to the configured instrumental repeatability (`config.method_precision`) and logs a diagnostic notice in `batch.alerts`.
-   If `use_method_precision=True` is passed to `batch.process()`, all sample and anchor measurement uncertainties use $\sigma_{\text{method}} / \sqrt{n}$.
