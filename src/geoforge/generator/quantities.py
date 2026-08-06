"""The quantity-type registry (docs/04 §QTR).

The pipeline is parameterized by quantity types; **nothing outside this module may special-case
"angle"**. A type declares six things — how goals are proposed, how it behaves under scaling,
its per-band value palette, its answer policy, its template family, and the figure marks it may
state — and registering those six enables it end to end.

Phase 1 registers `angle` only. `length`, `ratio` and `area` arrive in P3/P5 (docs/09) and must
land as registrations here, not as branches elsewhere. The registry is what keeps that promise
checkable: a test asserts the downstream code paths read these fields rather than the name.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from functools import lru_cache

from geoforge.config import EXTRACTION, GENERATION
from geoforge.solvers.types import Fact, FactKind


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
    format_answer: Callable[[Fraction], str]
    """Renders an exact value for `display` (docs/02)."""

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


def _format_degrees(value: Fraction) -> str:
    """Render an exact angle (in units of pi) as degrees."""
    degrees = value * 180
    return str(degrees.numerator) if degrees.denominator == 1 else str(degrees)


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
)


@lru_cache(maxsize=1)
def registry() -> Mapping[str, QuantityType]:
    """All registered quantity types, by name."""
    return {qt.name: qt for qt in (ANGLE,)}


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
