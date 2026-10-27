"""
Excel reporting module for exporting Batch results and metadata to multi-sheet Excel workbooks.
"""
import pandas as pd


def export_batch_to_excel(batch, filepath: str):
    """
    Exports the Results, QAQC, Uncertainty_Budget, and Parameters tables of a Batch
    object to a multi-sheet Excel file.

    Args:
        batch: Processed isotools Batch object.
        filepath: Target file path for the .xlsx file.
    """
    if batch.summary is None:
        raise RuntimeError("Run .process() before exporting the report.")

    mem_applied = getattr(batch, "memory_correction_applied", False)
    blank_applied = batch.blank_correction_applied
    lin_applied = batch.linearity_correction_applied
    drift_applied = batch.drift_correction_applied
    elem_applied = getattr(batch, "elemental_calibration_applied", False)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # 1. Results Sheet
        batch.report.to_excel(writer, sheet_name="Results")

        # 2. QAQC Sheet
        qaqc_df = batch.qaqc
        if not qaqc_df.empty:
            qaqc_df.to_excel(writer, sheet_name="QAQC")

        # 3. Uncertainty Budget Sheet
        budget_df = batch.uncertainty_budget
        if not budget_df.empty:
            budget_df.to_excel(writer, sheet_name="Uncertainty_Budget")

        # 4. Parameters / Metadata Sheet
        params = {
            "System": batch.config.name,
            "International Scale": getattr(batch.config, "scale", "N/A") or "N/A",
            "Strategy": batch.strategy.__class__.__name__ if batch.strategy else "None",
            "Target Column": batch.config.target_column,
            "Filepath": batch.filepath,
            "Anchors": ", ".join(batch.anchors.keys()),
            "Controls": ", ".join(batch.controls.keys()),
            "Drift Monitors": ", ".join(batch.drift_monitors.keys()),
            "Memory Correction Applied": mem_applied,
            "Memory Coefficients": (
                str(batch.memory_coefficients) if mem_applied and batch.memory_coefficients else "None"
            ),
            "Blank Correction Applied": blank_applied,
            "Blank Identifier": (
                batch.blank_info["identifier"] if blank_applied and batch.blank_info else "None"
            ),
            "Linearity Correction Applied": lin_applied,
            "Linearity Slope": batch.linearity_slope if lin_applied else "None",
            "Linearity Slope 95% CI": getattr(batch, "linearity_ci95", "None") if lin_applied else "None",
            "Linearity Slope Source": getattr(batch, "linearity_source", "None") if lin_applied else "None",
            "Linearity Reference Substance": batch.linearity_substance_used if lin_applied else "None",
            "Linearity Ref Area": batch.linearity_area_ref if lin_applied else "None",
            "Drift Correction Applied": drift_applied,
            "Drift Monitor Used": batch.drift_monitor_used if drift_applied else "None",
            "Drift Polynomial Degree": getattr(batch, "drift_degree", 1) if drift_applied else "None",
            "Drift Slope": getattr(batch, "drift_slope", "None") if drift_applied else "None",
            "Drift Slope 95% CI": getattr(batch, "drift_ci95", "None") if drift_applied else "None",
            "Elemental Calibration Applied": elem_applied,
        }

        if batch.strategy:
            params["Slope"] = getattr(batch.strategy, "slope", "N/A")
            params["Intercept"] = getattr(batch.strategy, "intercept", "N/A")

        pd.Series(params).to_frame("Value").to_excel(writer, sheet_name="Parameters")
