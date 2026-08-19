"""
HTML reporting module using Plotly and Jinja2.
"""
import base64
import os
from datetime import datetime
from typing import Optional
import pandas as pd
from scipy import stats as sp_stats
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from jinja2 import Environment, FileSystemLoader

# Set default plotly template
pio.templates.default = "plotly_white"


def _get_logo_base64() -> Optional[str]:
    """Loads and encodes the LIH laboratory logo as a base64 Data URI."""
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "isologo_lih.jpg")
    if not os.path.exists(logo_path):
        return None
    try:
        from PIL import Image
        import io
        img = Image.open(logo_path)
        img.thumbnail((350, 140))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception:
        try:
            with open(logo_path, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64_str}"
        except Exception:
            return None



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

    x_min, x_max = float(valid_data["row"].min()), float(valid_data["row"].max())
    y_min, y_max = float(valid_data[batch.config.target_column].min()), float(valid_data[batch.config.target_column].max())
    y_pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0

    fig.update_layout(
        autosize=True,
        title=f"Drift Analysis (Raw {batch.config.name} vs Row)",
        xaxis_title="Injection (Row)",
        yaxis_title=f"Raw {batch.config.target_column}",
        xaxis=dict(range=[x_min - 1, x_max + 1], autorange=False),
        yaxis=dict(range=[y_min - y_pad, y_max + y_pad], autorange=False),
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=90),
        hovermode="closest",
        plot_bgcolor="white"
    )

    return pio.to_html(fig, config={'responsive': True}, full_html=False, include_plotlyjs=False, post_script=None)

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

    x_min, x_max = float(anchor_data["d_true"].min()), float(anchor_data["d_true"].max())
    y_min, y_max = float(anchor_data["working_value"].min()), float(anchor_data["working_value"].max())
    x_pad = (x_max - x_min) * 0.08 if x_max != x_min else 1.0
    y_pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0

    fig.update_layout(
        autosize=True,
        title=f"Calibration Curve: {batch.config.name}",
        xaxis_title="Reference Value (True)",
        yaxis_title=f"Measured {batch.config.target_column} (Drift-Corrected)",
        xaxis=dict(range=[x_min - x_pad, x_max + x_pad], autorange=False),
        yaxis=dict(range=[y_min - y_pad, y_max + y_pad], autorange=False),
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=90),
        hovermode="closest",
        plot_bgcolor="white"
    )

    return pio.to_html(fig, config={'responsive': True}, full_html=False, include_plotlyjs=False, post_script=None)

def _create_linearity_plot(batch) -> str:
    """Generates an interactive Plotly linearity plot (Delta vs Signal Area/Amplitude)."""
    if not getattr(batch, "linearity_correction_applied", False) and not hasattr(batch, "linearity_info"):
        return "<p>No linearity correction applied.</p>"

    try:
        area_col = batch._detect_area_column()
    except Exception:
        return "<p>Area column not available for linearity plot.</p>"

    valid_data = batch.replicates[~batch.replicates["excluded"]].copy()
    if valid_data.empty:
        return "<p>No valid data for linearity plot.</p>"

    fig = go.Figure()

    substance = getattr(batch, "linearity_substance_used", None)
    sub_data = pd.DataFrame()

    if substance:
        s_lower = substance.strip().lower()
        mask = valid_data["sample_name"].str.strip().str.lower() == s_lower
        if not mask.any():
            for name in valid_data["sample_name"].unique():
                n_lower = name.strip().lower()
                if s_lower in n_lower or n_lower in s_lower or (
                    ("ac" in s_lower or "bz" in s_lower or "benzo" in s_lower) and
                    ("ac" in n_lower or "bz" in n_lower or "benzo" in n_lower)
                ):
                    mask = valid_data["sample_name"] == name
                    break
        if mask.any():
            sub_data = valid_data[mask]

    # If no specific substance matched, default to valid_data only if substance was not specified
    if sub_data.empty and not substance:
        sub_data = valid_data

    # Determine which Y series to plot
    if not sub_data.empty:
        if "pre_linearity_working_value" in sub_data.columns:
            y_col = "pre_linearity_working_value"
            y_label = "Blank-Corrected δ (‰)" if batch.blank_correction_applied else "Working δ (‰)"
        elif "working_value" in sub_data.columns:
            y_col = "working_value"
            y_label = "Working δ (‰)"
        else:
            y_col = batch.config.target_column
            y_label = f"Raw {batch.config.target_column} (‰)"

        for name, group in sub_data.groupby("sample_name"):
            fig.add_trace(go.Scatter(
                x=group[area_col].tolist(),
                y=group[y_col].tolist(),
                mode='markers',
                name=name,
                marker=dict(size=10, line=dict(width=1, color='DarkSlateGrey')),
                text=group["row"].tolist(),
                hovertemplate="<b>Row %{text}</b><br>Area: %{x}<br>Delta: %{y:.3f} ‰<extra></extra>"
            ))

        x_vals = pd.to_numeric(sub_data[area_col], errors='coerce').dropna().tolist()
        y_vals = pd.to_numeric(sub_data[y_col], errors='coerce').dropna().tolist()
    else:
        x_vals, y_vals = [], []
        y_label = "δ (‰)"

    slope = getattr(batch, "linearity_slope", None)
    ci_95 = getattr(batch, "linearity_ci95", None)
    r2 = getattr(batch, "linearity_r2", None)
    is_direct = getattr(batch, "linearity_is_direct", False)
    area_ref = getattr(batch, 'linearity_area_ref', 'N/A')

    if slope is not None and len(x_vals) >= 2:
        x_min, x_max = float(min(x_vals)), float(max(x_vals))
        y_mean = float(np.mean(y_vals))
        x_mean = float(np.mean(x_vals))
        intercept = y_mean - slope * x_mean

        x_line = [x_min, x_max]
        y_line = [slope * x_min + intercept, slope * x_max + intercept]

        fig.add_trace(go.Scatter(
            x=x_line,
            y=y_line,
            mode='lines',
            name=f'Linearity Slope ({slope:.5f})',
            line=dict(color='#d97706', dash='dash', width=2),
            hoverinfo='skip'
        ))

        if is_direct:
            eq_text = (
                f"<b>Linearity Slope:</b> {slope:.5f} ‰/unit<br>"
                f"<b>Source:</b> Direct Input (Transferred Slope)<br>"
                f"<b>Ref Area (A<sub>ref</sub>):</b> {area_ref}"
            )
        else:
            ci_str = f"± {ci_95:.5f}" if ci_95 is not None else "N/A"
            r2_str = f"{r2:.4f}" if r2 is not None else "N/A"
            eq_text = (
                f"<b>Slope:</b> {slope:.5f} ‰/unit<br>"
                f"<b>95% CI:</b> {ci_str}<br>"
                f"<b>R²:</b> {r2_str}<br>"
                f"<b>Ref Area (A<sub>ref</sub>):</b> {area_ref}"
            )

        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.02, y=0.95,
            text=eq_text,
            showarrow=False,
            align="left",
            bgcolor="rgba(255, 255, 255, 0.85)",
            bordercolor="black",
            borderwidth=1,
            font=dict(size=10)
        )
    elif slope is not None and is_direct:
        # Direct input slope applied, but no multi-point calibration range in this batch
        eq_text = (
            f"<b>Linearity Correction Applied</b><br>"
            f"<b>Slope:</b> {slope:.5f} ‰/unit<br>"
            f"<b>Source:</b> Direct Input (Transferred from Characterization Run)<br>"
            f"<b>Ref Area (A<sub>ref</sub>):</b> {area_ref}"
        )
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.02, y=0.95,
            text=eq_text,
            showarrow=False,
            align="left",
            bgcolor="rgba(255, 255, 255, 0.85)",
            bordercolor="black",
            borderwidth=1,
            font=dict(size=10)
        )


    if x_vals and y_vals:
        x_min, x_max = float(min(x_vals)), float(max(x_vals))
        y_min, y_max = float(min(y_vals)), float(max(y_vals))
        x_pad = (x_max - x_min) * 0.08 if x_max != x_min else 1.0
        y_pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0
        fig.update_layout(
            xaxis=dict(range=[x_min - x_pad, x_max + x_pad], autorange=False),
            yaxis=dict(range=[y_min - y_pad, y_max + y_pad], autorange=False),
        )

    fig.update_layout(
        autosize=True,
        title=f"Linearity Dependence ({batch.config.name} vs {area_col})",
        xaxis_title=f"Signal Intensity / Peak Area ({area_col})",
        yaxis_title=y_label,
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=90),
        hovermode="closest",
        plot_bgcolor="white"
    )


    return pio.to_html(fig, config={'responsive': True}, full_html=False, include_plotlyjs=False, post_script=None)


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
        results_df = batch.report.copy().reset_index()
        results_df.rename(columns={"group_name": "Sample Identifier"}, inplace=True)
        results_table_html = results_df.to_html(classes='table', border=0, index=False)

        # QAQC table
        qaqc_df = batch.qaqc.copy()
        if not qaqc_df.empty:
            qaqc_df = qaqc_df.reset_index()
            qaqc_df.rename(columns={"group_name": "Sample Identifier"}, inplace=True)
            qaqc_table_html = qaqc_df.to_html(classes='table', border=0, index=False)
        else:
            qaqc_table_html = None
    else:
        results_table_html = "<p><i>Batch not yet processed. Run .process() to see results.</i></p>"
        qaqc_table_html = None


    # Metadata & Decision Audit Context
    context = {
        "logo_b64": _get_logo_base64(),
        "system_name": batch.config.name,
        "filename": batch.filename,

        "filepath": batch.filepath,
        "acquisition_date": batch.acquisition_date,
        "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "target_column": batch.config.target_column,
        "strategy_name": batch.strategy.__class__.__name__ if batch.strategy else "Not Processed",

        "anchors": ", ".join(batch.anchors.keys()) if batch.anchors else "None",
        "controls": ", ".join(batch.controls.keys()) if batch.controls else "None",
        "drift_monitors": ", ".join(batch.drift_monitors.keys()) if batch.drift_monitors else "None",
        "excluded_rows": getattr(batch, "excluded_rows_list", []),
        "blank_correction_applied": batch.blank_correction_applied,
        "blank_info": batch.blank_info,
        "drift_correction_applied": batch.drift_correction_applied,

        "drift_monitor_used": batch.drift_monitor_used if batch.drift_correction_applied else "None",
        "drift_slope": getattr(batch, "drift_slope", None),
        "drift_ci95": getattr(batch, "drift_ci95", None),
        "drift_p_value": getattr(batch, "drift_p_value", None),
        "drift_r2": getattr(batch, "drift_r2", None),
        "linearity_correction_applied": getattr(batch, "linearity_correction_applied", False),
        "linearity_slope": getattr(batch, "linearity_slope", None),
        "linearity_ci95": getattr(batch, "linearity_ci95", None),
        "linearity_p_value": getattr(batch, "linearity_p_value", None),
        "linearity_r2": getattr(batch, "linearity_r2", None),
        "linearity_substance_used": getattr(batch, "linearity_substance_used", "None"),
        "linearity_area_ref": getattr(batch, "linearity_area_ref", None),
        "linearity_is_direct": getattr(batch, "linearity_is_direct", False),
        "linearity_source": getattr(batch, "linearity_source", "Inferred from Run Replicates"),



        "use_method_precision": getattr(batch, "use_method_precision", False),
        "method_precision": batch.config.method_precision,
        "strategy_slope": getattr(batch.strategy, "slope", None),
        "strategy_intercept": getattr(batch.strategy, "intercept", None),
        "strategy_r2": getattr(batch.strategy, "r_squared", None),
        "drift_monitors_set": len(batch.drift_monitors) > 0,
        "alerts": alerts,
        "drift_plot_html": _create_drift_plot(batch),
        "linearity_plot_html": _create_linearity_plot(batch),
        "cal_plot_html": _create_calibration_plot(batch),
        "results_table_html": results_table_html,
        "qaqc_table_html": qaqc_table_html,
    }

    html_content = template.render(context)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)


def _create_dual_isotope_plot(batch1, batch2) -> str:
    """Generates an interactive Plotly dual isotope scatter plot."""
    if batch1.summary is None or batch2.summary is None:
        return "<p>Both batches must be processed to generate a dual isotope plot.</p>"

    # Determine x (18O or batch2) and y (2H or batch1)
    if "18o" in batch2.config.target_column.lower():
        b_x, b_y = batch2, batch1
    elif "18o" in batch1.config.target_column.lower():
        b_x, b_y = batch1, batch2
    else:
        b_x, b_y = batch1, batch2

    df_x = b_x.report.copy()
    df_y = b_y.report.copy()

    col_x = f"corrected_{b_x.config.target_column}"
    col_y = f"corrected_{b_y.config.target_column}"

    merged = pd.merge(df_x, df_y, left_index=True, right_index=True, suffixes=(f"_{b_x.config.target_column}", f"_{b_y.config.target_column}"))

    if merged.empty:
        return "<p>No matching samples found between the two isotope batches.</p>"

    x_vals = merged[col_x].tolist()
    y_vals = merged[col_y].tolist()
    u_x = merged[f"combined_uncertainty_{b_x.config.target_column}"].tolist()
    u_y = merged[f"combined_uncertainty_{b_y.config.target_column}"].tolist()
    names = merged.index.tolist()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode='markers+text',
        name='Samples',
        text=names,
        textposition='top center',
        marker=dict(size=9, color='#2563eb', line=dict(width=1, color='DarkSlateGrey')),
        error_x=dict(type='data', array=u_x, visible=True, color='#94a3b8'),
        error_y=dict(type='data', array=u_y, visible=True, color='#94a3b8'),
        hovertemplate="<b>%{text}</b><br>" + f"{b_x.config.name}: %{{x:.2f}}<br>{b_y.config.name}: %{{y:.2f}}<extra></extra>"
    ))

    # Add Global Meteoric Water Line (GMWL: y = 8x + 10) if water isotopes
    if "18o" in b_x.config.target_column.lower() and "2h" in b_y.config.target_column.lower():
        min_x = min(x_vals) - 3.0
        max_x = max(x_vals) + 3.0
        x_line = [float(min_x), float(max_x)]
        y_gmwl = [float(8.0 * x + 10.0) for x in x_line]

        fig.add_trace(go.Scatter(
            x=x_line,
            y=y_gmwl,
            mode='lines',
            name='GMWL (y = 8x + 10)',
            line=dict(color='black', dash='dash', width=2),
            hoverinfo='skip'
        ))

        if len(x_vals) >= 3:
            try:
                slope, intercept, r_val, _, _ = sp_stats.linregress(x_vals, y_vals)
                y_lmwl = [float(slope * x + intercept) for x in x_line]
                fig.add_trace(go.Scatter(
                    x=x_line,
                    y=y_lmwl,
                    mode='lines',
                    name=f'LMWL (y = {slope:.2f}x + {intercept:.2f})',
                    line=dict(color='#10b981', width=2),
                    hoverinfo='skip'
                ))
            except Exception:
                pass

    x_min, x_max = float(min(x_vals)), float(max(x_vals))
    y_min, y_max = float(min(y_vals)), float(max(y_vals))
    x_pad = (x_max - x_min) * 0.08 if x_max != x_min else 1.0
    y_pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0

    fig.update_layout(
        autosize=True,
        title=f"Dual Isotope Plot: {b_y.config.name} vs {b_x.config.name}",
        xaxis_title=f"Normalized {b_x.config.target_column} (‰)",
        yaxis_title=f"Normalized {b_y.config.target_column} (‰)",
        xaxis=dict(range=[x_min - x_pad, x_max + x_pad], autorange=False),
        yaxis=dict(range=[y_min - y_pad, y_max + y_pad], autorange=False),
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=90),
        hovermode="closest",
        plot_bgcolor="white"
    )

    return pio.to_html(fig, config={'responsive': True}, full_html=False, include_plotlyjs=False, post_script=None)




def generate_dual_isotope_html_report(batch1, batch2, filepath: str, title: str = "Dual Isotope Analytical Report"):
    """
    Renders two processed Batch objects into a unified ISO 17025 Dual Isotope HTML report.
    """
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("dual_isotope.html")

    # Combine alerts
    alerts1 = batch1.alerts.to_dict('records') if not batch1.alerts.empty else []
    alerts2 = batch2.alerts.to_dict('records') if not batch2.alerts.empty else []
    for a in alerts1:
        a['system'] = batch1.config.name
    for a in alerts2:
        a['system'] = batch2.config.name
    combined_alerts = alerts1 + alerts2

    # Combined Results Table
    if batch1.summary is not None and batch2.summary is not None:
        r1 = batch1.report.copy()
        r2 = batch2.report.copy()
        col1 = f"corrected_{batch1.config.target_column}"
        col2 = f"corrected_{batch2.config.target_column}"

        merged = pd.merge(r1, r2, left_index=True, right_index=True, suffixes=(f"_{batch1.config.target_column}", f"_{batch2.config.target_column}"))

        # Calculate d-excess if Water 2H & 18O
        if "2h" in batch1.config.target_column.lower() and "18o" in batch2.config.target_column.lower():
            merged["d_excess"] = (merged[col1] - 8 * merged[col2]).round(2)
            merged["u_d_excess"] = np.sqrt(merged[f"combined_uncertainty_{batch1.config.target_column}"]**2 + 64 * merged[f"combined_uncertainty_{batch2.config.target_column}"]**2).round(2)
        elif "18o" in batch1.config.target_column.lower() and "2h" in batch2.config.target_column.lower():
            merged["d_excess"] = (merged[col2] - 8 * merged[col1]).round(2)
            merged["u_d_excess"] = np.sqrt(merged[f"combined_uncertainty_{batch2.config.target_column}"]**2 + 64 * merged[f"combined_uncertainty_{batch1.config.target_column}"]**2).round(2)

        merged_df = merged.reset_index()
        merged_df.rename(columns={"group_name": "Sample Identifier"}, inplace=True)
        results_table_html = merged_df.to_html(classes='table', border=0, index=False)
    else:
        results_table_html = "<p><i>Batches not yet processed. Run .process() on both batches to see combined results.</i></p>"

    # QAQC table
    qaqc1 = batch1.qaqc
    qaqc2 = batch2.qaqc
    if not qaqc1.empty or not qaqc2.empty:
        qaqc1_sub = qaqc1.copy() if not qaqc1.empty else pd.DataFrame()
        qaqc2_sub = qaqc2.copy() if not qaqc2.empty else pd.DataFrame()
        qaqc1_sub["System"] = batch1.config.name
        qaqc2_sub["System"] = batch2.config.name
        qaqc_combined = pd.concat([qaqc1_sub, qaqc2_sub]).reset_index()
        qaqc_combined.rename(columns={"group_name": "Sample Identifier"}, inplace=True)
        qaqc_table_html = qaqc_combined.to_html(classes='table', border=0, index=False)
    else:
        qaqc_table_html = None


    def get_iso_info(b):
        return {
            "system_name": b.config.name,
            "filename": b.filename,
            "filepath": b.filepath,
            "acquisition_date": b.acquisition_date,
            "target_column": b.config.target_column,
            "strategy_name": b.strategy.__class__.__name__ if b.strategy else "Not Processed",
            "anchors": ", ".join(b.anchors.keys()) if b.anchors else "None",
            "controls": ", ".join(b.controls.keys()) if b.controls else "None",
            "drift_monitors": ", ".join(b.drift_monitors.keys()) if b.drift_monitors else "None",
            "excluded_rows": getattr(b, "excluded_rows_list", []),
            "blank_correction_applied": b.blank_correction_applied,
            "blank_info": b.blank_info,
            "drift_correction_applied": b.drift_correction_applied,
            "drift_monitor_used": b.drift_monitor_used if b.drift_correction_applied else "None",
            "drift_slope": getattr(b, "drift_slope", None),
            "drift_ci95": getattr(b, "drift_ci95", None),
            "drift_p_value": getattr(b, "drift_p_value", None),
            "drift_r2": getattr(b, "drift_r2", None),
            "linearity_correction_applied": getattr(b, "linearity_correction_applied", False),
            "linearity_slope": getattr(b, "linearity_slope", None),
            "linearity_ci95": getattr(b, "linearity_ci95", None),
            "linearity_p_value": getattr(b, "linearity_p_value", None),
            "linearity_r2": getattr(b, "linearity_r2", None),
            "linearity_substance_used": getattr(b, "linearity_substance_used", "None"),
            "linearity_area_ref": getattr(b, "linearity_area_ref", None),
            "linearity_is_direct": getattr(b, "linearity_is_direct", False),
            "linearity_source": getattr(b, "linearity_source", "Inferred from Run Replicates"),
            "use_method_precision": getattr(b, "use_method_precision", False),
            "method_precision": b.config.method_precision,
            "strategy_slope": getattr(b.strategy, "slope", None),
            "strategy_intercept": getattr(b.strategy, "intercept", None),
            "strategy_r2": getattr(b.strategy, "r_squared", None),
        }

    context = {
        "logo_b64": _get_logo_base64(),
        "title": title,

        "filename": f"{batch1.filename} / {batch2.filename}",
        "acquisition_date": batch1.acquisition_date,
        "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "iso1": get_iso_info(batch1),
        "iso2": get_iso_info(batch2),
        "alerts": combined_alerts,

        "dual_plot_html": _create_dual_isotope_plot(batch1, batch2),
        "cal_plot_1_html": _create_calibration_plot(batch1),
        "cal_plot_2_html": _create_calibration_plot(batch2),
        "results_table_html": results_table_html,
        "qaqc_table_html": qaqc_table_html,
    }

    html_content = template.render(context)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)


