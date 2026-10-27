"""
Unit and integration tests for Carbon (13C) processing, blank mass-balance correction,
and double drop anomaly detection on atmospheric particulate sequences.
"""
import os
from unittest.mock import patch
import pandas as pd
import pytest

from isotools.config import CARBON_13C
from isotools.standards import get_standard
from isotools.core import Batch
from isotools.strategies.normalization import SinglePointOffset

# pylint: disable=redefined-outer-name

DATA_DIR = "local_data/particulado_atmosferico"
FILE_SEQ1 = os.path.join(DATA_DIR, "particulado seq 300626.xls")
FILE_SEQ2 = os.path.join(DATA_DIR, "particulado seq 010726.xls")


def test_carbon_config_and_standards():
    assert CARBON_13C.name == "Carbon (13C)"
    assert CARBON_13C.target_column == "d13c"
    assert CARBON_13C.amplitude_column == "amp_44"

    std = get_standard("8541", target_column="d13c")
    assert std is not None
    assert std.name == "NIST8541"
    assert std.d_true == -16.05
    assert std.u_true == 0.04


@patch("isotools.utils.readers.pd.read_excel")
def test_synthetic_blank_correction_and_double_drop_alerts(mock_read):
    """
    Self-contained test verifying:
    1. Missing Sample Peak detection (Row 3 has only peak_nr=1, no peak_nr=3)
    2. Double Drop detection on Row 4 immediately following missing sample peak Row 3
    3. Mass-balance blank correction math using 'bco cap'
    """
    raw_df = pd.DataFrame(
        {
            "Row": [1, 2, 3, 4, 5, 6],
            "Identifier 1": ["bco cap", "bco cap", "DroppedSample", "NextSample", "8541", "8541"],
            "Peak Nr": [3, 3, 1, 3, 3, 3],  # Row 3 lacks Peak 3!
            "Amount": [0.0, 0.0, 0.10, 0.10, 0.10, 0.10],
            "d 13C/12C": [-28.0, -28.0, -20.0, -15.0, -16.0, -16.0],
            "Ampl 44": [200, 200, 1000, 4000, 2000, 2000],
            "Area 44": [2.0, 2.0, 10.0, 40.0, 20.0, 20.0],
        }
    )
    mock_read.return_value = raw_df

    batch = Batch("dummy_carbon.xls", CARBON_13C)

    # 1. Verify Missing Sample Peak on Row 3 and Double Drop on Row 4
    alerts = batch.alerts
    assert 3 in alerts["row"].values
    assert 4 in alerts["row"].values
    reasons_row3 = " ".join(alerts[alerts["row"] == 3]["reason"].tolist())
    reasons_row4 = " ".join(alerts[alerts["row"] == 4]["reason"].tolist())
    assert "Missing Sample Peak" in reasons_row3
    assert "Double Drop Suspected" in reasons_row4

    # 2. Exclude Row 4 and apply blank correction
    batch.exclude_rows([4])
    assert 4 not in batch.alerts["row"].values

    batch.apply_blank_correction(blank_identifier="bco cap")
    assert batch.blank_correction_applied is True
    assert batch.blank_info["mean_area"] == pytest.approx(2.0)
    assert batch.blank_info["mean_delta"] == pytest.approx(-28.0)

    # For Row 5 (8541): A_raw=20.0, d_raw=-16.0, A_blk=2.0, d_blk=-28.0
    # A_net = 18.0; d_corr = (20*(-16) - 2*(-28)) / 18 = (-320 + 56) / 18 = -264 / 18 = -14.6667
    row5 = batch.replicates[batch.replicates["row"] == 5].iloc[0]
    assert row5["area_net"] == pytest.approx(18.0)
    assert row5["working_value"] == pytest.approx(-264.0 / 18.0)


@pytest.mark.skipif(
    not os.path.exists(FILE_SEQ2), reason="Local particulate data files not present"
)
def test_particulate_sequence_reading_and_double_drop_alerts():
    batch = Batch(FILE_SEQ2, CARBON_13C)
    assert not batch.replicates.empty
    assert "d13c" in batch.replicates.columns
    assert "area_44" in batch.replicates.columns

    alerts = batch.alerts
    assert not alerts.empty

    reasons = " ".join(alerts["reason"].tolist())
    assert "Missing Sample Peak" in reasons or "autosampler drop failure" in reasons
    assert "Double Drop Suspected" in reasons or "Abnormal Area/Amount Ratio" in reasons

    flagged_rows = alerts["row"].tolist()
    assert 20 in flagged_rows
    assert 21 in flagged_rows


@pytest.mark.skipif(
    not os.path.exists(FILE_SEQ2), reason="Local particulate data files not present"
)
def test_blank_correction_seq2():
    batch = Batch(FILE_SEQ2, CARBON_13C)
    batch.exclude_rows([20, 21])
    batch.apply_blank_correction(blank_identifier="bco cap")

    assert batch.blank_correction_applied is True
    assert batch.blank_info["identifier"] == "bco cap"
    assert "d_blank_corrected" in batch.replicates.columns

    row9 = batch.replicates[batch.replicates["row"] == 9]
    assert not row9.empty
    d_corr_val = row9["working_value"].iloc[0]
    assert pytest.approx(d_corr_val, abs=0.01) == 8.562


@pytest.mark.skipif(
    not os.path.exists(FILE_SEQ1), reason="Local particulate data files not present"
)
def test_full_carbon_pipeline():
    batch = Batch(FILE_SEQ1, CARBON_13C)
    batch.exclude_rows([1, 2, 3, 4, 5, 21])

    batch.apply_blank_correction(blank_identifier="bco cap")
    batch.apply_linearity_correction(substance_name="ac benzoico")
    assert batch.linearity_correction_applied is True
    assert batch.linearity_slope < 0.0

    batch.set_anchors(["8541"])
    strategy = SinglePointOffset()
    batch.process(strategy)

    assert batch.summary is not None
    assert "NIST8541" in batch.summary.index
    assert "corrected_d13c" in batch.summary.columns

    nist_corr = batch.summary.loc["NIST8541", "corrected_d13c"]
    assert pytest.approx(nist_corr, abs=0.05) == -16.05
