"""
Utilities for reading IRMS data from external files (e.g., Isodat Excel).
"""
from typing import List, Optional
import warnings
import pandas as pd
from ..config import SystemConfig

# Silence openpyxl warnings about malformed headers/footers in Isodat files
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class IsodatReader:
    """
    Handles reading and initial cleaning of Isodat Excel files.
    """

    def __init__(self, config: SystemConfig):
        """
        Initializes the reader with a system configuration.

        Args:
            config: SystemConfig defining the isotope system and column mapping.
        """
        self.config = config

    def read(
        self,
        filepath: str,
        sheet_name: int | str = 0,
        exclude_rows: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """
        Reads the file, renames columns, and filters rows.

        Args:
            filepath: Path to the .xls or .xlsx file.
            sheet_name: Sheet index or name.
            exclude_rows: Optional list of row IDs to ignore.

        Returns:
            Cleaned and filtered pandas DataFrame.
        """
        # 1. Load Data
        try:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
        except Exception as e:
            raise IOError(f"Failed to read file {filepath}: {e}") from e

        # 2. Clean Headers (Remove double spaces, strip whitespace)
        # Isodat often outputs "Ampl  28" with two spaces.
        df.columns = df.columns.str.replace(r"\s+", " ", regex=True).str.strip()

        # 3. Validate Columns
        # We distinguish between 'Essential' (required for logic) and 'Optional' (contextual)
        essential_internal_names = ["sample_name", "row", "peak_nr", self.config.target_column]

        missing_essential = []
        missing_optional = []

        for raw_col, internal_name in self.config.column_mapping.items():
            if raw_col not in df.columns:
                if internal_name in essential_internal_names:
                    missing_essential.append(raw_col)
                else:
                    missing_optional.append(raw_col)

        if missing_essential:
            raise ValueError(
                f"Missing ESSENTIAL columns in '{filepath}': {missing_essential}. "
                f"These are required for IRMS processing. Found columns: {list(df.columns)}"
            )

        if missing_optional:
            warnings.warn(
                f"Missing optional columns in '{filepath}': {missing_optional}. "
                "Calculations will proceed but some metadata may be lost."
            )

        # 4. Rename Columns using Config
        df = df.rename(columns=self.config.column_mapping)

        # 5. Standardize Sample Names (String cleanup)
        if "sample_name" in df.columns:
            df["sample_name"] = df["sample_name"].astype(str).str.strip()

        # 6. Apply System Filtering (e.g. Keep only Peak 2 for N2)
        df = self.config.filter_func(df)

        # 7. Apply User Exclusions (Manual Row IDs)
        # Assumes 'row' column exists from Isodat mapping
        if exclude_rows and "row" in df.columns:
            df = df[~df["row"].isin(exclude_rows)]

        return df
