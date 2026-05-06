"""
Standard normalization strategies for IRMS data.
"""
from typing import Dict
import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from ..models import ReferenceMaterial
from ..utils.kragten import propagate_kragten
from .abstract import CalibrationStrategy


class TwoPointLinear(CalibrationStrategy):
    """
    Standard 2-Point Linear Normalization.

    Equation: y = mx + b
    Slope (m) = (T2 - T1) / (R2 - R1)
    """

    def __init__(self):
        super().__init__()
        # State to store fitted parameters and their uncertainties
        self.r1 = 0.0
        self.u_r1 = 0.0  # Raw Std 1
        self.r2 = 0.0
        self.u_r2 = 0.0  # Raw Std 2
        self.t1 = 0.0
        self.u_t1 = 0.0  # True Std 1
        self.t2 = 0.0
        self.u_t2 = 0.0  # True Std 2

    def fit(self, anchor_stats: pd.DataFrame, refs: Dict[str, ReferenceMaterial]):
        """
        Fits the 2-point linear model.

        Args:
            anchor_stats: Summary stats for anchors.
            refs: Dictionary of ReferenceMaterial objects.
        """
        if len(anchor_stats) != 2:
            raise ValueError(
                f"TwoPointLinear requires exactly 2 anchor standards. Found {len(anchor_stats)}."
            )

        # Sort by expected delta to ensure consistency (Low -> High)
        # This helps identify which is R1/T1 and R2/T2 deterministically
        sorted_names = sorted(anchor_stats.index, key=lambda n: refs[n].d_true)
        name1, name2 = sorted_names[0], sorted_names[1]

        # 1. Capture Raw Values (Measured)
        self.r1 = anchor_stats.loc[name1, "mean"]
        self.u_r1 = anchor_stats.loc[name1, "sem"]
        self.r2 = anchor_stats.loc[name2, "mean"]
        self.u_r2 = anchor_stats.loc[name2, "sem"]

        # 2. Capture True Values (ReferenceMaterial)
        self.t1 = refs[name1].d_true
        self.u_t1 = refs[name1].u_true
        self.t2 = refs[name2].d_true
        self.u_t2 = refs[name2].u_true

        # 3. Calculate Nominal Slope/Intercept (Instrument Fit: Raw = m * True + b)
        # m = (r2 - r1) / (t2 - t1)
        self.slope = (self.r2 - self.r1) / (self.t2 - self.t1)
        self.intercept = self.r1 - (self.slope * self.t1)
        self.r_squared = 1.0

    def apply(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """
        Vectorized correction for raw data visualization.

        Args:
            df: Input DataFrame.
            target_col: Name of the column to correct.
        """
        df = df.copy()
        # Rearranged from Raw = m * True + b -> True = (Raw - b) / m
        df[f"corrected_{target_col}"] = (df[target_col] - self.intercept) / self.slope
        return df

    def propagate(self, summary_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """
        Runs Kragten propagation for every sample in the summary table.

        Args:
            summary_df: Aggregated sample stats.
            target_col: Name of the original target column.
        """
        results = []

        # The list of parameters defining the curve (Systematic Errors)
        # Order: [R1, R2, T1, T2]
        curve_params = [self.r1, self.r2, self.t1, self.t2]
        curve_uncs = [self.u_r1, self.u_r2, self.u_t1, self.u_t2]

        for _, row in summary_df.iterrows():
            r_samp = row["mean"]
            u_samp = row["sem"]

            # Full Parameter Set for this sample: [R_samp, R1, R2, T1, T2]
            # Uncertainty Set: [u_samp, u_r1, u_r2, u_t1, u_t2]

            # Define the equation f(args) -> true_delta
            def prediction_model(args):
                r_s, r1, r2, t1, t2 = args
                m = (r2 - r1) / (t2 - t1)
                b = r1 - (m * t1)
                return (r_s - b) / m

            _, unc = propagate_kragten(
                model_func=prediction_model,
                params=[r_samp] + curve_params,
                uncertainties=[u_samp] + curve_uncs,
            )
            results.append(unc)

        summary_df = summary_df.copy()
        summary_df["combined_uncertainty"] = results

        # Also ensure the corrected mean is set using the rigorous calculation (or just slope/intercept)
        # Usually recalculating with slope/intercept is fine for the mean.
        summary_df[f"corrected_{target_col}"] = (
            summary_df["mean"] - self.intercept
        ) / self.slope

        return summary_df


class MultiPointLinear(CalibrationStrategy):
    """
    Multi-Point Linear Normalization using Ordinary Least Squares (OLS).

    Useful when 3+ anchor standards are used.
    """

    def __init__(self):
        super().__init__()
        self.anchors_data = []  # List of dicts with raw_mean, raw_sem, true_val, true_unc

    def fit(self, anchor_stats: pd.DataFrame, refs: Dict[str, ReferenceMaterial]):
        """
        Fits the multi-point linear model using OLS.

        Args:
            anchor_stats: Summary stats for anchors.
            refs: Dictionary of ReferenceMaterial objects.
        """
        self.anchors_data = []
        x_raw = []
        y_true = []

        for name in anchor_stats.index:
            std = refs[name]
            raw_mean = anchor_stats.loc[name, "mean"]
            raw_sem = anchor_stats.loc[name, "sem"]
            true_val = std.d_true
            true_unc = std.u_true

            self.anchors_data.append({
                "name": name,
                "raw_mean": raw_mean,
                "raw_sem": raw_sem,
                "true_val": true_val,
                "true_unc": true_unc
            })
            x_raw.append(raw_mean)
            y_true.append(true_val)

        if len(x_raw) < 2:
            raise ValueError("MultiPointLinear requires at least 2 anchor standards.")

        # OLS fit (Instrument Fit: Raw = m * True + b)
        # We use scipy.stats.linregress to get R2 as well
        slope, intercept, r_value, _, _ = sp_stats.linregress(y_true, x_raw)
        self.slope = slope
        self.intercept = intercept
        self.r_squared = r_value**2

    def apply(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """
        Vectorized correction for raw data visualization.

        Args:
            df: Input DataFrame.
            target_col: Name of the column to correct.
        """
        df = df.copy()
        # True = (Raw - b) / m
        df[f"corrected_{target_col}"] = (df[target_col] - self.intercept) / self.slope
        return df

    def propagate(self, summary_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """
        Runs Kragten propagation for every sample in the summary table.

        Args:
            summary_df: Aggregated sample stats.
            target_col: Name of the original target column.
        """
        results = []

        # Parameters for Kragten: [R_samp, R1, T1, R2, T2, ..., Rn, Tn]
        params = []
        uncertainties = []
        for anchor in self.anchors_data:
            params.extend([anchor["raw_mean"], anchor["true_val"]])
            uncertainties.extend([anchor["raw_sem"], anchor["true_unc"]])

        def prediction_model(args):
            r_s = args[0]
            anchors = args[1:]
            x_raw_anchors = anchors[0::2]
            y_true_anchors = anchors[1::2]
            # Re-fit OLS inside Kragten for perturbation
            # Raw = m * True + b
            m, b = np.polyfit(y_true_anchors, x_raw_anchors, 1)
            return (r_s - b) / m

        for _, row in summary_df.iterrows():
            r_samp = row["mean"]
            u_samp = row["sem"]

            _, unc = propagate_kragten(
                model_func=prediction_model,
                params=[r_samp] + params,
                uncertainties=[u_samp] + uncertainties,
            )
            results.append(unc)

        summary_df = summary_df.copy()
        summary_df["combined_uncertainty"] = results
        summary_df[f"corrected_{target_col}"] = (
            summary_df["mean"] - self.intercept
        ) / self.slope

        return summary_df
