# isotools Development Backlog

## Phase 1: Core Robustness & Data Integrity
- [x] **Task 1: Non-Destructive Corrections**
    - Refactor `Batch` to store corrections in separate columns (`d_blank_corrected`, `d_linearity_corrected`, `d_drift_corrected`, `working_value`) instead of overwriting raw data.
    - Enforce the canonical CF-IRMS order of operations (`Exclusions -> Blank -> Linearity -> Drift -> Scale Normalization`) deterministically via `Batch._recompute_working_values()`.
- [x] **Task 2: Centralize Name Resolution**
    - Implement `Batch.get_canonical_name(raw_name, registry)` and `register_standard()` to unify standard identification across drift, linearity, calibration, and QA/QC.
- [x] **Task 3: Ingestion Validation**
    - Enhance `IsodatReader` to validate that all mapped essential columns exist in the raw file, deduplicate target column aliases, and flag missing sample peaks (autosampler drop failures).

## Phase 2: Usability & Reporting
- [x] **Task 4: Standardized Export**
    - Implement `Batch.save_report(filepath)` to export `Results`, `QAQC`, and `Parameters` sheets to a multi-sheet Excel file with full correction metadata.
- [x] **Task 5: Improved Grouping**
    - Ensure anchor and control standards are aggregated by canonical name in the final report, even if raw names differ.

## Phase 3: Advanced Features
- [ ] **Task 6: Metadata Integration**
    - Add ability to join external sample metadata (weights, site info) to the `Batch`.
- [ ] **Task 7: Non-Linear Calibration Models**
    - Implement quadratic/polynomial calibration strategies.
- [x] **Task 8: Analytical Corrections (Blank & Linearity)**
    - Implement mass-balance blank correction (`apply_blank_correction`) and signal-intensity linearity evaluation/correction (`check_linearity`, `apply_linearity_correction`).
- [ ] **Task 9: Memory / Carryover Correction**
    - Implement sample-to-sample memory correction for water isotope sequences.
- [ ] **Task 10: Long-term QA/QC Tracking**
    - Create a module to track and visualize control standards across multiple runs over time (e.g., Shewhart control charts).
- [x] **Task 11: Interactive HTML Reports (Single & Dual Isotope)**
    - Generate standalone interactive ISO 17025 HTML reports with Plotly graphs, 5-stage processing lineage audits, and dual-isotope meteoric water line analysis.
- [ ] **Task 12: Detailed Uncertainty Budget Breakdown**
    - Provide a percentage breakdown of uncertainty sources (measurement vs standard vs fit) in the report to help optimize analytical methods.
