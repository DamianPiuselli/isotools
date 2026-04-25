# tests/test_readers.py
from unittest.mock import patch
import pandas as pd
import pytest
from isotools.utils.readers import IsodatReader
from isotools.config import SystemConfig

# Allow pytest fixtures to intentionally shadow outer-scope names (e.g. `mock_config`).
# This keeps pytest's fixture injection and silences linters about redefined outer names.
# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_config():
    """Creates a dummy configuration for testing."""
    return SystemConfig(
        name="TestSys",
        target_column="val",
        column_mapping={"Raw Name": "sample_name", "Raw Val": "val", "Row": "row"},
        # filter_func: Keep rows where val > 0
        filter_func=lambda df: df[df["val"] > 0].copy(),
    )


@patch("pandas.read_excel")
def test_reader_renaming_and_cleaning(mock_read_excel, mock_config):
    """Test standard column renaming and string cleanup."""
    # Setup raw data with messy headers and spaces
    raw_data = {
        "Raw  Name": [" Std A ", "Sample B"],  # Note double space in key
        "Raw Val": [10.0, -5.0],
        "Row": [1, 2],
    }
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    df = reader.read("dummy.xls")

    # 1. Check Renaming (Raw Name -> sample_name)
    assert "sample_name" in df.columns

    # 2. Check String Cleanup (" Std A " -> "Std A")
    assert df.iloc[0]["sample_name"] == "Std A"

    # 3. Check System Filtering (val > 0)
    # Row 2 (val=-5.0) should be dropped by filter_func
    assert len(df) == 1
    assert df.iloc[0]["val"] == 10.0


@patch("pandas.read_excel")
def test_manual_row_exclusion(mock_read_excel, mock_config):
    """Test that explicit row exclusion works."""
    raw_data = {"Raw Name": ["A", "B", "C"], "Raw Val": [10, 10, 10], "Row": [1, 2, 3]}
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    # Exclude row 2
    df = reader.read("dummy.xls", exclude_rows=[2])

    assert len(df) == 2
    assert 2 not in df["row"].values


@patch("pandas.read_excel")
def test_reader_validation_fails_on_missing_columns(mock_read_excel, mock_config):
    """Test that reading fails if mapped columns are missing."""
    # Mock data missing "Raw Name"
    raw_data = {"Raw Val": [10], "Row": [1]}
    mock_read_excel.return_value = pd.DataFrame(raw_data)

    reader = IsodatReader(mock_config)
    with pytest.raises(ValueError, match="Missing expected columns"):
        reader.read("missing_cols.xls")
