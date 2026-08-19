import os
import pytest
import pandas as pd
from isotools import Batch, NITROGEN, TwoPointLinear

def test_save_html_report(tmp_path):
    # 1. Setup a dummy batch
    data = {
        "row": [1, 2, 3, 4, 5],
        "sample_name": ["USGS32", "USGS34", "Unknown1", "Unknown1", "Unknown1"],
        "peak_nr": [2, 2, 2, 2, 2],
        "d15n": [180.1, -1.7, 10.5, 10.6, 10.4],
        "amp_28": [1000, 1000, 1000, 1000, 1000]
    }
    df = pd.DataFrame(data)
    
    # We need to mock the reader to return this DF
    class MockReader:
        def __init__(self, config): pass
        def read(self, *args, **kwargs): return df.copy()

    from isotools.core import IsodatReader
    import isotools.core
    original_reader = isotools.core.IsodatReader
    isotools.core.IsodatReader = MockReader

    try:
        batch = Batch("dummy.xls", config=NITROGEN)
        batch.set_anchors(["USGS32", "USGS34"])
        batch.set_drift_monitors(["USGS32", "USGS34"])
        batch.process(TwoPointLinear())

        # 2. Generate report
        report_path = tmp_path / "report.html"
        batch.save_html_report(str(report_path))

        # 3. Verify
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Isotools Report" in content
        assert "NITROGEN" in content or "Nitrogen" in content
        assert "plotly-2.35.2.min.js" in content
        assert "Drift Analysis" in content
        assert "Drift Correction Applied" in content
        assert "Calibration Curve" in content
        assert "Unknown1" in content

    finally:
        isotools.core.IsodatReader = original_reader

def test_report_no_processing(tmp_path):
    # Test that report can be generated even if not processed (though plots might be empty)
    data = {
        "row": [1, 2],
        "sample_name": ["S1", "S2"],
        "peak_nr": [2, 2],
        "d15n": [10.0, 10.1],
        "amp_28": [1000, 1000]
    }
    df = pd.DataFrame(data)
    
    class MockReader:
        def __init__(self, config): pass
        def read(self, *args, **kwargs): return df.copy()

    import isotools.core
    original_reader = isotools.core.IsodatReader
    isotools.core.IsodatReader = MockReader

    try:
        batch = Batch("dummy.xls", config=NITROGEN)
        report_path = tmp_path / "report_unprocessed.html"
        batch.save_html_report(str(report_path))
        
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Not Processed" in content
    finally:
        isotools.core.IsodatReader = original_reader

def test_report_no_drift_monitors(tmp_path):
    data = {
        "row": [1, 2, 3],
        "sample_name": ["S1", "S2", "S3"],
        "peak_nr": [2, 2, 2],
        "d15n": [10.0, 10.1, 10.2],
        "amp_28": [1000, 1000, 1000]
    }
    df = pd.DataFrame(data)
    
    class MockReader:
        def __init__(self, config): pass
        def read(self, *args, **kwargs): return df.copy()

    import isotools.core
    original_reader = isotools.core.IsodatReader
    isotools.core.IsodatReader = MockReader

    try:
        batch = Batch("dummy.xls", config=NITROGEN)
        # No drift monitors set
        report_path = tmp_path / "report_no_drift.html"
        batch.save_html_report(str(report_path))
        
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Drift Analysis" not in content
    finally:
        isotools.core.IsodatReader = original_reader

def test_report_drift_monitors_no_correction(tmp_path):
    data = {
        "row": [1, 2, 3],
        "sample_name": ["USGS32", "USGS34", "S1"],
        "peak_nr": [2, 2, 2],
        "d15n": [180.1, -1.7, 10.0],
        "amp_28": [1000, 1000, 1000]
    }
    df = pd.DataFrame(data)
    
    class MockReader:
        def __init__(self, config): pass
        def read(self, *args, **kwargs): return df.copy()

    import isotools.core
    original_reader = isotools.core.IsodatReader
    isotools.core.IsodatReader = MockReader

    try:
        batch = Batch("dummy.xls", config=NITROGEN)
        batch.set_anchors(["USGS32", "USGS34"])
        batch.set_drift_monitors(["USGS32", "USGS34"])
        # No drift correction applied
        batch.process(TwoPointLinear())
        
        report_path = tmp_path / "report_no_corr.html"
        batch.save_html_report(str(report_path))
        
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Drift Analysis" in content
        assert "No Drift Correction Applied" in content
    finally:
        isotools.core.IsodatReader = original_reader


def test_generate_dual_isotope_html_report(tmp_path):
    from isotools import WATER_H, WATER_O, SinglePointOffset, generate_dual_isotope_html_report

    data_h = {
        "row": [1, 2, 3],
        "sample_name": ["Mar_H", "Sample1", "Sample1"],
        "peak_nr": [3, 3, 3],
        "d2h": [-0.5, -35.0, -35.2],
        "amp_2": [1000, 1000, 1000]
    }
    data_o = {
        "row": [1, 2, 3],
        "sample_name": ["Mar_O", "Sample1", "Sample1"],
        "peak_nr": [4, 4, 4],
        "d18o": [0.0, -5.0, -5.2],
        "amp_28": [1000, 1000, 1000]
    }

    class MockReaderH:
        def __init__(self, config): pass
        def read(self, *args, **kwargs): return pd.DataFrame(data_h)

    class MockReaderO:
        def __init__(self, config): pass
        def read(self, *args, **kwargs): return pd.DataFrame(data_o)

    import isotools.core
    original_reader = isotools.core.IsodatReader

    try:
        isotools.core.IsodatReader = MockReaderH
        batch_h = Batch("dummy_h.xls", config=WATER_H)
        batch_h.set_anchors(["Mar_H"])
        batch_h.process(SinglePointOffset())

        isotools.core.IsodatReader = MockReaderO
        batch_o = Batch("dummy_o.xls", config=WATER_O)
        batch_o.set_anchors(["Mar_O"])
        batch_o.process(SinglePointOffset())

        report_path = tmp_path / "dual_report.html"
        generate_dual_isotope_html_report(batch_h, batch_o, str(report_path))

        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Dual Isotope" in content
        assert "Sample1" in content
    finally:
        isotools.core.IsodatReader = original_reader

