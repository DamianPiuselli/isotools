# Concepts and Workflow

**isotools** is built around the concept of a **Batch**, which encapsulates all the data, quality control diagnostics, and mathematical corrections for a single analytical sequence. This approach replaces error-prone spreadsheet manipulation with a reproducible, auditable object-oriented lifecycle.

## The Canonical CF-IRMS Order of Operations

In Continuous-Flow Isotope Ratio Mass Spectrometry (CF-IRMS), following the *FIRMS Good Practice Guide for Isotope Ratio Mass Spectrometry* (Carter & Barwick) and the *Principle of Identical Treatment* (Werner & Brand, 2001), raw measured isotope delta values ($\delta_{\text{raw}}$) must be corrected in a strict physical sequence before scale normalization:

1.  **Stage 0 — Row Exclusions (`exclude_rows`):**
    *   Failed injections (missing sample peaks, double drops, severe amplitude anomalies, or integration outliers) are flagged and excluded first so they never bias blank averages, linearity slopes, drift slopes, or calibration fits.
2.  **Stage 1 — Blank Correction (`apply_blank_correction`):**
    *   Subtracts the mass-balance contribution of background or container blanks (e.g., tin capsules or filters) from both peak area and raw delta values:

$$
A_{\text{net}} = A_{\text{raw}} - \bar{A}_{\text{blk}}, \quad \delta_{\text{blank\_corr}} = \frac{A_{\text{raw}} \times \delta_{\text{raw}} - \bar{A}_{\text{blk}} \times \bar{\delta}_{\text{blk}}}{A_{\text{net}}}
$$

    *   Applied first because background contamination disproportionately shifts smaller peaks and would otherwise masquerade as an artificial linearity effect.
3.  **Stage 2 — Linearity Correction (`apply_linearity_correction`):**
    *   Corrects for ion-source and amplifier size dependence (shifts in $\delta$ as a function of peak area or amplitude $A$) relative to a reference area $A_{\text{ref}}$:

$$
\delta_{\text{lin\_corr}} = \delta_{\text{in}} - m_{\text{lin}} \times (A - A_{\text{ref}})
$$

    *   The slope $m_{\text{lin}}$ can be inferred automatically from variable-mass standards within the run or transferred directly from a characterization sequence.
4.  **Stage 3 — Drift Correction (`apply_drift_correction`):**
    *   Compensates for slow, time-dependent changes across the analytical sequence (modeled against injection `row`) using periodically interspersed drift monitor standards:

$$
\delta_{\text{drift\_corr}} = \delta_{\text{in}} - m_{\text{drift}} \times \text{row}
$$

    *   Evaluated and applied after blank and linearity corrections so that drift monitors reflect true temporal drift rather than weight-dependent variations.
5.  **Stage 4 — Scale Normalization & Uncertainty Propagation (`process`):**
    *   Fits the chosen calibration strategy (`SinglePointOffset`, `TwoPointLinear`, or `MultiPointLinear`) to the cleaned `working_value` of the registered **Anchor** standards, normalizes all replicates to the international scale (e.g., VSMOW, VPDB, AIR), and propagates combined standard uncertainty via the **Kragten method**.

### Deterministic Execution

`Batch` manages Stages 0–3 declaratively via an internal `_recompute_working_values()` pipeline. Even if you call `apply_drift_correction()`, `apply_linearity_correction()`, `apply_blank_correction()`, or `exclude_rows()` out of order—or re-run one with updated parameters—`isotools` automatically recomputes the entire chain in the canonical **Exclusions → Blank → Linearity → Drift** order without ever double-correcting or overwriting earlier stages.

## Reporting & Traceability

Once `.process()` has been executed:
-   `batch.report`: Returns a clean summary DataFrame with normalized $\delta$ values, combined standard uncertainties (`combined_uncertainty`), and replicate counts (`count`).
-   `batch.qaqc`: Returns a trueness verification table comparing calibrated **Control** standards against their certified values (`True_Value`, `Bias`, `Within_Unc`).
-   `batch.save_report("report.xlsx")`: Exports `Results`, `QAQC`, and `Parameters` sheets to an Excel workbook.
-   `batch.save_html_report("report.html")`: Generates a standalone, interactive ISO 17025 HTML report containing the 5-stage data lineage audit, diagnostic alert logs, interactive Plotly graphs, and sortable tables.
-   `generate_dual_isotope_html_report(batch1, batch2, "dual_report.html")`: Combines two processed batches (e.g., $\delta^2\text{H}$ and $\delta^{18}\text{O}$ in water, including deuterium excess $d = \delta^2\text{H} - 8 \times \delta^{18}\text{O}$ and GMWL/LMWL trendlines) into a unified HTML dashboard.
