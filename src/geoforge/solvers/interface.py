"""The Solver Abstraction Layer boundary (docs/03 §3.3).

Downstream code depends on this protocol, never on a concrete engine. That is what makes
engine churn an upgrade rather than a rewrite, and what allows bank validation to run on a
different engine than generation (docs/02 invariant 3).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from geoforge.solvers.types import (
    PremiseSpec,
    ProblemSpec,
    RealizedFigure,
    SolveOptions,
    SolveResult,
)


@runtime_checkable
class SolverBackend(Protocol):
    """Contract every engine adapter must satisfy.

    Requirements enforced by the contract test suite (`tests/solvers/`):

    * **Determinism** — the same `(spec, opts)` yields an equal `SolveResult`, timing aside.
    * **Fact normalization** — engine predicates map onto `FactKind`; an unmapped predicate
      raises rather than being dropped.
    * **DAG integrity** — every fact a step references exists in `proof_dag.facts`.
    * **No silent failure** — resource caps surface in `stats`, they never masquerade as an
      unsolvable problem.
    """

    name: str

    def solve(self, spec: ProblemSpec, opts: SolveOptions | None = None) -> SolveResult: ...

    def solve_facts(self, spec: PremiseSpec, opts: SolveOptions | None = None) -> SolveResult:
        """Solve over a fixed point set and an explicit premise set (docs/04 Stage 5, 6).

        Backends must treat an unrenderable premise as an error, never as a dropped premise:
        silently solving a *weaker* problem than asked would make premise minimization report a
        premise as unnecessary when it is not.
        """
        ...

    def realize(self, spec: ProblemSpec, opts: SolveOptions | None = None) -> RealizedFigure: ...


def get_backend(name: str | None = None) -> SolverBackend:
    """Resolve a backend by name. Defaults to `config.SOLVER.backend`."""
    from geoforge.config import SOLVER
    from geoforge.solvers.newclid_backend import NewclidBackend

    resolved = name or SOLVER.backend
    if resolved in ("yuclid", "python", "newclid"):
        # Both Newclid paths share one adapter; the engine choice rides in SolveOptions.
        return NewclidBackend()
    if resolved == "ag2ddar":
        raise NotImplementedError(
            "The AlphaGeometry 2 cross-validation backend lands in M6. Its adapter must "
            "calibrate the inverted angle convention first (docs/07 O7)."
        )
    raise ValueError(f"unknown solver backend: {resolved!r}")
