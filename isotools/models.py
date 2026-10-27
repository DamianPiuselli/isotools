"""
Data models for Reference Materials (standards).
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class ReferenceMaterial:
    """
    Representation of a Reference Material (standard).

    Includes true values, certified uncertainty, valid aliases for matching
    against raw Isodat data, and optional elemental mass fraction (%wt).
    """

    name: str
    d_true: float  # Certified Delta Value (‰)
    u_true: float  # Certified Uncertainty (1 sigma, ‰)
    aliases: List[str] = field(default_factory=list)
    target_column: str = ""  # Associated isotope target column (e.g., d2h, d18o, d15n, d13c)
    mass_fraction: Optional[float] = None  # Certified elemental weight percent (e.g. %C or %N)
    u_mass_fraction: float = 0.0  # Uncertainty on elemental weight percent (1 sigma)

    # Internal cache for fast lookups
    _lookup_set: Set[str] = field(init=False, repr=False)

    def __post_init__(self):
        if self.u_true < 0:
            raise ValueError(f"Uncertainty for {self.name} cannot be negative.")
        if self.u_mass_fraction < 0:
            raise ValueError(f"Mass fraction uncertainty for {self.name} cannot be negative.")

        # Normalize aliases to lowercase for case-insensitive matching
        self._lookup_set = {self.name.lower()} | {a.lower() for a in self.aliases}

    def matches(self, sample_name: str) -> bool:
        """
        Returns True if the provided sample_name matches this standard
        or any of its aliases.
        """
        if not isinstance(sample_name, str):
            return False
        return sample_name.strip().lower() in self._lookup_set

    def __repr__(self) -> str:
        return f"<RefMat {self.name}: {self.d_true} ± {self.u_true}>"
