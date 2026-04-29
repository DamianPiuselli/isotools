# isotools Development Backlog

## Phase 1: Core Robustness & Data Integrity
- [x] **Task 1: Non-Destructive Corrections**
    - Refactor `Batch` to store corrections in a separate column instead of overwriting raw data.
    - Update `apply_drift_correction` and `process` to use this new column.
- [x] **Task 2: Centralize Name Resolution**
    - Implement `Batch._get_canonical_name(raw_name)` to unify standard identification across `check_drift`, `plot_drift`, `process`, and `plot_calibration`.
- [x] **Task 3: Ingestion Validation**
    - Enhance `IsodatReader` to validate that all mapped columns exist in the raw file.
    - Provide clear error messages/warnings for missing data.

## Phase 2: Usability & Reporting
- [x] **Task 4: Standardized Export**
    - Implement `Batch.save_report(filepath)` to export results and QAQC to a multi-sheet Excel file.
    - Added explicit drift correction status (applied/not applied and monitor used) to the Parameters sheet for traceability.
- [x] **Task 5: Improved Grouping**
    - Ensure control standards are aggregated by canonical name in the final report, even if raw names differ.

## Phase 3: Advanced Features
- [ ] **Task 6: Metadata Integration**
    - Add ability to join external sample metadata (weights, site info) to the Batch.
- [ ] **Task 7: Non-Linear Models**
    - Implement quadratic/polynomial calibration strategies.
- [ ] **Task 8: Analytical Corrections (Linearity & Memory)**
    - Implement methods to correct for gas amount dependencies and sample-to-sample carryover.
- [ ] **Task 9: Long-term QA/QC Tracking**
    - Create a module to track and visualize control standards across multiple runs over time (e.g., Shewhart charts).
- [ ] **Task 10: Interactive HTML Reports**
    - Add functionality to generate standalone interactive reports with plots (Plotly/Bokeh) for easier data review.
- [ ] **Task 11: Detailed Uncertainty Budget**
    - Provide a breakdown of uncertainty sources (measurement vs standard vs fit) in the report to help optimize methods.
