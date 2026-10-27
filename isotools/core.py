"""
Core processing logic for IRMS data batches.
"""
# pylint: disable=too-many-lines
import os
import re
import datetime
from datetime import datetime as dt
import warnings
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats as sp_stats

from .config import SystemConfig
from .utils.readers import IsodatReader
from .utils.kragten import propagate_kragten
from .models import ReferenceMaterial
from .standards import get_standard
from .strategies.abstract import CalibrationStrategy
from .reporting.html import generate_html_report
from .reporting.excel import export_batch_to_excel


class Batch:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """
    The central object representing a single IRMS run/sequence.

    Manages the lifecycle of data from Raw -> Cleaned -> Calibrated -> Reported.
    Enforces the canonical CF-IRMS order of operations:
        0. Exclusions -> 0b. Memory Correction -> 1. Blank Correction ->
        2. Linearity Correction -> 3. Drift Correction -> 4. Scale Normalization ->
        4b. Elemental Composition Calibration
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
        reader = IsodatReader(config)
        self.replicates = reader.read(filepath, sheet_name=sheet_name)
        self.replicates["excluded"] = False

        # Initialize working_value as a copy of the raw target
        self.replicates["working_value"] = self.replicates[config.target_column].copy()

        # 2. State Containers
        self.anchors: Dict[str, ReferenceMaterial] = {}
        self.controls: Dict[str, ReferenceMaterial] = {}
        self.drift_monitors: Dict[str, ReferenceMaterial] = {}

        # Stage 0b: Memory (carryover) correction state
        self.memory_correction_applied: bool = False
        self.memory_coefficients: Optional[List[float]] = None
        self.memory_info: Optional[Dict] = None
        self._memory_params: Optional[Dict] = None

        # Stage 1: Blank correction state
        self.blank_correction_applied: bool = False
        self.blank_info: Optional[Dict] = None
        self._blank_params: Optional[Dict] = None

        # Stage 2: Linearity correction state
        self.linearity_correction_applied: bool = False
        self.linearity_slope: Optional[float] = None
        self.linearity_std_err: Optional[float] = None
        self.linearity_ci95: Optional[float] = None
        self.linearity_p_value: Optional[float] = None
        self.linearity_r2: Optional[float] = None
        self.linearity_substance_used: Optional[str] = None
        self.linearity_area_ref: Optional[float] = None
        self.linearity_is_direct: bool = False
        self.linearity_source: Optional[str] = None
        self.linearity_info: Optional[Dict] = None
        self._linearity_params: Optional[Dict] = None

        # Stage 3: Drift correction state
        self.drift_correction_applied: bool = False
        self.drift_monitor_used: Optional[str] = None
        self.drift_degree: int = 1
        self.drift_slope: Optional[float] = None
        self.drift_std_err: Optional[float] = None
        self.drift_ci95: Optional[float] = None
        self.drift_p_value: Optional[float] = None
        self.drift_r2: Optional[float] = None
        self.drift_poly_coeffs: Optional[List[float]] = None
        self.drift_info: Optional[Dict] = None
        self._drift_params: Optional[Dict] = None

        # Stage 4b: Elemental composition calibration state
        self.elemental_calibration_applied: bool = False
        self.elemental_info: Optional[Dict] = None
        self._elemental_params: Optional[Dict] = None

        # Processing & diagnostics state
        self.use_method_precision: bool = False
        self.summary: Optional[pd.DataFrame] = None
        self.strategy: Optional[CalibrationStrategy] = None
        self._alerts: pd.DataFrame = pd.DataFrame(columns=["row", "sample_name", "reason"])
        self._acquisition_date: Optional[str] = None

        # 3. Initial Diagnostics
        self.detect_outliers()
        self.initial_alerts: pd.DataFrame = self._alerts.copy()
        if not self._alerts.empty:
            warnings.warn(
                f"Detected {len(self._alerts)} suspicious data points on initial load. "
                "Check the .alerts property for details."
            )

    @property
    def filename(self) -> str:
        """Returns the basename of the source data file."""
        return os.path.basename(self.filepath) if self.filepath else "Unknown File"

    @property
    def acquisition_date(self) -> str:
        """
        Returns the measurement/acquisition date (YYYY-MM-DD).
        Can be set manually or inferred from filename/file mtime.
        """
        if self._acquisition_date:
            return self._acquisition_date

        if self.filepath:
            fname = os.path.basename(self.filepath)
            m_dmy = re.search(r"(\d{2})(\d{2})(\d{2,4})", fname)
            if m_dmy:
                d, m, y = m_dmy.groups()
                if len(y) == 2:
                    y = "20" + y
                try:
                    d_obj = datetime.date(int(y), int(m), int(d))
                    return d_obj.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            m_ymd = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", fname)
            if m_ymd:
                y, m, d = m_ymd.groups()
                try:
                    d_obj = datetime.date(int(y), int(m), int(d))
                    return d_obj.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            try:
                mtime = os.path.getmtime(self.filepath)
                return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except OSError:
                pass

        return dt.now().strftime("%Y-%m-%d")

    @acquisition_date.setter
    def acquisition_date(self, value: str):
        self._acquisition_date = value

    @property
    def data_view(self) -> pd.DataFrame:
        """Returns the full raw data for preliminary analysis and inspection."""
        return self.replicates

    @property
    def alerts(self) -> pd.DataFrame:
        """Returns a table of flagged outliers and problematic data."""
        return self._alerts

    def _check_extrapolation_alerts(self, valid: pd.DataFrame, norm_col: str) -> List[Dict]:
        """Checks if normalized unknown samples fall outside the calibrated true span of anchors."""
        extrap_alerts = []
        if len(self.anchors) < 2 or norm_col not in valid.columns:
            return extrap_alerts

        anchor_trues = [std.d_true for std in self.anchors.values()]
        a_min, a_max = min(anchor_trues), max(anchor_trues)

        for _, row in valid.iterrows():
            sname = row["sample_name"]
            if self.get_canonical_name(sname, self.anchors):
                continue
            val = row[norm_col]
            if pd.notna(val) and (val < a_min or val > a_max):
                extrap_alerts.append(
                    {
                        "row": row.get("row", -1),
                        "sample_name": sname,
                        "reason": (
                            f"Scale Extrapolation: Normalized value ({val:.2f} ‰) is outside "
                            f"the calibrated anchor span [{a_min:.2f}, {a_max:.2f}] ‰."
                        ),
                    }
                )
        return extrap_alerts

    def detect_outliers(self):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        Runs automatic diagnostics to identify suspicious data points.

        1. Missing Sample Peak / Autosampler Drop Failure Check.
        2. Double Drop / Abnormal Response Factor Check (Area/Amount).
        3. Range Check & Anchor Extrapolation Check (on normalized data).
        4. Precision Check (Sample SD > 3x method precision) with Instrument-Precision Flyer Pinpointing.
        5. Amplitude Check: Amplitude < 50% or > 200% of run median.
        6. Single Replicate Check (n=1): Fallback to instrumental method precision.
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
                    "reason": (
                        f"Missing Sample Peak: No sample peak detected for Row {r} ({name}). "
                        "Suspected autosampler drop failure."
                    ),
                }
            )

        if valid.empty:
            self._alerts = pd.DataFrame(alerts)
            if not self._alerts.empty:
                self._alerts = pd.DataFrame(alerts).drop_duplicates()
            return

        # --- 0b. Double Drop / Response Anomaly Check ---
        area_col = self._find_preferred_area_column(valid)
        if "amount" in valid.columns and area_col:
            weighed = valid[
                valid["amount"].notna() & (valid["amount"] > 0) & valid[area_col].notna()
            ].copy()
            if not weighed.empty:
                weighed["response"] = weighed[area_col] / weighed["amount"]
                median_resp = weighed["response"].median()

                if median_resp > 0:
                    high_resp = weighed[weighed["response"] > 1.5 * median_resp]
                    for _, row in high_resp.iterrows():
                        r_num = row.get("row", -1)
                        resp_val = row["response"]
                        if r_num - 1 in missing_rows_list or r_num - 2 in missing_rows_list:
                            reason = (
                                f"Double Drop Suspected: Unusually high response factor "
                                f"({resp_val:.0f} vs median {median_resp:.0f}) following missing sample peak."
                            )
                        else:
                            reason = (
                                f"Abnormal Area/Amount Ratio: Response factor ({resp_val:.0f}) > "
                                f"1.5x run median ({median_resp:.0f}). Suspected double drop or weighing error."
                            )

                        alerts.append(
                            {
                                "row": r_num,
                                "sample_name": row["sample_name"],
                                "reason": reason,
                            }
                        )

        # --- 1. Range Check & Anchor Extrapolation Check (Normalized only) ---
        norm_col = f"corrected_{self.config.target_column}"
        if norm_col in valid.columns:
            r_min, r_max = self.config.absolute_range
            out_of_range = valid[(valid[norm_col] < r_min) | (valid[norm_col] > r_max)]
            for _, row in out_of_range.iterrows():
                alerts.append(
                    {
                        "row": row.get("row", -1),
                        "sample_name": row["sample_name"],
                        "reason": (
                            f"Value {row[norm_col]:.2f} is outside expected range ({r_min}, {r_max})"
                        ),
                    }
                )
            alerts.extend(self._check_extrapolation_alerts(valid, norm_col))

        # --- 2. Precision Check (Variance) & Small-N Flyer Pinpointing ---
        # Note: Classical parametric outlier tests (Grubbs', Dixon's Q) have poor statistical power
        # at routine CF-IRMS replicate counts (n=2 to 4). Instead, we use the known instrumental
        # method repeatability (sigma_method) as an external reference scale:
        #   - For n >= 3, any replicate deviating from the group median by > 3*sigma_method
        #     (and accounting for the majority of the group spread) is pinpointed as the suspected flyer.
        #   - For n = 2, the median equals the mean so neither replicate can be distinguished without
        #     an external check (amplitude/area), so both rows are flagged for review.
        if self.config.method_precision > 0:
            threshold = 3 * self.config.method_precision
            precision_stats = valid.groupby("sample_name")["working_value"].std().reset_index()
            flagged_samples = precision_stats[precision_stats["working_value"] > threshold][
                "sample_name"
            ]

            for name in flagged_samples:
                sample_rows = valid[valid["sample_name"] == name]
                val_std = precision_stats[precision_stats["sample_name"] == name][
                    "working_value"
                ].values[0]

                flyer_suffix = ""
                if len(sample_rows) >= 3:
                    med_val = sample_rows["working_value"].median()
                    deviations = (sample_rows["working_value"] - med_val).abs()
                    flyers = sample_rows[deviations > threshold]
                    if not flyers.empty and "row" in flyers.columns:
                        flyer_rows_str = ", ".join(str(int(r)) for r in flyers["row"].tolist())
                        flyer_suffix = f" (Suspected flyer: Row {flyer_rows_str})"

                for _, row in sample_rows.iterrows():
                    alerts.append(
                        {
                            "row": row.get("row", -1),
                            "sample_name": name,
                            "reason": (
                                f"High Variance: SD ({val_std:.2f}) > 3x method precision "
                                f"({threshold:.2f}){flyer_suffix}"
                            ),
                        }
                    )

        # --- 3. Amplitude Check ---
        amp_col = self.config.amplitude_column
        if amp_col and amp_col in valid.columns:
            median_amp = valid[amp_col].median()
            bad_amp = valid[
                (valid[amp_col] < 0.5 * median_amp) | (valid[amp_col] > 2.0 * median_amp)
            ]
            for _, row in bad_amp.iterrows():
                alerts.append(
                    {
                        "row": row.get("row", -1),
                        "sample_name": row["sample_name"],
                        "reason": (
                            f"Amplitude Anomaly: {row[amp_col]:.0f} is far from run median ({median_amp:.0f})"
                        ),
                    }
                )

        # --- 4. Single Replicate Check (n=1) ---
        if not getattr(self, "use_method_precision", False):
            prec = self.config.method_precision if self.config.method_precision > 0 else 0.10
            counts = valid.groupby("sample_name")["working_value"].count()
            single_reps = counts[counts == 1].index.tolist()
            for sname in single_reps:
                sample_rows = valid[valid["sample_name"] == sname]
                r_num = sample_rows["row"].iloc[0] if not sample_rows.empty else -1
                alerts.append(
                    {
                        "row": r_num,
                        "sample_name": sname,
                        "reason": (
                            f"Single Replicate (n=1): Defaulted to instrumental method precision "
                            f"(1-σ = {prec:.2f} ‰) for uncertainty propagation."
                        ),
                    }
                )

        self._alerts = pd.DataFrame(alerts)
        if not self._alerts.empty:
            self._alerts = self._alerts.drop_duplicates()

    @property
    def excluded_rows_list(self) -> List[int]:
        """Returns a sorted list of unique Isodat row IDs currently marked as excluded."""
        if (
            hasattr(self, "replicates")
            and isinstance(self.replicates, pd.DataFrame)
            and "row" in self.replicates.columns
            and "excluded" in self.replicates.columns
        ):
            excluded_df = self.replicates[self.replicates["excluded"]]
            if not excluded_df.empty:
                return sorted(list(excluded_df["row"].unique().astype(int)))
        return []

    # --- Data Cleaning & Canonical Correction Pipeline ---

    def exclude_rows(self, row_ids: List[int]):
        """
        Manually excludes specific rows (by Isodat Row number) from processing.
        Automatically recomputes active pre-calibration corrections and refreshes diagnostics.

        Args:
            row_ids: List of 'row' numbers to exclude.
        """
        if "row" in self.replicates.columns:
            mask = self.replicates["row"].isin(row_ids)
            self.replicates.loc[mask, "excluded"] = True
            self._recompute_working_values()
        else:
            raise KeyError("Data does not contain 'row' column for exclusion.")

    def exclude_first_injections(self, n_skip: int = 1):
        """
        Excludes the first `n_skip` injections of every contiguous vial/sample block
        (ordered by injection 'row'), provided the block has more than `n_skip` injections.
        Essential for liquid water IRMS runs where early injections suffer from memory carryover.

        Args:
            n_skip: Number of initial injections to exclude per contiguous sample block.
        """
        if n_skip < 1:
            raise ValueError("n_skip must be >= 1.")

        valid = self.replicates[~self.replicates["excluded"]].sort_values("row")
        if valid.empty:
            return

        # Identify contiguous blocks where sample_name stays the same
        block_ids = (valid["sample_name"] != valid["sample_name"].shift()).cumsum()
        rows_to_exclude = []
        for _, block in valid.groupby(block_ids):
            if len(block) > n_skip:
                rows_to_exclude.extend(block["row"].iloc[:n_skip].tolist())

        if rows_to_exclude:
            self.exclude_rows(rows_to_exclude)

    def _recompute_working_values(self):
        """
        Executes all active pre-calibration corrections in the strict CF-IRMS order of operations:
            0. Reset working_value from raw target_column
            0b. Memory / Carryover Correction (Liquid Water)
            1. Blank Correction (Mass Balance)
            2. Linearity Correction (Peak Size / Signal Intensity)
            3. Drift Correction (Temporal / Sequence Position)
            4. Refresh diagnostics and invalidate calibration summary
        """
        self.replicates["working_value"] = self.replicates[self.config.target_column].copy()

        # 0b. Stage 0b: Sample-to-Sample Memory Correction
        if self.memory_correction_applied and self._memory_params is not None:
            self._execute_memory_stage(**self._memory_params)

        # 1. Stage 1: Mass-Balance Blank Correction
        if self.blank_correction_applied and self._blank_params:
            self._execute_blank_stage(**self._blank_params)

        # 2. Stage 2: Signal Intensity / Peak Area Linearity Correction
        if self.linearity_correction_applied and self._linearity_params:
            self._execute_linearity_stage(**self._linearity_params)

        # 3. Stage 3: Temporal Sequence Drift Correction
        if self.drift_correction_applied and self._drift_params:
            self._execute_drift_stage(**self._drift_params)

        # 4. Invalidate calibration summary and refresh outlier diagnostics
        self.summary = None
        self.detect_outliers()

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

    # --- Stage 0b: Memory / Carryover Correction ---

    def apply_memory_correction(
        self, coefficients: Optional[List[float]] = None, max_injections: int = 3
    ):
        """
        Applies sample-to-sample memory (carryover) correction across contiguous vial blocks
        (Stage 0b of CF-IRMS pipeline, following Gröning 2011/2018 & van Geldern & Barth 2012).

        Formula for injection j (0-indexed within new vial block i) following vial block i-1:
            d_corr = d_meas + (m_j / (1 - m_j)) * (d_meas - d_prev_vial_final)

        Args:
            coefficients: List of memory fractions [m_1, m_2, ...] for the 1st, 2nd, ...
                injections of each new vial block. If None, automatically estimated from
                transitions between consecutive blocks with large isotopic step changes.
            max_injections: Number of initial injections per block to estimate when
                coefficients is None (default 3).
        """
        self._memory_params = {
            "coefficients": coefficients,
            "max_injections": max_injections,
        }
        self.memory_correction_applied = True
        self._recompute_working_values()

    def _estimate_memory_coefficients(
        self, valid_sorted: pd.DataFrame, max_injections: int = 3
    ) -> List[float]:
        """
        Estimates memory coefficients [m_1, m_2, ...] from contiguous vial transitions
        where the step change |d_curr_final - d_prev_final| is significant (> 5 ‰)
        and the block has at least max_injections + 1 replicates.
        """
        block_ids = (
            valid_sorted["sample_name"] != valid_sorted["sample_name"].shift()
        ).cumsum()
        blocks = [group for _, group in valid_sorted.groupby(block_ids)]

        coeff_samples: List[List[float]] = [[] for _ in range(max_injections)]
        for idx in range(1, len(blocks)):
            prev_blk = blocks[idx - 1]
            curr_blk = blocks[idx]
            if len(curr_blk) <= max_injections:
                continue

            # Asymptotic true/final value of previous and current blocks (mean of last 2 injections)
            prev_final = float(prev_blk["working_value"].iloc[-2:].mean())
            curr_final = float(curr_blk["working_value"].iloc[-2:].mean())
            step = curr_final - prev_final
            if abs(step) < 5.0:
                continue

            for j in range(max_injections):
                meas_j = float(curr_blk["working_value"].iloc[j])
                # m_j = (curr_final - meas_j) / (curr_final - prev_final)
                m_j = (curr_final - meas_j) / step
                if 0.0 <= m_j < 0.8:
                    coeff_samples[j].append(m_j)

        estimated = []
        for j in range(max_injections):
            if coeff_samples[j]:
                estimated.append(round(float(np.median(coeff_samples[j])), 4))
            else:
                estimated.append(0.0)
        return estimated

    def _execute_memory_stage(
        self, coefficients: Optional[List[float]] = None, max_injections: int = 3
    ):
        """Internal execution of Stage 0b (Memory Correction) on raw working_value."""
        valid_mask = ~self.replicates["excluded"]
        valid_sorted = self.replicates[valid_mask].sort_values("row").copy()

        if valid_sorted.empty:
            return

        is_auto = coefficients is None
        if is_auto:
            coeffs = self._estimate_memory_coefficients(valid_sorted, max_injections)
        else:
            coeffs = [float(c) for c in coefficients]

        block_ids = (
            valid_sorted["sample_name"] != valid_sorted["sample_name"].shift()
        ).cumsum()
        blocks = [(blk_id, group) for blk_id, group in valid_sorted.groupby(block_ids)]

        d_mem_series = self.replicates["working_value"].copy()
        prev_final: Optional[float] = None

        for _, grp in blocks:
            # Asymptotic final value of this block (mean of trailing replicates)
            tail_count = min(2, len(grp))
            curr_final = float(grp["working_value"].iloc[-tail_count:].mean())

            if prev_final is not None:
                for j, (row_idx, row_data) in enumerate(grp.iterrows()):
                    if j < len(coeffs) and 0.0 < coeffs[j] < 1.0:
                        m_j = coeffs[j]
                        d_meas = float(row_data["working_value"])
                        d_corr = d_meas + (m_j / (1.0 - m_j)) * (d_meas - prev_final)
                        d_mem_series.loc[row_idx] = d_corr

            prev_final = curr_final

        self.replicates["d_memory_corrected"] = d_mem_series
        self.replicates["working_value"] = d_mem_series
        self.memory_coefficients = coeffs
        self.memory_info = {
            "coefficients": coeffs,
            "source": "Auto-Estimated from Sequence Step Transitions"
            if is_auto
            else "Manual Coefficients",
        }

    # --- Stage 1: Blank Correction ---

    def _find_preferred_area_column(self, df: pd.DataFrame) -> Optional[str]:
        """Finds the primary peak area column based on config amplitude suffix or standard names."""
        possible_areas = []
        if self.config.amplitude_column:
            suffix = self.config.amplitude_column.split("_")[-1]
            possible_areas.append(f"area_{suffix}")
        possible_areas.extend(["area_44", "area_28", "area_2", "area_all"])

        for col in possible_areas:
            if col in df.columns:
                return col
        return None

    def apply_blank_correction(
        self, blank_identifier: str = "bco cap", area_column: Optional[str] = None
    ):
        """
        Applies mass-balance blank correction to working values (Stage 1 of CF-IRMS pipeline).

        Formula:
            A_net = A_raw - A_blk
            d_corr = (A_raw * d_raw - A_blk * d_blk) / A_net

        Args:
            blank_identifier: Name (or partial alias) of the blank sample.
            area_column: Specific area column to use. If None, auto-detected.
        """
        self._blank_params = {
            "blank_identifier": blank_identifier,
            "area_column": area_column,
        }
        self.blank_correction_applied = True
        self._recompute_working_values()

    def _execute_blank_stage(
        self, blank_identifier: str = "bco cap", area_column: Optional[str] = None
    ):
        """Internal execution of Stage 1 (Blank Correction)."""
        valid = self.replicates[~self.replicates["excluded"]].copy()

        blank_mask = (
            valid["sample_name"].str.strip().str.lower() == blank_identifier.strip().lower()
        )
        blank_rows = valid[blank_mask]

        if blank_rows.empty:
            self.blank_correction_applied = False
            self._blank_params = None
            raise ValueError(
                f"No valid rows matching blank identifier '{blank_identifier}' found."
            )

        if area_column is None:
            area_column = self._find_preferred_area_column(self.replicates)

        if not area_column or area_column not in self.replicates.columns:
            self.blank_correction_applied = False
            self._blank_params = None
            raise KeyError("Could not auto-detect a valid 'area' column for blank correction.")

        n_blk = len(blank_rows)
        a_blk = float(blank_rows[area_column].mean())
        a_blk_std = float(blank_rows[area_column].std()) if n_blk > 1 else 0.0
        a_blk_sem = a_blk_std / np.sqrt(n_blk) if n_blk > 1 else 0.0

        d_blk = float(blank_rows["working_value"].mean())
        d_blk_std = float(blank_rows["working_value"].std()) if n_blk > 1 else 0.0
        d_blk_sem = d_blk_std / np.sqrt(n_blk) if n_blk > 1 else 0.0

        a_raw = self.replicates[area_column]
        d_raw = self.replicates["working_value"]

        a_net = a_raw - a_blk
        d_corr = (a_raw * d_raw - a_blk * d_blk) / a_net

        self.replicates["area_net"] = a_net
        self.replicates["d_blank_corrected"] = d_corr
        self.replicates["working_value"] = d_corr

        self.blank_info = {
            "identifier": blank_identifier,
            "area_column": area_column,
            "mean_area": a_blk,
            "std_area": a_blk_std,
            "sem_area": float(a_blk_sem),
            "mean_delta": d_blk,
            "std_delta": d_blk_std,
            "sem_delta": float(d_blk_sem),
            "n": n_blk,
        }

    # --- Stage 2: Linearity Analysis & Correction ---

    def detect_area_column(self, area_column: Optional[str] = None) -> str:
        """Detects the numeric peak area or amplitude column for linearity analysis."""
        if area_column and area_column in self.replicates.columns:
            return area_column

        preferred = self._find_preferred_area_column(self.replicates)
        if preferred:
            return preferred

        numeric_cols = self.replicates.select_dtypes(include=[np.number]).columns
        candidates = [
            col
            for col in numeric_cols
            if any(k in col.lower() for k in ["area", "ampl", "intensity", "signal"])
            and col != "area_net"
        ]
        if candidates:
            area_candidates = [c for c in candidates if "area" in c.lower()]
            if area_candidates:
                return area_candidates[0]
            return candidates[0]

        raise ValueError(
            "Could not auto-detect numeric peak area/amplitude column. Please specify 'area_column'."
        )

    def _detect_area_column(self, area_column: Optional[str] = None) -> str:
        """Backward-compatible alias for detect_area_column."""
        return self.detect_area_column(area_column)

    def check_linearity(  # pylint: disable=too-many-locals
        self,
        substance_name: Optional[str] = None,
        area_column: Optional[str] = None,
        use_working: bool = True,
        target_col_override: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Quantifies signal intensity / peak area dependence (linearity) using OLS regression.

        Calculates:
        - Slope (delta per area/amplitude unit)
        - Std_Err (1-sigma standard error of the slope)
        - CI_95 (95% Confidence Interval for slope)
        - p_value and R_squared

        Args:
            substance_name: Optional standard/sample name to evaluate. If None, evaluates all groups.
            area_column: Specific peak area or amplitude column name. Auto-detected if None.
            use_working: Whether to regress working_value (True) or raw target delta (False).
            target_col_override: Optional internal column name to regress against area.
        """
        if target_col_override and target_col_override in self.replicates.columns:
            col_to_use = target_col_override
        else:
            col_to_use = "working_value" if use_working else self.config.target_column

        area_col = self.detect_area_column(area_column)
        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        if substance_name:
            combined_reg = {**self.anchors, **self.controls, **self.drift_monitors}
            sub_canonical = self.get_canonical_name(substance_name, combined_reg)
            std_obj = None
            if not sub_canonical:
                std_obj = get_standard(substance_name, target_column=self.config.target_column)
                sub_canonical = std_obj.name if std_obj else substance_name

            mask = (
                valid_data["sample_name"].str.strip().str.lower()
                == sub_canonical.strip().lower()
            )
            if not mask.any() and std_obj:
                mask = valid_data["sample_name"].apply(std_obj.matches)
            if not mask.any():
                mask = valid_data["sample_name"].str.contains(
                    substance_name, case=False, na=False
                )
            filtered = valid_data[mask]
        else:
            filtered = valid_data

        if filtered.empty:
            return pd.DataFrame(
                columns=["Slope", "Std_Err", "CI_95", "p_value", "R_squared", "n", "Mean_Area"]
            )

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

            results.append(
                {
                    "Substance": name,
                    "Slope": slope,
                    "Std_Err": float(std_err) if not np.isnan(std_err) else 0.0,
                    "CI_95": ci_95,
                    "p_value": p_value,
                    "R_squared": r_value**2,
                    "n": len(x),
                    "Mean_Area": x.mean(),
                }
            )

        if not results:
            return pd.DataFrame(
                columns=["Slope", "Std_Err", "CI_95", "p_value", "R_squared", "n", "Mean_Area"]
            )

        return pd.DataFrame(results).set_index("Substance")

    def apply_linearity_correction(
        self,
        slope: Optional[float] = None,
        substance_name: Optional[str] = None,
        area_ref: Optional[float] = None,
        area_column: Optional[str] = None,
    ):
        """
        Applies mass/intensity linearity correction to working_value (Stage 2 of CF-IRMS pipeline).

        Formula:
            working_value = working_value - slope * (area - area_ref)
        """
        if slope is None and not substance_name:
            raise ValueError(
                "Must provide either a direct 'slope' or a 'substance_name' to infer slope."
            )

        self._linearity_params = {
            "slope": slope,
            "substance_name": substance_name,
            "area_ref": area_ref,
            "area_column": area_column,
        }
        self.linearity_correction_applied = True
        self._recompute_working_values()

    def _execute_linearity_stage(
        self,
        slope: Optional[float] = None,
        substance_name: Optional[str] = None,
        area_ref: Optional[float] = None,
        area_column: Optional[str] = None,
    ):
        """Internal execution of Stage 2 (Linearity Correction) on post-blank working_value."""
        area_col = self.detect_area_column(area_column)

        self.replicates["pre_linearity_working_value"] = self.replicates[
            "working_value"
        ].copy()

        std_err = 0.0
        ci_95 = None
        p_val = None
        r2 = None

        is_direct = slope is not None
        source_str = (
            "Direct Input (Transferred Slope)" if is_direct else "Inferred from Run Replicates"
        )

        if slope is None:
            stats = self.check_linearity(
                substance_name=substance_name,
                area_column=area_col,
                target_col_override="pre_linearity_working_value",
            )
            if stats.empty:
                self.linearity_correction_applied = False
                self._linearity_params = None
                raise ValueError(
                    f"Could not calculate linearity slope for substance '{substance_name}'. "
                    "Insufficient data."
                )
            matched_name = stats.index[0]
            slope = float(stats.loc[matched_name, "Slope"])
            std_err = float(stats.loc[matched_name, "Std_Err"])
            ci_95 = float(stats.loc[matched_name, "CI_95"])
            p_val = float(stats.loc[matched_name, "p_value"])
            r2 = float(stats.loc[matched_name, "R_squared"])
        elif substance_name:
            stats = self.check_linearity(
                substance_name=substance_name,
                area_column=area_col,
                target_col_override="pre_linearity_working_value",
            )
            if not stats.empty:
                matched_name = stats.index[0]
                std_err = float(stats.loc[matched_name, "Std_Err"])
                ci_95 = float(stats.loc[matched_name, "CI_95"])
                p_val = float(stats.loc[matched_name, "p_value"])
                r2 = float(stats.loc[matched_name, "R_squared"])

        valid_mask = ~self.replicates["excluded"]
        if area_ref is None:
            area_ref = float(self.replicates.loc[valid_mask, area_col].median())

        d_lin = self.replicates["pre_linearity_working_value"] - slope * (
            self.replicates[area_col] - area_ref
        )
        self.replicates["d_linearity_corrected"] = d_lin
        self.replicates["working_value"] = d_lin

        self.linearity_slope = slope
        self.linearity_std_err = std_err
        self.linearity_ci95 = ci_95
        self.linearity_p_value = p_val
        self.linearity_r2 = r2
        self.linearity_substance_used = substance_name or "Manual Input"
        self.linearity_area_ref = area_ref
        self.linearity_is_direct = is_direct
        self.linearity_source = source_str
        self.linearity_info = {
            "slope": slope,
            "std_err": std_err,
            "ci_95": ci_95,
            "p_value": p_val,
            "r_squared": r2,
            "substance": substance_name or "Manual Input",
            "area_ref": area_ref,
            "area_column": area_col,
            "is_direct": is_direct,
            "source": source_str,
        }

    # --- Stage 3: Drift Analysis & Correction ---

    def _get_pre_drift_column(self) -> str:
        """
        Returns the column representing the data state immediately prior to drift correction.
        """
        if "pre_drift_working_value" in self.replicates.columns:
            return "pre_drift_working_value"
        if (
            self.linearity_correction_applied
            and "d_linearity_corrected" in self.replicates.columns
        ):
            return "d_linearity_corrected"
        if self.blank_correction_applied and "d_blank_corrected" in self.replicates.columns:
            return "d_blank_corrected"
        if self.memory_correction_applied and "d_memory_corrected" in self.replicates.columns:
            return "d_memory_corrected"
        return self.config.target_column

    def check_drift(
        self, use_working: bool = False, target_col_override: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculates linear regression (Target vs Row) for all drift monitors.

        Returns a summary of slopes, standard errors, p-values, and 95% Confidence Intervals.
        """
        if not self.drift_monitors:
            raise ValueError("No drift monitors set. Use set_drift_monitors() first.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self.get_canonical_name(x, self.drift_monitors)
        )
        drift_data = valid_data[valid_data["canonical_name"].notna()]

        if target_col_override and target_col_override in valid_data.columns:
            col_to_use = target_col_override
        elif use_working:
            col_to_use = "working_value"
        else:
            col_to_use = self._get_pre_drift_column()

        results = []
        for name, group in drift_data.groupby("canonical_name"):
            if len(group) < 3:
                continue

            x = group["row"]
            y = group[col_to_use]

            slope, _, r_value, p_value, std_err = sp_stats.linregress(x, y)

            df_deg = len(x) - 2
            t_crit = sp_stats.t.ppf(0.975, df_deg)
            ci_95 = t_crit * std_err

            results.append(
                {
                    "Standard": name,
                    "Slope": slope,
                    "Std_Err": float(std_err) if not np.isnan(std_err) else 0.0,
                    "CI_95": ci_95,
                    "p_value": p_value,
                    "R_squared": r_value**2,
                    "n": len(x),
                }
            )

        if not results:
            return pd.DataFrame(
                columns=["Slope", "Std_Err", "CI_95", "p_value", "R_squared", "n"]
            )

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

        col_to_use = "working_value" if use_working else self._get_pre_drift_column()

        sns.scatterplot(
            data=drift_data,
            x="row",
            y=col_to_use,
            hue="canonical_name",
            s=60,
            alpha=0.7,
            ax=ax,
            zorder=3,
        )

        stats_df = self.check_drift(use_working=use_working)
        for i, (name, row) in enumerate(stats_df.iterrows()):
            group = drift_data[drift_data["canonical_name"] == name]
            x = group["row"]
            y = group[col_to_use]

            slope = row["Slope"]
            intercept = y.mean() - slope * x.mean()
            x_range = np.array([x.min(), x.max()])
            y_range = slope * x_range + intercept

            ax.plot(x_range, y_range, linestyle="--", alpha=0.8, zorder=2, color="black")

            txt = (
                f"{name}:\n\n"
                f"  y = {slope:.3f}x + {intercept:.3f}\n"
                f"  Slope CI 95%: {slope:.3f} ± {row['CI_95']:.3f}\n"
                f"  R² = {row['R_squared']:.3f}, p = {row['p_value']:.3f}"
            )

            ax.annotate(
                txt,
                xy=(0.02, 0.95 - i * 0.15),
                xycoords="axes fraction",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8),
                verticalalignment="top",
            )

        ax.set_title(f"Analytical Drift: {self.config.name}", fontsize=12, fontweight="bold")
        ax.set_xlabel("Injection (Row)", fontsize=10)
        ax.set_ylabel(
            f"{'Working' if use_working else 'Pre-Drift'} {self.config.target_column}",
            fontsize=10,
        )
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(title="Drift Monitor", loc="lower right")

        return ax

    def apply_drift_correction(self, monitor_name: str, degree: int = 1):
        """
        Applies a linear (degree=1) or polynomial (degree>=2) drift correction to the working
        data based on the specified monitor (Stage 3 of CF-IRMS pipeline).

        Args:
            monitor_name: Name or alias of the drift monitor standard.
            degree: Polynomial degree for drift modeling (1 = linear, 2 = quadratic, etc.).
        """
        if degree < 1:
            raise ValueError("Drift polynomial degree must be >= 1.")

        self._drift_params = {"monitor_name": monitor_name, "degree": degree}
        self.drift_correction_applied = True
        self._recompute_working_values()

    def _execute_drift_stage(self, monitor_name: str, degree: int = 1):
        """Internal execution of Stage 3 (Drift Correction) on post-blank/post-linearity working_value."""
        self.replicates["pre_drift_working_value"] = self.replicates["working_value"].copy()

        drift_stats = self.check_drift(
            use_working=False, target_col_override="pre_drift_working_value"
        )

        resolved_monitor = monitor_name
        if resolved_monitor not in drift_stats.index:
            resolved_monitor = self.get_canonical_name(monitor_name, self.drift_monitors)
            if not resolved_monitor or resolved_monitor not in drift_stats.index:
                self.drift_correction_applied = False
                self._drift_params = None
                raise ValueError(
                    f"Monitor standard '{monitor_name}' not found or has insufficient data for drift analysis."
                )

        slope = float(drift_stats.loc[resolved_monitor, "Slope"])
        std_err = float(drift_stats.loc[resolved_monitor, "Std_Err"])
        ci_95 = float(drift_stats.loc[resolved_monitor, "CI_95"])
        p_val = float(drift_stats.loc[resolved_monitor, "p_value"])
        r2 = float(drift_stats.loc[resolved_monitor, "R_squared"])

        if degree == 1:
            d_drift = self.replicates["pre_drift_working_value"] - (
                slope * self.replicates["row"]
            )
            poly_coeffs = [slope, 0.0]
        else:
            valid = self.replicates[~self.replicates["excluded"]]
            mon_rows = valid[
                valid["sample_name"].apply(
                    lambda x: self.get_canonical_name(x, self.drift_monitors) == resolved_monitor
                )
            ]
            if len(mon_rows) <= degree:
                raise ValueError(
                    f"Insufficient monitor replicates ({len(mon_rows)}) for degree={degree} polynomial drift."
                )
            x_mon = mon_rows["row"].values.astype(float)
            y_mon = mon_rows["pre_drift_working_value"].values.astype(float)
            coeffs = np.polyfit(x_mon, y_mon, degree)
            poly_coeffs = [float(c) for c in coeffs]

            # Evaluate polynomial drift relative to sequence start/intercept (constant term coeffs[-1])
            poly_trend = np.polyval(coeffs, self.replicates["row"].values.astype(float)) - coeffs[-1]
            d_drift = self.replicates["pre_drift_working_value"] - poly_trend

            # Compute polynomial R^2
            y_hat = np.polyval(coeffs, x_mon)
            ss_res = np.sum((y_mon - y_hat) ** 2)
            ss_tot = np.sum((y_mon - np.mean(y_mon)) ** 2)
            r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0

        self.replicates["d_drift_corrected"] = d_drift
        self.replicates["working_value"] = d_drift

        self.drift_monitor_used = resolved_monitor
        self.drift_degree = degree
        self.drift_slope = slope
        self.drift_std_err = std_err
        self.drift_ci95 = ci_95
        self.drift_p_value = p_val
        self.drift_r2 = r2
        self.drift_poly_coeffs = poly_coeffs
        self.drift_info = {
            "monitor": resolved_monitor,
            "degree": degree,
            "slope": slope,
            "std_err": std_err,
            "ci_95": ci_95,
            "p_value": p_val,
            "r_squared": r2,
            "poly_coeffs": poly_coeffs,
        }

    # --- Stage 4b: Elemental Mass Fraction (%C, %N) Calibration ---

    def calibrate_elemental_composition(
        self,
        standards: Optional[Dict[str, float]] = None,
        area_column: Optional[str] = None,
    ):
        """
        Calibrates elemental weight percent (%C, %N) using sample weights ('amount')
        and peak areas against reference standards with known mass fractions.

        Args:
            standards: Optional dictionary mapping standard name -> weight percent (e.g. {"ac benzoico": 68.85}).
                       If None, uses `mass_fraction` from registered anchors/controls or default standards.
            area_column: Optional area column name. Defaults to 'area_net' if blank-corrected,
                         else auto-detected area column.
        """
        self._elemental_params = {
            "standards": standards,
            "area_column": area_column,
        }
        self.elemental_calibration_applied = True
        self._execute_elemental_stage(standards=standards, area_column=area_column)
        if self.summary is not None:
            self._attach_elemental_to_summary()

    def _execute_elemental_stage(  # pylint: disable=too-many-locals
        self,
        standards: Optional[Dict[str, float]] = None,
        area_column: Optional[str] = None,
    ):
        """Internal execution of elemental weight percent calibration."""
        if "amount" not in self.replicates.columns:
            self.elemental_calibration_applied = False
            raise KeyError("Data does not contain 'amount' (sample weight) column.")

        if area_column is None:
            if self.blank_correction_applied and "area_net" in self.replicates.columns:
                area_col = "area_net"
            else:
                area_col = self.detect_area_column()
        else:
            area_col = area_column

        valid = self.replicates[~self.replicates["excluded"]].copy()
        weighed = valid[
            valid["amount"].notna() & (valid["amount"] > 0) & valid[area_col].notna()
        ].copy()

        if weighed.empty:
            self.elemental_calibration_applied = False
            raise ValueError("No valid weighed rows with positive 'amount' and peak area.")

        # Resolve known mass fractions for standards in the run
        def lookup_mass_fraction(sname: str) -> Optional[float]:
            if standards:
                for k, v in standards.items():
                    if k.strip().lower() == sname.strip().lower() or k.strip().lower() in sname.strip().lower():
                        return float(v)
            combined_reg = {**self.anchors, **self.controls, **self.drift_monitors}
            can = self.get_canonical_name(sname, combined_reg)
            if can and combined_reg[can].mass_fraction is not None:
                return float(combined_reg[can].mass_fraction)
            std_obj = get_standard(sname, target_column=self.config.target_column)
            if std_obj and std_obj.mass_fraction is not None:
                return float(std_obj.mass_fraction)
            return None

        weighed["known_mass_pct"] = weighed["sample_name"].apply(lookup_mass_fraction)
        cal_rows = weighed[weighed["known_mass_pct"].notna()].copy()

        if cal_rows.empty:
            self.elemental_calibration_applied = False
            raise ValueError(
                "No standards with known elemental mass_fraction found in weighed replicates."
            )

        # Elemental mass in standards: M_elem = amount * (mass_pct / 100.0)
        cal_rows["elem_mass"] = cal_rows["amount"] * (cal_rows["known_mass_pct"] / 100.0)

        # Response factor k = sum(area * elem_mass) / sum(area^2) (linear through origin)
        areas_std = cal_rows[area_col].values.astype(float)
        masses_std = cal_rows["elem_mass"].values.astype(float)
        k_factor = float(np.sum(areas_std * masses_std) / np.sum(areas_std**2))

        # Relative standard error of k_factor across calibration replicates
        indiv_k = masses_std / areas_std
        rel_u_k = (
            float(np.std(indiv_k, ddof=1) / (np.sqrt(len(indiv_k)) * k_factor))
            if len(indiv_k) > 1 and k_factor > 0
            else 0.01
        )

        elem_sym = self.config.element_symbol or "Element"
        pct_col = f"weight_pct_{elem_sym}"

        # Calculate elemental weight percent for all weighed rows
        valid_amt = self.replicates["amount"] > 0
        est_mass = self.replicates[area_col] * k_factor
        self.replicates[pct_col] = np.where(
            valid_amt, (est_mass / self.replicates["amount"]) * 100.0, np.nan
        )

        self.elemental_info = {
            "element_symbol": elem_sym,
            "pct_column": pct_col,
            "area_column": area_col,
            "k_factor": k_factor,
            "rel_u_k": rel_u_k,
            "n_standards": len(cal_rows),
        }

    def _attach_elemental_to_summary(self):
        """Aggregates elemental weight percent into self.summary if elemental calibration is active."""
        if not self.elemental_calibration_applied or not self.elemental_info or self.summary is None:
            return

        pct_col = self.elemental_info["pct_column"]
        u_pct_col = f"u_{pct_col}"
        rel_u_k = self.elemental_info["rel_u_k"]

        if pct_col not in self.replicates.columns:
            return

        summary_data = self.replicates[~self.replicates["excluded"]].copy()
        summary_data["group_name"] = summary_data["sample_name"].apply(self._get_group_name)

        elem_agg = summary_data.groupby("group_name")[pct_col].agg(["mean", "sem"])
        self.summary[pct_col] = elem_agg["mean"]
        # Combine replicate SEM and calibration response factor uncertainty in quadrature
        sem_filled = elem_agg["sem"].fillna(0.0)
        u_cal = elem_agg["mean"].abs() * rel_u_k
        self.summary[u_pct_col] = np.sqrt(sem_filled**2 + u_cal**2)

    # --- Stage 4: Calibration & Uncertainty Propagation ---

    def _get_working_value_label(self) -> str:
        """Returns a descriptive y-axis label reflecting active pre-calibration corrections."""
        active = []
        if self.memory_correction_applied:
            active.append("Memory")
        if self.blank_correction_applied:
            active.append("Blank")
        if self.linearity_correction_applied:
            active.append("Linearity")
        if self.drift_correction_applied:
            active.append("Drift")
        if active:
            return f"Measured {self.config.target_column} ({'/'.join(active)}-Corrected)"
        return f"Measured {self.config.target_column} (Raw)"

    def plot_calibration(self, ax: Optional[plt.Axes] = None):
        """
        Plots the calibration curve showing all individual anchor replicates
        and the fitted calibration line.
        """
        if self.strategy is None:
            raise RuntimeError("Run .process() before requesting calibration plot.")

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

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

        sns.scatterplot(
            data=anchor_data,
            x="d_true",
            y="working_value",
            hue="canonical_name",
            ax=ax,
            s=60,
            alpha=0.8,
            zorder=3,
        )

        t_min, t_max = anchor_data["d_true"].min(), anchor_data["d_true"].max()
        pad = (t_max - t_min) * 0.1 if t_max != t_min else 1.0
        t_line = np.linspace(t_min - pad, t_max + pad, 100)

        m = self.strategy.slope
        b = self.strategy.intercept
        y_line = (t_line * m) + b

        ax.plot(
            t_line,
            y_line,
            color="black",
            linestyle="--",
            label="Calibration Line",
            zorder=2,
        )

        txt = (
            f"Fit Equation (Measured vs True):\n"
            f"  y = {m:.4f}x + {b:.4f}\n"
            f"  R² = {self.strategy.r_squared:.4f}"
        )

        ax.annotate(
            txt,
            xy=(0.05, 0.95),
            xycoords="axes fraction",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8),
            verticalalignment="top",
        )

        scale_suffix = f" vs. {self.config.scale}" if self.config.scale else ""
        ax.set_title(f"Calibration Curve: {self.config.name}", fontsize=12, fontweight="bold")
        ax.set_xlabel(f"Reference Value (True{scale_suffix})", fontsize=10)
        ax.set_ylabel(self._get_working_value_label(), fontsize=10)
        ax.legend(loc="lower right")
        ax.grid(True, linestyle=":", alpha=0.6)

        return ax

    def _get_group_name(self, raw_name: str) -> str:
        """Maps raw sample names to canonical anchor/control names, or preserves unknown sample names."""
        can_name = self.get_canonical_name(raw_name, self.anchors)
        if can_name:
            return can_name
        can_name = self.get_canonical_name(raw_name, self.controls)
        if can_name:
            return can_name
        return raw_name

    def _compute_precalibration_uncertainties(
        self, summary_data: pd.DataFrame, anchor_rows: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Computes sample-level pre-calibration standard uncertainties (u_blank, u_linearity, u_drift)
        on the working scale for each group in self.summary.
        """
        groups = summary_data.groupby("group_name")
        u_blank_map = {}
        u_lin_map = {}
        u_drift_map = {}

        mean_anchor_row = (
            float(anchor_rows["row"].mean()) if not anchor_rows.empty else 0.0
        )

        for gname, grp in groups:
            # 1. Blank uncertainty via Kragten mass-balance perturbation
            u_b = 0.0
            if self.blank_correction_applied and self.blank_info:
                area_col = self.blank_info["area_column"]
                a_blk = self.blank_info["mean_area"]
                u_a_blk = self.blank_info.get("sem_area", 0.0)
                d_blk = self.blank_info["mean_delta"]
                u_d_blk = self.blank_info.get("sem_delta", 0.0)

                if area_col in grp.columns and (u_a_blk > 0 or u_d_blk > 0):
                    a_raw_mean = float(grp[area_col].mean())
                    d_raw_mean = float(grp[self.config.target_column].mean())
                    if a_raw_mean > a_blk:
                        def blank_model(args, a_s=a_raw_mean, d_s=d_raw_mean):
                            ab, db = args
                            return (a_s * d_s - ab * db) / (a_s - ab)

                        _, u_b = propagate_kragten(
                            blank_model, [a_blk, d_blk], [u_a_blk, u_d_blk]
                        )
            u_blank_map[gname] = float(u_b)

            # 2. Linearity slope uncertainty: |A_samp - A_ref| * u(m_lin)
            u_l = 0.0
            if (
                self.linearity_correction_applied
                and self.linearity_std_err
                and self.linearity_info
            ):
                area_col = self.linearity_info["area_column"]
                area_ref = self.linearity_area_ref or 0.0
                if area_col in grp.columns:
                    a_samp = float(grp[area_col].mean())
                    u_l = abs(a_samp - area_ref) * float(self.linearity_std_err)
            u_lin_map[gname] = float(u_l)

            # 3. Drift slope uncertainty: |row_samp - row_anchors| * u(m_drift)
            u_d = 0.0
            if self.drift_correction_applied and self.drift_std_err and "row" in grp.columns:
                r_samp = float(grp["row"].mean())
                u_d = abs(r_samp - mean_anchor_row) * float(self.drift_std_err)
            u_drift_map[gname] = float(u_d)

        self.summary["u_blank"] = pd.Series(u_blank_map)
        self.summary["u_linearity"] = pd.Series(u_lin_map)
        self.summary["u_drift"] = pd.Series(u_drift_map)
        return self.summary

    def process(self, strategy: CalibrationStrategy, use_method_precision: bool = False):
        """
        The Main Pipeline:

        0. Ensure pre-calibration corrections (Memory -> Blank -> Linearity -> Drift) are up to date
        1. Run Diagnostics (Detect Outliers)
        2. Prepare Anchor Stats for fitting
        3. Fit Strategy (using Anchors from working_value)
        4. Correct Replicates (Row-by-Row)
        5. Aggregate to Summary (Sample-Level) & Compute Pre-Calibration Uncertainties
        6. Propagate Full Uncertainty & Variance Budget (Kragten)
        7. Attach Elemental Composition (if active) & Refresh Diagnostics
        """
        self.strategy = strategy
        self.use_method_precision = use_method_precision

        self._recompute_working_values()

        if not self._alerts.empty:
            warnings.warn(
                f"Detected {len(self._alerts)} suspicious data points. "
                "Check the .alerts property for details."
            )

        valid_data = self.replicates[~self.replicates["excluded"]].copy()

        valid_data["canonical_name"] = valid_data["sample_name"].apply(
            lambda x: self.get_canonical_name(x, self.anchors)
        )
        anchor_rows = valid_data[valid_data["canonical_name"].notna()]

        if anchor_rows.empty:
            raise ValueError("No rows matched the provided Anchor Standards.")

        anchor_stats = anchor_rows.groupby("canonical_name")["working_value"].agg(
            ["mean", "sem", "count"]
        )

        prec = self.config.method_precision if self.config.method_precision > 0 else 0.10
        if use_method_precision:
            anchor_stats["sem"] = prec / np.sqrt(anchor_stats["count"])
        else:
            anchor_stats["sem"] = anchor_stats["sem"].fillna(
                prec / np.sqrt(anchor_stats["count"])
            )

        strategy.fit(anchor_stats, self.anchors)

        target_col = self.config.target_column
        norm_col = f"corrected_{target_col}"
        if norm_col in self.replicates.columns:
            self.replicates = self.replicates.drop(columns=[norm_col])

        self.replicates = strategy.apply(self.replicates, "working_value")
        self.replicates = self.replicates.rename(
            columns={"corrected_working_value": norm_col}
        )

        summary_data = self.replicates[~self.replicates["excluded"]].copy()
        summary_data["group_name"] = summary_data["sample_name"].apply(self._get_group_name)

        self.summary = summary_data.groupby("group_name")["working_value"].agg(
            ["mean", "sem", "count"]
        )

        if use_method_precision:
            self.summary["sem"] = prec / np.sqrt(self.summary["count"])
        else:
            self.summary["sem"] = self.summary["sem"].fillna(
                prec / np.sqrt(self.summary["count"])
            )

        # Compute pre-calibration uncertainty terms (u_blank, u_linearity, u_drift)
        self._compute_precalibration_uncertainties(summary_data, anchor_rows)

        # Propagate full uncertainty & variance budget
        self.summary = strategy.propagate(self.summary, self.config.target_column)

        # If elemental calibration was configured, attach elemental % columns
        if self.elemental_calibration_applied and self._elemental_params is not None:
            self._execute_elemental_stage(**self._elemental_params)
            self._attach_elemental_to_summary()

        # Refresh Diagnostics (Now including Range & Extrapolation Checks on normalized data)
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

        cols = [
            f"corrected_{self.config.target_column}",
            "combined_uncertainty",
            "count",
        ]
        if self.elemental_calibration_applied and self.elemental_info:
            pct_col = self.elemental_info["pct_column"]
            u_pct_col = f"u_{pct_col}"
            if pct_col in self.summary.columns:
                cols.extend([pct_col, u_pct_col])

        return self.summary[cols].round(2)

    @property
    def uncertainty_budget(self) -> pd.DataFrame:
        """
        Returns the detailed ISO 17025 uncertainty budget table showing the combined
        1-sigma uncertainty and the percentage variance contribution of each source:
        - pct_measurement (replicate repeatability / method precision)
        - pct_anchors (anchor measurement SEMs + certificate uncertainties)
        - pct_fit_residual (OLS regression residual scatter for 3+ anchors)
        - pct_blank (mass-balance blank area & delta uncertainties)
        - pct_linearity (linearity slope uncertainty)
        - pct_drift (drift slope uncertainty)
        """
        if self.summary is None:
            raise RuntimeError("Run .process() before requesting the uncertainty budget.")

        budget_cols = [
            "combined_uncertainty",
            "pct_measurement",
            "pct_anchors",
            "pct_fit_residual",
            "pct_blank",
            "pct_linearity",
            "pct_drift",
        ]
        available = [c for c in budget_cols if c in self.summary.columns]
        return self.summary[available].round(2)

    @property
    def qaqc(self) -> pd.DataFrame:
        """
        Returns trueness report for the Control standards, including ISO Guide 33
        normalized error (En_Score) accounting for both measurement and certificate uncertainty:
            En_Score = |Bias| / (2 * sqrt(u_combined^2 + u_true^2))
        """
        if self.summary is None:
            raise RuntimeError("Run .process() before requesting QAQC.")

        qc_rows = []
        target_col = f"corrected_{self.config.target_column}"
        for sample_name in self.summary.index:
            canonical_name = self.get_canonical_name(sample_name, self.controls)
            if canonical_name:
                std_obj = self.controls[canonical_name]
                row = self.summary.loc[sample_name].copy()
                row["True_Value"] = std_obj.d_true
                row["u_True"] = std_obj.u_true
                row["Bias"] = row[target_col] - std_obj.d_true
                u_bias = float(
                    np.sqrt(row["combined_uncertainty"] ** 2 + std_obj.u_true**2)
                )
                en_score = abs(row["Bias"]) / (2.0 * u_bias) if u_bias > 0 else 0.0
                row["En_Score"] = en_score
                row["Within_Unc"] = bool(en_score <= 1.0)
                qc_rows.append(row)

        if not qc_rows:
            return pd.DataFrame()

        df_qc = pd.DataFrame(qc_rows)[
            [
                "True_Value",
                "u_True",
                target_col,
                "combined_uncertainty",
                "Bias",
                "En_Score",
                "Within_Unc",
            ]
        ]
        num_cols = [
            "True_Value",
            "u_True",
            target_col,
            "combined_uncertainty",
            "Bias",
            "En_Score",
        ]
        df_qc[num_cols] = df_qc[num_cols].round(2)
        return df_qc

    def save_report(self, filepath: str):
        """
        Exports the Results, QAQC, Uncertainty_Budget, and Parameters tables to an Excel file.
        """
        export_batch_to_excel(self, filepath)

    def save_html_report(self, filepath: str):
        """
        Exports the results, diagnostics, and interactive plots to a standalone HTML file.
        """
        generate_html_report(self, filepath)
