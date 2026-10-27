# Concepts and Workflow

**isotools** is built around the concept of a **Batch**, which encapsulates all the data, quality control diagnostics, and mathematical corrections for a single analytical sequence. This approach replaces error-prone spreadsheet manipulation with a reproducible, auditable object-oriented lifecycle.

## The Canonical CF-IRMS Order of Operations

In Continuous-Flow Isotope Ratio Mass Spectrometry (CF-IRMS), following the *FIRMS Good Practice Guide for Isotope Ratio Mass Spectrometry* (Carter & Barwick) and the *Principle of Identical Treatment* (Werner & Brand, 2001), raw measured isotope delta values ($\delta_{\text{raw}}$) must be corrected in a strict physical sequence before scale normalization:

1.  **Stage 0 — Row Exclusions & Injection Filtering (`exclude_rows`, `exclude_first_injections`):**
    *   Failed injections (missing sample peaks, double drops, severe amplitude anomalies, or integration outliers) are flagged and excluded first so they never bias blank averages, linearity slopes, drift slopes, or calibration fits.
    *   In liquid water isotope analysis (TC/EA, equilibration, or laser spectroscopy), `batch.exclude_first_injections(n_skip)` automatically excludes the first $k$ injections of every contiguous vial block to eliminate early carryover-affected injections.
2.  **Stage 0b — Sample-to-Sample Memory Correction (`apply_memory_correction`):**
    *   Compensates for instrumental memory (carryover) between consecutive vials $i-1$ and $i$ following Gröning (2011) and van Geldern & Barth (2012). For injection $j$ within a new vial block:

$$
\delta_{\text{mem\_corr}, i, j} = \delta_{\text{raw}, i, j} + \frac{m_j}{1 - m_j} \times \left(\delta_{\text{raw}, i, j} - \bar{\delta}_{\text{final}, i-1}\right)
$$

    *   Memory coefficients $[m_1, m_2, \dots]$ can be supplied manually or estimated automatically (`coefficients=None`) from large step transitions between standards in the sequence.
3.  **Stage 1 — Blank Correction (`apply_blank_correction`):**
    *   Subtracts the mass-balance contribution of background or container blanks (e.g., tin capsules or filters) from both peak area and delta values:

$$
A_{\text{net}} = A_{\text{raw}} - \bar{A}_{\text{blk}}, \quad \delta_{\text{blank\_corr}} = \frac{A_{\text{raw}} \times \delta_{\text{in}} - \bar{A}_{\text{blk}} \times \bar{\delta}_{\text{blk}}}{A_{\text{net}}}
$$

    *   Applied before linearity because background contamination disproportionately shifts smaller peaks and would otherwise masquerade as an artificial linearity effect.
4.  **Stage 2 — Linearity Correction (`apply_linearity_correction`):**
    *   Corrects for ion-source and amplifier size dependence (shifts in $\delta$ as a function of peak area or amplitude $A$) relative to a reference area $A_{\text{ref}}$:

$$
\delta_{\text{lin\_corr}} = \delta_{\text{in}} - m_{\text{lin}} \times (A - A_{\text{ref}})
$$

    *   The slope $m_{\text{lin}}$ can be inferred automatically from variable-mass standards within the run or transferred directly from a characterization sequence.
5.  **Stage 3 — Drift Correction (`apply_drift_correction`):**
    *   Compensates for slow, time-dependent changes across the analytical sequence (modeled against injection `row`) using periodically interspersed drift monitor standards. Supports both linear (`degree=1`) and polynomial (`degree=2`, etc.) drift models:

$$
\delta_{\text{drift\_corr}} = \delta_{\text{in}} - P_{\text{drift}}(\text{row})
$$

6.  **Stage 4 — Scale Normalization & Elemental Composition (`process`, `calibrate_elemental_composition`):**
    *   Fits the chosen calibration strategy (`SinglePointOffset`, `TwoPointLinear`, or `MultiPointLinear`) to the cleaned `working_value` of the registered **Anchor** standards, normalizes all replicates to the international scale (`VSMOW-SLAP`, `VPDB`, `AIR-N2`), and propagates full-pipeline combined standard uncertainty via the **Kragten method**.
    *   For weighed solid EA-IRMS runs (`CARBON_13C`, `NITROGEN`), `batch.calibrate_elemental_composition()` uses peak areas and sample weights (`Amount`) against standards with known elemental mass fractions (`mass_fraction`) to compute $\text{\%C}$ (`weight_pct_C`) and $\text{\%N}$ (`weight_pct_N`). When combined in `generate_dual_isotope_html_report()`, mass and molar atomic $\text{C/N}$ ratios ($\text{C/N}_{\text{atomic}} = (\text{\%C} / \text{\%N}) \times (14.0067 / 12.011)$) are automatically calculated.

### Deterministic Execution

`Batch` manages Stages 0–3 declaratively via an internal `_recompute_working_values()` pipeline. Even if you call `apply_drift_correction()`, `apply_linearity_correction()`, `apply_blank_correction()`, `apply_memory_correction()`, or `exclude_rows()` out of order—or re-run one with updated parameters—`isotools` automatically recomputes the entire chain in the canonical **Exclusions → Memory → Blank → Linearity → Drift** order without ever double-correcting or overwriting earlier stages.

## QA/QC Diagnostics & Small-$N$ Replicate Outlier Philosophy

### Why Classical Outlier Tests Fail for Routine CF-IRMS ($n = 2\text{--}4$)
Classical parametric outlier tests such as **Grubbs' test** or **Dixon's Q-test** estimate sample variance purely from the internal replicate spread ($s$) of a single sample group. In routine CF-IRMS analysis, samples are typically measured in duplicates or triplicates ($n = 2\text{--}4$). At $n = 3$ ($\text{df} = 1$), a single anomalous injection inflates the group standard deviation $s$ so severely that the test statistic $|x_i - \bar{x}| / s$ is mathematically bounded ($\le 1.155$), giving Grubbs' test near-zero statistical power unless the outlier is dozens of standard deviations away.

Instead, `isotools` uses the known long-term **instrumental method repeatability** ($\sigma_{\text{method}}$, configured in `SystemConfig.method_precision`) as an external reference scale:
-   When a sample group's standard deviation exceeds $3 \times \sigma_{\text{method}}$ and $n \ge 3$, `detect_outliers()` compares each replicate against the **group median** (which is robust against a single flyer for $n \ge 3$) and pinpoints any replicate with $|x_i - \text{median}(x)| > 3 \times \sigma_{\text{method}}$ directly in the alert reason (`Suspected flyer: Row X`).
-   When $n = 2$, the median equals the mean, making it mathematically impossible to distinguish which of the two replicates is the flyer from $\delta$ values alone; `isotools` flags both rows for operator review alongside amplitude and area/weight response diagnostics.

### Scale Extrapolation & $E_n$ Trueness Scores
-   **Scale Extrapolation Alerts:** After `.process()`, any unknown sample or control whose calibrated $\delta$ value lies outside the $[\min(\delta_{\text{true,anchor}}), \max(\delta_{\text{true,anchor}})]$ span of the active calibration anchors is flagged in `batch.alerts` (`Scale Extrapolation`).
-   **Normalized Error ($E_n$) Score:** In `batch.qaqc`, control standards are evaluated using the ISO/IEC 17025 proficiency testing $E_n$ score (at $k = 2$, ~95% confidence):

$$
E_n = \frac{|\delta_{\text{measured}} - \delta_{\text{true}}|}{2 \times \sqrt{u_{\text{combined}}^2 + u_{\text{true}}^2}}
$$

A control standard passes trueness verification (`Within_Unc == True`) when $E_n \le 1.0$.

## Long-Term Laboratory QA/QC Tracking (`QualityControlLog`)

To monitor analytical stability across weeks, months, or years, `isotools` provides `QualityControlLog`:

```python
from isotools import QualityControlLog

qc_log = QualityControlLog("lab_qaqc_history.csv")
qc_log.record_batch(batch)

# Plot a Matplotlib Shewhart control chart (with +/- 2s warning and +/- 3s action limits)
qc_log.plot_shewhart("USGS35")

# Export a standalone interactive Plotly Shewhart HTML dashboard
qc_log.save_shewhart_html("USGS35", "USGS35_Shewhart_Chart.html")
```

## Reporting & Traceability

Once `.process()` has been executed:
-   `batch.report`: Returns a clean summary DataFrame with normalized $\delta$ values, combined standard uncertainties (`combined_uncertainty`), elemental weight percents (if calibrated), and replicate counts (`count`).
-   `batch.uncertainty_budget`: Returns the variance percentage breakdown (`pct_measurement`, `pct_anchors`, `pct_fit_residual`, `pct_blank`, `pct_linearity`, `pct_drift`) for every group.
-   `batch.qaqc`: Returns a trueness verification table comparing calibrated **Control** standards against their certified values (`True_Value`, `u_True`, `Bias`, `En_Score`, `Within_Unc`).
-   `batch.save_report("report.xlsx")`: Exports `Results`, `Uncertainty_Budget`, `QAQC`, and `Parameters` sheets to an Excel workbook.
-   `batch.save_html_report("report.html")`: Generates a standalone, interactive ISO 17025 HTML report containing the processing lineage audit, diagnostic alert logs, interactive Plotly graphs, uncertainty budget table, and sortable tables.
-   `generate_dual_isotope_html_report(batch1, batch2, "dual_report.html")`: Combines two processed batches (e.g., $\delta^2\text{H}$ and $\delta^{18}\text{O}$ in water with $d\text{-excess}$ and GMWL/LMWL fits, or $\delta^{13}\text{C}$ and $\delta^{15}\text{N}$ with $\text{C/N}_{\text{atomic}}$ ratios) into a unified HTML dashboard.
