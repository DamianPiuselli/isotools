"""
Tests for Phase 2: Full-Pipeline Kragten Uncertainty & Uncertainty Budget Decomposition.
"""

from unittest.mock import patch
import pandas as pd
import pytest

from isotools.config import NITROGEN
from isotools.core import Batch
from isotools.models import ReferenceMaterial
from isotools.strategies.normalization import MultiPointLinear, TwoPointLinear
from isotools.utils.kragten import propagate_kragten, propagate_kragten_budget


def test_propagate_kragten_budget_linear_function():
    """Verify propagate_kragten_budget matches propagate_kragten and variance shares sum to 100%."""
    def model(p):
        return 2.0 * p[0] - 3.0 * p[1]

    x_val = 10.0
    u_x = 0.5
    y_val = 5.0
    u_y = 0.2

    y0, u_comb = propagate_kragten(model, [x_val, y_val], [u_x, u_y])
    y0_b, u_comb_b, contribs = propagate_kragten_budget(
        model, [x_val, y_val], [u_x, u_y], param_names=["x", "y"]
    )

    assert y0 == pytest.approx(y0_b)
    assert u_comb == pytest.approx(u_comb_b)
    # Variance of (2x - 3y) is 4 * u_x^2 + 9 * u_y^2
    expected_var_x = 4.0 * (u_x ** 2)
    expected_var_y = 9.0 * (u_y ** 2)
    assert contribs["x"] == pytest.approx(expected_var_x, rel=1e-5)
    assert contribs["y"] == pytest.approx(expected_var_y, rel=1e-5)
    assert contribs["x"] + contribs["y"] == pytest.approx(u_comb_b ** 2, rel=1e-5)


def test_multipoint_linear_ols_residual_uncertainty():
    """Verify MultiPointLinear incorporates OLS residual standard error s_y/x when K >= 3."""
    refs = {
        "A1": ReferenceMaterial("A1", -30.0, 0.05),
        "A2": ReferenceMaterial("A2", -15.0, 0.05),
        "A3": ReferenceMaterial("A3", 0.0, 0.05),
    }

    # Collinear points -> s_y/x == 0
    stats_collinear = pd.DataFrame(
        {"mean": [-30.0, -15.0, 0.0], "sem": [0.02, 0.02, 0.02]},
        index=["A1", "A2", "A3"],
    )
    strat_collinear = MultiPointLinear()
    strat_collinear.fit(stats_collinear, refs)
    assert strat_collinear.residual_std_err == pytest.approx(0.0, abs=1e-10)

    summary_collinear = pd.DataFrame(
        {"mean": [-10.0], "sem": [0.05]}, index=["S1"]
    )
    res_collinear = strat_collinear.propagate(summary_collinear, target_col="d13c")
    assert res_collinear.loc["S1", "pct_fit_residual"] == pytest.approx(0.0, abs=1e-8)

    # Non-collinear anchor points -> s_y/x > 0
    stats_scattered = pd.DataFrame(
        {"mean": [-30.0, -14.2, 0.0], "sem": [0.02, 0.02, 0.02]},
        index=["A1", "A2", "A3"],
    )
    strat_scattered = MultiPointLinear()
    strat_scattered.fit(stats_scattered, refs)
    assert strat_scattered.residual_std_err > 0.3

    res_scattered = strat_scattered.propagate(summary_collinear.copy(), target_col="d13c")
    assert (
        res_scattered.loc["S1", "combined_uncertainty"]
        > res_collinear.loc["S1", "combined_uncertainty"]
    )
    assert res_scattered.loc["S1", "pct_fit_residual"] > 50.0


@patch("isotools.utils.readers.pd.read_excel")
def test_full_pipeline_uncertainty_budget_in_batch(mock_read):
    """Verify blank, linearity, and drift uncertainties propagate into batch.uncertainty_budget."""
    rows = []
    # Blanks
    for i in range(1, 4):
        rows.append({
            "Row": i,
            "Identifier 1": "blank",
            "Peak Nr": 2,
            "Ampl 28": 50.0 + (i - 2) * 5.0,
            "d 15N/14N": -5.0 + (i - 2) * 0.4,
            "Area All": 2.0 + (i - 2) * 0.2,
        })
    # Anchors USGS34 and USGS32
    for i in range(4, 7):
        rows.append({
            "Row": i,
            "Identifier 1": "USGS34",
            "Peak Nr": 2,
            "Ampl 28": 1500.0,
            "d 15N/14N": -1.8 + (i - 5) * 0.1,
            "Area All": 20.0,
        })
    for i in range(7, 10):
        rows.append({
            "Row": i,
            "Identifier 1": "USGS32",
            "Peak Nr": 2,
            "Ampl 28": 1500.0,
            "d 15N/14N": 180.0 + (i - 8) * 0.1,
            "Area All": 20.0,
        })
    # Linearity & Drift monitor USGS35 across rows and amplitudes
    for idx, (row_num, area_val, d_val) in enumerate([
        (10, 10.0, 2.5),
        (11, 20.0, 2.7),
        (12, 30.0, 3.0),
        (13, 20.0, 2.9),
    ]):
        rows.append({
            "Row": row_num,
            "Identifier 1": "USGS35",
            "Peak Nr": 2,
            "Ampl 28": 1000.0 + idx * 200.0,
            "d 15N/14N": d_val,
            "Area All": area_val,
        })
    # Sample S1
    for i in range(14, 17):
        rows.append({
            "Row": i,
            "Identifier 1": "S1",
            "Peak Nr": 2,
            "Ampl 28": 1200.0,
            "d 15N/14N": 10.0 + (i - 15) * 0.15,
            "Area All": 15.0,
        })

    mock_read.return_value = pd.DataFrame(rows)
    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS34", "USGS32"])
    batch.set_controls(["USGS35"])
    batch.set_drift_monitors(["USGS35"])

    batch.apply_blank_correction(blank_identifier="blank")
    batch.apply_linearity_correction(substance_name="USGS35")
    batch.apply_drift_correction(monitor_name="USGS35")
    batch.process(TwoPointLinear())

    budget = batch.uncertainty_budget
    assert not budget.empty
    assert "S1" in budget.index

    pct_cols = (
        "pct_measurement", "pct_anchors", "pct_fit_residual",
        "pct_blank", "pct_linearity", "pct_drift",
    )
    for col in pct_cols:
        assert col in budget.columns

    # Verify percentage contributions sum to 100% for S1
    s1_row = budget.loc["S1"]
    total_pct = sum(s1_row[col] for col in pct_cols)
    assert total_pct == pytest.approx(100.0, abs=1e-4)
    assert s1_row["pct_blank"] > 0.0
    assert s1_row["pct_linearity"] > 0.0
    assert s1_row["pct_drift"] > 0.0
