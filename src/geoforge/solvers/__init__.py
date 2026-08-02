"""Solver Abstraction Layer — the only place GeoForge touches an external engine.

Importing this package applies the upstream patches we carry (`_patches`), so any code path
that reaches an engine is patched before a solver is built.
"""

from geoforge.solvers import _patches
from geoforge.solvers.interface import (
    SolverBackend,
    ValidatorBackend,
    get_backend,
    get_validator,
)
from geoforge.solvers.types import (
    CONFIGURATION_KINDS,
    VALUED_KINDS,
    Fact,
    FactId,
    FactKind,
    Justification,
    JustificationKind,
    PremiseSpec,
    ProblemSpec,
    ProofDAG,
    ProofStep,
    RealizedFigure,
    SolveOptions,
    SolveResult,
    SolveStats,
    fact_from_id,
)

APPLIED_PATCHES: list[str] = _patches.apply_all()

__all__ = [
    "APPLIED_PATCHES",
    "CONFIGURATION_KINDS",
    "VALUED_KINDS",
    "Fact",
    "FactId",
    "FactKind",
    "Justification",
    "JustificationKind",
    "PremiseSpec",
    "ProblemSpec",
    "ProofDAG",
    "ProofStep",
    "RealizedFigure",
    "SolveOptions",
    "SolveResult",
    "SolveStats",
    "SolverBackend",
    "ValidatorBackend",
    "fact_from_id",
    "get_backend",
    "get_validator",
]
