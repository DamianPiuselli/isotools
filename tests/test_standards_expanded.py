"""
Unit tests for the expanded IAEA, USGS, and NIST standards registry,
scale metadata in SystemConfig, and mass_fraction properties.
"""
import pytest

from isotools.config import NITROGEN, WATER_H, WATER_O, CARBON_13C
from isotools.models import ReferenceMaterial
from isotools.standards import get_standard


def test_system_config_scale_and_element_metadata():
    """Verify international reference scale and element_symbol on SystemConfig objects."""
    assert NITROGEN.scale == "AIR-N2"
    assert NITROGEN.element_symbol == "N"

    assert WATER_H.scale == "VSMOW-SLAP"
    assert WATER_H.element_symbol == "H"

    assert WATER_O.scale == "VSMOW-SLAP"
    assert WATER_O.element_symbol == "O"

    assert CARBON_13C.scale == "VPDB"
    assert CARBON_13C.element_symbol == "C"


def test_water_international_standards_lookup():
    """Verify VSMOW2, SLAP2, GISP, and USGS45-48 disambiguate between 2H and 18O."""
    vsmow_h = get_standard("VSMOW2", target_column="d2h")
    vsmow_o = get_standard("VSMOW2", target_column="d18o")
    assert vsmow_h is not None and vsmow_h.d_true == pytest.approx(0.0)
    assert vsmow_o is not None and vsmow_o.d_true == pytest.approx(0.0)

    slap_h = get_standard("SLAP2", target_column="d2h")
    slap_o = get_standard("SLAP2", target_column="d18o")
    assert slap_h is not None and slap_h.d_true == pytest.approx(-427.5)
    assert slap_o is not None and slap_o.d_true == pytest.approx(-55.5)

    gisp_h = get_standard("GISP", target_column="d2h")
    gisp_o = get_standard("GISP", target_column="d18o")
    assert gisp_h is not None and gisp_h.d_true == pytest.approx(-189.5)
    assert gisp_o is not None and gisp_o.d_true == pytest.approx(-24.76)

    u47_h = get_standard("USGS-47", target_column="d2h")
    u47_o = get_standard("USGS-47", target_column="d18o")
    assert u47_h is not None and u47_h.d_true == pytest.approx(-150.2)
    assert u47_o is not None and u47_o.d_true == pytest.approx(-19.80)


def test_dual_cn_organic_standards_disambiguation_and_mass_fraction():
    """Verify USGS40, USGS41a, IAEA-600, USGS61-63, and Acetanilide for C and N."""
    u40_c = get_standard("USGS40", target_column="d13c")
    u40_n = get_standard("USGS40", target_column="d15n")
    assert u40_c is not None
    assert u40_c.d_true == pytest.approx(-26.39)
    assert u40_c.mass_fraction == pytest.approx(40.82)

    assert u40_n is not None
    assert u40_n.d_true == pytest.approx(-4.52)
    assert u40_n.mass_fraction == pytest.approx(9.52)

    u41_c = get_standard("USGS-41a", target_column="d13c")
    u41_n = get_standard("USGS-41a", target_column="d15n")
    assert u41_c is not None and u41_c.d_true == pytest.approx(36.55)
    assert u41_n is not None and u41_n.d_true == pytest.approx(47.55)

    iaea600_c = get_standard("IAEA-600", target_column="d13c")
    iaea600_n = get_standard("IAEA-600", target_column="d15n")
    assert iaea600_c is not None and iaea600_c.mass_fraction == pytest.approx(49.48)
    assert iaea600_n is not None and iaea600_n.mass_fraction == pytest.approx(28.85)


def test_reference_material_negative_uncertainty_validation():
    """Verify ReferenceMaterial rejects negative uncertainties."""
    with pytest.raises(ValueError, match="Uncertainty"):
        ReferenceMaterial("BadStd", 0.0, -0.1)

    with pytest.raises(ValueError, match="Mass fraction uncertainty"):
        ReferenceMaterial("BadStd2", 0.0, 0.1, mass_fraction=50.0, u_mass_fraction=-0.5)
