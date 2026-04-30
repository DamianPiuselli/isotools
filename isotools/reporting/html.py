"""
HTML reporting module using Plotly and Jinja2.
"""
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from jinja2 import Environment, FileSystemLoader

# Set default plotly template
pio.templates.default = "plotly_white"

def _create_drift_plot(batch) -> str:
    """Generates an interactive Plotly drift plot."""
    if not batch.drift_monitors:
        return "<p>No drift monitors configured.</p>"

    valid_data = batch.replicates[~batch.replicates["excluded"]].copy()
    valid_data["canonical_name"] = valid_data["sample_name"].apply(
        lambda x: batch._get_canonical_name(x, batch.drift_monitors)
    )
    drift_data = valid_data[valid_data["canonical_name"].notna()]

    if drift_data.empty:
        return "<p>No drift monitor data found.</p>"

    fig = go.Figure()
    
    col_to_use = "working_value" # We usually plot working value for drift check
    
    for name, group in drift_data.groupby("canonical_name"):
        fig.add_trace(go.Scatter(
            x=group["row"],
            y=group[col_to_use],
            mode='markers',
            name=name,
            text=group["sample_name"],
            hovertemplate="<b>%{text}</b><br>Row: %{x}<br>Value: %{y:.3f}<extra></extra>"
        ))

    # Add trendline if possible
    stats_df = batch.check_drift(use_working=False) # Check drift on raw
    for name, stats in stats_df.iterrows():
        # Get row range for this monitor
        monitor_rows = drift_data[drift_data["canonical_name"] == name]["row"]
        x_range = [monitor_rows.min(), monitor_rows.max()]
        # We need the intercept too, check_drift currently returns Slope, CI, p, R2, n
        # I might need to update check_drift to return intercept or calculate it here.
        # For now, let's just do a quick fit here for the visual trendline.
        import numpy as np
        group = drift_data[drift_data["canonical_name"] == name]
        m, b = np.polyfit(group["row"], group[batch.config.target_column], 1)
        
        fig.add_trace(go.Scatter(
            x=x_range,
            y=[m*x_range[0] + b, m*x_range[1] + b],
            mode='lines',
            name=f"{name} trend",
            line=dict(dash='dash'),
            hoverinfo='skip'
        ))

    fig.update_layout(
        title=f"Drift Analysis ({batch.config.name})",
        xaxis_title="Injection (Row)",
        yaxis_title=f"Raw {batch.config.target_column}",
        legend_title="Standards",
        margin=dict(l=0, r=0, t=40, b=0)
    )

    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

def _create_calibration_plot(batch) -> str:
    """Generates an interactive Plotly calibration plot."""
    if batch._strategy is None:
        return "<p>Process batch before generating calibration plot.</p>"

    valid_data = batch.replicates[~batch.replicates["excluded"]].copy()
    valid_data["canonical_name"] = valid_data["sample_name"].apply(
        lambda x: batch._get_canonical_name(x, batch.anchors)
    )
    anchor_data = valid_data[valid_data["canonical_name"].notna()]

    if anchor_data.empty:
        return "<p>No anchor data found.</p>"

    def get_true_val(can_name):
        return batch.anchors[can_name].d_true
    
    anchor_data["d_true"] = anchor_data["canonical_name"].apply(get_true_val)

    fig = go.Figure()

    # Scatter points
    for name, group in anchor_data.groupby("canonical_name"):
        fig.add_trace(go.Scatter(
            x=group["d_true"],
            y=group["working_value"],
            mode='markers',
            name=name,
            text=group["sample_name"],
            hovertemplate="<b>%{text}</b><br>True: %{x}<br>Measured: %{y:.3f}<extra></extra>"
        ))

    # Calibration line
    t_min, t_max = anchor_data["d_true"].min(), anchor_data["d_true"].max()
    pad = (t_max - t_min) * 0.1 if t_max != t_min else 1.0
    t_line = [t_min - pad, t_max + pad]
    y_line = [t * batch._strategy.slope + batch._strategy.intercept for t in t_line]

    fig.add_trace(go.Scatter(
        x=t_line,
        y=y_line,
        mode='lines',
        name='Fit',
        line=dict(color='black', dash='dot'),
        hoverinfo='skip'
    ))

    fig.update_layout(
        title=f"Calibration Curve: {batch.config.name}",
        xaxis_title="Reference Value (True)",
        yaxis_title=f"Measured {batch.config.target_column} (Drift-Corrected)",
        margin=dict(l=0, r=0, t=40, b=0)
    )

    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

def generate_html_report(batch, filepath: str):
    """
    Renders the Batch data into a standalone HTML report.
    """
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("single_isotope.html")

    # Prepare Data
    alerts = batch.alerts.to_dict('records') if not batch.alerts.empty else []

    # Results table - Only if processed
    if batch._summary is not None:
        results_df = batch.report.copy()
        results_table_html = results_df.to_html(classes='table', border=0)

        # QAQC table
        qaqc_df = batch.qaqc
        qaqc_table_html = qaqc_df.to_html(classes='table', border=0) if not qaqc_df.empty else None
    else:
        results_table_html = "<p><i>Batch not yet processed. Run .process() to see results.</i></p>"
        qaqc_table_html = None

    # Metadata
    context = {
        "system_name": batch.config.name,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filepath": batch.filepath,
        "strategy_name": batch._strategy.__class__.__name__ if batch._strategy else "Not Processed",
        "alerts": alerts,
        "drift_plot_html": _create_drift_plot(batch),
        "cal_plot_html": _create_calibration_plot(batch),
        "results_table_html": results_table_html,
        "qaqc_table_html": qaqc_table_html
    }

    html_content = template.render(context)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
