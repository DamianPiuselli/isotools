"""
Unit and integration tests for the Batch controller, CF-IRMS order of operations,
outlier diagnostics, and standard resolution.
"""
import os
from unittest.mock import patch
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from isotools.core import Batch
from isotools.config import NITROGEN, WATER_H, CARBON_13C
from isotools.models import ReferenceMaterial
from isotools.standards import DEFAULT_STANDARDS, get_standard, register_standard
from isotools.strategies import SinglePointOffset, TwoPointLinear

# Allow pytest fixtures to intentionally shadow outer-scope names.
# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_isodat_file():
    """Simulate reading a file with N2 data."""
    data = {
        "Identifier 1": ["USGS32", "USGS32", "USGS34", "USGS34", "Unknown"],
        "Peak Nr": [2, 2, 2, 2, 2],  # NITROGEN keeps Peak 2
        "d 15N/14N": [180.0, 180.0, -1.8, -1.8, 50.0],  # Perfect data
        "Row": [1, 2, 3, 4, 5],
    }
    return pd.DataFrame(data)


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_workflow_integration(mock_read, mock_isodat_file):
    """Full integration test of the Batch class."""
    mock_read.return_value = mock_isodat_file

    batch = Batch("dummy.xls", config=NITROGEN)
    assert "d15n" in batch.replicates.columns
    assert len(batch.replicates) == 5

    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    report = batch.report
    unknown_res = report.loc["Unknown"]
    assert unknown_res["corrected_d15n"] == pytest.approx(50.0, abs=0.1)
    assert batch.qaqc.empty


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_qaqc_with_controls(mock_read):
    """Verify that Batch.qaqc computes bias and Within_Unc for registered control standards."""
    data = {
        "Identifier 1": ["USGS32", "USGS32", "USGS34", "USGS34", "USGS35", "USGS35"],
        "Peak Nr": [2, 2, 2, 2, 2, 2],
        "d 15N/14N": [180.0, 180.0, -1.8, -1.8, 2.75, 2.65],
        "Row": [1, 2, 3, 4, 5, 6],
    }
    mock_read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS32", "USGS34"])
    batch.set_controls(["USGS35"])
    batch.process(TwoPointLinear())

    qaqc = batch.qaqc
    assert not qaqc.empty
    assert "USGS35" in qaqc.index
    assert qaqc.loc["USGS35", "True_Value"] == pytest.approx(2.7)
    assert qaqc.loc["USGS35", "Bias"] == pytest.approx(0.0, abs=0.05)
    assert bool(qaqc.loc["USGS35", "Within_Unc"]) is True


@patch("isotools.utils.readers.pd.read_excel")
def test_cf_irms_canonical_order_of_operations(mock_read):
    """
    Verify that applying Blank, Linearity, and Drift corrections in ANY call order
    always produces the exact same canonical CF-IRMS result:
        Stage 1 (Blank) -> Stage 2 (Linearity) -> Stage 3 (Drift) -> Stage 4 (Scale Normalization)
    and that re-calling any correction method is idempotent (no double-correction).
    """
    rows = [
        # Blanks
        {"Row": 1, "Identifier 1": "bco cap", "Peak Nr": 3, "d 13C/12C": -28.0, "Area 44": 1.5, "Ampl 44": 150},
        {"Row": 2, "Identifier 1": "bco cap", "Peak Nr": 3, "d 13C/12C": -28.2, "Area 44": 1.5, "Ampl 44": 150},
        # Linearity standards (varying area)
        {"Row": 3, "Identifier 1": "ac benzoico", "Peak Nr": 3, "d 13C/12C": -24.5, "Area 44": 20.0, "Ampl 44": 1000},
        {"Row": 4, "Identifier 1": "ac benzoico", "Peak Nr": 3, "d 13C/12C": -24.9, "Area 44": 50.0, "Ampl 44": 2500},
        {"Row": 5, "Identifier 1": "ac benzoico", "Peak Nr": 3, "d 13C/12C": -25.4, "Area 44": 90.0, "Ampl 44": 4500},
        {"Row": 6, "Identifier 1": "ac benzoico", "Peak Nr": 3, "d 13C/12C": -25.8, "Area 44": 120.0, "Ampl 44": 6000},
        # Drift & Anchor monitor (8541 across the run)
        {"Row": 7, "Identifier 1": "8541", "Peak Nr": 3, "d 13C/12C": -16.2, "Area 44": 40.0, "Ampl 44": 2000},
        {"Row": 10, "Identifier 1": "8541", "Peak Nr": 3, "d 13C/12C": -15.9, "Area 44": 42.0, "Ampl 44": 2100},
        {"Row": 14, "Identifier 1": "8541", "Peak Nr": 3, "d 13C/12C": -15.5, "Area 44": 39.0, "Ampl 44": 1950},
        # Unknown Samples
        {"Row": 8, "Identifier 1": "Sample_A", "Peak Nr": 3, "d 13C/12C": -21.0, "Area 44": 35.0, "Ampl 44": 1750},
        {"Row": 9, "Identifier 1": "Sample_A", "Peak Nr": 3, "d 13C/12C": -20.8, "Area 44": 37.0, "Ampl 44": 1850},
    ]
    df_raw = pd.DataFrame(rows)

    # Batch 1: Applied in canonical order (Blank -> Linearity -> Drift)
    mock_read.return_value = df_raw.copy()
    b_canonical = Batch("seq.xls", config=CARBON_13C)
    b_canonical.set_anchors(["8541"])
    b_canonical.set_drift_monitors(["8541"])
    b_canonical.apply_blank_correction("bco cap")
    b_canonical.apply_linearity_correction(substance_name="ac benzoico")
    b_canonical.apply_drift_correction("8541")
    b_canonical.process(SinglePointOffset())

    # Batch 2: Applied in reverse order (Drift -> Linearity -> Blank)
    mock_read.return_value = df_raw.copy()
    b_reverse = Batch("seq.xls", config=CARBON_13C)
    b_reverse.set_anchors(["8541"])
    b_reverse.set_drift_monitors(["8541"])
    b_reverse.apply_drift_correction("8541")
    b_reverse.apply_linearity_correction(substance_name="ac benzoico")
    b_reverse.apply_blank_correction("bco cap")
    b_reverse.process(SinglePointOffset())

    # Verify working_value, slopes, and final calibrated summary match identically
    assert b_canonical.linearity_slope == pytest.approx(b_reverse.linearity_slope, abs=1e-9)
    assert b_canonical.drift_slope == pytest.approx(b_reverse.drift_slope, abs=1e-9)
    np.testing.assert_allclose(
        b_canonical.replicates["working_value"].values,
        b_reverse.replicates["working_value"].values,
        rtol=1e-9,
    )
    pd.testing.assert_frame_equal(b_canonical.summary, b_reverse.summary)

    # Verify idempotency: calling apply_linearity_correction or apply_drift_correction again does not double-correct
    b_canonical.apply_linearity_correction(substance_name="ac benzoico")
    b_canonical.apply_drift_correction("8541")
    b_canonical.process(SinglePointOffset())
    pd.testing.assert_frame_equal(b_canonical.summary, b_reverse.summary)


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_outlier_exclusion(mock_read, mock_isodat_file):
    """Test that excluding a row removes it from calculations."""
    mock_read.return_value = mock_isodat_file

    batch = Batch("dummy.xls", config=NITROGEN)
    batch.exclude_rows([5])

    assert batch.replicates.loc[batch.replicates["row"] == 5, "excluded"].iloc[0]

    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    assert "Unknown" not in batch.report.index


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_plot_calibration(mock_read, mock_isodat_file):
    """Test that plot_calibration generates an axes object."""
    mock_read.return_value = mock_isodat_file

    batch = Batch("dummy.xls", config=NITROGEN)

    with pytest.raises(RuntimeError, match=r"Run .process\(\) before"):
        batch.plot_calibration()

    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    ax = batch.plot_calibration()
    assert isinstance(ax, plt.Axes)
    plt.close()


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_precision_override(mock_read):
    """Test that use_method_precision correctly overrides sample SEM."""
    data = {
        "Identifier 1": ["Mar_H", "Mar_H", "Antartida_H", "Antartida_H", "S1", "S1"],
        "Peak Nr": [3, 3, 3, 3, 3, 3],
        "d 3H2/2H2": [-10.0, -10.0, -90.0, -90.0, -50.0, -50.0],
        "Row": [1, 2, 3, 4, 5, 6],
    }
    mock_read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=WATER_H)
    batch.set_anchors(["Mar_H", "Antartida_H"])

    batch.process(TwoPointLinear(), use_method_precision=False)
    unc_empirical = batch.summary.loc["S1", "combined_uncertainty"]
    sem_empirical = batch.summary.loc["S1", "sem"]
    assert sem_empirical == 0.0

    batch.process(TwoPointLinear(), use_method_precision=True)
    unc_overridden = batch.summary.loc["S1", "combined_uncertainty"]
    sem_overridden = batch.summary.loc["S1", "sem"]

    assert sem_overridden == pytest.approx(1.4 / np.sqrt(2))
    assert unc_overridden > unc_empirical


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_data_view(mock_read, mock_isodat_file):
    """Test that data_view returns the full replicates DataFrame."""
    mock_read.return_value = mock_isodat_file
    batch = Batch("dummy.xls", config=NITROGEN)

    view = batch.data_view
    assert isinstance(view, pd.DataFrame)
    assert len(view) == 5
    assert "sample_name" in view.columns
    assert "row" in view.columns
    assert "d15n" in view.columns
    assert "excluded" in view.columns


@patch("isotools.utils.readers.pd.read_excel")
def test_outlier_detection(mock_read):
    """Test that outliers are correctly identified."""
    data = {
        "Identifier 1": ["RangeOut", "VarOut", "VarOut", "AmpOut", "Mar_H", "Antartida_H"],
        "Peak Nr": [3, 3, 3, 3, 3, 3],
        "d 3H2/2H2": [2000.0, -50.0, -100.0, -50.0, -0.49, -94.89],
        "Row": [1, 2, 3, 4, 5, 6],
        "Ampl 2": [1000, 1000, 1000, 100, 1000, 1000],
    }
    mock_read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=WATER_H)
    alerts = batch.alerts

    assert any("High Variance" in r for r in alerts[alerts["sample_name"] == "VarOut"]["reason"])
    assert any("Amplitude Anomaly" in r for r in alerts[alerts["sample_name"] == "AmpOut"]["reason"])
    assert not any(
        "outside expected range" in r for r in alerts[alerts["sample_name"] == "RangeOut"]["reason"]
    )

    batch.set_anchors(["Mar_H", "Antartida_H"])
    batch.process(strategy=TwoPointLinear())
    alerts_post = batch.alerts
    assert any(
        "outside expected range" in r
        for r in alerts_post[alerts_post["sample_name"] == "RangeOut"]["reason"]
    )


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_save_report(mock_read, mock_isodat_file, tmp_path):
    """Test that save_report creates an Excel file."""
    mock_read.return_value = mock_isodat_file
    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    report_path = tmp_path / "test_report.xlsx"
    batch.save_report(str(report_path))

    assert os.path.exists(report_path)
    xls = pd.ExcelFile(report_path)
    assert "Results" in xls.sheet_names
    assert "Parameters" in xls.sheet_names


def test_standard_alias_resolution_and_registration():
    """Verify get_standard disambiguation and register_standard custom registration."""
    std_h = get_standard("Mar", target_column="d2h")
    std_o = get_standard("Mar", target_column="d18o")

    assert std_h is not None
    assert std_h.name == "Mar_H"
    assert std_h.d_true == -0.49

    assert std_o is not None
    assert std_o.name == "Mar_O"
    assert std_o.d_true == -0.027

    custom = ReferenceMaterial(
        name="Lab-Water-Test",
        d_true=-12.34,
        u_true=0.15,
        aliases=["lwt1"],
        target_column="d18o",
    )
    try:
        register_standard(custom)
        found = get_standard("lwt1", target_column="d18o")
        assert found is not None
        assert found.name == "Lab-Water-Test"
        assert found.d_true == -12.34
    finally:
        DEFAULT_STANDARDS[:] = [s for s in DEFAULT_STANDARDS if s.name != "Lab-Water-Test"]


@patch("isotools.utils.readers.pd.read_excel")
def test_single_replicate_uncertainty_fallback(mock_read):
    """Test that samples with count == 1 fall back to instrument method precision."""
    data = {
        "Identifier 1": ["USGS32", "USGS32", "USGS34", "USGS34", "SingleSample"],
        "Peak Nr": [2, 2, 2, 2, 2],
        "d 15N/14N": [180.0, 180.0, -1.8, -1.8, 50.0],
        "Row": [1, 2, 3, 4, 5],
    }
    mock_read.return_value = pd.DataFrame(data)

    batch = Batch("dummy_26112025.xls", config=NITROGEN)
    assert batch.acquisition_date == "2025-11-26"

    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    assert "SingleSample" in batch.summary.index
    unc = batch.summary.loc["SingleSample", "combined_uncertainty"]
    assert not pd.isna(unc)
    assert unc > 0

    alerts = batch.alerts
    assert not alerts.empty
    reasons = " ".join(alerts[alerts["sample_name"] == "SingleSample"]["reason"].tolist())
    assert "Single Replicate (n=1)" in reasons

    batch2 = Batch("dummy.xls", config=NITROGEN)
    batch2.set_anchors(["USGS32", "USGS34"])
    batch2.process(TwoPointLinear(), use_method_precision=True)
    alerts2 = batch2.alerts
    reasons2 = (
        " ".join(alerts2[alerts2["sample_name"] == "SingleSample"]["reason"].tolist())
        if not alerts2.empty
        else ""
    )
    assert "Single Replicate (n=1)" not in reasons2
