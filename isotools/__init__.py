"""
isotools - A library for automated IRMS data processing.
"""

# 1. The Core Controller & QA/QC Log
# The user's primary starting point.
from .core import Batch
from .qaqc_log import QualityControlLog

# 2. Data Models
# Necessary for defining new standards or understanding the data structure.
from .models import ReferenceMaterial

# 3. Configurations
# Pre-defined system setups.
from .config import SystemConfig, NITROGEN, WATER_H, WATER_O, CARBON_13C

# 4. Standards
# The database of known reference materials.
from .standards import (
    USGS32, USGS34, USGS35,
    IAEA_N1, IAEA_N2, IAEA_NO3, IAEA600_N,
    USGS40_N, USGS41A_N, USGS61_N, USGS62_N, USGS63_N, ACETANILIDE_N,
    MAR_H, BUENOS_AIRES_H, MENDOZA_H, ANTARTIDA_H,
    VSMOW2_H, SLAP2_H, GISP_H, USGS45_H, USGS46_H, USGS47_H, USGS48_H,
    MAR_O, BUENOS_AIRES_O, MENDOZA_O, ANTARTIDA_O,
    VSMOW2_O, SLAP2_O, GISP_O, USGS45_O, USGS46_O, USGS47_O, USGS48_O,
    NIST8541, SRM1649A, SRM1649a,
    NBS19_C, NBS18_C, IAEA603_C, IAEA_CH6, IAEA600_C,
    USGS40_C, USGS41A_C, USGS61_C, USGS62_C, USGS63_C,
    BENZOIC_ACID_C, ACETANILIDE_C,
    get_standard, register_standard,
)

# 5. Strategies
# The calibration logic needed for Batch.process()
from .strategies import CalibrationStrategy, SinglePointOffset, TwoPointLinear, MultiPointLinear

# 6. Reporting
from .reporting import generate_html_report, generate_dual_isotope_html_report

# Define what gets imported with `from isotools import *`
__all__ = [
    "Batch",
    "QualityControlLog",
    "ReferenceMaterial",
    "SystemConfig",
    "NITROGEN",
    "WATER_H",
    "WATER_O",
    "CARBON_13C",
    "USGS32",
    "USGS34",
    "USGS35",
    "IAEA_N1",
    "IAEA_N2",
    "IAEA_NO3",
    "IAEA600_N",
    "USGS40_N",
    "USGS41A_N",
    "USGS61_N",
    "USGS62_N",
    "USGS63_N",
    "ACETANILIDE_N",
    "MAR_H",
    "BUENOS_AIRES_H",
    "MENDOZA_H",
    "ANTARTIDA_H",
    "VSMOW2_H",
    "SLAP2_H",
    "GISP_H",
    "USGS45_H",
    "USGS46_H",
    "USGS47_H",
    "USGS48_H",
    "MAR_O",
    "BUENOS_AIRES_O",
    "MENDOZA_O",
    "ANTARTIDA_O",
    "VSMOW2_O",
    "SLAP2_O",
    "GISP_O",
    "USGS45_O",
    "USGS46_O",
    "USGS47_O",
    "USGS48_O",
    "NIST8541",
    "SRM1649A",
    "SRM1649a",
    "NBS19_C",
    "NBS18_C",
    "IAEA603_C",
    "IAEA_CH6",
    "IAEA600_C",
    "USGS40_C",
    "USGS41A_C",
    "USGS61_C",
    "USGS62_C",
    "USGS63_C",
    "BENZOIC_ACID_C",
    "ACETANILIDE_C",
    "get_standard",
    "register_standard",
    "CalibrationStrategy",
    "SinglePointOffset",
    "TwoPointLinear",
    "MultiPointLinear",
    "generate_html_report",
    "generate_dual_isotope_html_report",
]
