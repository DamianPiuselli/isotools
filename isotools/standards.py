"""
Registry of common Reference Materials (standards) used in IRMS.
Includes IAEA, USGS, NIST, and laboratory reference materials for N, H, O, and C.
"""
from .models import ReferenceMaterial

# =============================================================================
# 1. NITROGEN STANDARDS (d15n vs. AIR-N2)
# =============================================================================
USGS32 = ReferenceMaterial(
    name="USGS32",
    d_true=180.0,
    u_true=1.0,
    aliases=["USGS-32", "KN032"],
    target_column="d15n",
    mass_fraction=13.85,
)

USGS34 = ReferenceMaterial(
    name="USGS34",
    d_true=-1.8,
    u_true=0.2,
    aliases=["USGS-34", "KN034"],
    target_column="d15n",
    mass_fraction=13.85,
)

USGS35 = ReferenceMaterial(
    name="USGS35",
    d_true=2.7,
    u_true=0.2,
    aliases=["USGS-35", "KN035"],
    target_column="d15n",
    mass_fraction=16.47,
)

IAEA_N1 = ReferenceMaterial(
    name="IAEA-N-1",
    d_true=0.4,
    u_true=0.2,
    aliases=["IAEA-N1", "IAEAN1", "N-1"],
    target_column="d15n",
    mass_fraction=21.20,
)

IAEA_N2 = ReferenceMaterial(
    name="IAEA-N-2",
    d_true=20.3,
    u_true=0.2,
    aliases=["IAEA-N2", "IAEAN2", "N-2"],
    target_column="d15n",
    mass_fraction=21.20,
)

IAEA_NO3 = ReferenceMaterial(
    name="IAEA-NO-3",
    d_true=4.7,
    u_true=0.2,
    aliases=["IAEA-NO3", "IAEANO3", "NO-3", "USGS33"],
    target_column="d15n",
    mass_fraction=13.85,
)

IAEA600_N = ReferenceMaterial(
    name="IAEA-600_N",
    d_true=1.0,
    u_true=0.2,
    aliases=["IAEA-600", "IAEA600", "Caffeine IAEA-600"],
    target_column="d15n",
    mass_fraction=28.85,
)

USGS40_N = ReferenceMaterial(
    name="USGS40_N",
    d_true=-4.52,
    u_true=0.06,
    aliases=["USGS40", "USGS-40"],
    target_column="d15n",
    mass_fraction=9.52,
)

USGS41A_N = ReferenceMaterial(
    name="USGS41a_N",
    d_true=47.55,
    u_true=0.15,
    aliases=["USGS41a", "USGS-41a", "USGS41A", "USGS-41A"],
    target_column="d15n",
    mass_fraction=9.52,
)

USGS61_N = ReferenceMaterial(
    name="USGS61_N",
    d_true=-2.87,
    u_true=0.04,
    aliases=["USGS61", "USGS-61"],
    target_column="d15n",
    mass_fraction=28.85,
)

USGS62_N = ReferenceMaterial(
    name="USGS62_N",
    d_true=20.17,
    u_true=0.06,
    aliases=["USGS62", "USGS-62"],
    target_column="d15n",
    mass_fraction=28.85,
)

USGS63_N = ReferenceMaterial(
    name="USGS63_N",
    d_true=37.83,
    u_true=0.06,
    aliases=["USGS63", "USGS-63"],
    target_column="d15n",
    mass_fraction=28.85,
)

ACETANILIDE_N = ReferenceMaterial(
    name="Acetanilide_N",
    d_true=1.18,
    u_true=0.10,
    aliases=["Acetanilide", "Acetanilida"],
    target_column="d15n",
    mass_fraction=10.36,
)

# =============================================================================
# 2. WATER STANDARDS - HYDROGEN (d2h vs. VSMOW-SLAP)
# =============================================================================
VSMOW2_H = ReferenceMaterial(
    name="VSMOW2_H",
    d_true=0.0,
    u_true=0.3,
    aliases=["VSMOW2", "VSMOW-2", "VSMOW"],
    target_column="d2h",
)

SLAP2_H = ReferenceMaterial(
    name="SLAP2_H",
    d_true=-427.5,
    u_true=0.3,
    aliases=["SLAP2", "SLAP-2", "SLAP"],
    target_column="d2h",
)

GISP_H = ReferenceMaterial(
    name="GISP_H",
    d_true=-189.5,
    u_true=1.2,
    aliases=["GISP"],
    target_column="d2h",
)

USGS45_H = ReferenceMaterial(
    name="USGS45_H",
    d_true=-10.3,
    u_true=0.4,
    aliases=["USGS45", "USGS-45"],
    target_column="d2h",
)

USGS46_H = ReferenceMaterial(
    name="USGS46_H",
    d_true=-235.8,
    u_true=0.7,
    aliases=["USGS46", "USGS-46"],
    target_column="d2h",
)

USGS47_H = ReferenceMaterial(
    name="USGS47_H",
    d_true=-150.2,
    u_true=0.5,
    aliases=["USGS47", "USGS-47"],
    target_column="d2h",
)

USGS48_H = ReferenceMaterial(
    name="USGS48_H",
    d_true=-2.0,
    u_true=0.4,
    aliases=["USGS48", "USGS-48"],
    target_column="d2h",
)

MAR_H = ReferenceMaterial(
    name="Mar_H",
    d_true=-0.49,
    u_true=1.34,
    aliases=["Mar", "MAR"],
    target_column="d2h",
)

BUENOS_AIRES_H = ReferenceMaterial(
    name="Buenos Aires_H",
    d_true=-36.92,
    u_true=1.34,
    aliases=["BSAS", "Buenos Aires"],
    target_column="d2h",
)

MENDOZA_H = ReferenceMaterial(
    name="Mendoza_H",
    d_true=-72.07,
    u_true=1.34,
    aliases=["MDZA", "Mendoza"],
    target_column="d2h",
)

ANTARTIDA_H = ReferenceMaterial(
    name="Antartida_H",
    d_true=-94.89,
    u_true=1.34,
    aliases=["ANTARTIDA", "Antartida"],
    target_column="d2h",
)

# =============================================================================
# 3. WATER STANDARDS - OXYGEN (d18o vs. VSMOW-SLAP)
# =============================================================================
VSMOW2_O = ReferenceMaterial(
    name="VSMOW2_O",
    d_true=0.0,
    u_true=0.02,
    aliases=["VSMOW2", "VSMOW-2", "VSMOW"],
    target_column="d18o",
)

SLAP2_O = ReferenceMaterial(
    name="SLAP2_O",
    d_true=-55.5,
    u_true=0.02,
    aliases=["SLAP2", "SLAP-2", "SLAP"],
    target_column="d18o",
)

GISP_O = ReferenceMaterial(
    name="GISP_O",
    d_true=-24.76,
    u_true=0.09,
    aliases=["GISP"],
    target_column="d18o",
)

USGS45_O = ReferenceMaterial(
    name="USGS45_O",
    d_true=-2.238,
    u_true=0.011,
    aliases=["USGS45", "USGS-45"],
    target_column="d18o",
)

USGS46_O = ReferenceMaterial(
    name="USGS46_O",
    d_true=-29.80,
    u_true=0.03,
    aliases=["USGS46", "USGS-46"],
    target_column="d18o",
)

USGS47_O = ReferenceMaterial(
    name="USGS47_O",
    d_true=-19.80,
    u_true=0.02,
    aliases=["USGS47", "USGS-47"],
    target_column="d18o",
)

USGS48_O = ReferenceMaterial(
    name="USGS48_O",
    d_true=-2.224,
    u_true=0.012,
    aliases=["USGS48", "USGS-48"],
    target_column="d18o",
)

MAR_O = ReferenceMaterial(
    name="Mar_O",
    d_true=-0.027,
    u_true=0.22,
    aliases=["Mar", "MAR"],
    target_column="d18o",
)

BUENOS_AIRES_O = ReferenceMaterial(
    name="Buenos Aires_O",
    d_true=-5.442,
    u_true=0.22,
    aliases=["BSAS", "Buenos Aires"],
    target_column="d18o",
)

MENDOZA_O = ReferenceMaterial(
    name="Mendoza_O",
    d_true=-11.362,
    u_true=0.22,
    aliases=["MDZA", "Mendoza"],
    target_column="d18o",
)

ANTARTIDA_O = ReferenceMaterial(
    name="Antartida_O",
    d_true=-12.78,
    u_true=0.22,
    aliases=["ANTARTIDA", "Antartida"],
    target_column="d18o",
)

# =============================================================================
# 4. CARBON STANDARDS (d13c vs. VPDB)
# =============================================================================
NIST8541 = ReferenceMaterial(
    name="NIST8541",
    d_true=-16.05,
    u_true=0.04,
    aliases=["NIST-8541", "8541", "USGS24", "USGS-24", "Graphite"],
    target_column="d13c",
    mass_fraction=100.0,
)

SRM1649A = ReferenceMaterial(
    name="1649a",
    d_true=-25.60,
    u_true=0.20,
    aliases=["NIST1649a", "NIST-1649a", "SRM 1649a", "SRM-1649a", "1649A", "Urban Dust"],
    target_column="d13c",
    mass_fraction=17.68,
)
# Alias for backward compatibility
SRM1649a = SRM1649A  # pylint: disable=invalid-name

NBS19_C = ReferenceMaterial(
    name="NBS19",
    d_true=1.95,
    u_true=0.02,
    aliases=["NBS-19", "NIST8544", "TS-limestone"],
    target_column="d13c",
    mass_fraction=12.00,
)

NBS18_C = ReferenceMaterial(
    name="NBS18",
    d_true=-5.014,
    u_true=0.035,
    aliases=["NBS-18", "NIST8543", "Carbonatite"],
    target_column="d13c",
    mass_fraction=12.00,
)

IAEA603_C = ReferenceMaterial(
    name="IAEA-603",
    d_true=2.46,
    u_true=0.01,
    aliases=["IAEA603", "Calcite IAEA-603"],
    target_column="d13c",
    mass_fraction=12.00,
)

IAEA600_C = ReferenceMaterial(
    name="IAEA-600_C",
    d_true=-27.771,
    u_true=0.043,
    aliases=["IAEA-600", "IAEA600", "Caffeine IAEA-600"],
    target_column="d13c",
    mass_fraction=49.48,
)

IAEA_CH6 = ReferenceMaterial(
    name="IAEA-CH-6",
    d_true=-10.449,
    u_true=0.033,
    aliases=["IAEA-CH6", "IAEACH6", "CH-6", "Sucrose", "NIST8542"],
    target_column="d13c",
    mass_fraction=42.10,
)

USGS40_C = ReferenceMaterial(
    name="USGS40_C",
    d_true=-26.39,
    u_true=0.04,
    aliases=["USGS40", "USGS-40"],
    target_column="d13c",
    mass_fraction=40.82,
)

USGS41A_C = ReferenceMaterial(
    name="USGS41a_C",
    d_true=36.55,
    u_true=0.08,
    aliases=["USGS41a", "USGS-41a", "USGS41A", "USGS-41A"],
    target_column="d13c",
    mass_fraction=40.82,
)

USGS61_C = ReferenceMaterial(
    name="USGS61_C",
    d_true=-35.05,
    u_true=0.04,
    aliases=["USGS61", "USGS-61"],
    target_column="d13c",
    mass_fraction=49.48,
)

USGS62_C = ReferenceMaterial(
    name="USGS62_C",
    d_true=-14.79,
    u_true=0.04,
    aliases=["USGS62", "USGS-62"],
    target_column="d13c",
    mass_fraction=49.48,
)

USGS63_C = ReferenceMaterial(
    name="USGS63_C",
    d_true=-1.17,
    u_true=0.04,
    aliases=["USGS63", "USGS-63"],
    target_column="d13c",
    mass_fraction=49.48,
)

BENZOIC_ACID_C = ReferenceMaterial(
    name="Benzoic Acid",
    d_true=-28.80,
    u_true=0.10,
    aliases=["ac benzoico", "Acido Benzoico", "Benzoic", "IAEA-601"],
    target_column="d13c",
    mass_fraction=68.85,
)

ACETANILIDE_C = ReferenceMaterial(
    name="Acetanilide_C",
    d_true=-29.53,
    u_true=0.10,
    aliases=["Acetanilide", "Acetanilida"],
    target_column="d13c",
    mass_fraction=71.09,
)

# =============================================================================
# REGISTRY & LOOKUP
# =============================================================================
DEFAULT_STANDARDS = [
    # Nitrogen
    USGS32,
    USGS34,
    USGS35,
    IAEA_N1,
    IAEA_N2,
    IAEA_NO3,
    IAEA600_N,
    USGS40_N,
    USGS41A_N,
    USGS61_N,
    USGS62_N,
    USGS63_N,
    ACETANILIDE_N,
    # Water 2H
    VSMOW2_H,
    SLAP2_H,
    GISP_H,
    USGS45_H,
    USGS46_H,
    USGS47_H,
    USGS48_H,
    MAR_H,
    BUENOS_AIRES_H,
    MENDOZA_H,
    ANTARTIDA_H,
    # Water 18O
    VSMOW2_O,
    SLAP2_O,
    GISP_O,
    USGS45_O,
    USGS46_O,
    USGS47_O,
    USGS48_O,
    MAR_O,
    BUENOS_AIRES_O,
    MENDOZA_O,
    ANTARTIDA_O,
    # Carbon 13C
    NIST8541,
    SRM1649A,
    NBS19_C,
    NBS18_C,
    IAEA603_C,
    IAEA600_C,
    IAEA_CH6,
    USGS40_C,
    USGS41A_C,
    USGS61_C,
    USGS62_C,
    USGS63_C,
    BENZOIC_ACID_C,
    ACETANILIDE_C,
]


def register_standard(standard: ReferenceMaterial) -> None:
    """
    Registers a custom ReferenceMaterial in the default standards registry.
    If a standard with the same canonical name and target_column already exists,
    it is replaced; otherwise it is prepended so custom standards take priority.
    """
    if not isinstance(standard, ReferenceMaterial):
        raise TypeError("Expected a ReferenceMaterial instance.")

    for i, existing in enumerate(DEFAULT_STANDARDS):
        if (
            existing.name.lower() == standard.name.lower()
            and existing.target_column == standard.target_column
        ):
            DEFAULT_STANDARDS[i] = standard
            return

    DEFAULT_STANDARDS.insert(0, standard)


def get_standard(
    name: str, target_column: str = None, custom_standards: list = None
) -> ReferenceMaterial:
    """
    Attempts to find a ReferenceMaterial object matching the given name.
    Checks custom_standards first (if provided), then defaults.
    Returns None if no match found.
    """
    registry = (custom_standards or []) + DEFAULT_STANDARDS

    for std in registry:
        if std.matches(name):
            if (
                target_column is None
                or not std.target_column
                or std.target_column == target_column
            ):
                return std
    return None
