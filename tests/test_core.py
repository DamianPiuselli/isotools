# tests/test_core.py
from unittest.mock import patch
import pandas as pd
import pytest
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
