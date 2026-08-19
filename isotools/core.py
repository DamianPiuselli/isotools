"""
Core processing logic for IRMS data batches.
"""
import warnings
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats as sp_stats

from .config import SystemConfig
from .utils.readers import IsodatReader
from .models import ReferenceMaterial
from .standards import get_standard
from .strategies.abstract import CalibrationStrategy
from .reporting.html import generate_html_report


class Batch:
    """
    The central object representing a single IRMS run/sequence.

    Manages the lifecycle of data from Raw -> Cleaned -> Calibrated -> Reported.
    """

    def __init__(self, filepath: str, config: SystemConfig, sheet_name: int | str = 0):
        """
        Initializes a new Batch from an Isodat file.

        Args:
            filepath: Path to the .xls or .xlsx Isodat file.
            config: SystemConfig defining the isotope system.
            sheet_name: Name or index of the Excel sheet to read.
        """
        self.config = config
        self.filepath = filepath

        # 1. Load the Raw Data (Replicates Table)
        # We add an 'excluded' flag column immediately
        reader = IsodatReader(config)
        self.replicates = reader.read(filepath, sheet_name=sheet_name)
        self.replicates["excluded"] = False

        # Initialize working_value as a copy of the raw target
        self.replicates["working_value"] = self.replicates[config.target_column].copy()

        # 2. State Containers
        self.anchors: Dict[str, ReferenceMaterial] = {}  # Used for calibration
        self.controls: Dict[str, ReferenceMaterial] = {}  # Used for QC/Trueness
        self.drift_monitors: Dict[str, ReferenceMaterial] = {}  # Used for Drift Check
        self.drift_correction_applied = False
        self.drift_monitor_used: Optional[str] = None
        self.blank_correction_applied = False
        self.blank_info: Optional[Dict] = None
        self.linearity_correction_applied: bool = False
        self.linearity_slope: Optional[float] = None
        self.linearity_substance_used: Optional[str] = None
        self.linearity_area_ref: Optional[float] = None
        self.linearity_info: Optional[Dict] = None
        self.excluded_rows_list: List[int] = []
        self.use_method_precision: bool = False
        self.summary: Optional[pd.DataFrame] = None
        self.strategy: Optional[CalibrationStrategy] = None
        self._alerts: pd.DataFrame = pd.DataFrame(columns=["row", "sample_name", "reason"])



        # 3. Initial Diagnostics
        self.detect_outliers()
        self.initial_alerts: pd.DataFrame = self._alerts.copy()
        if not self._alerts.empty:
            warnings.warn(
                f"Detected {len(self._alerts)} suspicious data points on initial load. "
                "Check the .alerts property for details."
            )


    @property
    def data_view(self) -> pd.DataFrame:
        """Returns the full raw data for preliminary analysis and inspection."""
        return self.replicates

    @property
    def alerts(self) -> pd.DataFrame:
        """Returns a table of flagged outliers and problematic data."""
        return self._alerts

    def detect_outliers(self):
        """
        Runs automatic diagnostics to identify suspicious data points.

        1. Missing Sample Peak / Autosampler Drop Failure Check.
        2. Double Drop / Abnormal Response Factor Check (Area/Amount).
        3. Range Check: Outside expected environmental values (on normalized data).
        4. Precision Check: Sample SD > 3x method precision (on raw/drift-corrected data).
        5. Amplitude Check: Amplitude < 50% or > 200% of run median.
        """
        alerts = []
        valid = self.replicates[~self.replicates["excluded"]].copy()

        # --- 0. Missing Sample Peak Check ---
        missing_info = self.replicates.attrs.get("missing_sample_rows_info", {})
        missing_rows_list = sorted(list(missing_info.keys()))
        for r, name in missing_info.items():
            alerts.append(
                {
                    "row": r,
                    "sample_name": name,
                    "reason": f"Missing Sample Peak: No sample peak detected for Row {r} ({name}). Suspected autosampler drop failure.",
                }
            )

        if valid.empty:
            self._alerts = pd.DataFrame(alerts)
            if not self._alerts.empty:
                self._alerts = pd.DataFrame(alerts).drop_duplicates()
            return

        # --- 0b. Double Drop / Response Anomaly Check ---
        # Find area column
        possible_areas = []
        if self.config.amplitude_column:
            suffix = self.config.amplitude_column.split("_")[-1]
            possible_areas.append(f"area_{suffix}")
        possible_areas.extend(["area_44", "area_28", "area_2", "area_all"])

        area_col = None
        for col in possible_areas:
            if col in valid.columns:
                area_col = col
                break

        if "amount" in valid.columns and area_col:
            # Filter rows with valid positive amount and area
            weighed = valid[(valid["amount"].notna()) & (valid["amount"] > 0) & (valid[area_col].notna())].copy()
            if not weighed.empty:
                weighed["response"] = weighed[area_col] / weighed["amount"]
                median_resp = weighed["response"].median()

                if median_resp > 0:
                    high_resp = weighed[weighed["response"] > 1.5 * median_resp]
                    for _, row in high_resp.iterrows():
                        r_num = row.get("row", -1)
                        resp_val = row["response"]
                        # Check if preceded by a missing sample peak row (e.g. row - 1 or row - 2)
                        if (r_num - 1) in missing_rows_list or (r_num - 2) in missing_rows_list:
                            reason = (
                                f"Double Drop Suspected: Unusually high response factor "
                                f"({resp_val:.0f} vs median {median_resp:.0f}) following missing sample peak."
                            )
                        else:
                            reason = (
                                f"Abnormal Area/Amount Ratio: Response factor "
                                f"({resp_val:.0f}) > 1.5x run median ({median_resp:.0f}). Suspected double drop or weighing error."
                            )

                        alerts.append(
                            {
                                "row": r_num,
                                "sample_name": row["sample_name"],
                                "reason": reason,
                            }
                        )

        # --- 1. Range Check (Normalized only) ---
        target_col = self.config.target_column
        norm_col = f"corrected_{target_col}"

        if norm_col in valid.columns:
            r_min, r_max = self.config.absolute_range
            out_of_range = valid[
                (valid[norm_col] < r_min) | (valid[norm_col] > r_max)
            ]
            for _, row in out_of_range.iterrows():
                alerts.append(
                    {
                        "row": row.get("row", -1),
                        "sample_name": row["sample_name"],
                        "reason": f"Value {row[norm_col]:.2f} is outside expected range ({r_min}, {r_max})",
                    }
                )

        # --- 2. Precision Check (Variance) ---
        if self.config.method_precision > 0:
            threshold = 3 * self.config.method_precision
            # Calculate STD per sample
            precision_stats = valid.groupby("sample_name")["working_value"].std().reset_index()
            flagged_samples = precision_stats[precision_stats["working_value"] > threshold]["sample_name"]

            for name in flagged_samples:
                sample_rows = valid[valid["sample_name"] == name]
                val_std = precision_stats[precision_stats["sample_name"] == name]["working_value"].values[0]
                for _, row in sample_rows.iterrows():
                    alerts.append(
                        {
                            "row": row.get("row", -1),
                            "sample_name": name,
                            "reason": f"High Variance: SD ({val_std:.2f}) > 3x method precision ({threshold:.2f})",
                        }
                    )

        # --- 3. Amplitude Check ---
        amp_col = self.config.amplitude_column
        if amp_col and amp_col in valid.columns:
            median_amp = valid[amp_col].median()
            # Flag if < 50% or > 200% of median
            bad_amp = valid[
                (valid[amp_col] < 0.5 * median_amp) | (valid[amp_col] > 2.0 * median_amp)
            ]
            for _, row in bad_amp.iterrows():
                alerts.append(
                    {
                        "row": row.get("row", -1),
                        "sample_name": row["sample_name"],
                        "reason": f"Amplitude Anomaly: {row[amp_col]:.0f} is far from run median ({median_amp:.0f})",
                    }
                )

        self._alerts = pd.DataFrame(alerts)
        if not self._alerts.empty:
            self._alerts = self._alerts.drop_duplicates()


    # --- Data Cleaning ---

    def exclude_rows(self, row_ids: List[int]):
        """
        Manually excludes specific rows (by Isodat Row number) from processing.

        Args:
            row_ids: List of 'row' numbers to exclude.
        """
        if "row" in self.replicates.columns:
            mask = self.replicates["row"].isin(row_ids)
            self.replicates.loc[mask, "excluded"] = True
            self.excluded_rows_list = sorted(list(set(self.excluded_rows_list + row_ids)))
            # Invalidate summary cache since data changed
            self.summary = None
        else:
            raise KeyError("Data does not contain 'row' column for exclusion.")


    # --- Standards Management ---

    def set_anchors(self, names: List[str]):
        """Registers the standards used to BUILD the calibration curve."""
        self.anchors = self._resolve_standards(names)

    def set_controls(self, names: List[str]):
        """Registers standards used to CHECK accuracy (QC), not for fitting."""
        self.controls = self._resolve_standards(names)

    def set_drift_monitors(self, names: List[str]):
        """Registers standards used to monitor analytical DRIFT."""
        self.drift_monitors = self._resolve_standards(names)

    def _resolve_standards(self, names: List[str]) -> Dict[str, ReferenceMaterial]:
        """Helper to look up standard objects from the registry."""
        resolved = {}
        for name in names:
            std = get_standard(name, target_column=self.config.target_column)
            if not std:
                raise ValueError(
                    f"Standard '{name}' not found in library. Please define it manually."
                )
            resolved[std.name] = std
        return resolved

    def get_canonical_name(
        self, raw_name: str, registry: Dict[str, ReferenceMaterial]
    ) -> Optional[str]:
        """
        Maps a potentially messy raw sample name to a canonical standard name
        if it matches any aliases in the provided registry.
        """
        for std in registry.values():
            if std.matches(raw_name):
                return std.name
        return None

    # --- Drift Analysis ---

    def check_drift(self, use_working: bool = False) -> pd.DataFrame:
        """
        Calculates linear regression (Target vs Row) for all drift monitors.

        Returns a summary of slopes, p-values, and 95% Confidence Intervals.

        Args:
            use_working: If True, uses the current 'working_value' (which might be
                        already drift-corrected). If False (default), uses the
                        original raw target column.
        """
        if not self.drift_monitors:
            raise ValueError("No drift monitors set. Use set_drift_monitors() first.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        # Add canonical name for grouping
        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self.get_canonical_name(x, self.drift_monitors)
        )
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        col_to_use = "working_value" if use_working else self.config.target_column

        results = []
        for name, group in drift_data.groupby("canonical_name"):
            if len(group) < 3:
                continue

            x = group["row"]
            y = group[col_to_use]

            slope, _, r_value, p_value, std_err = sp_stats.linregress(x, y)

            # 95% CI for the slope: slope +/- t_crit * std_err
            df_deg = len(x) - 2
            t_crit = sp_stats.t.ppf(0.975, df_deg)
            ci_95 = t_crit * std_err

            results.append({
                "Standard": name,
                "Slope": slope,
                "CI_95": ci_95,
                "p_value": p_value,
                "R_squared": r_value**2,
                "n": len(x)
            })

        if not results:
            return pd.DataFrame(columns=["Slope", "CI_95", "p_value", "R_squared", "n"])

        return pd.DataFrame(results).set_index("Standard")

    def plot_drift(self, ax: Optional[plt.Axes] = None, use_working: bool = False):
        """
        Plots target column vs row for all drift monitors with trendlines.
        """
        if not self.drift_monitors:
            raise ValueError("No drift monitors set. Use set_drift_monitors() first.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self.get_canonical_name(x, self.drift_monitors)
        )
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        if drift_data.empty:
            raise ValueError("No data found matching the registered drift monitors.")

        if ax is None:
            _, ax = plt.subplots(figsize=(10, 6))

        col_to_use = "working_value" if use_working else self.config.target_column

        # Plot individual points with different colors per monitor
        sns.scatterplot(
            data=drift_data,
            x="row",
            y=col_to_use,
            hue="canonical_name",
            s=60,
            alpha=0.7,
            ax=ax,
            zorder=3
        )

        # Add regression lines manually for better control
        stats_df = self.check_drift(use_working=use_working)
        for i, (name, row) in enumerate(stats_df.iterrows()):
            group = drift_data[drift_data["canonical_name"] == name]
            x = group["row"]
            y = group[col_to_use]

            # Re-calculate line for plotting
            slope = row["Slope"]
            intercept = y.mean() - slope * x.mean()
            x_range = np.array([x.min(), x.max()])
            y_range = slope * x_range + intercept

            ax.plot(x_range, y_range, linestyle='--', alpha=0.8, zorder=2, color="black")

            # Enhanced annotation with CI for decision making
            txt = (f"{name}:\n\n"
                   f"  y = {slope:.3f}x + {intercept:.3f}\n"
                   f"  Slope CI 95%: {slope:.3f} ± {row['CI_95']:.3f}\n"
                   f"  R² = {row['R_squared']:.3f}, p = {row['p_value']:.3f}")

            ax.annotate(
                txt,
                xy=(0.02, 0.95 - i*0.15),
                xycoords='axes fraction',
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8),
                verticalalignment='top'
            )

        # Formatting for consistency
        ax.set_title(f"Analytical Drift: {self.config.name}", fontsize=12, fontweight='bold')
        ax.set_xlabel("Injection (Row)", fontsize=10)
        ax.set_ylabel(f"{'Working' if use_working else 'Raw'} {self.config.target_column}", fontsize=10)
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend(title="Drift Monitor", loc='lower right')

        return ax

    def apply_drift_correction(self, monitor_name: str):
        """
        Applies a linear drift correction to the working data based on the specified monitor.
        Always calculates the slope from RAW data to ensure consistency.
        Formula: working_value = raw_value - (slope * row)
        """
        # Always check drift on raw data to get the absolute slope
        drift_stats = self.check_drift(use_working=False)

        # Check if monitor_name is canonical or raw
        if monitor_name not in drift_stats.index:
            monitor_name = self.get_canonical_name(monitor_name, self.drift_monitors)

            if monitor_name not in drift_stats.index:
                raise ValueError(
                    f"Monitor standard '{monitor_name}' not found or has insufficient data for drift analysis."
                )

        slope = float(drift_stats.loc[monitor_name, "Slope"])
        ci_95 = float(drift_stats.loc[monitor_name, "CI_95"])
        p_val = float(drift_stats.loc[monitor_name, "p_value"])
        r2 = float(drift_stats.loc[monitor_name, "R_squared"])

        # Apply correction to working_value, starting from raw target
        self.replicates["working_value"] = self.replicates[self.config.target_column] - (slope * self.replicates["row"])

        # Record correction metadata
        self.drift_correction_applied = True
        self.drift_monitor_used = monitor_name
        self.drift_slope = slope
        self.drift_ci95 = ci_95
        self.drift_p_value = p_val
        self.drift_r2 = r2
        self.drift_info = {
            "monitor": monitor_name,
            "slope": slope,
            "ci_95": ci_95,
            "p_value": p_val,
            "r_squared": r2
        }
        # Invalidate summary cache
        self.summary = None


    def _detect_area_column(self, area_column: Optional[str] = None) -> str:
        if area_column and area_column in self.replicates.columns:
            return area_column

        numeric_cols = self.replicates.select_dtypes(include=[np.number]).columns
        candidates = [
            col for col in numeric_cols
            if any(k in col.lower() for k in ["area", "ampl", "intensity", "signal"])
        ]
        if candidates:
            area_candidates = [c for c in candidates if "area" in c.lower()]
            if area_candidates:
                return area_candidates[0]
            return candidates[0]

        raise ValueError("Could not auto-detect numeric peak area/amplitude column. Please specify 'area_column'.")


    def check_linearity(
        self,
        substance_name: Optional[str] = None,
        area_column: Optional[str] = None,
        use_working: bool = True
    ) -> pd.DataFrame:
        """
        Quantifies signal intensity / peak area dependence (linearity) using OLS regression.

        Calculates:
        - Slope (delta per area/amplitude unit)
        - CI_95 (95% Confidence Interval for slope)
        - p_value and R_squared

        Args:
            substance_name: Optional standard/sample name to evaluate. If None, evaluates all groups.
            area_column: Specific peak area or amplitude column name. Auto-detected if None.
            use_working: Whether to regress working_value (True) or raw target delta (False).
        """
        col_to_use = "working_value" if use_working else self.config.target_column
        area_col = self._detect_area_column(area_column)

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        if substance_name:
            sub_canonical = self.get_canonical_name(substance_name, self.anchors) or substance_name
            mask = valid_data["sample_name"].str.strip().str.lower() == sub_canonical.strip().lower()
            if not mask.any():
                mask = valid_data["sample_name"].str.contains(substance_name, case=False, na=False)
            filtered = valid_data[mask]
        else:
            filtered = valid_data

        if filtered.empty:
            return pd.DataFrame(columns=["Slope", "CI_95", "p_value", "R_squared", "n", "Mean_Area"])

        results = []
        for name, group in filtered.groupby("sample_name"):
            group_clean = group.dropna(subset=[area_col, col_to_use])
            if len(group_clean) < 3:
                continue

            x = group_clean[area_col]
            y = group_clean[col_to_use]

            if x.max() == x.min():
                continue

            slope, _, r_value, p_value, std_err = sp_stats.linregress(x, y)
            df_deg = len(x) - 2
            t_crit = sp_stats.t.ppf(0.975, df_deg)
            ci_95 = t_crit * std_err if not np.isnan(std_err) else 0.0

            results.append({
                "Substance": name,
                "Slope": slope,
                "CI_95": ci_95,
                "p_value": p_value,
                "R_squared": r_value**2,
                "n": len(x),
                "Mean_Area": x.mean()
            })

        if not results:
            return pd.DataFrame(columns=["Slope", "CI_95", "p_value", "R_squared", "n", "Mean_Area"])

        return pd.DataFrame(results).set_index("Substance")

    def apply_linearity_correction(
        self,
        slope: Optional[float] = None,
        substance_name: Optional[str] = None,
        area_ref: Optional[float] = None,
        area_column: Optional[str] = None
    ):
        """
        Applies mass/intensity linearity correction to working_value.

        Formula:
            working_value = working_value - slope * (area - area_ref)

        Args:
            slope: Direct slope (delta unit per area unit). If None, inferred from substance_name.
            substance_name: Standard/sample name used to infer slope if slope is None.
            area_ref: Reference area value. If None, defaults to median area of valid replicates.
            area_column: Specific column name for signal area/amplitude. Auto-detected if None.
        """
        area_col = self._detect_area_column(area_column)

        ci_95 = None
        p_val = None
        r2 = None

        is_direct = slope is not None
        source_str = "Direct Input (Transferred Slope)" if is_direct else "Inferred from Run Replicates"

        if slope is None:
            if not substance_name:
                raise ValueError("Must provide either a direct 'slope' or a 'substance_name' to infer slope.")
            stats = self.check_linearity(substance_name=substance_name, area_column=area_col, use_working=True)
            if stats.empty:
                raise ValueError(f"Could not calculate linearity slope for substance '{substance_name}'. Insufficient data.")
            matched_name = stats.index[0]
            slope = float(stats.loc[matched_name, "Slope"])
            ci_95 = float(stats.loc[matched_name, "CI_95"])
            p_val = float(stats.loc[matched_name, "p_value"])
            r2 = float(stats.loc[matched_name, "R_squared"])
        else:
            if substance_name:
                stats = self.check_linearity(substance_name=substance_name, area_column=area_col, use_working=True)
                if not stats.empty:
                    matched_name = stats.index[0]
                    ci_95 = float(stats.loc[matched_name, "CI_95"])
                    p_val = float(stats.loc[matched_name, "p_value"])
                    r2 = float(stats.loc[matched_name, "R_squared"])

        valid_mask = ~self.replicates["excluded"]
        if area_ref is None:
            area_ref = float(self.replicates.loc[valid_mask, area_col].median())

        # Store pre-linearity working value for auditing and accurate plot alignment
        self.replicates["pre_linearity_working_value"] = self.replicates["working_value"].copy()

        # Apply correction to working_value
        self.replicates["working_value"] = self.replicates["working_value"] - slope * (self.replicates[area_col] - area_ref)


        # Record attributes
        self.linearity_correction_applied = True
        self.linearity_slope = slope
        self.linearity_ci95 = ci_95
        self.linearity_p_value = p_val
        self.linearity_r2 = r2
        self.linearity_substance_used = substance_name or "Manual Input"
        self.linearity_area_ref = area_ref
        self.linearity_is_direct = is_direct
        self.linearity_source = source_str
        self.linearity_info = {
            "slope": slope,
            "ci_95": ci_95,
            "p_value": p_val,
            "r_squared": r2,
            "substance": substance_name or "Manual Input",
            "area_ref": area_ref,
            "area_column": area_col,
            "is_direct": is_direct,
            "source": source_str
        }


        # Invalidate summary cache
        self.summary = None



    def apply_blank_correction(self, blank_identifier: str = "bco cap", area_column: Optional[str] = None):
        """
        Applies mass-balance blank correction to working values.

        Formula:
            A_net = A_raw - A_blk
            d_corr = (A_raw * d_raw - A_blk * d_blk) / A_net

        Args:
            blank_identifier: Name (or partial alias) of the blank sample.
            area_column: Specific area column to use. If None, auto-detected.
        """
        valid = self.replicates[~self.replicates["excluded"]].copy()

        blank_mask = valid["sample_name"].str.strip().str.lower() == blank_identifier.strip().lower()
        blank_rows = valid[blank_mask]

        if blank_rows.empty:
            raise ValueError(f"No valid rows matching blank identifier '{blank_identifier}' found.")

        if area_column is None:
            possible_areas = []
            if self.config.amplitude_column:
                suffix = self.config.amplitude_column.split("_")[-1]
                possible_areas.append(f"area_{suffix}")
            possible_areas.extend(["area_44", "area_28", "area_2", "area_all"])

            for col in possible_areas:
                if col in self.replicates.columns:
                    area_column = col
                    break

        if not area_column or area_column not in self.replicates.columns:
            raise KeyError("Could not auto-detect a valid 'area' column for blank correction.")

        a_blk = blank_rows[area_column].mean()
        a_blk_std = blank_rows[area_column].std()
        d_blk = blank_rows["working_value"].mean()
        d_blk_std = blank_rows["working_value"].std()

        a_raw = self.replicates[area_column]
        d_raw = self.replicates["working_value"]

        a_net = a_raw - a_blk
        d_corr = (a_raw * d_raw - a_blk * d_blk) / a_net

        self.replicates["area_net"] = a_net
        self.replicates["d_blank_corrected"] = d_corr
        self.replicates["working_value"] = d_corr

        self.blank_correction_applied = True
        self.blank_info = {
            "identifier": blank_identifier,
            "area_column": area_column,
            "mean_area": a_blk,
            "std_area": a_blk_std,
            "mean_delta": d_blk,
            "std_delta": d_blk_std,
        }
        self.summary = None

    def plot_calibration(self, ax: Optional[plt.Axes] = None):

        """
        Plots the calibration curve showing all individual anchor replicates
        and the fitted calibration line.
        """
        if self.strategy is None:
            raise RuntimeError("Run .process() before requesting calibration plot.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        # 1. Filter for Anchors and add True Values
        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self.get_canonical_name(x, self.anchors)
        )
        anchor_data = valid_data[valid_data["canonical_name"].notna()].copy()

        def get_true_val(canonical_name):
            return self.anchors[canonical_name].d_true

        anchor_data["d_true"] = anchor_data["canonical_name"].apply(get_true_val)

        if anchor_data.empty:
            raise ValueError("No anchors found in data to plot.")

        if ax is None:
            _, ax = plt.subplots(figsize=(8, 6))

        # 2. Scatter Individual Replicates (True on X, Measured on Y)
        sns.scatterplot(
            data=anchor_data,
            x="d_true",
            y="working_value",
            hue="canonical_name",
            ax=ax,
            s=60,
            alpha=0.8,
            zorder=3
        )

        # 3. Draw the Calibration Line (Instrument Fit: Raw = m * True + b)
        t_min, t_max = anchor_data["d_true"].min(), anchor_data["d_true"].max()
        pad = (t_max - t_min) * 0.1 if t_max != t_min else 1.0
        t_line = np.linspace(t_min - pad, t_max + pad, 100)

        # Raw = m * True + b
        m = self.strategy.slope
        b = self.strategy.intercept
        y_line = (t_line * m) + b

        ax.plot(
            t_line,
            y_line,
            color='black',
            linestyle='--',
            label='Calibration Line',
            zorder=2
        )

        # Annotation with Equation and R2
        txt = (f"Fit Equation (Measured vs True):\n"
               f"  y = {m:.4f}x + {b:.4f}\n"
               f"  R² = {self.strategy.r_squared:.4f}")

        ax.annotate(
            txt,
            xy=(0.05, 0.95),
            xycoords='axes fraction',
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8),
            verticalalignment='top'
        )

        # Formatting for consistency
        ax.set_title(f"Calibration Curve: {self.config.name}", fontsize=12, fontweight='bold')
        ax.set_xlabel("Reference Value (True)", fontsize=10)
        ax.set_ylabel(f"Measured {self.config.target_column} (Drift-Corrected)", fontsize=10)
        ax.legend(loc='lower right')
        ax.grid(True, linestyle=':', alpha=0.6)

        return ax

    # --- Processing Core ---

    def process(self, strategy: CalibrationStrategy, use_method_precision: bool = False):
        """
        The Main Pipeline:

        1. Run Diagnostics (Detect Outliers)
        2. Prepare Anchor Stats for fitting
        3. Fit Strategy (using Anchors from working_value)
        4. Correct Replicates (Row-by-Row)
        5. Aggregate to Summary (Sample-Level)
        6. Propagate Uncertainty (Kragten)
        7. Refresh Diagnostics (Including Range Checks)
        """
        self.strategy = strategy
        self.use_method_precision = use_method_precision


        # A. Run Diagnostics
        self.detect_outliers()
        if not self._alerts.empty:
            warnings.warn(
                f"Detected {len(self._alerts)} suspicious data points. "
                "Check the .alerts property for details."
            )

        # B. Filter valid data for calculation
        valid_data = self.replicates[~self.replicates["excluded"]]

        # C. Prepare Anchor Stats for Fitting
        valid_data = valid_data.copy()
        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self.get_canonical_name(x, self.anchors)
        )
        anchor_rows = valid_data[valid_data["canonical_name"].notna()]

        if anchor_rows.empty:
            raise ValueError("No rows matched the provided Anchor Standards.")

        # Use working_value for fitting
        anchor_stats = anchor_rows.groupby("canonical_name")["working_value"].agg(
            ["mean", "sem", "count"]
        )

        # Optional Precision Override: use sigma / sqrt(n)
        if use_method_precision and self.config.method_precision > 0:
            anchor_stats["sem"] = self.config.method_precision / np.sqrt(
                anchor_stats["count"]
            )

        # D. Fit the Strategy
        strategy.fit(anchor_stats, self.anchors)

        # E. Apply to Replicates (Vectorized)
        # Always use working_value as input
        target_col = self.config.target_column
        norm_col = f"corrected_{target_col}"
        if norm_col in self.replicates.columns:
            self.replicates = self.replicates.drop(columns=[norm_col])

        self.replicates = strategy.apply(self.replicates, "working_value")

        # Rename the output column to match the expected client-facing name
        self.replicates = self.replicates.rename(
            columns={"corrected_working_value": norm_col}
        )

        # F. Aggregate to Summary (Sample Level)
        # We group by canonical name for standards, but keep raw names for unknowns
        summary_data = self.replicates[~self.replicates["excluded"]].copy()

        def get_group_name(raw_name):
            # Check Anchors first
            can_name = self.get_canonical_name(raw_name, self.anchors)
            if can_name:
                return can_name
            # Then Controls
            can_name = self.get_canonical_name(raw_name, self.controls)
            if can_name:
                return can_name
            # Fallback to raw name
            return raw_name

        summary_data["group_name"] = summary_data["sample_name"].apply(get_group_name)

        self.summary = summary_data.groupby("group_name")[
            "working_value"
        ].agg(["mean", "sem", "count"])

        if use_method_precision and self.config.method_precision > 0:
            self.summary["sem"] = self.config.method_precision / np.sqrt(
                self.summary["count"]
            )

        # G. Propagate Uncertainty (Sample Level)
        # strategy.propagate will add 'combined_uncertainty' and its own 'corrected_{target_col}'
        # but we need to tell it that the input mean is 'working_value'
        self.summary = strategy.propagate(self.summary, self.config.target_column)

        # H. Refresh Diagnostics (Now including Range Checks on normalized data)
        self.detect_outliers()
        if not self._alerts.empty:
            warnings.warn(
                "Detected suspicious data points after processing. "
                "Check the .alerts property for details."
            )

    # --- Reporting ---

    @property
    def report(self) -> pd.DataFrame:
        """Returns the final client-ready table."""
        if self.summary is None:
            raise RuntimeError("Run .process() before requesting a report.")

        # Clean up the table for display
        # We might want to filter out the Anchors from the main report?
        # For now, return everything clean
        cols = [
            f"corrected_{self.config.target_column}",
            "combined_uncertainty",
            "count",
        ]
        return self.summary[cols].round(2)

    @property
    def qaqc(self) -> pd.DataFrame:
        """Returns trueness report for the Control standards."""
        if self.summary is None:
            raise RuntimeError("Run .process() before requesting QAQC.")

        # Filter summary for rows that match our Controls
        qc_rows = []
        for sample_name in self.summary.index:
            canonical_name = self.get_canonical_name(sample_name, self.controls)
            if canonical_name:
                std_obj = self.controls[canonical_name]
                # Found a QC sample
                row = self.summary.loc[sample_name].copy()
                row["True_Value"] = std_obj.d_true
                row["Bias"] = (
                    row[f"corrected_{self.config.target_column}"] - std_obj.d_true
                )
                row["Within_Unc"] = abs(row["Bias"]) < (
                    2 * row["combined_uncertainty"]
                )  # Simple check
                qc_rows.append(row)

        if not qc_rows:
            return pd.DataFrame()

        return pd.DataFrame(qc_rows)[
            [
                "True_Value",
                f"corrected_{self.config.target_column}",
                "Bias",
                "Within_Unc",
            ]
        ]

    def save_report(self, filepath: str):
        """
        Exports the Results and QAQC tables to a multi-sheet Excel file.
        """
        if self.summary is None:
            raise RuntimeError("Run .process() before exporting the report.")

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # 1. Results Sheet
            self.report.to_excel(writer, sheet_name="Results")

            # 2. QAQC Sheet
            qaqc_df = self.qaqc
            if not qaqc_df.empty:
                qaqc_df.to_excel(writer, sheet_name="QAQC")

            # 3. Parameters/Metadata Sheet
            params = {
                "System": self.config.name,
                "Strategy": self.strategy.__class__.__name__ if self.strategy else "None",
                "Target Column": self.config.target_column,
                "Filepath": self.filepath,
                "Anchors": ", ".join(self.anchors.keys()),
                "Controls": ", ".join(self.controls.keys()),
                "Drift Monitors": ", ".join(self.drift_monitors.keys()),
                "Drift Correction Applied": self.drift_correction_applied,
                "Drift Monitor Used": self.drift_monitor_used if self.drift_correction_applied else "None",
                "Drift Slope": getattr(self, "drift_slope", "None") if self.drift_correction_applied else "None",
                "Drift Slope 95% CI": getattr(self, "drift_ci95", "None") if self.drift_correction_applied else "None",
                "Linearity Correction Applied": self.linearity_correction_applied,
                "Linearity Slope": self.linearity_slope if self.linearity_correction_applied else "None",
                "Linearity Slope 95% CI": getattr(self, "linearity_ci95", "None") if self.linearity_correction_applied else "None",
                "Linearity Slope Source": getattr(self, "linearity_source", "None") if self.linearity_correction_applied else "None",
                "Linearity Reference Substance": self.linearity_substance_used if self.linearity_correction_applied else "None",
                "Linearity Ref Area": self.linearity_area_ref if self.linearity_correction_applied else "None",


                "Blank Correction Applied": self.blank_correction_applied,
                "Blank Identifier": self.blank_info["identifier"] if self.blank_correction_applied and self.blank_info else "None",

            }

            if self.strategy:
                # Add fit parameters if available
                params["Slope"] = getattr(self.strategy, "slope", "N/A")
                params["Intercept"] = getattr(self.strategy, "intercept", "N/A")

            pd.Series(params).to_frame("Value").to_excel(writer, sheet_name="Parameters")

    def save_html_report(self, filepath: str):
        """
        Exports the results, diagnostics, and interactive plots to a standalone HTML file.
        """
        generate_html_report(self, filepath)
