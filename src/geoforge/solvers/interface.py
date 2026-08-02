"""The Solver Abstraction Layer boundary (docs/03 §3.3).

Downstream code depends on this protocol, never on a concrete engine. That is what makes
engine churn an upgrade rather than a rewrite, and what allows bank validation to run on a
different engine than generation (docs/02 invariant 3).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from geoforge.solvers.types import (
    Fact,
    PremiseSpec,
    ProblemSpec,
    RealizedFigure,
    SolveOptions,
    SolveResult,
)


@runtime_checkable
class ValidatorBackend(Protocol):
    """The subset of the SAL an *independent validator* has to implement (docs/04 §V).

    Split out in M6, and the split is a finding rather than a convenience. The AG2 DDAR
    validator has no construction language and no proof recorder: it consumes premises over
    fixed coordinates and answers "does this follow?". It cannot implement `solve` (there is
    no JGEX front end) or `realize` (there is nothing to instantiate). Declaring it a full
    `SolverBackend` would have meant three methods that raise, and a contract suite that
    quietly skips most of itself — so the roles are two protocols instead, and
    `isinstance(validator, SolverBackend)` is deliberately False.

    That asymmetry is not a defect in the validator. Re-derivation is all bank validation
    asks for, and the readable proof always comes from the generation engine.
    """

    name: str

    @property
    def engine_version(self) -> str:
        """The engine build a verdict came from. Read-only: a validation record that cannot
        name its engine is not evidence of anything."""
        ...

    def solve_facts(self, spec: PremiseSpec, opts: SolveOptions | None = None) -> SolveResult:
        """Decide the goals of `spec` from its premises over its fixed coordinates.

        A goal appears in `proof_dag.proved_goals` iff the engine derived it. Backends must
        raise on a premise they cannot express rather than dropping it: solving a weaker
        problem than asked would make a validator report success it did not earn.
        """
        ...


@runtime_checkable
class SolverBackend(ValidatorBackend, Protocol):
    """Contract every *generation* engine adapter must satisfy.

    Requirements enforced by the contract test suite (`tests/solvers/`):

    * **Determinism** — the same `(spec, opts)` yields an equal `SolveResult`, timing aside.
    * **Fact normalization** — engine predicates map onto `FactKind`; an unmapped predicate
      raises rather than being dropped.
    * **DAG integrity** — every fact a step references exists in `proof_dag.facts`.
    * **No silent failure** — resource caps surface in `stats`, they never masquerade as an
      unsolvable problem.
    """

    def solve(self, spec: ProblemSpec, opts: SolveOptions | None = None) -> SolveResult: ...

    def realize(self, spec: ProblemSpec, opts: SolveOptions | None = None) -> RealizedFigure: ...

    def check_facts(
        self, points: tuple[tuple[str, float, float], ...], facts: tuple[Fact, ...]
    ) -> tuple[bool, ...]:
        """Evaluate facts numerically against a set of coordinates (docs/04 Stage 8).

        Verification only — this never derives a fact, it measures whether one holds of a
        drawing (docs/02 invariant 4). The well-posedness gate uses it to tell a resampled
        figure in the *same* configuration as the reference from one that has flipped, which is
        a legitimately different figure rather than evidence of ill-posedness.

        Backends must delegate to their engine's own numeric predicates rather than
        reimplementing them: `sameclock`, `sameside` and friends have exact conventions, and a
        near-miss reimplementation would silently accept flipped configurations.
        """
        ...


def get_backend(name: str | None = None) -> SolverBackend:
    """Resolve a backend by name. Defaults to `config.SOLVER.backend`."""
    from geoforge.config import SOLVER
    from geoforge.solvers.newclid_backend import NewclidBackend

    resolved = name or SOLVER.backend
    if resolved in ("yuclid", "python", "newclid"):
        # Both Newclid paths share one adapter; the engine choice rides in SolveOptions.
        return NewclidBackend()
    if resolved == "ag2ddar":
        raise ValueError(
            "ag2ddar is a validator, not a generation backend: it has no construction "
            "language and records no proof. Use get_validator() (docs/04 §V)."
        )
    raise ValueError(f"unknown solver backend: {resolved!r}")


def get_validator(name: str | None = None) -> ValidatorBackend:
    """Resolve the bank-validation backend. Defaults to `config.VALIDATION.backend`.

    Deliberately a separate entry point from `get_backend`. Bank validation must run on a
    different engine than generation (docs/02 invariant 3, CLAUDE.md), and one resolver
    returning either role is how that invariant gets violated by accident.
    """
    from geoforge.config import VALIDATION
    from geoforge.solvers.ag2_backend import AG2DDARBackend

    resolved = name or VALIDATION.backend
    if resolved == "ag2ddar":
        return AG2DDARBackend()
    raise ValueError(f"unknown validator backend: {resolved!r}")
