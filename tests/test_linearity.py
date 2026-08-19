"""
Unit tests for mass/intensity linearity evaluation and correction in isotools.
"""

import os
import pytest
import pandas as pd
import numpy as np
from isotools import CARBON_13C, NIST8541, Batch, SinglePointOffset


@pytest.fixture
def dummy_linearity_file(tmp_path):
    """Creates a temporary Excel file with synthetic mass/area linearity dependence."""
    file_path = tmp_path / "dummy_linearity.xls"

    rows = []
    # ac benzoico run across varying mass/area (35 to 190) with linearity slope = -0.0041
    areas = [35.0, 50.0, 85.0, 95.0, 145.0, 150.0, 175.0, 185.0]
    base_delta = -3.0
    slope = -0.0041
    area_ref = 100.0

    for idx, area in enumerate(areas, start=1):
        raw_d13c = base_delta + slope * (area - area_ref) + np.random.normal(0, 0.02)
        rows.append({
            "Row": idx,
            "Identifier 1": "ac benzoico",
            "Amount": 0.05,
            "Peak Nr": 3,
            "d 13C/12C": round(raw_d13c, 3),
            "Ampl 44": int(area * 55),
            "Area 44": round(area, 3),
        })

    # Add NIST8541 anchor
    for idx in range(9, 14):
        rows.append({
            "Row": idx,
            "Identifier 1": "8541",
            "Amount": 0.05,
            "Peak Nr": 3,
            "d 13C/12C": -16.0,
            "Ampl 44": 2500,
            "Area 44": 45.0,
        })



    df = pd.DataFrame(rows)
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)

    return str(file_path)


def test_check_linearity(dummy_linearity_file):
    batch = Batch(dummy_linearity_file, CARBON_13C)
    stats = batch.check_linearity(substance_name="ac benzoico")

    assert not stats.empty
    assert "ac benzoico" in stats.index
    assert "Slope" in stats.columns
    assert "CI_95" in stats.columns
    assert "R_squared" in stats.columns
    assert stats.loc["ac benzoico", "n"] == 8

    # Check slope is negative and close to -0.0041
    slope = stats.loc["ac benzoico", "Slope"]
    assert slope < 0.0


def test_apply_linearity_correction_inferred(dummy_linearity_file):
    batch = Batch(dummy_linearity_file, CARBON_13C)
    initial_working = batch.replicates["working_value"].copy()

    batch.apply_linearity_correction(substance_name="ac benzoico")

    assert batch.linearity_correction_applied is True
    assert batch.linearity_slope is not None
    assert batch.linearity_area_ref is not None

    # Verify working values were adjusted
    corrected_working = batch.replicates["working_value"]
    assert not np.allclose(initial_working, corrected_working)


def test_apply_linearity_correction_manual_slope(dummy_linearity_file):
    batch = Batch(dummy_linearity_file, CARBON_13C)
    initial_working = batch.replicates["working_value"].copy()
    area_col = batch._detect_area_column()

    manual_slope = -0.0041
    batch.apply_linearity_correction(slope=manual_slope, substance_name="ac benzoico", area_ref=100.0)

    assert batch.linearity_correction_applied is True
    assert batch.linearity_slope == manual_slope
    assert batch.linearity_area_ref == 100.0

    # Test formula: working = raw - slope * (area - 100.0)
    expected_row0 = initial_working.iloc[0] - manual_slope * (batch.replicates[area_col].iloc[0] - 100.0)
    assert pytest.approx(batch.replicates["working_value"].iloc[0], abs=1e-3) == expected_row0



def test_linearity_parameters_export(dummy_linearity_file, tmp_path):
    batch = Batch(dummy_linearity_file, CARBON_13C)
    batch.apply_linearity_correction(slope=-0.0041, substance_name="ac benzoico")
    batch.set_anchors(["8541"])
    batch.process(SinglePointOffset())

    export_path = tmp_path / "linearity_report.xlsx"
    batch.save_report(str(export_path))

    params_df = pd.read_excel(export_path, sheet_name="Parameters", index_col=0)
    assert params_df.loc["Linearity Correction Applied", "Value"] is True
    assert float(params_df.loc["Linearity Slope", "Value"]) == pytest.approx(-0.0041)
