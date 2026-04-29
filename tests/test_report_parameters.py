# tests/test_report_parameters.py
from unittest.mock import patch
import pandas as pd
import os
from isotools.core import Batch
from isotools.config import Water_H
from isotools.strategies import TwoPointLinear

@patch("isotools.core.get_standard")
def test_parameters_sheet_drift_info(mock_get_std, tmp_path):
    # 1. Setup Data - Need at least 3 points for drift analysis as per core.py
    data = {
        "Identifier 1": ["Mar_H", "Mar_H", "Mar_H", "Antartida_H", "Sample1"],
        "Peak Nr": [3, 3, 3, 3, 3],
        "d 3H2/2H2": [-0.5, -0.6, -0.7, -95.0, -50.0],
        "Row": [1, 2, 3, 4, 5],
    }
    
    from isotools.models import ReferenceMaterial
    mock_get_std.side_effect = lambda name: {
        "mar_h": ReferenceMaterial(name="Mar_H", d_true=0.0, u_true=0.1),
        "antartida_h": ReferenceMaterial(name="Antartida_H", d_true=-94.4, u_true=0.5)
    }.get(name.lower())

    # We only mock read_excel for the Batch initialization
    with patch("isotools.utils.readers.pd.read_excel") as mock_read:
        mock_read.return_value = pd.DataFrame(data)
        batch = Batch("dummy.xls", config=Water_H)
    
    batch.set_anchors(["Mar_H", "Antartida_H"])
    batch.set_drift_monitors(["Mar_H"])
    
    # CASE 1: No drift correction applied
    batch.process(TwoPointLinear())
    report_path_no_drift = tmp_path / "report_no_drift.xlsx"
    batch.save_report(str(report_path_no_drift))
    
    # Read the ACTUAL file we just saved
    params_no_drift = pd.read_excel(report_path_no_drift, sheet_name="Parameters", index_col=0)
    assert params_no_drift.loc["Drift Correction Applied", "Value"] == False
    assert pd.isna(params_no_drift.loc["Drift Monitor Used", "Value"]) or params_no_drift.loc["Drift Monitor Used", "Value"] == "None"
    
    # CASE 2: Apply drift correction
    batch.apply_drift_correction("Mar_H")
    batch.process(TwoPointLinear()) # Re-process to update summary
    report_path_with_drift = tmp_path / "report_with_drift.xlsx"
    batch.save_report(str(report_path_with_drift))
    
    # Read the ACTUAL file we just saved
    params_with_drift = pd.read_excel(report_path_with_drift, sheet_name="Parameters", index_col=0)
    assert params_with_drift.loc["Drift Correction Applied", "Value"] == True
    assert params_with_drift.loc["Drift Monitor Used", "Value"] == "Mar_H"
