"""Solver Abstraction Layer — the only place GeoForge touches an external engine.

Importing this package applies the upstream patches we carry (`_patches`), so any code path
that reaches an engine is patched before a solver is built.
"""

from geoforge.solvers import _patches
from geoforge.solvers.interface import SolverBackend, get_backend
from geoforge.solvers.types import (
    CONFIGURATION_KINDS,
    VALUED_KINDS,
    Fact,
    FactId,
    FactKind,
    Justification,
    JustificationKind,
    ProblemSpec,
    ProofDAG,
    ProofStep,
    SolveOptions,
    SolveResult,
    SolveStats,
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
    "ProblemSpec",
    "ProofDAG",
    "ProofStep",
    "SolveOptions",
    "SolveResult",
    "SolveStats",
    "SolverBackend",
    "get_backend",
]
