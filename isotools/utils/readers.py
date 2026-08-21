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

        # 3. Validate and Rename Columns Case-Insensitively
        # 3. Validate and Rename Columns Case-Insensitively
        # Essential internal names are required for logic if defined in the config mapping
        all_essentials = ["sample_name", "row", self.config.target_column]
        if "peak_nr" in self.config.column_mapping.values():
            all_essentials.append("peak_nr")
        essential_internal_names = [name for name in all_essentials if name in self.config.column_mapping.values()]

        # Build normalized lookups for existing columns: normalized_header -> original_header
        df_cols_norm = {col.lower().replace(" ", ""): col for col in df.columns}

        # Build dynamic mapping from original header in df to internal name
        dynamic_mapping = {}
        for raw_col, internal_name in self.config.column_mapping.items():
            raw_col_norm = raw_col.lower().replace(" ", "")
            if raw_col_norm in df_cols_norm:
                actual_col = df_cols_norm[raw_col_norm]
                dynamic_mapping[actual_col] = internal_name

        # Check if all essential internal names were satisfied by mapped columns
        found_internal_names = set(dynamic_mapping.values())
        missing_essential = [name for name in essential_internal_names if name not in found_internal_names]

        if missing_essential:
            raise ValueError(
                f"Missing ESSENTIAL columns in '{filepath}': {missing_essential}. "
                f"These are required for IRMS processing. Found columns: {list(df.columns)}"
            )

        # 4. Rename Columns using Dynamic Case-Insensitive Mapping
        df = df.rename(columns=dynamic_mapping)

        # 5. Standardize Sample Names (String cleanup)
        if "sample_name" in df.columns:
            df["sample_name"] = df["sample_name"].astype(str).str.strip()

        # Track raw row metadata before filtering
        raw_rows_info = {}
        missing_sample_info = {}
        if "row" in df.columns:
            all_raw_rows = set(df["row"].dropna().unique())
            filtered_df = self.config.filter_func(df)
            filtered_rows = set(filtered_df["row"].dropna().unique())
            missing_rows = sorted(list(all_raw_rows - filtered_rows))
            for r in missing_rows:
                sub = df[df["row"] == r]
                name = sub["sample_name"].iloc[0] if "sample_name" in sub.columns and not sub.empty else f"Row {r}"
                missing_sample_info[r] = name
            df = filtered_df
            df.attrs["missing_sample_rows_info"] = missing_sample_info
            df.attrs["all_raw_rows"] = sorted(list(all_raw_rows))
        else:
            df = self.config.filter_func(df)

        # 7. Apply User Exclusions (Manual Row IDs)
        # Assumes 'row' column exists from Isodat mapping
        if exclude_rows and "row" in df.columns:
            df = df[~df["row"].isin(exclude_rows)]

        return df

