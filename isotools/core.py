from typing import List, Dict, Optional
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

        # 2. State Containers
        self.anchors: Dict[str, ReferenceMaterial] = {}  # Used for calibration
        self.controls: Dict[str, ReferenceMaterial] = {}  # Used for QC/Trueness
        self.drift_monitors: Dict[str, ReferenceMaterial] = {}  # Used for Drift Check
        self._summary: Optional[pd.DataFrame] = None
        self._strategy: Optional[CalibrationStrategy] = None

    @property
    def data_view(self) -> pd.DataFrame:
        """Returns a quick summary of the raw data for inspection."""
        # Simple aggregation to show user what standards/samples are present
        return self.replicates.groupby("sample_name").size().to_frame("n_injections")

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

    # --- Drift Analysis ---

    def check_drift(self) -> pd.DataFrame:
        """
        Calculates linear regression (Target vs Row) for all drift monitors.
        Returns a summary of slopes, p-values, and 95% Confidence Intervals.
        """
        if not self.drift_monitors:
            raise ValueError("No drift monitors set. Use set_drift_monitors() first.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()
        
        # Add canonical name for grouping
        def map_to_canonical(raw_name):
            for std in self.drift_monitors.values():
                if std.matches(raw_name):
                    return std.name
            return None

        valid_data["canonical_name"] = valid_data["sample_name"].apply(map_to_canonical)
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        results = []
        for name, group in drift_data.groupby("canonical_name"):
            if len(group) < 3:
                continue
            
            x = group["row"]
            y = group[self.config.target_column]
            
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

        return pd.DataFrame(results).set_index("Standard")

    def plot_drift(self, ax: Optional[plt.Axes] = None):
        """
        Plots target column vs row for all drift monitors with trendlines.
        """
        if not self.drift_monitors:
            raise ValueError("No drift monitors set. Use set_drift_monitors() first.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()
        
        def map_to_canonical(raw_name):
            for std in self.drift_monitors.values():
                if std.matches(raw_name):
                    return std.name
            return None

        valid_data["canonical_name"] = valid_data["sample_name"].apply(map_to_canonical)
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        if drift_data.empty:
            raise ValueError("No data found matching the registered drift monitors.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        sns.regplot(
            data=drift_data,
            x="row",
            y=self.config.target_column,
            scatter_kws={"alpha": 0.6},
            ax=ax
        )
        
        # Add labels and formatting
        ax.set_title(f"Drift Analysis ({self.config.name})")
        ax.set_xlabel("Injection (Row)")
        ax.set_ylabel(f"Raw {self.config.target_column}")
        
        # Calculate stats for annotation
        stats_df = self.check_drift()
        for i, (name, row) in enumerate(stats_df.iterrows()):
            txt = f"{name}: Slope={row['Slope']:.4f} ± {row['CI_95']:.4f} (p={row['p_value']:.3f})"
            ax.annotate(txt, xy=(0.05, 0.95 - i*0.05), xycoords='axes fraction', fontsize=10)

        return ax

    def apply_drift_correction(self, monitor_name: str):
        """
        Applies a linear drift correction to the raw target data based on the specified monitor.
        Formula: y_new = y_old - (slope * row)
        """
        stats = self.check_drift()
        
        # We need to find the canonical name for the monitor_name provided
        # Or check if it exists in the stats index directly
        if monitor_name not in stats.index:
            # Maybe it's a raw name? Let's check drift_monitors
            canonical_name = None
            for std in self.drift_monitors.values():
                if std.matches(monitor_name):
                    canonical_name = std.name
                    break
            
            if canonical_name in stats.index:
                monitor_name = canonical_name
            else:
                raise ValueError(f"Monitor standard '{monitor_name}' not found or has insufficient data for drift analysis.")

        slope = stats.loc[monitor_name, "Slope"]
        
        # Apply correction to all rows
        self.replicates[self.config.target_column] -= slope * self.replicates["row"]
        
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
        def get_true_val(raw_name):
            for std in self.anchors.values():
                if std.matches(raw_name):
                    return std.d_true
            return None

        valid_data["d_true"] = valid_data["sample_name"].apply(get_true_val)
        anchor_data = valid_data[valid_data["d_true"].notna()]

        if anchor_data.empty:
            raise ValueError("No anchors found in data to plot.")

        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))

        # 2. Scatter Individual Replicates
        sns.scatterplot(
            data=anchor_data,
            x=self.config.target_column,
            y="d_true",
            hue="sample_name",
            ax=ax,
            s=60,
            alpha=0.8,
            zorder=3
        )

        # 3. Draw the Calibration Line
        # We draw it across the range of anchors
        x_min, x_max = anchor_data[self.config.target_column].min(), anchor_data[self.config.target_column].max()
        # Add some padding
        pad = (x_max - x_min) * 0.1 if x_max != x_min else 1.0
        x_line = np.linspace(x_min - pad, x_max + pad, 100)
        
        synthetic_df = pd.DataFrame({self.config.target_column: x_line})
        corrected_df = self._strategy.apply(synthetic_df, self.config.target_column)
        
        ax.plot(
            x_line, 
            corrected_df[f"corrected_{self.config.target_column}"], 
            color='black', 
            linestyle='--', 
            label='Calibration Line',
            zorder=2
        )

        ax.set_title(f"Calibration Curve: {self.config.name}")
        ax.set_xlabel(f"Measured {self.config.target_column}")
        ax.set_ylabel("Reference Value (True)")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.6)

        return ax

    # --- Processing Core ---

    def process(self, strategy: CalibrationStrategy):
        """
        The Main Pipeline:
        1. Fit Strategy (using Anchors)
        2. Correct Replicates (Row-by-Row)
        3. Aggregate to Summary (Sample-Level)
        4. Propagate Uncertainty (Kragten)
        """
        self._strategy = strategy

        # A. Filter valid data for calculation
        valid_data = self.replicates[~self.replicates["excluded"]]

        # B. Prepare Anchor Stats for Fitting
        # We need the Raw Mean/SEM of the standards identified as anchors
        # match_func logic: Find rows where sample_name matches an anchor
        anchor_rows = valid_data[
            valid_data["sample_name"].apply(
                lambda x: any(std.matches(x) for std in self.anchors.values())
            )
        ]

        if anchor_rows.empty:
            raise ValueError("No rows matched the provided Anchor Standards.")

        # Group by the *canonical* standard name, not the messy raw name
        # We map the raw name to the canonical name first
        def map_to_canonical(raw_name):
            for std in self.anchors.values():
                if std.matches(raw_name):
                    return std.name
            return None

        anchor_stats = anchor_rows.groupby(
            anchor_rows["sample_name"].apply(map_to_canonical)
        )[self.config.target_column].agg(["mean", "sem"])

        # C. Fit the Strategy
        strategy.fit(anchor_stats, self.anchors)

        # D. Apply to Replicates (Vectorized)
        # This updates self.replicates with a new 'corrected_d15n' column
        self.replicates = strategy.apply(self.replicates, self.config.target_column)

        # E. Aggregate to Summary (Sample Level)
        # We group by the raw sample name here
        self._summary = valid_data.groupby("sample_name")[
            self.config.target_column
        ].agg(["mean", "sem", "count"])

        # F. Propagate Uncertainty (Sample Level)
        # This adds 'combined_uncertainty' and 'corrected_mean' to _summary
        self._summary = strategy.propagate(self._summary, self.config.target_column)

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
            for _, std_obj in self.controls.items():
                if std_obj.matches(sample_name):
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
