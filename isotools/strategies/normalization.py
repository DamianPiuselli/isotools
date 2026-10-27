"""
Standard normalization strategies for IRMS data.
"""
from typing import Dict
import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from ..models import ReferenceMaterial
from ..utils.kragten import propagate_kragten_budget
from .abstract import CalibrationStrategy


def _append_budget_columns(
    summary_df: pd.DataFrame,
    var_meas_list: list,
    var_anchors_list: list,
    var_fit_list: list,
    slope: float,
) -> pd.DataFrame:
    """
    Combines calibration variance components with pre-calibration variance components
    (blank, linearity, drift) scaled by 1/slope^2, and computes percentage budget columns.
    """
    inv_m2 = 1.0 / (slope**2) if slope != 0 else 1.0
    n_rows = len(summary_df)

    u_blank_w = (
        summary_df["u_blank"].fillna(0.0).values
        if "u_blank" in summary_df.columns
        else np.zeros(n_rows)
    )
    u_lin_w = (
        summary_df["u_linearity"].fillna(0.0).values
        if "u_linearity" in summary_df.columns
        else np.zeros(n_rows)
    )
    u_drift_w = (
        summary_df["u_drift"].fillna(0.0).values
        if "u_drift" in summary_df.columns
        else np.zeros(n_rows)
    )

    var_meas = np.array(var_meas_list, dtype=float)
    var_anchors = np.array(var_anchors_list, dtype=float)
    var_fit = np.array(var_fit_list, dtype=float)
    var_blank = (u_blank_w**2) * inv_m2
    var_lin = (u_lin_w**2) * inv_m2
    var_drift = (u_drift_w**2) * inv_m2

    total_var = var_meas + var_anchors + var_fit + var_blank + var_lin + var_drift
    u_combined = np.sqrt(total_var)

    summary_df["combined_uncertainty"] = u_combined

    # Avoid division by zero when total_var == 0
    safe_total = np.where(total_var > 0, total_var, 1.0)
    summary_df["pct_measurement"] = np.where(total_var > 0, 100.0 * var_meas / safe_total, 0.0)
    summary_df["pct_anchors"] = np.where(total_var > 0, 100.0 * var_anchors / safe_total, 0.0)
    summary_df["pct_fit_residual"] = np.where(total_var > 0, 100.0 * var_fit / safe_total, 0.0)
    summary_df["pct_blank"] = np.where(total_var > 0, 100.0 * var_blank / safe_total, 0.0)
    summary_df["pct_linearity"] = np.where(total_var > 0, 100.0 * var_lin / safe_total, 0.0)
    summary_df["pct_drift"] = np.where(total_var > 0, 100.0 * var_drift / safe_total, 0.0)

    return summary_df


class TwoPointLinear(CalibrationStrategy):
    """
    Standard 2-Point Linear Normalization.

    Equation: y = mx + b
    Slope (m) = (R2 - R1) / (T2 - T1)
    """

    def __init__(self):
        super().__init__()
        self.r1 = 0.0
        self.u_r1 = 0.0
        self.r2 = 0.0
        self.u_r2 = 0.0
        self.t1 = 0.0
        self.u_t1 = 0.0
        self.t2 = 0.0
        self.u_t2 = 0.0

    def fit(self, anchor_stats: pd.DataFrame, refs: Dict[str, ReferenceMaterial]):
        """Fits the 2-point linear model."""
        if len(anchor_stats) != 2:
            raise ValueError(
                f"TwoPointLinear requires exactly 2 anchor standards. Found {len(anchor_stats)}."
            )

        sorted_names = sorted(anchor_stats.index, key=lambda n: refs[n].d_true)
        name1, name2 = sorted_names[0], sorted_names[1]

        self.r1 = anchor_stats.loc[name1, "mean"]
        self.u_r1 = anchor_stats.loc[name1, "sem"]
        self.r2 = anchor_stats.loc[name2, "mean"]
        self.u_r2 = anchor_stats.loc[name2, "sem"]

        self.t1 = refs[name1].d_true
        self.u_t1 = refs[name1].u_true
        self.t2 = refs[name2].d_true
        self.u_t2 = refs[name2].u_true

        self.slope = (self.r2 - self.r1) / (self.t2 - self.t1)
        self.intercept = self.r1 - (self.slope * self.t1)
        self.r_squared = 1.0

    def apply(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """Vectorized correction for row-level data."""
        df = df.copy()
        df[f"corrected_{target_col}"] = (df[target_col] - self.intercept) / self.slope
        return df

    def propagate(self, summary_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """Runs Kragten propagation and records variance budget components."""
        var_meas_list = []
        var_anchors_list = []
        var_fit_list = []

        curve_params = [self.r1, self.r2, self.t1, self.t2]
        curve_uncs = [self.u_r1, self.u_r2, self.u_t1, self.u_t2]
        param_names = ["measurement", "anchors", "anchors", "anchors", "anchors"]

        def prediction_model(args):
            r_s, r1, r2, t1, t2 = args
            m = (r2 - r1) / (t2 - t1)
            b = r1 - (m * t1)
            return (r_s - b) / m

        for _, row in summary_df.iterrows():
            r_samp = row["mean"]
            u_samp = row["sem"]

            _, _, contribs = propagate_kragten_budget(
                model_func=prediction_model,
                params=[r_samp] + curve_params,
                uncertainties=[u_samp] + curve_uncs,
                param_names=param_names,
            )
            var_meas_list.append(contribs["measurement"])
            var_anchors_list.append(contribs["anchors"])
            var_fit_list.append(0.0)

        summary_df = summary_df.copy()
        summary_df[f"corrected_{target_col}"] = (
            summary_df["mean"] - self.intercept
        ) / self.slope

        return _append_budget_columns(
            summary_df, var_meas_list, var_anchors_list, var_fit_list, self.slope
        )


class MultiPointLinear(CalibrationStrategy):
    """
    Multi-Point Linear Normalization using Ordinary Least Squares (OLS).

    Useful when 3+ anchor standards are used. Includes OLS residual standard error
    (s_y/x) in the uncertainty budget when N >= 3.
    """

    def __init__(self):
        super().__init__()
        self.anchors_data = []
        self.residual_std_err = 0.0

    def fit(self, anchor_stats: pd.DataFrame, refs: Dict[str, ReferenceMaterial]):
        """Fits the multi-point linear model using OLS."""
        self.anchors_data = []
        x_raw = []
        y_true = []

        for name in anchor_stats.index:
            std = refs[name]
            raw_mean = anchor_stats.loc[name, "mean"]
            raw_sem = anchor_stats.loc[name, "sem"]
            true_val = std.d_true
            true_unc = std.u_true

            self.anchors_data.append(
                {
                    "name": name,
                    "raw_mean": raw_mean,
                    "raw_sem": raw_sem,
                    "true_val": true_val,
                    "true_unc": true_unc,
                }
            )
            x_raw.append(raw_mean)
            y_true.append(true_val)

        if len(x_raw) < 2:
            raise ValueError("MultiPointLinear requires at least 2 anchor standards.")

        slope, intercept, r_value, _, _ = sp_stats.linregress(y_true, x_raw)
        self.slope = float(slope)
        self.intercept = float(intercept)
        self.r_squared = float(r_value**2)

        if len(x_raw) >= 3:
            y_arr = np.array(y_true, dtype=float)
            x_arr = np.array(x_raw, dtype=float)
            residuals = x_arr - (self.slope * y_arr + self.intercept)
            self.residual_std_err = float(np.sqrt(np.sum(residuals**2) / (len(x_raw) - 2)))
        else:
            self.residual_std_err = 0.0

    def apply(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """Vectorized correction for row-level data."""
        df = df.copy()
        df[f"corrected_{target_col}"] = (df[target_col] - self.intercept) / self.slope
        return df

    def propagate(self, summary_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """Runs Kragten propagation and includes OLS residual fit scatter."""
        var_meas_list = []
        var_anchors_list = []
        var_fit_list = []

        params = []
        uncertainties = []
        param_names = ["measurement"]
        for anchor in self.anchors_data:
            params.extend([anchor["raw_mean"], anchor["true_val"]])
            uncertainties.extend([anchor["raw_sem"], anchor["true_unc"]])
            param_names.extend(["anchors", "anchors"])

        def prediction_model(args):
            r_s = args[0]
            anchors = args[1:]
            x_raw_anchors = anchors[0::2]
            y_true_anchors = anchors[1::2]
            m, b = np.polyfit(y_true_anchors, x_raw_anchors, 1)
            return (r_s - b) / m

        n_anc = len(self.anchors_data)
        fit_var_const = (
            (self.residual_std_err / (abs(self.slope) * np.sqrt(n_anc))) ** 2
            if n_anc >= 3 and self.slope != 0
            else 0.0
        )

        for _, row in summary_df.iterrows():
            r_samp = row["mean"]
            u_samp = row["sem"]

            _, _, contribs = propagate_kragten_budget(
                model_func=prediction_model,
                params=[r_samp] + params,
                uncertainties=[u_samp] + uncertainties,
                param_names=param_names,
            )
            var_meas_list.append(contribs["measurement"])
            var_anchors_list.append(contribs["anchors"])
            var_fit_list.append(fit_var_const)

        summary_df = summary_df.copy()
        summary_df[f"corrected_{target_col}"] = (
            summary_df["mean"] - self.intercept
        ) / self.slope

        return _append_budget_columns(
            summary_df, var_meas_list, var_anchors_list, var_fit_list, self.slope
        )


class SinglePointOffset(CalibrationStrategy):
    """
    Single-Point Offset Normalization (Shift/Offset Correction).

    Formula:
        offset = raw_anchor_mean - true_anchor_val
        corrected = raw_value - offset
    """

    def __init__(self):
        super().__init__()
        self.r_anchor = 0.0
        self.u_r_anchor = 0.0
        self.t_anchor = 0.0
        self.u_t_anchor = 0.0
        self.offset = 0.0

    def fit(self, anchor_stats: pd.DataFrame, refs: Dict[str, ReferenceMaterial]):
        """Fits the single-point offset model."""
        if len(anchor_stats) != 1:
            raise ValueError(
                f"SinglePointOffset requires exactly 1 anchor standard. Found {len(anchor_stats)}."
            )
        name = anchor_stats.index[0]
        std = refs[name]

        self.r_anchor = anchor_stats.loc[name, "mean"]
        self.u_r_anchor = anchor_stats.loc[name, "sem"]
        self.t_anchor = std.d_true
        self.u_t_anchor = std.u_true

        self.offset = self.r_anchor - self.t_anchor
        self.slope = 1.0
        self.intercept = self.offset
        self.r_squared = 1.0

    def apply(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """Vectorized correction subtracting constant offset."""
        df = df.copy()
        df[f"corrected_{target_col}"] = df[target_col] - self.offset
        return df

    def propagate(self, summary_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """Runs Kragten uncertainty propagation for single-point offset."""
        var_meas_list = []
        var_anchors_list = []
        var_fit_list = []

        def prediction_model(args):
            r_s, r_anc, t_anc = args
            return r_s - (r_anc - t_anc)

        for _, row in summary_df.iterrows():
            r_samp = row["mean"]
            u_samp = row["sem"]

            _, _, contribs = propagate_kragten_budget(
                model_func=prediction_model,
                params=[r_samp, self.r_anchor, self.t_anchor],
                uncertainties=[u_samp, self.u_r_anchor, self.u_t_anchor],
                param_names=["measurement", "anchors", "anchors"],
            )
            var_meas_list.append(contribs["measurement"])
            var_anchors_list.append(contribs["anchors"])
            var_fit_list.append(0.0)

        summary_df = summary_df.copy()
        summary_df[f"corrected_{target_col}"] = summary_df["mean"] - self.offset

        return _append_budget_columns(
            summary_df, var_meas_list, var_anchors_list, var_fit_list, self.slope
        )
