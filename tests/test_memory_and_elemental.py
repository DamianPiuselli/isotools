"""
Tests for Phase 4 (Water Isotope Memory Correction & First-k Injection Filtering)
and Phase 5 (Elemental Mass Fraction %C, %N, and C/N Atomic Ratios).
"""

import os
import tempfile
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest

from isotools.config import CARBON_13C, NITROGEN, WATER_O
from isotools.core import Batch
from isotools.reporting.html import generate_dual_isotope_html_report
from isotools.strategies.normalization import SinglePointOffset


@patch("isotools.utils.readers.pd.read_excel")
def test_exclude_first_injections(mock_read):
    """Verify exclude_first_injections marks the first k injections of each contiguous vial run."""
    rows = []
    # Vial 1: 6 injections of W1
    for i in range(1, 7):
        rows.append({
            "Row": i,
            "Identifier 1": "W1",
            "Peak Nr": 4,
            "Ampl 28": 2000.0,
            "d 18O/16O": -10.0 + (0.5 if i <= 2 else 0.0),
            "Area 28": 25.0,
        })
    # Vial 2: 6 injections of W2
    for i in range(7, 13):
        rows.append({
            "Row": i,
            "Identifier 1": "W2",
            "Peak Nr": 4,
            "Ampl 28": 2000.0,
            "d 18O/16O": -30.0 + (2.0 if i <= 8 else 0.0),
            "Area 28": 25.0,
        })
    # Vial 3: W1 again (new contiguous block)
    for i in range(13, 17):
        rows.append({
            "Row": i,
            "Identifier 1": "W1",
            "Peak Nr": 4,
            "Ampl 28": 2000.0,
            "d 18O/16O": -10.0,
            "Area 28": 25.0,
        })

    mock_read.return_value = pd.DataFrame(rows)
    batch = Batch("dummy.xls", config=WATER_O)
    batch.exclude_first_injections(2)

    excluded_rows = batch.replicates[batch.replicates["excluded"]]["row"].tolist()
    assert excluded_rows == [1, 2, 7, 8, 13, 14]


@patch("isotools.utils.readers.pd.read_excel")
def test_apply_memory_correction_manual_and_auto(mock_read):
    """Verify Gröning (2011) memory correction recovers true uncontaminated values."""
    true_w1 = 0.0
    true_w2 = -40.0
    true_s1 = -10.0
    coeffs = [0.08, 0.02]

    # Build synthetic sequence with exact Gröning vial-to-vial carryover model:
    # d_meas(j) = (1 - m_j)*d_true + m_j*d_prev_vial_final
    vials = [("W1", true_w1, 6), ("W2", true_w2, 6), ("S1", true_s1, 6)]
    rows = []
    row_counter = 1
    prev_vial_true = None

    for ident, true_val, n_inj in vials:
        for j in range(n_inj):
            if prev_vial_true is not None and j < len(coeffs):
                m_j = coeffs[j]
                d_meas = (1.0 - m_j) * true_val + m_j * prev_vial_true
            else:
                d_meas = true_val
            rows.append({
                "Row": row_counter,
                "Identifier 1": ident,
                "Peak Nr": 4,
                "Ampl 28": 2500.0,
                "d 18O/16O": d_meas,
                "Area 28": 30.0,
            })
            row_counter += 1
        prev_vial_true = true_val

    df = pd.DataFrame(rows)

    # 1. Manual coefficients
    mock_read.return_value = df.copy()
    batch_manual = Batch("dummy.xls", config=WATER_O)
    batch_manual.apply_memory_correction(coefficients=coeffs)
    assert "d_memory_corrected" in batch_manual.replicates.columns
    w2_corr = batch_manual.replicates[batch_manual.replicates["sample_name"] == "W2"]["d_memory_corrected"]
    s1_corr = batch_manual.replicates[batch_manual.replicates["sample_name"] == "S1"]["d_memory_corrected"]
    np.testing.assert_allclose(w2_corr.values, true_w2, atol=1e-6)
    np.testing.assert_allclose(s1_corr.values, true_s1, atol=1e-6)

    # 2. Auto-estimated coefficients from step changes
    mock_read.return_value = df.copy()
    batch_auto = Batch("dummy.xls", config=WATER_O)
    batch_auto.apply_memory_correction(coefficients=None, max_injections=2)
    est_coeffs = batch_auto.memory_info["coefficients"]
    assert est_coeffs[0] == pytest.approx(coeffs[0], abs=1e-3)
    assert est_coeffs[1] == pytest.approx(coeffs[1], abs=1e-3)

    w2_raw_std = batch_auto.replicates[batch_auto.replicates["sample_name"] == "W2"]["d18o"].std()
    w2_auto_std = batch_auto.replicates[batch_auto.replicates["sample_name"] == "W2"]["d_memory_corrected"].std()
    assert w2_auto_std < w2_raw_std * 0.01


@patch("isotools.utils.readers.pd.read_excel")
def test_calibrate_elemental_composition_and_dual_cn_ratio(mock_read):
    """Verify elemental %C and %N calibration and dual-isotope C/N mass and atomic ratios."""
    # Acetanilide: %C = 71.09, %N = 10.36 -> C/N mass = 6.862, C/N atomic = 8.002
    # Suppose k_C = 0.02 mg C / (V s), k_N = 0.01 mg N / (V s)
    df_c = pd.DataFrame([
        {"Row": 1, "Identifier 1": "USGS40", "Peak Nr": 3, "Ampl 44": 2000.0, "d 13C/12C": -26.39, "Area 44": 20.395, "Amount": 1.0},
        {"Row": 2, "Identifier 1": "USGS40", "Peak Nr": 3, "Ampl 44": 2000.0, "d 13C/12C": -26.39, "Area 44": 40.790, "Amount": 2.0},
        {"Row": 3, "Identifier 1": "Acetanilide", "Peak Nr": 3, "Ampl 44": 2500.0, "d 13C/12C": -29.53, "Area 44": 35.545, "Amount": 1.0},
        {"Row": 4, "Identifier 1": "Sample1", "Peak Nr": 3, "Ampl 44": 2200.0, "d 13C/12C": -25.00, "Area 44": 35.545, "Amount": 1.0},
        {"Row": 5, "Identifier 1": "Sample1", "Peak Nr": 3, "Ampl 44": 2200.0, "d 13C/12C": -25.10, "Area 44": 35.545, "Amount": 1.0},
    ])
    df_n = pd.DataFrame([
        {"Row": 1, "Identifier 1": "USGS40", "Peak Nr": 2, "Ampl 28": 1500.0, "d 15N/14N": -4.52, "Area 28": 9.52, "Amount": 1.0},
        {"Row": 2, "Identifier 1": "USGS40", "Peak Nr": 2, "Ampl 28": 1500.0, "d 15N/14N": -4.52, "Area 28": 19.04, "Amount": 2.0},
        {"Row": 3, "Identifier 1": "Acetanilide", "Peak Nr": 2, "Ampl 28": 1600.0, "d 15N/14N": 1.18, "Area 28": 10.36, "Amount": 1.0},
        {"Row": 4, "Identifier 1": "Sample1", "Peak Nr": 2, "Ampl 28": 1600.0, "d 15N/14N": 5.00, "Area 28": 10.36, "Amount": 1.0},
        {"Row": 5, "Identifier 1": "Sample1", "Peak Nr": 2, "Ampl 28": 1600.0, "d 15N/14N": 5.10, "Area 28": 10.36, "Amount": 1.0},
    ])

    mock_read.return_value = df_c
    batch_c = Batch("dummy_c.xls", config=CARBON_13C)
    batch_c.set_anchors(["USGS40"])
    batch_c.set_controls(["Acetanilide"])
    batch_c.calibrate_elemental_composition()
    batch_c.process(SinglePointOffset())

    mock_read.return_value = df_n
    batch_n = Batch("dummy_n.xls", config=NITROGEN)
    batch_n.set_anchors(["USGS40"])
    batch_n.set_controls(["Acetanilide"])
    batch_n.calibrate_elemental_composition()
    batch_n.process(SinglePointOffset())

    assert "weight_pct_C" in batch_c.replicates.columns
    assert "weight_pct_C" in batch_c.report.columns
    assert batch_c.report.loc["Sample1", "weight_pct_C"] == pytest.approx(71.09, rel=1e-3)

    assert "weight_pct_N" in batch_n.replicates.columns
    assert "weight_pct_N" in batch_n.report.columns
    assert batch_n.report.loc["Sample1", "weight_pct_N"] == pytest.approx(10.36, rel=1e-3)

    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "dual_cn.html")
        generate_dual_isotope_html_report(batch_c, batch_n, html_path)
        with open(html_path, "r", encoding="utf-8") as f:
            html_text = f.read()
        assert "CN_atomic_ratio" in html_text
        assert "CN_mass_ratio" in html_text
        # Acetanilide C8H9NO has mass C/N = 6.86 and atomic C/N = 8.0
        assert "6.86" in html_text
        assert "8.0" in html_text
