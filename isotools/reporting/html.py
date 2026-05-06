"""
HTML reporting module using Plotly and Jinja2.
"""
import os
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from jinja2 import Environment, FileSystemLoader

# Set default plotly template
pio.templates.default = "plotly_white"

def _create_drift_plot(batch) -> str:
    """Generates an interactive Plotly drift plot."""
    valid_data = batch.replicates[~batch.replicates["excluded"]].copy()
    if valid_data.empty:
        return "<p>No data available for drift plot.</p>"

    # Identify drift monitors vs others
    valid_data["canonical_name"] = valid_data["sample_name"].apply(
        lambda x: batch.get_canonical_name(x, batch.drift_monitors)
    )

    fig = go.Figure()

    # 1. Plot Unknowns/Samples first (as a background)
    unknowns = valid_data[valid_data["canonical_name"].isna()]
    if not unknowns.empty:
        fig.add_trace(go.Scatter(
            x=unknowns["row"].tolist(),
            y=unknowns[batch.config.target_column].tolist(),
            mode='markers',
            name='Samples/Others',
            marker=dict(color='lightgrey', size=8, opacity=0.5),
            text=unknowns["sample_name"].tolist(),
            hovertemplate="<b>%{text}</b><br>Row: %{x}<br>Raw: %{y:.3f}<extra></extra>"
        ))

    # 2. Plot Drift Monitors
    monitors = valid_data[valid_data["canonical_name"].notna()]
    for name, group in monitors.groupby("canonical_name"):
        fig.add_trace(go.Scatter(
            x=group["row"].tolist(),
            y=group[batch.config.target_column].tolist(),
            mode='markers',
            name=f"Monitor: {name}",
            marker=dict(size=10, line=dict(width=1, color='DarkSlateGrey')),
            text=group["sample_name"].tolist(),
            hovertemplate="<b>%{text}</b><br>Row: %{x}<br>Raw: %{y:.3f}<extra></extra>"
        ))

    # 3. Add trendlines and annotations
    if batch.drift_monitors:
        stats_df = batch.check_drift(use_working=False)
        for i, (name, stats) in enumerate(stats_df.iterrows()):
            monitor_rows = monitors[monitors["canonical_name"] == name]["row"]
            if monitor_rows.empty:
                continue

            x_min, x_max = monitor_rows.min(), monitor_rows.max()
            group = monitors[monitors["canonical_name"] == name]
            m = stats["Slope"]
            # Re-calculate intercept locally for plotting
            b = group[batch.config.target_column].mean() - m * group["row"].mean()

            # Use Python lists for x and y to avoid binary encoding
            x_line = [float(x_min), float(x_max)]
            y_line = [float(m * x_min + b), float(m * x_max + b)]

            fig.add_trace(go.Scatter(
                x=x_line,
                y=y_line,
                mode='lines',
                name=f"{name} Trend",
                line=dict(dash='dash', width=2),
                hoverinfo='skip'
            ))

            # Annotation for equation
            eq_text = f"{name}: y = {m:.4f}x + {b:.4f}<br>R² = {stats['R_squared']:.4f}"
            fig.add_annotation(
                xref="paper", yref="paper",
                x=0.02, y=0.98 - (i * 0.08),
                text=eq_text,
                showarrow=False,
                align="left",
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor="black",
                borderwidth=1,
                font=dict(size=10)
            )

    fig.update_layout(
        title=f"Drift Analysis (Raw {batch.config.name} vs Row)",
        xaxis_title="Injection (Row)",
        yaxis_title=f"Raw {batch.config.target_column}",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=100, b=50),
        hovermode="closest",
        plot_bgcolor="white"
    )

    # CRITICAL: Do NOT use binary encoding for data arrays
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, post_script=None)

def _create_calibration_plot(batch) -> str:
    """Generates an interactive Plotly calibration plot."""
    if batch.strategy is None:
        return "<p>Process batch before generating calibration plot.</p>"

    valid_data = batch.replicates[~batch.replicates["excluded"]].copy()
    valid_data["canonical_name"] = valid_data["sample_name"].apply(
        lambda x: batch.get_canonical_name(x, batch.anchors)
    )
    anchor_data = valid_data[valid_data["canonical_name"].notna()].copy()

    if anchor_data.empty:
        return "<p>No anchor data found.</p>"

    anchor_data["d_true"] = anchor_data["canonical_name"].apply(lambda x: batch.anchors[x].d_true)

    fig = go.Figure()

    # 1. Scatter Individual Replicates
    for name, group in anchor_data.groupby("canonical_name"):
        fig.add_trace(go.Scatter(
            x=group["d_true"].tolist(),
            y=group["working_value"].tolist(),
            mode='markers',
            name=name,
            marker=dict(size=10, line=dict(width=1, color='DarkSlateGrey')),
            text=group["sample_name"].tolist(),
            hovertemplate="<b>%{text}</b><br>True: %{x}<br>Measured: %{y:.3f}<extra></extra>"
        ))

    # 2. Draw Calibration Line
    t_min, t_max = anchor_data["d_true"].min(), anchor_data["d_true"].max()
    pad = (t_max - t_min) * 0.1 if t_max != t_min else 1.0
    t_line = np.linspace(t_min - pad, t_max + pad, 100).tolist() # Convert to list

    m = batch.strategy.slope
    b = batch.strategy.intercept
    y_line = [float(m * t + b) for t in t_line] # Convert to list of floats

    fig.add_trace(go.Scatter(
        x=t_line,
        y=y_line,
        mode='lines',
        name='Linear Fit',
        line=dict(color='black', width=2),
        hoverinfo='skip'
    ))

    # 3. Annotation for Equation
    eq_text = f"y = {m:.4f}x + {b:.4f}<br>R² = {batch.strategy.r_squared:.4f}"
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.05, y=0.95,
        text=eq_text,
        showarrow=False,
        align="left",
        bgcolor="rgba(255, 255, 255, 0.7)",
        bordercolor="black",
        borderwidth=1
    )

    fig.update_layout(
        title=f"Calibration Curve: {batch.config.name}",
        xaxis_title="Reference Value (True)",
        yaxis_title=f"Measured {batch.config.target_column} (Drift-Corrected)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=100, b=50),
        hovermode="closest",
        plot_bgcolor="white"
    )

    return pio.to_html(fig, full_html=False, include_plotlyjs=False, post_script=None)

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
    if batch.summary is not None:
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
        "strategy_name": batch.strategy.__class__.__name__ if batch.strategy else "Not Processed",
        "drift_correction_applied": batch.drift_correction_applied,
        "drift_monitors_set": len(batch.drift_monitors) > 0,
        "alerts": alerts,
        "drift_plot_html": _create_drift_plot(batch),
        "cal_plot_html": _create_calibration_plot(batch),
        "results_table_html": results_table_html,
        "qaqc_table_html": qaqc_table_html
    }

    html_content = template.render(context)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
