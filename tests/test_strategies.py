"""
Unit tests for calibration strategies (SinglePointOffset, TwoPointLinear, MultiPointLinear)
and Kragten numerical uncertainty propagation.
"""
import pandas as pd
import pytest

from isotools.strategies import SinglePointOffset, TwoPointLinear, MultiPointLinear
from isotools.models import ReferenceMaterial


def test_two_point_fit_logic():
    """
    Verify slope/intercept calculation.
    Scenario:
      Std Low:  True=0,  Measured=10
      Std High: True=100, Measured=110
      Equation should be: True = 1.0 * (Raw) - 10
    """
    std_low = ReferenceMaterial("LOW", 0.0, 0.1)
    std_high = ReferenceMaterial("HIGH", 100.0, 0.1)
    refs = {"LOW": std_low, "HIGH": std_high}

    stats = pd.DataFrame(
        {"mean": [10.0, 110.0], "sem": [0.0, 0.0]}, index=["LOW", "HIGH"]
    )

    strategy = TwoPointLinear()
    strategy.fit(stats, refs)

    assert strategy.slope == pytest.approx(1.0)
    assert strategy.intercept == pytest.approx(10.0)


def test_single_point_offset_fit_and_propagate():
    """Verify SinglePointOffset fit, apply, and Kragten uncertainty propagation."""
    std = ReferenceMaterial("ANCHOR", -16.05, 0.04)
    refs = {"ANCHOR": std}
    stats = pd.DataFrame({"mean": [-15.05], "sem": [0.03]}, index=["ANCHOR"])

    strategy = SinglePointOffset()
    strategy.fit(stats, refs)

    # offset = raw - true = -15.05 - (-16.05) = +1.00
    assert strategy.offset == pytest.approx(1.00)
    assert strategy.slope == pytest.approx(1.0)
    assert strategy.intercept == pytest.approx(1.00)

    df = pd.DataFrame({"working_value": [-15.05, -20.0]})
    df_corr = strategy.apply(df, "working_value")
    assert df_corr["corrected_working_value"].iloc[0] == pytest.approx(-16.05)
    assert df_corr["corrected_working_value"].iloc[1] == pytest.approx(-21.00)

    summary = pd.DataFrame({"mean": [-20.0], "sem": [0.05]}, index=["Sample1"])
    prop = strategy.propagate(summary, target_col="d13c")
    assert prop.loc["Sample1", "corrected_d13c"] == pytest.approx(-21.00)
    # Combined unc = sqrt(0.05^2 + 0.03^2 + 0.04^2) = sqrt(0.0050) = 0.07071
    assert prop.loc["Sample1", "combined_uncertainty"] == pytest.approx(0.07071, abs=1e-4)


def test_multi_point_linear_fit_and_propagate():
    """Verify MultiPointLinear OLS fit, apply, and Kragten uncertainty propagation."""
    refs = {
        "S1": ReferenceMaterial("S1", 0.0, 0.1),
        "S2": ReferenceMaterial("S2", -50.0, 0.1),
        "S3": ReferenceMaterial("S3", -100.0, 0.1),
    }
    # Raw = 2.0 * True + 5.0 -> S1: 5.0, S2: -95.0, S3: -195.0
    stats = pd.DataFrame(
        {"mean": [5.0, -95.0, -195.0], "sem": [0.1, 0.1, 0.1]},
        index=["S1", "S2", "S3"],
    )

    strategy = MultiPointLinear()
    strategy.fit(stats, refs)

    assert strategy.slope == pytest.approx(2.0)
    assert strategy.intercept == pytest.approx(5.0)
    assert strategy.r_squared == pytest.approx(1.0)

    summary = pd.DataFrame({"mean": [-45.0], "sem": [0.2]}, index=["Unknown"])
    prop = strategy.propagate(summary, target_col="d2h")
    # True = (-45.0 - 5.0) / 2.0 = -25.0
    assert prop.loc["Unknown", "corrected_d2h"] == pytest.approx(-25.0)
    assert prop.loc["Unknown", "combined_uncertainty"] > 0.0


def test_kragten_propagation_structure():
    """
    Verify that uncertainty propagation returns higher uncertainty
    when input uncertainty increases.
    """
    strategy = TwoPointLinear()
    strategy.r1, strategy.r2 = 0, 10
    strategy.t1, strategy.t2 = 0, 10
    strategy.u_r1, strategy.u_r2 = 0.1, 0.1
    strategy.u_t1, strategy.u_t2 = 0.0, 0.0
    strategy.slope = 1.0
    strategy.intercept = 0.0

    summary = pd.DataFrame({"mean": [5.0, 5.0], "sem": [0.0, 1.0]}, index=["A", "B"])
    result = strategy.propagate(summary, target_col="val")

    assert "combined_uncertainty" in result.columns

    unc_a = result.loc["A", "combined_uncertainty"]
    unc_b = result.loc["B", "combined_uncertainty"]

    assert unc_b > unc_a
    assert unc_a > 0
