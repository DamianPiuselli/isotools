"""
Calibration strategies for IRMS data.
"""
from .abstract import CalibrationStrategy
from .normalization import SinglePointOffset, TwoPointLinear, MultiPointLinear

__all__ = ["CalibrationStrategy", "SinglePointOffset", "TwoPointLinear", "MultiPointLinear"]

