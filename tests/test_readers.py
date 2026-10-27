"""
Unit tests for IsodatReader header cleaning, validation, and duplicate alias safety.
"""
from unittest.mock import patch
import pandas as pd
import pytest

from isotools.utils.readers import IsodatReader
from isotools.config import SystemConfig, WATER_H

# Allow pytest fixtures to intentionally shadow outer-scope names (e.g. `mock_config`).
# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_config():
    """Creates a dummy configuration for testing."""
    return SystemConfig(
        name="TestSys",
        target_column="val",
        column_mapping={"Raw Name": "sample_name", "Raw Val": "val", "Row": "row"},
        filter_func=lambda df: df[df["val"] > 0].copy(),
    )


@patch("pandas.read_excel")
def test_reader_renaming_and_cleaning(mock_read_excel, mock_config):
    """Test standard column renaming and string cleanup."""
    raw_data = {
        "Raw  Name": [" Std A ", "Sample B"],
        "Raw Val": [10.0, -5.0],
        "Row": [1, 2],
    }
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    df = reader.read("dummy.xls")

    assert "sample_name" in df.columns
    assert df.iloc[0]["sample_name"] == "Std A"
    assert len(df) == 1
    assert df.iloc[0]["val"] == 10.0


@patch("pandas.read_excel")
def test_manual_row_exclusion(mock_read_excel, mock_config):
    """Test that explicit row exclusion works."""
    raw_data = {"Raw Name": ["A", "B", "C"], "Raw Val": [10, 10, 10], "Row": [1, 2, 3]}
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    df = reader.read("dummy.xls", exclude_rows=[2])

    assert len(df) == 2
    assert 2 not in df["row"].values


@patch("pandas.read_excel")
def test_reader_validation_fails_on_missing_columns(mock_read_excel, mock_config):
    """Test that reading fails if mapped columns are missing."""
    raw_data = {"Raw Val": [10], "Row": [1]}
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    with pytest.raises(ValueError, match="Missing ESSENTIAL columns"):
        reader.read("missing_cols.xls")


@patch("pandas.read_excel")
def test_reader_case_and_space_insensitivity(mock_read_excel, mock_config):
    """Test that column validation succeeds even with different case and spacing."""
    raw_data = {
        "rawname": ["Std A", "Sample B"],
        "RAW  val": [10.0, 5.0],
        "row": [1, 2],
    }
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    df = reader.read("dummy.xls")

    assert "sample_name" in df.columns
    assert "val" in df.columns
    assert "row" in df.columns
    assert df.iloc[0]["sample_name"] == "Std A"
    assert df.iloc[0]["val"] == 10.0


@patch("pandas.read_excel")
def test_reader_first_match_deduplication(mock_read_excel):
    """Verify that if both 'd 3H2/2H2' and 'd 2H/1H' exist, only the first is mapped to 'd2h'."""
    raw_data = {
        "Row": [1, 2],
        "Identifier 1": ["Mar_H", "S1"],
        "Peak Nr": [3, 3],
        "d 3H2/2H2": [-0.5, -40.0],
        "d 2H/1H": [-999.0, -999.0],
    }
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(WATER_H)
    df = reader.read("dummy_water.xls")

    assert list(df.columns).count("d2h") == 1
    assert isinstance(df["d2h"], pd.Series)
    assert df.iloc[0]["d2h"] == pytest.approx(-0.5)
