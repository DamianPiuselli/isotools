# Concepts and Workflow

**isotools** is built around the concept of a **Batch**, which encapsulates all the data and logic for a single analytical sequence. This approach replaces procedural scripting with an object-oriented lifecycle.

## The Batch Lifecycle

A typical workflow in `isotools` follows these stages:

1.  **Initialization:** The `Batch` object is created by reading an Isodat Excel export. Raw data is immediately validated, and basic metadata (like row numbers and sample names) is indexed.
2.  **Standards Registration:** You inform the batch which samples are reference materials.
    *   **Anchors:** Used to build the calibration curve.
    *   **Controls:** Used to verify trueness (QA/QC).
    *   **Drift Monitors:** Used to check for and correct analytical drift.
3.  **Outlier Detection:** The batch automatically flags suspicious replicates based on environmental ranges, analytical precision, and signal amplitude.
4.  **Drift Correction (Optional):** If a linear drift is detected in the monitors, the batch can apply a correction to all samples before calibration.
5.  **Processing:** The calibration strategy (e.g., Two-Point Linear) is applied. This step fits the regression and propagates all sources of uncertainty.
6.  **Reporting:** Results are aggregated and exported into structured formats (Pandas DataFrames, Excel, or interactive HTML).

## Why Batch-Centric?

-   **Reproducibility:** The entire state of an analytical run is contained in one object.
-   **Traceability:** Every sample knows exactly how it was corrected and what the source of its uncertainty was.
-   **Simplicity:** High-level commands like `.process()` hide the complex matrix math and error propagation, making it accessible to non-programmers.
