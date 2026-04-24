from typing import List, Dict, Optional
import pandas as pd
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
