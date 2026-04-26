from typing import List, Dict, Optional, Iterable
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from .config import SystemConfig
from .utils.readers import IsodatReader
from .models import ReferenceMaterial
from .standards import get_standard
from .strategies.abstract import CalibrationStrategy


class Batch:
    """
    The central object representing a single IRMS run/sequence.
    Manages the lifecycle of data from Raw -> Cleaned -> Calibrated -> Reported.
    """

    def __init__(self, filepath: str, config: SystemConfig, sheet_name: int | str = 0):
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
        self._summary: Optional[pd.DataFrame] = None
        self._strategy: Optional[CalibrationStrategy] = None
        self._alerts: pd.DataFrame = pd.DataFrame(columns=["row", "sample_name", "reason"])

        # 3. Initial Diagnostics
        self.detect_outliers()
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
        1. Range Check: Outside expected environmental values (on normalized data).
        2. Precision Check: Sample SD > 3x method precision (on raw/drift-corrected data).
        3. Amplitude Check: Amplitude < 50% or > 200% of run median.
        """
        alerts = []
        valid = self.replicates[~self.replicates["excluded"]].copy()

        if valid.empty:
            self._alerts = pd.DataFrame(columns=["row", "sample_name", "reason"])
            return

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
            stats = valid.groupby("sample_name")["working_value"].std().reset_index()
            flagged_samples = stats[stats["working_value"] > threshold]["sample_name"]
            
            for name in flagged_samples:
                sample_rows = valid[valid["sample_name"] == name]
                val_std = stats[stats["sample_name"] == name]["working_value"].values[0]
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
        """
        if "row" in self.replicates.columns:
            mask = self.replicates["row"].isin(row_ids)
            self.replicates.loc[mask, "excluded"] = True
            # Invalidate summary cache since data changed
            self._summary = None
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
            std = get_standard(name)
            if not std:
                raise ValueError(
                    f"Standard '{name}' not found in library. Please define it manually."
                )
            resolved[std.name] = std
        return resolved

    def _get_canonical_name(
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
            lambda x: self._get_canonical_name(x, self.drift_monitors)
        )
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        col_to_use = "working_value" if use_working else self.config.target_column

        results = []
        for name, group in drift_data.groupby("canonical_name"):
            if len(group) < 3:
                continue
            
            x = group["row"]
            y = group[col_to_use]
            
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            
            # 95% CI for the slope: slope +/- t_crit * std_err
            df_deg = len(x) - 2
            t_crit = stats.t.ppf(0.975, df_deg)
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
            lambda x: self._get_canonical_name(x, self.drift_monitors)
        )
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        if drift_data.empty:
            raise ValueError("No data found matching the registered drift monitors.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        col_to_use = "working_value" if use_working else self.config.target_column

        sns.regplot(
            data=drift_data,
            x="row",
            y=col_to_use,
            scatter_kws={"alpha": 0.6},
            ax=ax
        )
        
        # Add labels and formatting
        ax.set_title(f"Drift Analysis ({self.config.name})")
        ax.set_xlabel("Injection (Row)")
        ax.set_ylabel(f"{'Working' if use_working else 'Raw'} {self.config.target_column}")
        
        # Calculate stats for annotation
        stats_df = self.check_drift(use_working=use_working)
        for i, (name, row) in enumerate(stats_df.iterrows()):
            txt = f"{name}: Slope={row['Slope']:.4f} ± {row['CI_95']:.4f} (p={row['p_value']:.3f})"
            ax.annotate(txt, xy=(0.05, 0.95 - i*0.05), xycoords='axes fraction', fontsize=10)

        return ax

    def apply_drift_correction(self, monitor_name: str):
        """
        Applies a linear drift correction to the working data based on the specified monitor.
        Always calculates the slope from RAW data to ensure consistency.
        Formula: working_value = raw_value - (slope * row)
        """
        # Always check drift on raw data to get the absolute slope
        stats = self.check_drift(use_working=False)
        
        # Check if monitor_name is canonical or raw
        if monitor_name not in stats.index:
            monitor_name = self._get_canonical_name(monitor_name, self.drift_monitors)
            
            if monitor_name not in stats.index:
                raise ValueError(
                    f"Monitor standard '{monitor_name}' not found or has insufficient data for drift analysis."
                )

        slope = stats.loc[monitor_name, "Slope"]
        
        # Apply correction to working_value, starting from raw target
        self.replicates["working_value"] = self.replicates[self.config.target_column] - (slope * self.replicates["row"])
        
        # Invalidate summary cache
        self._summary = None

    def plot_calibration(self, ax: Optional[plt.Axes] = None):
        """
        Plots the calibration curve showing all individual anchor replicates 
        and the fitted calibration line.
        """
        if self._strategy is None:
            raise RuntimeError("Run .process() before requesting calibration plot.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()
        
        # 1. Filter for Anchors and add True Values
        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self._get_canonical_name(x, self.anchors)
        )
        anchor_data = valid_data[valid_data["canonical_name"].notna()]
        
        def get_true_val(canonical_name):
            return self.anchors[canonical_name].d_true

        anchor_data["d_true"] = anchor_data["canonical_name"].apply(get_true_val)

        if anchor_data.empty:
            raise ValueError("No anchors found in data to plot.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))

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
        # We draw it across the range of true values
        t_min, t_max = anchor_data["d_true"].min(), anchor_data["d_true"].max()
        # Add some padding
        pad = (t_max - t_min) * 0.1 if t_max != t_min else 1.0
        t_line = np.linspace(t_min - pad, t_max + pad, 100)
        
        # Raw = m * True + b
        y_line = (t_line * self._strategy.slope) + self._strategy.intercept
        
        ax.plot(
            t_line, 
            y_line, 
            color='black', 
            linestyle='--', 
            label='Calibration Line',
            zorder=2
        )

        ax.set_title(f"Calibration Curve: {self.config.name}")
        ax.set_xlabel("Reference Value (True)")
        ax.set_ylabel(f"Measured {self.config.target_column} (Drift-Corrected)")
        ax.legend()
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
        self._strategy = strategy

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
            lambda x: self._get_canonical_name(x, self.anchors)
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
            columns={f"corrected_working_value": norm_col}
        )

        # F. Aggregate to Summary (Sample Level)
        # We group by canonical name for standards, but keep raw names for unknowns
        summary_data = self.replicates[~self.replicates["excluded"]].copy()
        
        def get_group_name(raw_name):
            # Check Anchors first
            can_name = self._get_canonical_name(raw_name, self.anchors)
            if can_name:
                return can_name
            # Then Controls
            can_name = self._get_canonical_name(raw_name, self.controls)
            if can_name:
                return can_name
            # Fallback to raw name
            return raw_name

        summary_data["group_name"] = summary_data["sample_name"].apply(get_group_name)
        
        self._summary = summary_data.groupby("group_name")[
            "working_value"
        ].agg(["mean", "sem", "count"])

        if use_method_precision and self.config.method_precision > 0:
            self._summary["sem"] = self.config.method_precision / np.sqrt(
                self._summary["count"]
            )

        # G. Propagate Uncertainty (Sample Level)
        # strategy.propagate will add 'combined_uncertainty' and its own 'corrected_{target_col}'
        # but we need to tell it that the input mean is 'working_value'
        self._summary = strategy.propagate(self._summary, self.config.target_column)

        # H. Refresh Diagnostics (Now including Range Checks on normalized data)
        self.detect_outliers()
        if not self._alerts.empty:
            warnings.warn(
                f"Detected {len(self._alerts)} suspicious data points after processing. "
                "Check the .alerts property for details."
            )

    # --- Reporting ---

    @property
    def report(self) -> pd.DataFrame:
        """Returns the final client-ready table."""
        if self._summary is None:
            raise RuntimeError("Run .process() before requesting a report.")

        # Clean up the table for display
        # We might want to filter out the Anchors from the main report?
        # For now, return everything clean
        cols = [
            f"corrected_{self.config.target_column}",
            "combined_uncertainty",
            "count",
        ]
        return self._summary[cols].round(2)

    @property
    def qaqc(self) -> pd.DataFrame:
        """Returns trueness report for the Control standards."""
        if self._summary is None:
            raise RuntimeError("Run .process() before requesting QAQC.")

        # Filter summary for rows that match our Controls
        qc_rows = []
        for sample_name in self._summary.index:
            canonical_name = self._get_canonical_name(sample_name, self.controls)
            if canonical_name:
                std_obj = self.controls[canonical_name]
                # Found a QC sample
                row = self._summary.loc[sample_name].copy()
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
        if self._summary is None:
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
                "Strategy": self._strategy.__class__.__name__ if self._strategy else "None",
                "Target Column": self.config.target_column,
                "Filepath": self.filepath,
                "Anchors": ", ".join(self.anchors.keys()),
                "Controls": ", ".join(self.controls.keys()),
                "Drift Monitors": ", ".join(self.drift_monitors.keys()),
            }
            if self._strategy:
                # Add fit parameters if available
                params["Slope"] = getattr(self._strategy, "slope", "N/A")
                params["Intercept"] = getattr(self._strategy, "intercept", "N/A")

            pd.Series(params).to_frame("Value").to_excel(writer, sheet_name="Parameters")
