"""
Unit tests for Excel report Parameters sheet export.
"""
from unittest.mock import patch
import pandas as pd

from isotools.core import Batch
from isotools.config import WATER_H
from isotools.models import ReferenceMaterial
from isotools.strategies import TwoPointLinear


@patch("isotools.core.get_standard")
def test_parameters_sheet_drift_info(mock_get_std, tmp_path):
    data = {
        "Identifier 1": ["Mar_H", "Mar_H", "Mar_H", "Antartida_H", "Sample1"],
        "Peak Nr": [3, 3, 3, 3, 3],
        "d 3H2/2H2": [-0.5, -0.6, -0.7, -95.0, -50.0],
        "Row": [1, 2, 3, 4, 5],
    }

    mock_get_std.side_effect = lambda name, *args, **kwargs: {
        "mar_h": ReferenceMaterial(name="Mar_H", d_true=0.0, u_true=0.1),
        "antartida_h": ReferenceMaterial(name="Antartida_H", d_true=-94.4, u_true=0.5),
    }.get(name.lower())

    with patch("isotools.utils.readers.pd.read_excel") as mock_read:
        mock_read.return_value = pd.DataFrame(data)
        batch = Batch("dummy.xls", config=WATER_H)

    batch.set_anchors(["Mar_H", "Antartida_H"])
    batch.set_drift_monitors(["Mar_H"])

    # CASE 1: No drift correction applied
    batch.process(TwoPointLinear())
    report_path_no_drift = tmp_path / "report_no_drift.xlsx"
    batch.save_report(str(report_path_no_drift))

    params_no_drift = pd.read_excel(report_path_no_drift, sheet_name="Parameters", index_col=0)
    assert not bool(params_no_drift.loc["Drift Correction Applied", "Value"])
    drift_mon_val = params_no_drift.loc["Drift Monitor Used", "Value"]
    assert pd.isna(drift_mon_val) or drift_mon_val == "None"

    # CASE 2: Apply drift correction
    batch.apply_drift_correction("Mar_H")
    batch.process(TwoPointLinear())
    report_path_with_drift = tmp_path / "report_with_drift.xlsx"
    batch.save_report(str(report_path_with_drift))

    params_with_drift = pd.read_excel(
        report_path_with_drift, sheet_name="Parameters", index_col=0
    )
    assert bool(params_with_drift.loc["Drift Correction Applied", "Value"]) is True
    assert params_with_drift.loc["Drift Monitor Used", "Value"] == "Mar_H"
