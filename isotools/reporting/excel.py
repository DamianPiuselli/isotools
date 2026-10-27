"""
Excel reporting module for exporting Batch results and metadata to multi-sheet Excel workbooks.
"""
import pandas as pd


def export_batch_to_excel(batch, filepath: str):
    """
    Exports the Results, QAQC, and Parameters tables of a Batch object to a multi-sheet Excel file.

    Args:
        batch: Processed isotools Batch object.
        filepath: Target file path for the .xlsx file.
    """
    if batch.summary is None:
        raise RuntimeError("Run .process() before exporting the report.")

    drift_applied = batch.drift_correction_applied
    lin_applied = batch.linearity_correction_applied
    blank_applied = batch.blank_correction_applied

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # 1. Results Sheet
        batch.report.to_excel(writer, sheet_name="Results")

        # 2. QAQC Sheet
        qaqc_df = batch.qaqc
        if not qaqc_df.empty:
            qaqc_df.to_excel(writer, sheet_name="QAQC")

        # 3. Parameters / Metadata Sheet
        params = {
            "System": batch.config.name,
            "Strategy": batch.strategy.__class__.__name__ if batch.strategy else "None",
            "Target Column": batch.config.target_column,
            "Filepath": batch.filepath,
            "Anchors": ", ".join(batch.anchors.keys()),
            "Controls": ", ".join(batch.controls.keys()),
            "Drift Monitors": ", ".join(batch.drift_monitors.keys()),
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
            "Drift Slope": getattr(batch, "drift_slope", "None") if drift_applied else "None",
            "Drift Slope 95% CI": getattr(batch, "drift_ci95", "None") if drift_applied else "None",
        }

        if batch.strategy:
            params["Slope"] = getattr(batch.strategy, "slope", "N/A")
            params["Intercept"] = getattr(batch.strategy, "intercept", "N/A")

        pd.Series(params).to_frame("Value").to_excel(writer, sheet_name="Parameters")
