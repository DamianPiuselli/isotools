"""
Unit tests for single-isotope and dual-isotope HTML report generation.
"""
from unittest.mock import patch
import pandas as pd

from isotools import (
    Batch,
    NITROGEN,
    WATER_H,
    WATER_O,
    SinglePointOffset,
    TwoPointLinear,
    generate_dual_isotope_html_report,
)


@patch("isotools.core.IsodatReader")
def test_save_html_report(mock_reader_cls, tmp_path):
    data = {
        "row": [1, 2, 3, 4, 5],
        "sample_name": ["USGS32", "USGS34", "Unknown1", "Unknown1", "Unknown1"],
        "peak_nr": [2, 2, 2, 2, 2],
        "d15n": [180.1, -1.7, 10.5, 10.6, 10.4],
        "amp_28": [1000, 1000, 1000, 1000, 1000],
    }
    mock_reader_cls.return_value.read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS32", "USGS34"])
    batch.set_drift_monitors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    report_path = tmp_path / "report.html"
    batch.save_html_report(str(report_path))

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Isotools Report" in content
    assert "NITROGEN" in content or "Nitrogen" in content
    assert "plotly-2.35.2.min.js" in content
    assert "Drift Analysis" in content
    assert "Drift Correction Applied" in content
    assert "Calibration Curve" in content
    assert "Unknown1" in content


@patch("isotools.core.IsodatReader")
def test_report_no_processing(mock_reader_cls, tmp_path):
    data = {
        "row": [1, 2],
        "sample_name": ["S1", "S2"],
        "peak_nr": [2, 2],
        "d15n": [10.0, 10.1],
        "amp_28": [1000, 1000],
    }
    mock_reader_cls.return_value.read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=NITROGEN)
    report_path = tmp_path / "report_unprocessed.html"
    batch.save_html_report(str(report_path))

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Not Processed" in content


@patch("isotools.core.IsodatReader")
def test_report_no_drift_monitors(mock_reader_cls, tmp_path):
    data = {
        "row": [1, 2, 3],
        "sample_name": ["S1", "S2", "S3"],
        "peak_nr": [2, 2, 2],
        "d15n": [10.0, 10.1, 10.2],
        "amp_28": [1000, 1000, 1000],
    }
    mock_reader_cls.return_value.read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=NITROGEN)
    report_path = tmp_path / "report_no_drift.html"
    batch.save_html_report(str(report_path))

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Drift Analysis" not in content


@patch("isotools.core.IsodatReader")
def test_report_drift_monitors_no_correction(mock_reader_cls, tmp_path):
    data = {
        "row": [1, 2, 3],
        "sample_name": ["USGS32", "USGS34", "S1"],
        "peak_nr": [2, 2, 2],
        "d15n": [180.1, -1.7, 10.0],
        "amp_28": [1000, 1000, 1000],
    }
    mock_reader_cls.return_value.read.return_value = pd.DataFrame(data)

    batch = Batch("dummy.xls", config=NITROGEN)
    batch.set_anchors(["USGS32", "USGS34"])
    batch.set_drift_monitors(["USGS32", "USGS34"])
    batch.process(TwoPointLinear())

    report_path = tmp_path / "report_no_corr.html"
    batch.save_html_report(str(report_path))

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Drift Analysis" in content
    assert "No Drift Correction Applied" in content
    assert "Excluded rows: None" not in content


@patch("isotools.core.IsodatReader")
def test_generate_dual_isotope_html_report(mock_reader_cls, tmp_path):
    data_h = {
        "row": [1, 2, 3],
        "sample_name": ["Mar_H", "Sample1", "Sample1"],
        "peak_nr": [3, 3, 3],
        "d2h": [-0.5, -35.0, -35.2],
        "amp_2": [1000, 1000, 1000],
    }
    data_o = {
        "row": [1, 2, 3],
        "sample_name": ["Mar_O", "Sample1", "Sample1"],
        "peak_nr": [4, 4, 4],
        "d18o": [0.0, -5.0, -5.2],
        "amp_28": [1000, 1000, 1000],
    }

    mock_reader_cls.return_value.read.side_effect = [
        pd.DataFrame(data_h),
        pd.DataFrame(data_o),
    ]

    batch_h = Batch("dummy_h.xls", config=WATER_H)
    batch_h.set_anchors(["Mar_H"])
    batch_h.process(SinglePointOffset())

    batch_o = Batch("dummy_o.xls", config=WATER_O)
    batch_o.set_anchors(["Mar_O"])
    batch_o.process(SinglePointOffset())

    report_path = tmp_path / "dual_report.html"
    generate_dual_isotope_html_report(batch_h, batch_o, str(report_path))

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Dual Isotope" in content
    assert "Sample1" in content
