"""
Unit tests for analytical drift evaluation, plotting, and linear drift correction.
"""
from unittest.mock import patch
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from isotools.core import Batch
from isotools.config import WATER_H
from isotools.models import ReferenceMaterial

# pylint: disable=redefined-outer-name


@pytest.fixture
def drift_data():
    """Simulate data with a clear drift and some noise."""
    data = {
        "Identifier 1": ["Buenos Aires"] * 10,
        "Peak Nr": [3] * 10,
        "d 3H2/2H2": [
            -40.0,
            -39.79,
            -39.61,
            -39.38,
            -39.22,
            -39.0,
            -38.81,
            -38.59,
            -38.4,
            -38.19,
        ],
        "Row": list(range(1, 11)),
    }
    return pd.DataFrame(data)


@patch("isotools.utils.readers.pd.read_excel")
def test_drift_calculation(mock_read, drift_data):
    mock_read.return_value = drift_data

    with patch("isotools.core.get_standard") as mock_get_std:
        ba_std = ReferenceMaterial(
            name="Buenos Aires", d_true=-40.0, u_true=0.5, aliases=["buenos aires"]
        )
        mock_get_std.side_effect = (
            lambda name, *args, **kwargs: ba_std if name.lower() == "buenos aires" else None
        )

        batch = Batch("dummy.xls", config=WATER_H)
        batch.set_drift_monitors(["Buenos Aires"])

        stats = batch.check_drift()

        assert "Buenos Aires" in stats.index
        assert stats.loc["Buenos Aires", "Slope"] == pytest.approx(0.2, abs=0.01)
        assert stats.loc["Buenos Aires", "p_value"] < 0.001
        assert stats.loc["Buenos Aires", "n"] == 10
        assert stats.loc["Buenos Aires", "CI_95"] > 0


@patch("isotools.utils.readers.pd.read_excel")
def test_drift_plot(mock_read, drift_data):
    mock_read.return_value = drift_data
    with patch("isotools.core.get_standard") as mock_get_std:
        ba_std = ReferenceMaterial(name="Buenos Aires", d_true=-40.0, u_true=0.5)
        mock_get_std.return_value = ba_std

        batch = Batch("dummy.xls", config=WATER_H)
        batch.set_drift_monitors(["Buenos Aires"])

        ax = batch.plot_drift()
        assert isinstance(ax, plt.Axes)
        plt.close()


@patch("isotools.utils.readers.pd.read_excel")
def test_apply_drift_correction(mock_read, drift_data):
    mock_read.return_value = drift_data
    with patch("isotools.core.get_standard") as mock_get_std:
        ba_std = ReferenceMaterial(name="Buenos Aires", d_true=-40.0, u_true=0.5)
        mock_get_std.return_value = ba_std

        batch = Batch("dummy.xls", config=WATER_H)
        batch.set_drift_monitors(["Buenos Aires"])

        stats_before = batch.check_drift()
        assert stats_before.loc["Buenos Aires", "Slope"] == pytest.approx(0.2, abs=0.01)

        batch.apply_drift_correction("Buenos Aires")

        stats_after = batch.check_drift(use_working=True)
        assert stats_after.loc["Buenos Aires", "Slope"] == pytest.approx(0.0, abs=0.0001)

        stats_raw = batch.check_drift(use_working=False)
        assert stats_raw.loc["Buenos Aires", "Slope"] == pytest.approx(0.2, abs=0.01)


@patch("isotools.utils.readers.pd.read_excel")
def test_drift_tracking_attributes(mock_read, drift_data):
    mock_read.return_value = drift_data
    with patch("isotools.core.get_standard") as mock_get_std:
        ba_std = ReferenceMaterial(name="Buenos Aires", d_true=-40.0, u_true=0.5)
        mock_get_std.return_value = ba_std

        batch = Batch("dummy.xls", config=WATER_H)

        assert batch.drift_correction_applied is False
        assert batch.drift_monitor_used is None

        batch.set_drift_monitors(["Buenos Aires"])
        batch.apply_drift_correction("Buenos Aires")

        assert batch.drift_correction_applied is True
        assert batch.drift_monitor_used == "Buenos Aires"


def test_drift_no_monitors():
    with patch("isotools.utils.readers.pd.read_excel") as mock_read:
        mock_read.return_value = pd.DataFrame(
            {"Identifier 1": ["S1"], "Peak Nr": [3], "d 3H2/2H2": [0], "Row": [1]}
        )
        batch = Batch("dummy.xls", config=WATER_H)
        with pytest.raises(ValueError, match="No drift monitors set"):
            batch.check_drift()
