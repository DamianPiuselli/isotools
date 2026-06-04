"""
Registry of common Reference Materials (standards) used in IRMS.
"""
from .models import ReferenceMaterial

# --- Nitrogen Standards ---
USGS32 = ReferenceMaterial(
    name="USGS32",
    d_true=180.0,
    u_true=1.0,
    aliases=[
        "USGS-32",
        "KN032",
    ],
    target_column="d15n",
)

USGS34 = ReferenceMaterial(
    name="USGS34",
    d_true=-1.8,
    u_true=0.2,
    aliases=["USGS-34", "KN034"],
    target_column="d15n",
)

USGS35 = ReferenceMaterial(
    name="USGS35",
    d_true=2.7,
    u_true=0.2,
    aliases=["USGS-35", "KN035"],
    target_column="d15n",
)

# --- Water Standards (2H) ---
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

# --- Water Standards (18O) ---
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

# --- Registry & Lookup ---
# This list defines what the library "knows" by default.
DEFAULT_STANDARDS = [
    USGS32, USGS34, USGS35,
    MAR_H, BUENOS_AIRES_H, MENDOZA_H, ANTARTIDA_H,
    MAR_O, BUENOS_AIRES_O, MENDOZA_O, ANTARTIDA_O
]


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
