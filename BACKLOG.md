# isotools Development Backlog

## Phase 1: Core Robustness & Data Integrity
- [x] **Task 1: Non-Destructive Corrections**
    - Refactor `Batch` to store corrections in separate columns (`d_memory_corrected`, `d_blank_corrected`, `d_linearity_corrected`, `d_drift_corrected`, `working_value`) instead of overwriting raw data.
    - Enforce the canonical CF-IRMS order of operations (`Exclusions -> Memory -> Blank -> Linearity -> Drift -> Scale Normalization`) deterministically via `Batch._recompute_working_values()`.
- [x] **Task 2: Centralize Name Resolution**
    - Implement `Batch.get_canonical_name(raw_name, registry)` and `register_standard()` to unify standard identification across drift, linearity, calibration, and QA/QC.
- [x] **Task 3: Ingestion Validation**
    - Enhance `IsodatReader` to validate that all mapped essential columns exist in the raw file, deduplicate target column aliases, and flag missing sample peaks (autosampler drop failures).

## Phase 2: Usability & Reporting
- [x] **Task 4: Standardized Export**
    - Implement `Batch.save_report(filepath)` to export `Results`, `Uncertainty_Budget`, `QAQC`, and `Parameters` sheets to a multi-sheet Excel file with full correction metadata.
- [x] **Task 5: Improved Grouping**
    - Ensure anchor and control standards are aggregated by canonical name in the final report, even if raw names differ.

## Phase 3: Advanced Features & Metrological Completeness
- [ ] **Task 6: Metadata Integration**
    - Add ability to join external sample metadata (site info, coordinates) to the `Batch`.
- [x] **Task 7: Polynomial Drift & Elemental Composition Models**
    - Support polynomial drift regression (`apply_drift_correction(..., degree=2)`) and elemental weight percent calibration (`calibrate_elemental_composition()` for $\text{\%C}$, $\text{\%N}$, and $\text{C/N}_{\text{atomic}}$).
- [x] **Task 8: Analytical Corrections (Blank & Linearity)**
    - Implement mass-balance blank correction (`apply_blank_correction`) and signal-intensity linearity evaluation/correction (`check_linearity`, `apply_linearity_correction`).
- [x] **Task 9: Memory / Carryover Correction & Injection Filtering**
    - Implement sample-to-sample memory correction (`apply_memory_correction`) and first-$k$ injection filtering (`exclude_first_injections`) for water isotope sequences.
- [x] **Task 10: Long-term QA/QC Tracking**
    - Implement `QualityControlLog` (`isotools/qaqc_log.py`) to track and visualize control standards across multiple runs over time using Matplotlib and interactive Plotly Shewhart control charts.
- [x] **Task 11: Interactive HTML Reports (Single & Dual Isotope)**
    - Generate standalone interactive ISO 17025 HTML reports with Plotly graphs, processing lineage audits, uncertainty budget breakdowns, and dual-isotope analysis ($d\text{-excess}$ and $\text{C/N}_{\text{atomic}}$).
- [x] **Task 12: Detailed Uncertainty Budget Breakdown**
    - Provide a full-pipeline Kragten variance percentage breakdown (`batch.uncertainty_budget`: measurement vs anchors vs OLS fit residual vs blank vs linearity vs drift) in Excel and HTML reports.
