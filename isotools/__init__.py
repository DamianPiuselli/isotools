"""
isotools - A library for automated IRMS data processing.
"""

# 1. The Core Controller
# The user's primary starting point.
from .core import Batch

# 2. Data Models
# Necessary for defining new standards or understanding the data structure.
from .models import ReferenceMaterial

# 3. Configurations
# Pre-defined system setups.
from .config import SystemConfig, Nitrogen, Water_H, Water_O

# 4. Standards
# The database of known reference materials.
from .standards import (
    USGS32, USGS34, USGS35,
    MAR_H, BUENOS_AIRES_H, MENDOZA_H, ANTARTIDA_H,
    MAR_O, BUENOS_AIRES_O, MENDOZA_O, ANTARTIDA_O,
    get_standard
)

# 5. Strategies
# The calibration logic needed for Batch.process()
from .strategies import CalibrationStrategy, TwoPointLinear, MultiPointLinear

# Define what gets imported with `from isotools import *`
__all__ = [
    "Batch",
    "ReferenceMaterial",
    "SystemConfig",
    "Nitrogen",
    "Water_H",
    "Water_O",
    "USGS32",
    "USGS34",
    "USGS35",
    "MAR_H",
    "BUENOS_AIRES_H",
    "MENDOZA_H",
    "ANTARTIDA_H",
    "MAR_O",
    "BUENOS_AIRES_O",
    "MENDOZA_O",
    "ANTARTIDA_O",
    "get_standard",
    "CalibrationStrategy",
    "TwoPointLinear",
    "MultiPointLinear",
]
