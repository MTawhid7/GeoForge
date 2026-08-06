"""The quantity-type registry (docs/04 §QTR).

The pipeline is parameterized by quantity types; **nothing outside this module may special-case
"angle"**. A type declares how goals are proposed, how it behaves under scaling, its per-band
value palette, its answer policy, its template family, the figure marks it may state, how it is
verified, and how its goal reads as a published answer — and registering those enables it end to
end.

**Registered: `angle`, `area`.** `length` and `ratio` arrive in P3 (docs/09) and must land as
registrations here, not as branches elsewhere. The registry is what keeps that promise checkable:
a test asserts the downstream code paths read these fields rather than the name.

`area` is what proved the promise was worth keeping, and what it cost (docs/10 A3, A4). It is the
first quantity **no engine can evaluate** — none in the lineage has an area predicate — and
enabling it required widening four fields rather than editing any stage:

* `goal_extractor` takes a `FigureView` (coordinates *and* certified facts), because an area is
  computed from what was certified, not measured off the diagram.
* `verifier` — there is no engine call to make.
* `format_answer` takes a `Fact`, because an area's value is a surd and cannot be a `Fraction`.
* `claim_of` — Stages 8 and 9 took a `VertexAngle`, which assumed every goal is an angle.

That is the whole list. No stage of the pipeline branches on a quantity's name.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from functools import lru_cache

from geoforge.config import AREA as AREA_CONFIG
from geoforge.config import EXTRACTION, GENERATION, TRANSLATION, WELLPOSED
from geoforge.generator.translation.vertex_angles import VertexAngle
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import (
    Fact,
    FactKind,
    PremiseSpec,
    ProofDAG,
    RealizedFigure,
    SolveOptions,
    SolveResult,
)


class Dimension(StrEnum):
    """How a quantity behaves when the whole figure is scaled (docs/04 Stage 2)."""

    SCALE_FREE = "scale_free"
    """Invariant under similarity: angles, ratios. Must have NO length givens — one would be
    redundant and would fail Stage-6 minimization anyway."""
    SCALE_PINNED = "scale_pinned"
    """Changes with the figure's size: lengths (dimension 1), areas (dimension 2). Exactly one
    given must fix the scale, and it must be a leaf of the goal's derivation."""


class Exactness(StrEnum):
    """The exactness class of the accepted answer (docs/02 answer policy)."""

    INTEGER = "integer"
    FRACTION = "fraction"
    DECIMAL = "decimal"
    """Checked against `approx` within a per-puzzle tolerance; exact form revealed after."""


class InputMode(StrEnum):
    """Which frontend widget collects the answer (docs/06)."""

    KEYPAD = "keypad"
    FRACTION = "fraction"
    DECIMAL = "decimal"


@dataclass(frozen=True, slots=True)
class AnswerPolicy:
    exactness: Exactness
    input_mode: InputMode
    unit: str
    """Display suffix, e.g. 'deg'. Never baked into a number — docs/02 keeps `exact`,
    `approx` and `display` separate."""


@dataclass(frozen=True, slots=True)
class FigureView:
    """Everything a `goal_extractor` may look at (docs/04 §QTR).

    **Widened 2026-08-06 from bare coordinates.** The original signature took only
    `Mapping[str, tuple[float, float]]`, which suited `angle` — it measures the diagram and
    proposes a value for the engine to verify. It does not suit any quantity the engine cannot
    evaluate: an area is computed from *certified facts* (a right angle here, a midpoint there),
    and a coordinates-only extractor would have to re-derive that geometry from numbers, which
    docs/02 invariant 4 forbids outright.

    A dataclass rather than a second positional argument, because this is the seam every future
    quantity type reaches through and the last widening should be the last one. Adding a field
    here does not change any existing extractor's signature.
    """

    coords: Mapping[str, tuple[float, float]]
    """Reference-diagram coordinates. Numerics may **propose** from these, never conclude."""
    facts: tuple[Fact, ...]
    """What the engine certified about this figure — premises and configuration facts.

    An extractor that reads these is doing what the pipeline is for; one that reads `coords` to
    decide whether something is *true* is deriving from numerics and is a bug.
    """


@dataclass(frozen=True, slots=True, order=True)
class Proposal:
    """A candidate goal read off the reference diagram. **Not yet true.**

    Numerics only ever propose (docs/02 invariant 4). A Proposal becomes a puzzle goal only
    once the engine derives its `fact` symbolically, which is `extract.verify` and not this
    module's business.
    """

    quantity_type: str
    fact: Fact
    """The candidate, with its exact snapped value. Spelling need not be canonical: the engine
    canonicalizes on verification and the canonical form comes back in the result."""
    subject: tuple[str, ...]
    """The human-facing object, e.g. ('a', 'b', 'c') for the angle at vertex b."""
    measured: float
    """The raw measurement in the type's display unit, kept for diagnostics. Never truth."""

    @property
    def key(self) -> str:
        return f"{self.quantity_type}:{'.'.join(self.subject)}"


class VerificationError(Exception):
    """The verifier could not answer at all — distinct from answering "not verified".

    Kept separate because "the engine crashed" and "the premises do not force this value" are
    different facts, and Stage 5's attrition report counts them separately (`ENGINE_ERROR` vs
    `NOT_VERIFIED`). Collapsing them would make a broken backend look like a hard corpus.
    """


@dataclass(frozen=True, slots=True)
class Verification:
    """Evidence that a proposal is true. What a `verifier` returns on success.

    Two verification routes exist and the registry has to hold both (docs/04 §QTR):

    * **Engine-verified** — the default, and the only one before 2026-08-06. The engine derives
      the proposal's `fact` symbolically from the figure's premises, and `result` carries the
      traced proof DAG that Stage 6 minimizes.
    * **Layer-verified** — for a quantity no engine can *evaluate*. `area` is the first: no
      engine in the lineage has an area predicate (docs/03 §3.7), so the value is computed by
      arithmetic on engine-certified facts and checked against the reference diagram
      (docs/10 §10.8). There is no engine proof DAG for the *value*, so `result` is None.

    `evidence` is what the verification consumed, and it is not optional bookkeeping: those are
    premises the puzzle must state and Stage 6 must not minimize away.
    """

    fact: Fact
    """The goal in its canonical form. For an engine-verified quantity this is the engine's own
    spelling, which is the one that matches the proof DAG's ids."""
    evidence: tuple[Fact, ...]
    """Facts the verification consumed. Premises Stage 6 must keep."""
    proof_dag: ProofDAG
    """The derivation, whatever produced it. Stage 6 minimizes this and M4 translates its steps.

    An engine-verified quantity gets the engine's traced DAG; a layer-verified one gets the
    layer's own decomposition rendered as steps (`area.proof_dag`). Required rather than
    optional, because a verification with no derivation is a value nobody can be shown how to
    reach, and shipping one would mean shipping a puzzle with no solution.
    """
    result: SolveResult | None = None
    """The engine solve, when there was one. None for a layer-verified quantity."""


@dataclass(frozen=True, slots=True)
class Claim:
    """What a puzzle publishes as its answer, and how to re-measure it in another figure.

    **The seam that lets Stage 8 and Stage 9 be quantity-generic** (docs/10 A4). Both used to
    take a `VertexAngle`, which encoded three assumptions at once: that a goal is an angle, that
    its value is degrees, and that re-measuring it means reading three points off a diagram. An
    area breaks all three. It also *simplifies* the second one — a shoelace area has no mod-pi
    ambiguity to resolve — so the generalization removes a special case rather than adding one.

    `measure` is what makes the well-posedness gate work: it re-reads the published quantity from
    a resampled figure, and a value that moves between two figures both satisfying the statement
    means the puzzle has no answer. Numerics VERIFY here, exactly as everywhere else.
    """

    subject: tuple[str, ...]
    """Engine point names the claim is about. The figure must draw all of them."""
    question: str
    """What the puzzle asks, e.g. `∠ABC` or `[ABC]`."""
    exact: str
    """The answer in the schema's closed exact-value grammar (docs/02)."""
    display: str
    """The player-facing rendering, e.g. `40°` or `25√3/4`."""
    approx: float
    measure: Callable[[Mapping[str, tuple[float, float]]], float | None]
    """Re-read this quantity from another figure's coordinates. None when it cannot be read
    there — a resample to discard, not a failure."""
    render_tolerance: float
    """How far the reference diagram may sit from the published value before the puzzle is
    refused. Absolute, in the quantity's own units."""
    drift_tolerance: float
    """How far the value may move between configuration-matching resamples before the statement
    is judged not to determine it."""
    angle: VertexAngle | None = None
    """The vertex-angle reading, when the quantity has one. Stage 9 draws a goal arc from it;
    a claim without one asks its question in the statement text instead of on the figure."""


#: Given the goal fact and the reference diagram, what the puzzle publishes. None when the goal
#: has no reading in this figure, which Stage 7 counts as `goal_unreadable`.
ClaimOf = Callable[[Fact, Mapping[str, tuple[float, float]]], "Claim | None"]


#: Given a backend, a realized figure and a proposal, decide whether the proposal is true.
#:
#: Returns None for "not verified" — the common and correct outcome, meaning the diagram happened
#: to show a nice value the premises do not force. Raises `VerificationError` when it could not
#: decide at all.
Verifier = Callable[
    ["SolverBackend", "RealizedFigure", Proposal, "SolveOptions"], "Verification | None"
]


def verify_with_engine(
    backend: SolverBackend,
    figure: RealizedFigure,
    proposal: Proposal,
    opts: SolveOptions,
) -> Verification | None:
    """The default: the engine must derive the proposal symbolically from the premises.

    Extracted unchanged from `extract.extract_goals` when the registry grew a `verifier` field;
    every quantity the engine can evaluate uses this and nothing else.

    Verification runs through `solve_facts` with the coordinates held fixed. Re-parsing the
    construction with the goal attached makes the engine's problem builder resample until the
    goal happens to hold numerically, which turns an under-determined candidate into a hang
    instead of a rejection (docs/04 Stage 5).
    """
    from geoforge.solvers.newclid_backend import UnsupportedFactKind

    spec = PremiseSpec(points=figure.points, premises=figure.declared, goals=(proposal.fact,))
    try:
        result = backend.solve_facts(spec, opts)
    except UnsupportedFactKind as exc:
        raise VerificationError("backend cannot express this fact kind") from exc
    except Exception as exc:
        raise VerificationError(str(exc)) from exc

    if not result.solved or not result.proof_dag.proved_goals:
        return None
    canonical = result.proof_dag.index()[result.proof_dag.proved_goals[0]]
    return Verification(
        fact=canonical,
        evidence=tuple(figure.declared),
        proof_dag=result.proof_dag,
        result=result,
    )


@dataclass(frozen=True, slots=True)
class QuantityType:
    """One registered quantity type. The six §QTR fields, plus its fact kind."""

    name: str
    fact_kind: FactKind
    dimension: Dimension
    answer_policy: AnswerPolicy
    template_family: str
    """Which readable-step template family covers it (docs/03 §3.5). M4 consumes this."""
    marks: tuple[str, ...]
    """Figure mark kinds this type may state (docs/02 highlight ID grammar)."""
    goal_extractor: Callable[[FigureView], tuple[Proposal, ...]]
    """Proposes candidate goals from the figure — its coordinates *and* its certified facts.

    Takes a `FigureView` rather than bare coordinates (widened 2026-08-06): a quantity the engine
    cannot evaluate, such as `area`, is computed from certified facts, and reading coordinates to
    decide what is true would violate docs/02 invariant 4."""
    nice_values: Callable[[str], tuple[int, ...]]
    """Given-value palette for a difficulty band (docs/04 Stage 2)."""
    format_answer: Callable[[Fact], str]
    """Renders a goal's exact value for `display` (docs/02).

    Takes the whole `Fact` rather than a `Fraction` (widened 2026-08-06, the last of the three
    §QTR signatures that assumed every quantity is a rational engine predicate). An area's value
    lives in `Fact.exact` as a surd and cannot be a `Fraction` at all — which is the entire
    reason the layer exists."""
    claim_of: ClaimOf
    """How the goal reads as a published answer (docs/10 A4). Stage 8 re-measures through this
    and Stage 9 renders from it, so neither has to know what quantity it is holding.

    Required rather than defaulted: a type with no claim reaches Stage 8 and is discarded as
    `goal_unreadable` on every puzzle it produces — attrition that reads as a hard corpus rather
    than as a missing registration."""
    verifier: Verifier = verify_with_engine
    """How a proposal of this type is shown to be true (docs/04 §QTR, added 2026-08-06).

    Defaults to the engine, which is right for every quantity the engine can evaluate. A type
    the engine has no predicate for — `area` is the first — supplies its own, and that is what
    keeps such a type a *registration* rather than a branch elsewhere in the pipeline."""

    @property
    def is_scale_pinned(self) -> bool:
        return self.dimension is Dimension.SCALE_PINNED


# --------------------------------------------------------------------------------------
# angle
# --------------------------------------------------------------------------------------


def snap_to_integer_degrees(degrees: float) -> int | None:
    """Snap a measured angle to a whole number of degrees, or None if it is not one.

    This is the nice-value filter for angles, and it is deliberately *absolute* rather than
    relative. See `config.EXTRACTION.angle_snap_tolerance_degrees` for why the engine's own
    `get_quotient` is not used, and for the measured gap this threshold sits in.
    """
    nearest = round(degrees)
    if abs(degrees - nearest) > EXTRACTION.angle_snap_tolerance_degrees:
        return None
    if not EXTRACTION.min_goal_degrees <= nearest <= EXTRACTION.max_goal_degrees:
        return None
    return int(nearest)


def directed_line_angle(
    p: tuple[float, float],
    q: tuple[float, float],
    r: tuple[float, float],
    s: tuple[float, float],
) -> float:
    """Directed angle from line pq to line rs, mod pi, in degrees.

    GeoForge's normative angle convention (solvers/types.py). Point order *within* a line does
    not affect it — a line has no direction — which is why the engine may reorder those points
    when it canonicalizes without touching the value.
    """
    v1 = (q[0] - p[0], q[1] - p[1])
    v2 = (s[0] - r[0], s[1] - r[1])
    delta = math.atan2(v2[1], v2[0]) - math.atan2(v1[1], v1[0])
    return math.degrees(delta % math.pi)


def _vertex_angle(
    apex: tuple[float, float], u: tuple[float, float], v: tuple[float, float]
) -> float:
    """Undirected angle at `apex` between the rays to `u` and `v`, in degrees (0, 180)."""
    ux, uy = u[0] - apex[0], u[1] - apex[1]
    vx, vy = v[0] - apex[0], v[1] - apex[1]
    nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
    if nu == 0.0 or nv == 0.0:
        return 0.0
    cosine = max(-1.0, min(1.0, (ux * vx + uy * vy) / (nu * nv)))
    return math.degrees(math.acos(cosine))


def propose_angles(view: FigureView) -> tuple[Proposal, ...]:
    """Propose vertex angles that measure a whole number of degrees.

    Only *vertex* angles are enumerated — pairs of lines through a shared point — because that
    is the shape of the question a human asks ("find angle ABC"). The general line-to-line
    angle between two non-incident lines is a legitimate future extension; it belongs here, in
    the extractor, not in the pipeline.

    Each proposal is spelled so that the directed fact's value *equals* the undirected vertex
    angle in the reference diagram. Both spellings are symbolically true (they differ by the
    supplement) and choosing the matching one keeps the puzzle's answer identical to the value
    the engine proves. Which of the two a human reads off a *resampled* figure is a
    configuration question, settled by the configuration facts in M4's translator and held
    fixed by the M5 well-posedness gate.
    """
    coords = view.coords
    out: list[Proposal] = []
    for vertex in sorted(coords):
        others = sorted(n for n in coords if n != vertex)
        for u, v in itertools.combinations(others, 2):
            degrees = _vertex_angle(coords[vertex], coords[u], coords[v])
            snapped = snap_to_integer_degrees(degrees)
            if snapped is None:
                continue
            # Swapping the two lines negates a directed angle mod pi, i.e. sends d to 180 - d.
            # Pick the order whose directed value is the vertex angle rather than its
            # supplement.
            directed = directed_line_angle(coords[vertex], coords[u], coords[vertex], coords[v])
            keep_order = abs(directed - degrees) <= abs((180.0 - directed) - degrees)
            first, second = (u, v) if keep_order else (v, u)
            out.append(
                Proposal(
                    quantity_type=ANGLE.name,
                    fact=Fact(
                        kind=FactKind.CONSTANT_ANGLE,
                        args=(vertex, first, vertex, second),
                        value=Fraction(snapped, 180),
                    ),
                    subject=(u, vertex, v),
                    measured=degrees,
                )
            )
    return tuple(sorted(out))


def _angle_nice_values(band: str) -> tuple[int, ...]:
    return GENERATION.nice_angle_degrees[band]


def _format_degrees(fact: Fact) -> str:
    """Render an exact angle (in units of pi) as degrees."""
    if fact.value is None:
        raise ValueError(f"{fact.fact_id} carries no angle value")
    degrees = fact.value * 180
    return str(degrees.numerator) if degrees.denominator == 1 else str(degrees)


def _angle_claim(fact: Fact, coords: Mapping[str, tuple[float, float]]) -> Claim | None:
    """The goal as a vertex angle. Unchanged behaviour, moved behind the registry seam.

    The published value comes from `angle.degrees` — the *resolved vertex* reading — and not from
    `fact.value * 180`. The two differ by the supplement whenever the configuration puts the
    vertex angle on the other side of the directed one (docs/03 §3.5 item 2c), and it is the
    resolved one the player sees on the figure.
    """
    from geoforge.generator.translation.phrases import angle_of
    from geoforge.generator.translation.vertex_angles import measure

    angle = angle_of(fact, coords)
    if angle is None or angle.degrees is None:
        return None
    degrees = angle.degrees
    exact = str(degrees.numerator) if degrees.denominator == 1 else str(degrees)
    return Claim(
        subject=(angle.p, angle.vertex, angle.q),
        question=angle.text,
        exact=exact,
        display=f"{exact}°",
        approx=float(degrees),
        measure=lambda c: measure(c, angle.p, angle.vertex, angle.q),
        render_tolerance=TRANSLATION.angle_render_tolerance_degrees,
        drift_tolerance=WELLPOSED.relative_tolerance * 180.0,
        angle=angle,
    )


ANGLE = QuantityType(
    name="angle",
    fact_kind=FactKind.CONSTANT_ANGLE,
    dimension=Dimension.SCALE_FREE,
    answer_policy=AnswerPolicy(
        exactness=Exactness.INTEGER, input_mode=InputMode.KEYPAD, unit="deg"
    ),
    template_family="angle",
    marks=("arc", "tick"),
    goal_extractor=propose_angles,
    nice_values=_angle_nice_values,
    format_answer=_format_degrees,
    claim_of=_angle_claim,
)


# --------------------------------------------------------------------------------------
# area (docs/10 A3)
# --------------------------------------------------------------------------------------
#
# The first quantity no engine can evaluate, and the reason the three §QTR signatures above
# were widened. It is a registration and nothing else: no stage of the pipeline branches on
# the name "area", exactly as this module's docstring promises.


#: Fact kinds the area layer can consume. A triangle none of whose vertices appear in one of
#: these has no route to an area, so enumerating it is wasted work — and the enumeration is
#: cubic in the point count, which is where that would be paid.
_AREA_INPUT_KINDS: frozenset[FactKind] = frozenset(
    {
        FactKind.CONSTANT_LENGTH,
        FactKind.SQUARED_CONSTANT_LENGTH,
        FactKind.PERPENDICULAR,
        FactKind.CONSTANT_ANGLE,
        FactKind.MIDPOINT,
        FactKind.COLLINEAR,
        FactKind.CONSTANT_RATIO,
    }
)


def propose_areas(view: FigureView) -> tuple[Proposal, ...]:
    """Propose the area of every triangle the certified facts determine.

    **This extractor reads facts, not coordinates, and that inversion is the point.** `angle`
    measures the diagram and asks the engine whether the premises force what it saw; there is
    no such question to ask here, because no engine has an area predicate. So the layer computes
    from what was certified and the diagram's only role is to reject a wrong answer — which is
    still numerics verifying rather than deriving (docs/02 invariant 4, docs/10 §10.3).

    A wrong value raises out of here rather than being skipped. `area.verify` is the only thing
    standing between a mis-certified premise and the bank, since cross-engine validation is
    structurally blind to this arithmetic (docs/10 §10.8).
    """
    from geoforge.generator import area as area_layer

    usable = tuple(f for f in view.facts if f.kind in _AREA_INPUT_KINDS)
    reachable = {arg for fact in usable for arg in fact.args} & view.coords.keys()

    out: list[Proposal] = []
    for tri in itertools.combinations(sorted(reachable), 3):
        result = area_layer.triangle_area(tri, usable)
        if result is None:
            continue
        area_layer.verify(result, view.coords)
        out.append(
            Proposal(
                quantity_type=AREA.name,
                fact=result.fact,
                subject=tri,
                measured=result.approx,
            )
        )
    return tuple(sorted(out))


def verify_area(
    backend: SolverBackend,
    figure: RealizedFigure,
    proposal: Proposal,
    opts: SolveOptions,
) -> Verification | None:
    """Re-derive the proposal's area from the certified facts, and hand back the derivation.

    The backend is unused, and deliberately so: an engine that had an opinion here would be an
    engine with an area predicate, and none of them has one. The `Verifier` signature is uniform
    so that `extract_goals` needs no branch, not because every verifier needs every argument.

    The recomputation is not a second opinion — it runs the same routes over the same facts. It
    is how the verifier obtains the *derivation tree*, which a `Proposal` cannot carry: a
    Proposal holds a `Fact`, and a Fact holds a value rather than an argument. The independent
    check is the shoelace comparison inside `area.verify`, and it runs on every node.
    """
    from geoforge.generator import area as area_layer

    del backend, opts
    if len(proposal.subject) != 3:
        raise VerificationError(f"area layer handles triangles; got {proposal.subject}")
    tri = (proposal.subject[0], proposal.subject[1], proposal.subject[2])
    result = area_layer.triangle_area(tri, figure.declared)
    if result is None:
        return None
    area_layer.verify(result, figure.coords())
    if result.fact.fact_id != proposal.fact.fact_id:
        # Deterministic inputs must give a deterministic value; a divergence means the routes
        # are order-dependent, which would break reproducibility from the seed (invariant 2).
        raise VerificationError(
            f"area re-derivation disagreed with the proposal: "
            f"{result.fact.fact_id} vs {proposal.fact.fact_id}"
        )
    # The figure's configuration travels with the derivation. Without it Stage 8 compares the
    # reference against mirrored resamples and calls the difference underdetermination
    # (docs/10 §10.10h) -- the area is mod-pi invariant, the sentence naming the angle is not.
    configuration = tuple(f for f in figure.declared if f.is_configuration)
    return Verification(
        fact=result.fact,
        evidence=result.all_inputs,
        proof_dag=area_layer.proof_dag(result, configuration),
    )


def _area_nice_values(band: str) -> tuple[int, ...]:
    """Side lengths worth stating on an area figure.

    Small integers, because the answer's interest comes from the surd the geometry introduces —
    `sqrt(3)/4 * s^2` — not from the arithmetic on `s`. A large given only makes the number
    uglier without making the puzzle harder.
    """
    del band
    return (1, 2, 3, 4, 5, 6)


def _format_area(fact: Fact) -> str:
    """Render an exact area. Already canonical: the layer writes it in the schema's grammar."""
    if fact.exact is None:
        raise ValueError(f"{fact.fact_id} carries no area value")
    return fact.exact


def _area_claim(fact: Fact, coords: Mapping[str, tuple[float, float]]) -> Claim | None:
    """The goal as a region's area, re-measurable by the shoelace formula.

    **Simpler than the angle case, not harder.** A vertex angle has to be resolved against the
    figure's configuration because a directed angle mod pi admits two readings (docs/03 §3.5
    item 2c); an area admits one. So this needs no resolution step and cannot fail the way
    `angle_of` can — it fails only when the figure does not draw the region at all.

    `angle=None`, so Stage 9 asks the question in the statement rather than drawing a goal arc.
    Shading the region is a genuine improvement and a `Marks` change; asking in text is what the
    reference puzzles of docs/10 §10.1 do anyway.
    """
    import sympy

    from geoforge.generator.area import UnrepresentableArea, display_text, shoelace
    from geoforge.generator.translation.vertex_angles import label

    if fact.exact is None or len(fact.args) < 3:
        return None
    region = tuple(fact.args)
    try:
        value = sympy.sympify(fact.exact)
        if not isinstance(value, sympy.Expr):
            return None
        shown = display_text(value)
    except (UnrepresentableArea, SyntaxError, TypeError, sympy.SympifyError):
        return None
    approx = float(value)

    def measure_region(where: Mapping[str, tuple[float, float]]) -> float | None:
        if not set(region) <= where.keys():
            return None
        return shoelace(tuple(where[p] for p in region))

    scale = max(1.0, abs(approx))
    return Claim(
        subject=region,
        question=f"[{''.join(label(p) for p in region)}]",
        exact=fact.exact,
        display=shown,
        approx=approx,
        measure=measure_region,
        # Tight, because the layer already checked this exact value against this exact diagram
        # and raised if it disagreed (docs/10 §10.8). A loose reference tolerance here would be
        # a second, weaker opinion about something already settled.
        render_tolerance=AREA_CONFIG.verification_tolerance * scale,
        drift_tolerance=WELLPOSED.relative_tolerance * scale,
    )


AREA = QuantityType(
    name="area",
    fact_kind=FactKind.AREA,
    dimension=Dimension.SCALE_PINNED,
    answer_policy=AnswerPolicy(exactness=Exactness.DECIMAL, input_mode=InputMode.DECIMAL, unit=""),
    template_family="area",
    marks=("length_label", "tick"),
    goal_extractor=propose_areas,
    nice_values=_area_nice_values,
    format_answer=_format_area,
    claim_of=_area_claim,
    verifier=verify_area,
)


@lru_cache(maxsize=1)
def registry() -> Mapping[str, QuantityType]:
    """All registered quantity types, by name."""
    return {qt.name: qt for qt in (ANGLE, AREA)}


def enabled_types() -> tuple[QuantityType, ...]:
    """Types enabled for generation, in deterministic order.

    Phase 1 enables everything registered. When `length`/`ratio`/`area` register, this becomes
    a config-driven subset so a band can target one type without unregistering the others.
    """
    return tuple(registry()[name] for name in sorted(registry()))


def get(name: str) -> QuantityType:
    try:
        return registry()[name]
    except KeyError:
        raise ValueError(
            f"unknown quantity type {name!r}; registered: {sorted(registry())}"
        ) from None
