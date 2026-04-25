# tests/test_strategies.py
import pandas as pd
import pytest
from isotools.strategies import TwoPointLinear
from isotools.models import ReferenceMaterial


def test_two_point_fit_logic():
    """
    Verify slope/intercept calculation.
    Scenario:
      Std Low:  True=0,  Measured=10
      Std High: True=100, Measured=110
      Equation should be: True = 1.0 * (Raw) - 10
    """
    # 1. Setup Standards
    std_low = ReferenceMaterial("LOW", 0.0, 0.1)
    std_high = ReferenceMaterial("HIGH", 100.0, 0.1)
    refs = {"LOW": std_low, "HIGH": std_high}

    # 2. Setup Input Stats (Mean/SEM)
    # Index must match standard names
    stats = pd.DataFrame(
        {"mean": [10.0, 110.0], "sem": [0.0, 0.0]}, index=["LOW", "HIGH"]
    )

    # 3. Fit
    strategy = TwoPointLinear()
    strategy.fit(stats, refs)

    # 4. Check Parameters (Instrument Fit: Raw = m * True + b)
    # Raw = 1.0 * True + 10.0
    assert strategy.slope == pytest.approx(1.0)
    assert strategy.intercept == pytest.approx(10.0)


def test_kragten_propagation_structure():
    """
    Verify that uncertainty propagation returns higher uncertainty
    when input uncertainty increases.
    """
    strategy = TwoPointLinear()
    # Manually seed parameters (y = 1x + 0)
    strategy.r1, strategy.r2 = 0, 10
    strategy.t1, strategy.t2 = 0, 10
    strategy.u_r1, strategy.u_r2 = 0.1, 0.1  # Small unc in standards
    strategy.u_t1, strategy.u_t2 = 0.0, 0.0

    # Recalculate slope/int internally
    strategy.slope = 1.0
    strategy.intercept = 0.0

    # Create dummy summary df
    # Sample A: Mean=5, SEM=0 (Perfect precision)
    # Sample B: Mean=5, SEM=1 (High noise)
    summary = pd.DataFrame({"mean": [5.0, 5.0], "sem": [0.0, 1.0]}, index=["A", "B"])

    result = strategy.propagate(summary, target_col="val")

    # Assertions
    assert "combined_uncertainty" in result.columns

    # Sample B (High SEM) should have higher uncertainty than A
    unc_a = result.loc["A", "combined_uncertainty"]
    unc_b = result.loc["B", "combined_uncertainty"]

    assert unc_b > unc_a
    # Sample A uncertainty comes purely from the Curve (Systematic)
    assert unc_a > 0
