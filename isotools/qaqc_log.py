"""
Long-term laboratory QA/QC tracking and Shewhart control chart generation.
"""

import os
from datetime import datetime
from typing import Optional
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


class QualityControlLog:
    """
    Manages a persistent CSV log of quality control standard measurements and
    analytical run parameters across batches, supporting ISO/IEC 17025 longitudinal
    monitoring and Shewhart control chart visualization.
    """

    COLUMNS = [
        "timestamp",
        "filename",
        "acquisition_date",
        "system_name",
        "target_column",
        "scale",
        "standard_name",
        "true_value",
        "u_true",
        "measured_value",
        "combined_uncertainty",
        "bias",
        "en_score",
        "within_unc",
        "strategy_name",
        "cal_slope",
        "cal_intercept",
        "blank_mean_area",
        "blank_mean_delta",
        "linearity_slope",
        "drift_slope",
    ]

    def __init__(self, filepath: str):
        self.filepath = filepath

    def load(self) -> pd.DataFrame:
        """Loads the historical QA/QC log from disk, or returns an empty DataFrame."""
        if not os.path.exists(self.filepath):
            return pd.DataFrame(columns=self.COLUMNS)
        return pd.read_csv(self.filepath)

    def record_batch(self, batch) -> pd.DataFrame:
        """
        Extracts control standard performance and batch calibration metadata from a
        processed Batch object and appends them to the persistent CSV log.

        Args:
            batch: A processed Batch instance with control standards.

        Returns:
            DataFrame of newly appended rows.
        """
        if batch.summary is None:
            raise RuntimeError("Cannot record an unprocessed batch. Call batch.process() first.")

        qaqc_df = batch.qaqc
        if qaqc_df.empty:
            return pd.DataFrame(columns=self.COLUMNS)

        target_col = batch.config.target_column
        corr_col = f"corrected_{target_col}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        strategy_name = type(batch.strategy).__name__ if batch.strategy else None
        cal_slope = getattr(batch.strategy, "slope", np.nan)
        cal_intercept = getattr(batch.strategy, "intercept", np.nan)
        blank_area = (
            batch.blank_info.get("mean_area", np.nan) if batch.blank_info else np.nan
        )
        blank_delta = (
            batch.blank_info.get("mean_delta", np.nan) if batch.blank_info else np.nan
        )
        lin_slope = (
            batch.linearity_info.get("slope", np.nan) if batch.linearity_info else np.nan
        )
        drift_slope = (
            batch.drift_info.get("slope", np.nan) if batch.drift_info else np.nan
        )

        new_rows = []
        for std_name, row in qaqc_df.iterrows():
            new_rows.append(
                {
                    "timestamp": now_str,
                    "filename": batch.filename,
                    "acquisition_date": batch.acquisition_date,
                    "system_name": batch.config.name,
                    "target_column": target_col,
                    "scale": batch.config.scale,
                    "standard_name": str(std_name),
                    "true_value": float(row["True_Value"]),
                    "u_true": float(row.get("u_True", 0.0)),
                    "measured_value": float(row[corr_col]),
                    "combined_uncertainty": float(row["combined_uncertainty"]),
                    "bias": float(row["Bias"]),
                    "en_score": float(row.get("En_Score", np.nan)),
                    "within_unc": bool(row["Within_Unc"]),
                    "strategy_name": strategy_name,
                    "cal_slope": float(cal_slope) if cal_slope is not None else np.nan,
                    "cal_intercept": (
                        float(cal_intercept) if cal_intercept is not None else np.nan
                    ),
                    "blank_mean_area": float(blank_area),
                    "blank_mean_delta": float(blank_delta),
                    "linearity_slope": float(lin_slope),
                    "drift_slope": float(drift_slope),
                }
            )

        new_df = pd.DataFrame(new_rows, columns=self.COLUMNS)
        parent_dir = os.path.dirname(os.path.abspath(self.filepath))
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        write_header = not os.path.exists(self.filepath)
        new_df.to_csv(self.filepath, mode="a", header=write_header, index=False)
        return new_df

    def get_control_history(
        self, standard_name: str, target_column: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Returns the historical QA/QC log entries matching `standard_name`
        (and optionally `target_column`).
        """
        df = self.load()
        if df.empty:
            return df

        mask = (
            df["standard_name"].astype(str).str.strip().str.lower()
            == standard_name.strip().lower()
        )
        if target_column:
            mask = mask & (
                df["target_column"].astype(str).str.strip().str.lower()
                == target_column.strip().lower()
            )
        return df[mask].reset_index(drop=True)

    def plot_shewhart(
        self,
        standard_name: str,
        target_column: Optional[str] = None,
        ax: Optional[plt.Axes] = None,
    ) -> plt.Axes:
        """
        Plots a Shewhart quality control chart for `standard_name`, displaying:
        - Individual batch measurements with 1-sigma combined uncertainty error bars
        - Certified reference value (dashed green line)
        - Long-term laboratory mean X_bar (solid blue line)
        - Warning limits X_bar +/- 2s (dotted orange lines)
        - Action / control limits X_bar +/- 3s (dashed red lines)
        """
        hist = self.get_control_history(standard_name, target_column=target_column)
        if hist.empty:
            raise ValueError(f"No historical QA/QC records found for '{standard_name}'.")

        if ax is None:
            _, ax = plt.subplots(figsize=(10, 5))

        x_idx = np.arange(1, len(hist) + 1)
        y_vals = hist["measured_value"].values.astype(float)
        y_errs = hist["combined_uncertainty"].values.astype(float)
        true_val = float(hist["true_value"].iloc[-1])

        mean_val = float(np.mean(y_vals))
        sd_val = float(np.std(y_vals, ddof=1)) if len(y_vals) > 1 else 0.0

        ax.errorbar(
            x_idx,
            y_vals,
            yerr=y_errs,
            fmt="o-",
            color="#1f77b4",
            ecolor="#7f7f7f",
            capsize=4,
            label="Measured ± u_c",
            zorder=4,
        )
        ax.axhline(
            true_val,
            color="#2ca02c",
            linestyle="--",
            linewidth=1.5,
            label=f"Certified ({true_val:.2f} ‰)",
        )
        ax.axhline(
            mean_val,
            color="#1f77b4",
            linestyle="-",
            linewidth=1.2,
            label=f"Lab Mean ({mean_val:.2f} ‰)",
        )

        if sd_val > 0:
            ax.axhline(
                mean_val + 2 * sd_val,
                color="#ff7f0e",
                linestyle=":",
                label=f"±2s Warning (±{2 * sd_val:.2f} ‰)",
            )
            ax.axhline(mean_val - 2 * sd_val, color="#ff7f0e", linestyle=":")
            ax.axhline(
                mean_val + 3 * sd_val,
                color="#d62728",
                linestyle="--",
                label=f"±3s Action (±{3 * sd_val:.2f} ‰)",
            )
            ax.axhline(mean_val - 3 * sd_val, color="#d62728", linestyle="--")

        scale_str = str(hist["scale"].iloc[-1]) if "scale" in hist.columns else ""
        t_col = str(hist["target_column"].iloc[-1])
        unit_label = f"‰ vs. {scale_str}" if scale_str and scale_str != "nan" else "‰"

        ax.set_title(
            f"Shewhart Control Chart: {standard_name} ({t_col})",
            fontsize=12,
            fontweight="bold",
        )
        ax.set_xlabel("Analytical Run Sequence", fontsize=10)
        ax.set_ylabel(f"{t_col} ({unit_label})", fontsize=10)
        ax.set_xticks(x_idx)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="best", fontsize=9)
        return ax

    def save_shewhart_html(  # pylint: disable=too-many-locals
        self,
        standard_name: str,
        filepath: str,
        target_column: Optional[str] = None,
    ):
        """
        Generates a standalone interactive Plotly HTML Shewhart control chart report
        for `standard_name`.
        """
        hist = self.get_control_history(standard_name, target_column=target_column)
        if hist.empty:
            raise ValueError(f"No historical QA/QC records found for '{standard_name}'.")

        x_labels = [
            f"#{i + 1}: {row['filename']} ({row['acquisition_date']})"
            for i, row in hist.iterrows()
        ]
        y_vals = hist["measured_value"].values.astype(float)
        y_errs = hist["combined_uncertainty"].values.astype(float)
        true_val = float(hist["true_value"].iloc[-1])

        mean_val = float(np.mean(y_vals))
        sd_val = float(np.std(y_vals, ddof=1)) if len(y_vals) > 1 else 0.0

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_vals.tolist(),
                error_y=dict(type="data", array=y_errs.tolist(), visible=True),
                mode="lines+markers",
                name="Measured ± u_c",
                marker=dict(size=9, color="#2563eb"),
                line=dict(color="#2563eb", width=2),
            )
        )

        fig.add_hline(
            y=true_val,
            line_dash="dash",
            line_color="#16a34a",
            annotation_text=f"Certified ({true_val:.2f} ‰)",
            annotation_position="top left",
        )
        fig.add_hline(
            y=mean_val,
            line_dash="solid",
            line_color="#1e40af",
            annotation_text=f"Lab Mean ({mean_val:.2f} ‰)",
            annotation_position="bottom left",
        )

        if sd_val > 0:
            for mult, color, label in [
                (2.0, "#d97706", "+2s Warning"),
                (-2.0, "#d97706", "-2s Warning"),
                (3.0, "#dc2626", "+3s Action"),
                (-3.0, "#dc2626", "-3s Action"),
            ]:
                fig.add_hline(
                    y=mean_val + mult * sd_val,
                    line_dash="dot" if abs(mult) == 2.0 else "dashdot",
                    line_color=color,
                    annotation_text=f"{label} ({mean_val + mult * sd_val:.2f} ‰)",
                )

        scale_str = str(hist["scale"].iloc[-1]) if "scale" in hist.columns else ""
        t_col = str(hist["target_column"].iloc[-1])
        unit_label = f"‰ vs. {scale_str}" if scale_str and scale_str != "nan" else "‰"

        fig.update_layout(
            title=f"Shewhart Control Chart — {standard_name} ({t_col})",
            xaxis_title="Analytical Run",
            yaxis_title=f"{t_col} ({unit_label})",
            template="plotly_white",
            height=520,
        )

        plot_div = pio.to_html(fig, full_html=False, include_plotlyjs="cdn")
        table_html = hist.to_html(classes="table", border=0, index=False)

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Shewhart Control Chart - {standard_name}</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 2rem; color: #1e293b; }}
        h1, h2 {{ color: #0f172a; }}
        .summary {{ margin-bottom: 1.5rem; padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; }}
        table.table {{ border-collapse: collapse; width: 100%; font-size: 0.875rem; margin-top: 1rem; }}
        table.table th, table.table td {{ border: 1px solid #cbd5e1; padding: 0.5rem 0.75rem; text-align: left; }}
        table.table th {{ background: #f1f5f9; }}
    </style>
</head>
<body>
    <h1>Long-Term QA/QC Shewhart Control Chart: {standard_name}</h1>
    <div class="summary">
        <strong>Target Parameter:</strong> {t_col} ({unit_label}) &nbsp;|&nbsp;
        <strong>Runs Logged:</strong> {len(hist)} &nbsp;|&nbsp;
        <strong>Certified Value:</strong> {true_val:.2f} ‰ &nbsp;|&nbsp;
        <strong>Lab Mean:</strong> {mean_val:.2f} ‰ &nbsp;|&nbsp;
        <strong>Long-Term 1s Repeatability:</strong> {sd_val:.2f} ‰
    </div>
    <div>{plot_div}</div>
    <h2>Historical QA/QC Log</h2>
    <div>{table_html}</div>
</body>
</html>
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_doc)
