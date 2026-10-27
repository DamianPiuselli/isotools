"""
Tests for Phase 3 (Rigorous QA/QC: En_Score, small-N replicate flyer pinpointing,
scale extrapolation alerts, polynomial drift degree >= 2) and Phase 6 (QualityControlLog
and Shewhart control charts).
"""

import os
import tempfile
from unittest.mock import patch
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from isotools.config import NITROGEN
from isotools.core import Batch
from isotools.qaqc_log import QualityControlLog
from isotools.strategies.normalization import SinglePointOffset, TwoPointLinear


@patch("isotools.utils.readers.pd.read_excel")
def test_qaqc_en_score_and_extrapolation_alert(mock_read):
    """Verify En_Score in batch.qaqc and Scale Extrapolation alert for out-of-bracket samples."""
    data = {
        "Row": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "Identifier 1": [
            "USGS34", "USGS34",
            "USGS35", "USGS35",
            "IAEA-N-1", "IAEA-N-1",
            "IAEA-N-2", "IAEA-N-2",
            "ExtremeSample", "ExtremeSample",
        ],
        "Peak Nr": [2] * 10,
        "Ampl 28": [2000.0] * 10,
        # Anchors: USGS34 (-1.8) and USGS35 (+2.7)
        # Controls: IAEA-N-1 (true 0.4, measured 0.42 -> En <= 1.0)
        #           IAEA-N-2 (true 20.3, measured 30.0 -> En > 1.0 + extrapolated)
        # Sample: ExtremeSample (measured -15.0 -> extrapolated below -1.8)
        "d 15N/14N": [
            -1.80, -1.80,
            2.70, 2.70,
            0.41, 0.43,
            29.95, 30.05,
            -15.00, -15.05,
        ],
    }
    mock_read.return_value = pd.DataFrame(data)
    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS34", "USGS35"])
    batch.set_controls(["IAEA-N-1", "IAEA-N-2"])
    batch.process(TwoPointLinear())

    qaqc = batch.qaqc
    assert "En_Score" in qaqc.columns
    assert "u_True" in qaqc.columns

    assert qaqc.loc["IAEA-N-1", "En_Score"] <= 1.0
    assert bool(qaqc.loc["IAEA-N-1", "Within_Unc"]) is True

    assert qaqc.loc["IAEA-N-2", "En_Score"] > 1.0
    assert bool(qaqc.loc["IAEA-N-2", "Within_Unc"]) is False

    # Verify Scale Extrapolation alerts for ExtremeSample and IAEA-N-2
    extrap_alerts = batch.alerts[
        batch.alerts["reason"].str.contains("Scale Extrapolation", na=False)
    ]
    assert not extrap_alerts.empty
    flagged_samples = set(extrap_alerts["sample_name"].unique())
    assert "ExtremeSample" in flagged_samples


@patch("isotools.utils.readers.pd.read_excel")
def test_small_n_replicate_flyer_pinpointing(mock_read):
    """Verify median-based flyer pinpointing for n>=3 and n=2 fallback."""
    data = {
        "Row": [1, 2, 3, 4, 5],
        # Group3 has 3 replicates: two tight at 5.0, 5.05, and Row 3 is a flyer at 8.5
        # Group2 has 2 replicates far apart: 2.0 and 6.0 (both should be flagged without flyer guess)
        "Identifier 1": ["Group3", "Group3", "Group3", "Group2", "Group2"],
        "Peak Nr": [2] * 5,
        "Ampl 28": [2000.0] * 5,
        "d 15N/14N": [5.00, 5.05, 8.50, 2.00, 6.00],
    }
    mock_read.return_value = pd.DataFrame(data)
    batch = Batch("dummy.xls", config=NITROGEN)

    alerts = batch.alerts
    g3_var = alerts[
        (alerts["sample_name"] == "Group3")
        & (alerts["reason"].str.contains("High Variance", na=False))
    ]
    assert not g3_var.empty
    assert "Suspected flyer: Row 3" in g3_var.iloc[0]["reason"]

    # For n=2 (Group2), both rows 4 and 5 should be flagged without a flyer guess
    g2_var = alerts[
        (alerts["sample_name"] == "Group2")
        & (alerts["reason"].str.contains("High Variance", na=False))
    ]
    assert set(g2_var["row"].tolist()) == {4, 5}
    assert "Suspected flyer" not in g2_var.iloc[0]["reason"]


@patch("isotools.utils.readers.pd.read_excel")
def test_polynomial_drift_correction_degree_2(mock_read):
    """Verify quadratic (degree=2) drift correction removes non-linear temporal drift."""
    rows_idx = np.arange(1, 10, dtype=float)
    # Quadratic drift curve: 0.05 * row^2 - 0.2 * row
    quad_drift = 0.05 * (rows_idx ** 2) - 0.2 * rows_idx
    true_vals = np.array([
        2.7, 10.0, 2.7, 10.0, 2.7, 10.0, 2.7, 10.0, 2.7
    ])
    names = [
        "USGS35", "S1", "USGS35", "S1", "USGS35", "S1", "USGS35", "S1", "USGS35"
    ]

    df = pd.DataFrame({
        "Row": rows_idx.astype(int),
        "Identifier 1": names,
        "Peak Nr": [2] * 9,
        "Ampl 28": [2000.0] * 9,
        "d 15N/14N": true_vals + quad_drift,
    })
    mock_read.return_value = df

    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS35"])
    batch.set_drift_monitors(["USGS35"])
    batch.apply_drift_correction("USGS35", degree=2)
    batch.process(SinglePointOffset())

    assert batch.drift_degree == 2
    assert batch.drift_info["degree"] == 2
    assert batch.drift_info["r_squared"] == pytest.approx(1.0, abs=1e-6)
    # After quadratic drift removal and single-point offset, S1 should be recovered to 10.0 with near-zero SEM
    assert batch.report.loc["S1", "corrected_d15n"] == pytest.approx(10.0, abs=1e-4)
    assert batch.summary.loc["S1", "sem"] == pytest.approx(0.0, abs=1e-4)


@patch("isotools.utils.readers.pd.read_excel")
def test_quality_control_log_and_shewhart_charts(mock_read):
    """Verify QualityControlLog records multiple batches and generates Shewhart plots & HTML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "lab_qc_log.csv")
        html_path = os.path.join(tmpdir, "shewhart_usgs35.html")
        qc_log = QualityControlLog(csv_path)

        # Simulate 4 analytical batches over time with slight random variation on USGS35
        measured_controls = [2.68, 2.74, 2.65, 2.72]
        for idx, ctrl_val in enumerate(measured_controls, start=1):
            df = pd.DataFrame({
                "Row": [1, 2, 3, 4, 5, 6],
                "Identifier 1": ["USGS34", "USGS34", "USGS32", "USGS32", "USGS35", "USGS35"],
                "Peak Nr": [2] * 6,
                "Ampl 28": [2000.0] * 6,
                "d 15N/14N": [-1.8, -1.8, 180.0, 180.0, ctrl_val - 0.02, ctrl_val + 0.02],
            })
            mock_read.return_value = df
            batch = Batch(f"run_{idx}.xls", config=NITROGEN)
            batch.set_anchors(["USGS34", "USGS32"])
            batch.set_controls(["USGS35"])
            batch.process(TwoPointLinear())
            appended = qc_log.record_batch(batch)
            assert len(appended) == 1

        history = qc_log.get_control_history("USGS35", target_column="d15n")
        assert len(history) == 4
        assert np.all(history["within_unc"])

        # Test Matplotlib Shewhart plot
        ax = qc_log.plot_shewhart("USGS35")
        assert ax is not None
        assert "USGS35" in ax.get_title()
        plt.close("all")

        # Test standalone HTML Shewhart report
        qc_log.save_shewhart_html("USGS35", html_path)
        assert os.path.exists(html_path)
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        assert "Shewhart Control Chart" in html_content
        assert "USGS35" in html_content
        assert "run_4.xls" in html_content
