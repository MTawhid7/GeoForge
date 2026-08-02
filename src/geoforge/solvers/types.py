"""Engine-neutral data model for the Solver Abstraction Layer (docs/03 §3.3).

Everything downstream of the SAL depends on these types and never on an engine's own
classes. That is what makes the engine swappable (docs/02 invariant 1) and what lets bank
validation run on a *different* engine than generation (docs/02 invariant 3).

All types are frozen and ordered so that two solves can be compared for determinism.

Angle convention (normative for all of GeoForge)
-----------------------------------------------
`Fact.value` for an angle is a directed **line-to-line** angle, modulo pi, in units of pi:
the rotation taking the first line to the second. 1/2 means 90 degrees; degrees = value*180.
This matches Newclid. It is NOT the human vertex angle: the same fact renders as angle ABC
= 40 or 140 depending on the figure's configuration, which is why the translator needs
configuration facts (docs/03 §3.5, docs/04 Stage 6).

Phase 0 verified that AlphaGeometry 2's DDAR uses the *opposite* orientation, so its adapter
must invert before emitting Facts. An uncalibrated validator would report a soundness
failure on every puzzle (docs/07 O7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from typing import NewType

FactId = NewType("FactId", str)


class FactKind(StrEnum):
    """Canonical geometric fact vocabulary.

    Deliberately the standard names shared by the AlphaGeometry lineage (Newclid, AG2 DDAR,
    JGEX), so the vocabulary is engine-neutral rather than a re-invention.
    """

    # Incidence and ordering
    DIFFERENT = "diff"
    MIDPOINT = "midp"
    COLLINEAR = "coll"
    N_COLLINEAR = "ncoll"
    SAME_CLOCK = "sameclock"
    SAME_SIDE = "sameside"
    N_SAME_SIDE = "nsameside"
    # Direction
    PERPENDICULAR = "perp"
    N_PERPENDICULAR = "nperp"
    PARALLEL = "para"
    N_PARALLEL = "npara"
    # Circles
    CIRCUMCENTER = "circle"
    CYCLIC = "cyclic"
    # Angles
    CONSTANT_ANGLE = "aconst"
    A_COMPUTE = "acompute"
    OBTUSE_ANGLE = "obtuse_angle"
    EQUAL_ANGLES = "eqangle"
    ANGLE_EQUATION = "aequation"
    # Lengths and ratios
    CONSTANT_LENGTH = "lconst"
    L_COMPUTE = "lcompute"
    SQUARED_CONSTANT_LENGTH = "l2const"
    CONGRUENT = "cong"
    CONSTANT_RATIO = "rconst"
    R_COMPUTE = "rcompute"
    SQUARED_CONSTANT_RATIO = "r2const"
    EQUAL_RATIOS = "eqratio"
    LENGTH_EQUATION = "lequation"
    # Triangles
    SIMTRI_CLOCK = "simtri"
    SIMTRI_REFLECT = "simtrir"
    CONTRI_CLOCK = "contri"
    CONTRI_REFLECT = "contrir"
    # Composite
    PYTHAGOREAN_PREMISES = "pythagorean_premises"
    PYTHAGOREAN_CONCLUSIONS = "pythagorean_conclusions"


#: Facts that describe the figure's *configuration* rather than a metric relation.
#: These are checked numerically, never consumed symbolically by a rule — which is exactly
#: why premise minimization would silently strip them if they were not tracked separately
#: (docs/04 Stage 6, the soundness hole this design closes).
CONFIGURATION_KINDS: frozenset[FactKind] = frozenset(
    {
        FactKind.SAME_SIDE,
        FactKind.N_SAME_SIDE,
        FactKind.SAME_CLOCK,
        FactKind.OBTUSE_ANGLE,
        FactKind.N_COLLINEAR,
        FactKind.N_PARALLEL,
        FactKind.N_PERPENDICULAR,
        FactKind.DIFFERENT,
    }
)

#: Fact kinds that carry an exact numeric value, i.e. candidate puzzle goals.
VALUED_KINDS: frozenset[FactKind] = frozenset(
    {
        FactKind.CONSTANT_ANGLE,
        FactKind.CONSTANT_LENGTH,
        FactKind.CONSTANT_RATIO,
        FactKind.SQUARED_CONSTANT_LENGTH,
        FactKind.SQUARED_CONSTANT_RATIO,
    }
)


@dataclass(frozen=True, slots=True, order=True)
class Fact:
    """A canonical geometric fact.

    `args` arrive already canonicalized by the engine (symmetric arguments sorted), so two
    spellings of the same fact produce the same `fact_id`.
    """

    kind: FactKind
    args: tuple[str, ...]
    value: Fraction | None = None
    """Exact value for VALUED_KINDS; None otherwise. Angles are in units of pi (see module
    docstring). Never a float: the exact layer is exact."""

    @property
    def fact_id(self) -> FactId:
        """Stable, engine-independent identity. Used for all DAG references."""
        base = f"{self.kind.value}:{':'.join(self.args)}"
        return FactId(base if self.value is None else f"{base}={self.value}")

    @property
    def is_configuration(self) -> bool:
        return self.kind in CONFIGURATION_KINDS

    @property
    def is_valued(self) -> bool:
        return self.value is not None

    def degrees(self) -> Fraction:
        """Angle value in degrees. Only meaningful for CONSTANT_ANGLE."""
        if self.kind is not FactKind.CONSTANT_ANGLE or self.value is None:
            raise ValueError(f"{self.fact_id} is not a valued angle fact")
        return self.value * 180


def fact_from_id(fact_id: FactId | str) -> Fact:
    """Parse a canonical fact id back into a `Fact` — the inverse of `Fact.fact_id`.

    Needed because the bank validator (docs/04 §V) reads *emitted puzzle JSON*, not the
    generator's in-memory objects. A validator that had to be handed the generator's own data
    structures would be re-checking the run rather than re-checking the artifact, and the
    artifact is what ships.

    Unambiguous by construction: point names never contain `:` or `=`, so the first token is
    the kind, the last `=` (if any) opens the value.
    """
    head, sep, raw_value = str(fact_id).partition("=")
    tokens = head.split(":")
    if len(tokens) < 2 or not tokens[0]:
        raise ValueError(f"not a fact id: {fact_id!r}")
    try:
        kind = FactKind(tokens[0])
    except ValueError as exc:
        raise ValueError(f"unknown fact kind in {fact_id!r}") from exc
    value = Fraction(raw_value) if sep else None
    if (value is not None) != (kind in VALUED_KINDS):
        raise ValueError(
            f"{fact_id!r} carries a value iff its kind is valued; "
            f"{kind.value} is {'valued' if kind in VALUED_KINDS else 'not valued'}"
        )
    return Fact(kind=kind, args=tuple(tokens[1:]), value=value)


class JustificationKind(StrEnum):
    """Why a fact holds. Mirrors the lineage's justification taxonomy."""

    ASSUMPTION = "assumption"
    """Contributed by the construction — a premise leaf."""
    NUMERICAL_CHECK = "numerical_check"
    """Checked against the diagram; the source of configuration facts."""
    RULE_APPLICATION = "rule"
    """A named theorem fired. Translatable to a readable step (docs/03 §3.5)."""
    AR_DEDUCTION = "ar"
    """Algebraic reasoning: a linear combination over angle/ratio atoms. Readable only
    within the max_ar_chain budget."""
    LINE_MERGE = "line_merge"
    CIRCLE_MERGE = "circle_merge"
    DIRECT_CONSEQUENCE = "direct_consequence"
    REFLEXIVITY = "reflexivity"


@dataclass(frozen=True, slots=True, order=True)
class Justification:
    kind: JustificationKind
    rule_id: str | None = None
    """Engine rule identifier, e.g. 'r03'. Public API once it reaches puzzle JSON."""
    rule_name: str | None = None
    """Human description from the engine, e.g. 'Arc determines internal angles'. Seeds the
    translation template (docs/03 §3.5)."""
    ar_reason: str | None = None
    """'Angle Chasing' or 'Ratio Chasing' for AR deductions."""


@dataclass(frozen=True, slots=True, order=True)
class ProofStep:
    """One hyperedge of the proof DAG: premises --justification--> conclusion."""

    conclusion: FactId
    premises: tuple[FactId, ...]
    justification: Justification


@dataclass(frozen=True, slots=True)
class ProofDAG:
    """The recorded derivation. Empty `steps` in saturation mode (see NewclidBackend.solve)."""

    facts: tuple[Fact, ...]
    """All facts referenced by the DAG, sorted for determinism."""
    steps: tuple[ProofStep, ...]
    assumptions: tuple[FactId, ...]
    """Construction-contributed premises — the pool puzzle givens are drawn from."""
    numerical_checks: tuple[FactId, ...]
    """Configuration facts. Premises for well-posedness even though no rule consumes them."""
    trivial: tuple[FactId, ...]
    proved_goals: tuple[FactId, ...]
    unproved_goals: tuple[str, ...]

    def index(self) -> dict[FactId, Fact]:
        return {f.fact_id: f for f in self.facts}

    def configuration_facts(self) -> tuple[Fact, ...]:
        return tuple(f for f in self.facts if f.is_configuration)

    def depth(self) -> int:
        """Longest premise->goal chain, the primary difficulty signal (docs/05 §5.1)."""
        if not self.steps:
            return 0
        by_conclusion = {s.conclusion: s for s in self.steps}
        memo: dict[FactId, int] = {}

        def _depth(fid: FactId, seen: frozenset[FactId]) -> int:
            if fid in memo:
                return memo[fid]
            step = by_conclusion.get(fid)
            if step is None or fid in seen:
                return 0
            d = 1 + max(
                (_depth(p, seen | {fid}) for p in step.premises),
                default=0,
            )
            memo[fid] = d
            return d

        return max((_depth(g, frozenset()) for g in self.proved_goals), default=0)


@dataclass(frozen=True, slots=True)
class SolveStats:
    """Run metadata. Timing is excluded from equality so determinism tests can compare
    results directly."""

    engine: str
    engine_version: str
    steps: int = 0
    n_facts: int = 0
    saturated: bool = False
    hit_cap: bool = False
    wall_seconds: float = field(default=0.0, compare=False)


@dataclass(frozen=True, slots=True)
class ProblemSpec:
    """Input to the SAL: a construction in JGEX surface syntax, plus optional goals.

    JGEX is the lingua franca of the AlphaGeometry lineage (docs/03 §3.4), so using it as the
    wire format buys interoperability with engine benchmarks and reference corpora for free.
    M2's typed `Construction` renders to this.
    """

    construction: str
    """JGEX clauses, e.g. 'a b c = triangle a b c; o = circle o a b c'. No goal part."""
    goals: tuple[str, ...] = ()
    """Goal predicates, e.g. ('aconst a b a c 1pi/3',). Empty means saturate."""

    def to_jgex(self) -> str:
        if not self.goals:
            return self.construction
        return f"{self.construction} ? {'; '.join(self.goals)}"


@dataclass(frozen=True, slots=True)
class PremiseSpec:
    """A problem stated as *facts over a fixed point set*, rather than as a construction.

    The construction-level `ProblemSpec` cannot express Stage 6's "drop a premise and re-run a
    restricted closure" (docs/04): there is no construction for "the same figure, minus one
    hypothesis". This spec holds the coordinates fixed and varies the symbolic premise set,
    which is exactly what premise minimization and goal verification need.

    Holding coordinates fixed matters twice over. It keeps the engine from re-randomizing the
    figure out from under a candidate goal, and it keeps configuration facts (which the engine
    checks against coordinates, not against premises) available no matter which premises are
    dropped — the reason they can never be minimized away.
    """

    points: tuple[tuple[str, float, float], ...]
    premises: tuple[Fact, ...]
    goals: tuple[Fact, ...] = ()
    """Empty means saturate, as in `ProblemSpec`."""

    @property
    def description(self) -> str:
        return (
            f"{len(self.points)} points; "
            f"premises {', '.join(f.fact_id for f in self.premises)}; "
            f"goals {', '.join(f.fact_id for f in self.goals)}"
        )

    def coords(self) -> dict[str, tuple[float, float]]:
        return {name: (x, y) for name, x, y in self.points}


@dataclass(frozen=True, slots=True)
class RealizedFigure:
    """A construction instantiated with coordinates, without running deduction.

    Stage 3 (docs/04) rejects degenerate figures *before* paying for a closure, so the SAL
    exposes instantiation on its own. `points` is empty when the engine could not realize the
    construction at all, with `error` saying why — that is ordinary attrition, not a bug.
    """

    points: tuple[tuple[str, float, float], ...]
    declared: tuple[Fact, ...] = ()
    """Facts the construction itself contributes. Stage 3 needs these to distinguish
    *declared* collinearity (legitimate: `on_line`, `midpoint`, `foot` all create it) from
    *accidental* near-collinearity (rejected, docs/04 Stage 3)."""
    error: str | None = None
    dropped_assumptions: tuple[str, ...] = ()
    """Assumptions the adapter could not map into `FactKind`, recorded rather than discarded
    silently (docs/08 §8.1). Losing one only costs yield — a goal verified from a subset of the
    construction's hypotheses is still symbolically true — but it must be visible, because a
    growing count means the fact vocabulary has fallen behind the engine's."""

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.points)

    def declared_collinear(self) -> frozenset[frozenset[str]]:
        """Point sets the construction declared collinear, as unordered triples."""
        out: set[frozenset[str]] = set()
        for fact in self.declared:
            if fact.kind in (FactKind.COLLINEAR, FactKind.MIDPOINT):
                pts = list(fact.args)
                for i in range(len(pts)):
                    for j in range(i + 1, len(pts)):
                        for k in range(j + 1, len(pts)):
                            out.add(frozenset((pts[i], pts[j], pts[k])))
        return frozenset(out)

    def coords(self) -> dict[str, tuple[float, float]]:
        return {name: (x, y) for name, x, y in self.points}


@dataclass(frozen=True, slots=True)
class SolveOptions:
    seed: int = 42
    backend: str | None = None
    """None uses config.SOLVER.backend."""
    max_wall_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class SolveResult:
    """What every backend returns. Compare two of these to test determinism."""

    spec: ProblemSpec | PremiseSpec
    facts: tuple[Fact, ...]
    proof_dag: ProofDAG
    numeric_model: tuple[tuple[str, float, float], ...]
    """The engine's reference coordinates, sorted by point name. Numerics VERIFY, never
    DERIVE (docs/02 invariant 4) — these exist to check facts and propose candidates."""
    stats: SolveStats
    solved: bool

    def valued_facts(self) -> tuple[Fact, ...]:
        return tuple(f for f in self.facts if f.is_valued)

    def coords(self) -> dict[str, tuple[float, float]]:
        return {name: (x, y) for name, x, y in self.numeric_model}
