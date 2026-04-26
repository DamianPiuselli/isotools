# tests/test_core.py
from unittest.mock import patch
import pandas as pd
import pytest
import os
from isotools.core import Batch
from isotools.config import Nitrogen
from isotools.strategies import TwoPointLinear

# --- Fixtures ---
# Allow pytest fixtures to intentionally shadow outer-scope names (e.g. `mock_config`).
# This keeps pytest's fixture injection and silences linters about redefined outer names.
# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_isodat_file():
    """Simulate reading a file with N2 data."""
    data = {
        "Identifier 1": ["USGS32", "USGS32", "USGS34", "USGS34", "Unknown"],
        "Peak Nr": [2, 2, 2, 2, 2],  # Nitrogen keeps Peak 2
        "d 15N/14N": [180.0, 180.0, -1.8, -1.8, 50.0],  # Perfect data
        "Row": [1, 2, 3, 4, 5],
    }
    return pd.DataFrame(data)


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_workflow_integration(mock_read, mock_isodat_file):
    """
    Full integration test of the Batch class.
    """
    mock_read.return_value = mock_isodat_file

    # 1. Initialize
    batch = Batch("dummy.xls", config=Nitrogen)

    # Verify data loaded and renamed (d 15N/14N -> d15n)
    assert "d15n" in batch.replicates.columns
    assert len(batch.replicates) == 5

    # 2. Configure Standards
    # We use the built-in standards (USGS32/34 are in default registry)
    batch.set_anchors(["USGS32", "USGS34"])

    # 3. Process
    # Since data is perfect (matches true values), slope should be 1, intercept 0
    batch.process(TwoPointLinear())

    # 4. Check Report
    report = batch.report

    # "Unknown" sample should have value ~50.0
    unknown_res = report.loc["Unknown"]
    assert unknown_res["corrected_d15n"] == pytest.approx(50.0, abs=0.1)

    # 5. Check QAQC
    # We didn't set controls, so this should be empty
    assert batch.qaqc.empty


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_outlier_exclusion(mock_read, mock_isodat_file):
    """Test that excluding a row removes it from calculations."""
    mock_read.return_value = mock_isodat_file

    batch = Batch("dummy.xls", config=Nitrogen)

    # Exclude Row 5 (The Unknown sample)
    batch.exclude_rows([5])

    # Verify flag is set
    # FIX: Pylint C0121 - Use direct truthiness check instead of '== True'
    assert batch.replicates.loc[batch.replicates["row"] == 5, "excluded"].iloc[0]

    # Process
    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    # The 'Unknown' sample (Row 5) was the only row for that sample name.
    # So it should NOT appear in the final summary report.
    assert "Unknown" not in batch.report.index

@patch("isotools.utils.readers.pd.read_excel")
def test_batch_plot_calibration(mock_read, mock_isodat_file):
    """Test that plot_calibration generates an axes object."""
    mock_read.return_value = mock_isodat_file
    import matplotlib.pyplot as plt
    
    batch = Batch("dummy.xls", config=Nitrogen)
    
    # Error if called before process
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
    from isotools.config import Water_H
    import numpy as np
    
    # 1. Setup data with perfect precision (all same values)
    # Row 1-2: Anchor 1, Row 3-4: Anchor 2, Row 5: Sample
    data = {
        "Identifier 1": ["Mar_H", "Mar_H", "Antartida_H", "Antartida_H", "S1", "S1"],
        "Peak Nr": [3, 3, 3, 3, 3, 3],
        "d 3H2/2H2": [-10.0, -10.0, -90.0, -90.0, -50.0, -50.0],
        "Row": [1, 2, 3, 4, 5, 6],
    }
    mock_read.return_value = pd.DataFrame(data)
    
    batch = Batch("dummy.xls", config=Water_H)
    batch.set_anchors(["Mar_H", "Antartida_H"])
    
    # 2. Process with empirical SEM (which will be 0.0)
    batch.process(TwoPointLinear(), use_method_precision=False)
    unc_empirical = batch._summary.loc["S1", "combined_uncertainty"]
    sem_empirical = batch._summary.loc["S1", "sem"]
    assert sem_empirical == 0.0
    
    # 3. Process with method precision (Water_H precision = 1.4)
    # For S1 with n=2, expected SEM = 1.4 / sqrt(2) = 0.9899
    batch.process(TwoPointLinear(), use_method_precision=True)
    unc_overridden = batch._summary.loc["S1", "combined_uncertainty"]
    sem_overridden = batch._summary.loc["S1", "sem"]
    
    assert sem_overridden == pytest.approx(1.4 / np.sqrt(2))
    assert unc_overridden > unc_empirical


@patch("isotools.utils.readers.pd.read_excel")
def test_batch_data_view(mock_read, mock_isodat_file):
    """Test that data_view returns the full replicates DataFrame."""
    mock_read.return_value = mock_isodat_file
    batch = Batch("dummy.xls", config=Nitrogen)
    
    view = batch.data_view
    
    # Check that it returns a DataFrame
    assert isinstance(view, pd.DataFrame)
    
    # Check that it has the same number of rows as input
    assert len(view) == 5
    
    # Check that essential columns are present
    assert "sample_name" in view.columns
    assert "row" in view.columns
    assert "d15n" in view.columns
    assert "excluded" in view.columns

@patch("isotools.utils.readers.pd.read_excel")
def test_outlier_detection(mock_read):
    """Test that outliers are correctly identified."""
    from isotools.config import Water_H
    from isotools.strategies import TwoPointLinear
    
    # Setup data with:
    # 1. Range outlier (Row 1) - should only flag AFTER process
    # 2. Variance outlier (S1: Row 2-3) - flags immediately
    # 3. Amplitude outlier (Row 4) - flags immediately
    data = {
        "Identifier 1": ["RangeOut", "VarOut", "VarOut", "AmpOut", "Mar_H", "Antartida_H"],
        "Peak Nr": [3, 3, 3, 3, 3, 3],
        "d 3H2/2H2": [2000.0, -50.0, -100.0, -50.0, -0.49, -94.89],
        "Row": [1, 2, 3, 4, 5, 6],
        "Ampl 2": [1000, 1000, 1000, 100, 1000, 1000],
    }
    mock_read.return_value = pd.DataFrame(data)
    
    batch = Batch("dummy.xls", config=Water_H)
    alerts = batch.alerts
    
    # 1. Variance check (immediate)
    assert any("High Variance" in r for r in alerts[alerts["sample_name"] == "VarOut"]["reason"])
    
    # 2. Amplitude check (immediate)
    assert any("Amplitude Anomaly" in r for r in alerts[alerts["sample_name"] == "AmpOut"]["reason"])
    
    # 3. Range check (NOT immediate)
    assert not any("outside expected range" in r for r in alerts[alerts["sample_name"] == "RangeOut"]["reason"])

    # 4. Now process and check range
    batch.set_anchors(["Mar_H", "Antartida_H"]) 
    batch.process(strategy=TwoPointLinear())
    alerts_post = batch.alerts
    assert any("outside expected range" in r for r in alerts_post[alerts_post["sample_name"] == "RangeOut"]["reason"])

@patch("isotools.utils.readers.pd.read_excel")
def test_batch_save_report(mock_read, mock_isodat_file, tmp_path):
    """Test that save_report creates an Excel file."""
    mock_read.return_value = mock_isodat_file
    batch = Batch("dummy.xls", config=Nitrogen)
    batch.set_anchors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    report_path = tmp_path / "test_report.xlsx"
    batch.save_report(str(report_path))

    assert os.path.exists(report_path)
    # Verify we can read it back
    xls = pd.ExcelFile(report_path)
    assert "Results" in xls.sheet_names
    assert "Parameters" in xls.sheet_names
