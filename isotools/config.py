from dataclasses import dataclass, field
from typing import Dict, Callable
import pandas as pd


@dataclass
class SystemConfig:
    """
    Configuration for a specific isotope system (e.g., N2, CO2).
    Defines how to interpret the raw Isodat file columns and rows.
    """

    name: str
    target_column: str
    column_mapping: Dict[str, str]
    # A function that takes the raw DF and returns the filtered DF (e.g. keeping specific peaks)
    filter_func: Callable[[pd.DataFrame], pd.DataFrame] = field(default=lambda df: df)
    # Optional method repeatability (1-sigma instrument precision)
    method_precision: float = 0.0
    # Expected environmental range (min, max)
    absolute_range: tuple[float, float] = (-2000.0, 2000.0)
    # The column used for signal intensity/amplitude (e.g. amp_28, amp_2)
    amplitude_column: str = ""


# --- Logic Helpers ---
def _filter_n2_peaks(df: pd.DataFrame) -> pd.DataFrame:
    """Standard N2 logic: Keep Peak 2 (Sample Gas)."""
    if "peak_nr" in df.columns:
        return df[df["peak_nr"] == 2].copy()
    return df


def _filter_water_h_peaks(df: pd.DataFrame) -> pd.DataFrame:
    """Water 2H logic: Keep Peak 3."""
    if "peak_nr" in df.columns:
        return df[df["peak_nr"] == 3].copy()
    return df


def _filter_water_o_peaks(df: pd.DataFrame) -> pd.DataFrame:
    """Water 18O logic: Keep Peak 4."""
    if "peak_nr" in df.columns:
        return df[df["peak_nr"] == 4].copy()
    return df


# --- Configurations ---

NITROGEN_MAPPING = {
    # Standard Isodat Columns
    "Row": "row",
    "Identifier 1": "sample_name",
    "Identifier 2": "sample_id_2",
    "Peak Nr": "peak_nr",
    "Amount": "amount",
    "Area All": "area_all",
    "Comment": "comment",
    # N2 Specifics
    "d 15N/14N": "d15n",
    "R 15N/14N": "r15n",
    "Ampl 28": "amp_28",
    "Ampl 29": "amp_29",
    "Area 28": "area_28",
    "Area 29": "area_29",
}

WATER_H_MAPPING = {
    "Row": "row",
    "Identifier 1": "sample_name",
    "Identifier 2": "sample_id_2",
    "Peak Nr": "peak_nr",
    "d 3H2/2H2": "d2h",
    "Ampl 2": "amp_2",
    "Area 2": "area_2",
}

WATER_O_MAPPING = {
    "Row": "row",
    "Identifier 1": "sample_name",
    "Identifier 2": "sample_id_2",
    "Peak Nr": "peak_nr",
    "d 18O/16O": "d18o",
    "Ampl 28": "amp_28",
    "Area 28": "area_28",
}

# The public objects
Nitrogen = SystemConfig(
    name="Nitrogen (N2)",
    target_column="d15n",
    column_mapping=NITROGEN_MAPPING,
    filter_func=_filter_n2_peaks,
    amplitude_column="amp_28",
    absolute_range=(-20.0, 50.0),
)

Water_H = SystemConfig(
    name="Water (2H)",
    target_column="d2h",
    column_mapping=WATER_H_MAPPING,
    filter_func=_filter_water_h_peaks,
    method_precision=1.4,
    amplitude_column="amp_2",
    absolute_range=(-400.0, 50.0),
)

Water_O = SystemConfig(
    name="Water (18O)",
    target_column="d18o",
    column_mapping=WATER_O_MAPPING,
    filter_func=_filter_water_o_peaks,
    method_precision=0.24,
    amplitude_column="amp_28",
    absolute_range=(-60.0, 20.0),
)
