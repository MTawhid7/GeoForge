"""Every threshold, tolerance, and weight in GeoForge lives here.

Hard rule (CLAUDE.md, docs/08 §8.2): no magic numbers inline anywhere else in the codebase.
Values carry a provenance note — where they came from — so future tuning is evidence-based
rather than superstition. Values marked PHASE0 were measured in spikes/p0/REPORT.md.
"""

from geoforge.config.thresholds import (
    BANDING,
    BANK,
    DEGENERACY,
    EXTRACTION,
    FILTERS,
    GENERATION,
    INTEREST,
    LAYOUT,
    MINIMIZATION,
    SCHEMA,
    SCORING,
    SOLVER,
    TOLERANCE,
    TRANSLATION,
    VALIDATION,
    WELLPOSED,
)

__all__ = [
    "BANDING",
    "BANK",
    "DEGENERACY",
    "EXTRACTION",
    "FILTERS",
    "GENERATION",
    "INTEREST",
    "LAYOUT",
    "MINIMIZATION",
    "SCHEMA",
    "SCORING",
    "SOLVER",
    "TOLERANCE",
    "TRANSLATION",
    "VALIDATION",
    "WELLPOSED",
]
