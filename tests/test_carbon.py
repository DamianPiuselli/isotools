"""
Unit and integration tests for Carbon (13C) processing, blank mass-balance correction,
and double drop anomaly detection on atmospheric particulate sequences.
"""
import os
import pytest
import pandas as pd

from isotools.config import CARBON_13C
from isotools.standards import NIST8541, get_standard
from isotools.core import Batch
from isotools.strategies.normalization import SinglePointOffset, TwoPointLinear


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


def test_particulate_sequence_reading_and_double_drop_alerts():
    batch = Batch(FILE_SEQ2, CARBON_13C)
    assert not batch.replicates.empty
    assert "d13c" in batch.replicates.columns
    assert "area_44" in batch.replicates.columns

    # Verify alerts table contains Missing Sample Peak and Double Drop
    alerts = batch.alerts
    assert not alerts.empty

    reasons = " ".join(alerts["reason"].tolist())
    assert "Missing Sample Peak" in reasons or "autosampler drop failure" in reasons
    assert "Double Drop Suspected" in reasons or "Abnormal Area/Amount Ratio" in reasons

    # Confirm row 20 is flagged for missing peak, row 21 for double drop
    flagged_rows = alerts["row"].tolist()
    assert 20 in flagged_rows
    assert 21 in flagged_rows


def test_blank_correction_seq2():
    batch = Batch(FILE_SEQ2, CARBON_13C)

    # Exclude problematic double drop row 21 & missing peak row 20 if needed
    batch.exclude_rows([20, 21])

    # Apply mass-balance blank correction using 'bco cap'
    batch.apply_blank_correction(blank_identifier="bco cap")

    assert batch.blank_correction_applied is True
    assert batch.blank_info["identifier"] == "bco cap"
    assert "d_blank_corrected" in batch.replicates.columns

    # Verify blank corrected delta for NIST 8541 in Row 9
    row9 = batch.replicates[batch.replicates["row"] == 9]
    assert not row9.empty
    # Raw value ~ 7.036, Blank corrected value ~ 8.562
    d_corr_val = row9["working_value"].iloc[0]
    assert pytest.approx(d_corr_val, abs=0.01) == 8.562


def test_full_carbon_pipeline():
    batch = Batch(FILE_SEQ1, CARBON_13C)

    # Exclude empty runs
    batch.exclude_rows([1, 21])

    # 1. Blank correction
    batch.apply_blank_correction(blank_identifier="bco cap")

    # 2. Set NIST8541 as Anchor
    batch.set_anchors(["8541"])

    # 3. Fit SinglePointOffset strategy
    strategy = SinglePointOffset()
    batch.process(strategy)

    assert batch.summary is not None
    assert "NIST8541" in batch.summary.index
    assert "corrected_d13c" in batch.summary.columns

    # Verify NIST8541 corrected mean is calibrated to -16.05
    nist_corr = batch.summary.loc["NIST8541", "corrected_d13c"]
    assert pytest.approx(nist_corr, abs=0.05) == -16.05
