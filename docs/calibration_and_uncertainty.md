# Calibration and Uncertainty

`isotools` prioritizes rigorous error propagation to ensure that reported isotope values are scientifically defensible.

## Calibration Strategies

The library supports multiple mathematical approaches to normalize raw machine values to the international scale (e.g., VSMOW, VPDB):

### 1. Two-Point Linear Normalization
The most common technique in stable isotope labs. It uses two standards with widely different isotopic values to solve for the linear compression/expansion of the scale:

$$
\delta_{true} = m \cdot \delta_{raw} + b
$$

### 2. Multi-Point OLS
For runs with 3 or more anchor standards, an Ordinary Least Squares (OLS) regression is used to determine the best-fit line.

## Uncertainty Propagation (The Kragten Method)

Standard error propagation (like the Delta method) can be difficult to implement correctly for complex multi-step processes. `isotools` uses the **Kragten Numerical Differentiation** method.

### How it works:
1.  The library identifies all input variables that have uncertainty (e.g., the raw measurement of the sample, the certified values of the standards, and the raw measurements of those standards).
2.  Each variable is "perturbed" by its standard uncertainty, and the final result is recalculated.
3.  The difference in the result allows the library to determine the sensitivity of the final value to each input.
4.  These components are combined in quadrature to provide a final **Combined Standard Uncertainty**.

### Sources of Error Included:
-   **Measurement Noise:** The Standard Error of the Mean (SEM) of the sample replicates.
-   **Standard Uncertainty:** The known uncertainty of the reference materials from their certificates.
-   **Calibration Error:** The uncertainty introduced by the regression fit (slope and intercept).
