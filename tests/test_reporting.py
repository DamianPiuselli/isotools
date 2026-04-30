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
        batch.process(TwoPointLinear())

        # 2. Generate report
        report_path = tmp_path / "report.html"
        batch.save_html_report(str(report_path))

        # 3. Verify
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Isotools Report" in content
        assert "NITROGEN" in content or "Nitrogen" in content
        assert "plotly-latest.min.js" in content
        assert "Drift Analysis" in content
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
