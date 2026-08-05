"""Exact triangle areas from engine-certified quantities (docs/10 step A2).

The contract, and it is the whole design (docs/10 §10.3, docs/07 T6):

    the ENGINE certifies geometry -- that two lines are perpendicular, that a length is 4.
    this MODULE does arithmetic on what it certified, and nothing else.
    NUMERICS VERIFY, NEVER DERIVE -- the shoelace check confirms the answer, it never supplies it.

So every function here reads `Fact`s and returns a value or `None`. None of them looks at
coordinates to decide *whether* something is true; coordinates appear only in `verify`, and only
to reject.

Why area is worth this. `aconst` is 0-derived over 40 seeded figures -- 102 declared, 0 derived --
so every angle puzzle is a chase from stated angles, and every angle answer is a rational multiple
of pi because `ConstantAngle.angle` is a `Fraction` (docs/07 T18). No engine in the lineage can
represent sqrt(3)/2, let alone derive it. An equilateral triangle of side s has area
(sqrt3/4)*s^2, and that is one multiplication away from facts the engine hands us for free.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

import sympy

from geoforge.config import AREA
from geoforge.solvers.types import Fact, FactKind

Coords = Mapping[str, tuple[float, float]]


class AreaVerificationError(RuntimeError):
    """An exactly-computed area disagrees with the reference diagram.

    Deliberately an exception and not a discard. Every other rejection in this module means
    "the engine did not certify enough to answer", which is ordinary attrition. This one means
    the layer computed a number that is *wrong*, which is either a bug here or a mis-certified
    premise, and docs/10 §10.8 makes it a build failure because the cross-engine validator
    cannot see layer arithmetic and so will not catch it downstream.
    """


@dataclass(frozen=True, slots=True)
class AreaResult:
    """An exact area, the route that produced it, and the facts it consumed."""

    exact: sympy.Expr
    """The exact value. May be irrational -- that is the point of the layer."""
    route: str
    """Which primitive produced it; becomes the solution step's rule id."""
    inputs: tuple[Fact, ...]
    """The engine facts consumed. These are premises the puzzle must state and Stage 6 must
    keep, so they are returned rather than discarded."""

    @property
    def approx(self) -> float:
        return float(self.exact)

    @property
    def is_irrational(self) -> bool:
        """True when the value is not a rational number -- the answers angle cannot reach."""
        return not sympy.nsimplify(self.exact).is_rational


# ----------------------------------------------------------------------------------------
# Reading certified quantities out of the engine's facts
# ----------------------------------------------------------------------------------------


def _pair(u: str, v: str) -> frozenset[str]:
    return frozenset((u, v))


def certified_lengths(facts: tuple[Fact, ...]) -> dict[frozenset[str], sympy.Expr]:
    """Segment lengths the engine certified, exactly.

    `lconst` gives the length; `l2const` gives its **square**, so it yields an irrational side
    directly (`l2const ab = 3` means |ab| = sqrt(3)). Nothing derives a squared constant
    (docs/07 T21), so l2const is only ever a given -- but a given is exactly what the layer
    needs, and it is the cheapest source of an irrational input we have.
    """
    out: dict[frozenset[str], sympy.Expr] = {}
    for fact in facts:
        if fact.value is None or len(fact.args) != 2:
            continue
        key = _pair(*fact.args)
        if fact.kind is FactKind.CONSTANT_LENGTH:
            out[key] = sympy.nsimplify(_as_exact(fact.value))
        elif fact.kind is FactKind.SQUARED_CONSTANT_LENGTH and key not in out:
            out[key] = sympy.sqrt(_as_exact(fact.value))
    return out


def certified_right_angles(facts: tuple[Fact, ...]) -> set[tuple[str, frozenset[str]]]:
    """Right angles, as (apex, {other two points}).

    `perp a b c d` states line ab ⟂ line cd. It pins a triangle's angle only when the two lines
    meet at one of its vertices, which is the shared-point test below. Unlike `aconst` this
    carries no mod-pi ambiguity: a right angle is its own supplement, which is exactly why it is
    also the one angle no directed-angle fixture may use (ONBOARDING gotcha 6).
    """
    out: set[tuple[str, frozenset[str]]] = set()
    for fact in facts:
        if fact.kind is not FactKind.PERPENDICULAR or len(fact.args) != 4:
            continue
        a, b, c, d = fact.args
        shared = {a, b} & {c, d}
        if len(shared) != 1:
            continue
        apex = shared.pop()
        far = ({a, b} | {c, d}) - {apex}
        if len(far) == 2:
            out.add((apex, frozenset(far)))
    return out


def certified_vertex_angles(facts: tuple[Fact, ...]) -> dict[tuple[str, frozenset[str]], Fraction]:
    """Stated angles, keyed by (apex, {the two far points}), as a fraction of pi.

    **The mod-pi hazard lives here** (docs/10 §10.5). `aconst` is a *directed* line-to-line
    angle mod pi, so a stated 60 degrees may realize as a 120 degree vertex angle -- measured:
    `s_angle b a c 60o` produced |bc| = 2*sqrt(3), i.e. cos C = -1/2, i.e. 120 degrees.

    This function therefore returns the DIRECTED value and does not pretend to resolve it. Only
    a consumer whose formula is invariant under theta -> pi - theta may use it, which today is
    `_sas` alone because sin(theta) = sin(pi - theta). Sector area, arc length and circular
    segment are NOT invariant and must not call this without resolving against configuration
    facts first.
    """
    out: dict[tuple[str, frozenset[str]], Fraction] = {}
    for fact in facts:
        if fact.kind is not FactKind.CONSTANT_ANGLE or fact.value is None or len(fact.args) != 4:
            continue
        a, b, c, d = fact.args
        shared = {a, b} & {c, d}
        if len(shared) != 1:
            continue
        apex = shared.pop()
        far = ({a, b} | {c, d}) - {apex}
        if len(far) != 2:
            continue
        try:
            out[(apex, frozenset(far))] = Fraction(str(fact.value))
        except (ValueError, ZeroDivisionError):
            continue
    return out


def _as_exact(value: object) -> sympy.Expr:
    """A fact's value as an exact SymPy number. Floats are refused, not rounded."""
    if isinstance(value, Fraction):
        return sympy.Rational(value.numerator, value.denominator)
    if isinstance(value, int):
        return sympy.Integer(value)
    return sympy.nsimplify(sympy.sympify(str(value)), rational=True)


# ----------------------------------------------------------------------------------------
# The primitives (docs/10 §10.5)
# ----------------------------------------------------------------------------------------


def _right_angle_area(
    tri: tuple[str, str, str],
    lengths: dict[frozenset[str], sympy.Expr],
    rights: set[tuple[str, frozenset[str]]],
    facts: tuple[Fact, ...],
) -> AreaResult | None:
    """(1/2)*leg*leg at a certified right angle. Mod-pi safe: a right angle is unambiguous."""
    for apex in tri:
        others = tuple(p for p in tri if p != apex)
        if (apex, frozenset(others)) not in rights:
            continue
        leg1, leg2 = lengths.get(_pair(apex, others[0])), lengths.get(_pair(apex, others[1]))
        if leg1 is None or leg2 is None:
            continue
        return AreaResult(
            exact=sympy.simplify(sympy.Rational(1, 2) * leg1 * leg2),
            route="area_right_triangle",
            inputs=_facts_used(facts, tri),
        )
    return None


def _heron(
    tri: tuple[str, str, str],
    lengths: dict[frozenset[str], sympy.Expr],
    facts: tuple[Fact, ...],
) -> AreaResult | None:
    """Heron's formula from three certified sides. No angle involved, so trivially mod-pi safe."""
    a, b, c = tri
    sides = [lengths.get(_pair(a, b)), lengths.get(_pair(b, c)), lengths.get(_pair(a, c))]
    if any(s is None for s in sides):
        return None
    x, y, z = sides
    assert x is not None and y is not None and z is not None
    s = (x + y + z) / 2
    value = sympy.simplify(sympy.sqrt(s * (s - x) * (s - y) * (s - z)))
    # A certified-but-degenerate triple gives zero area; that is not a puzzle.
    if value == 0 or not value.is_real:
        return None
    return AreaResult(exact=value, route="area_heron", inputs=_facts_used(facts, tri))


def _sas(
    tri: tuple[str, str, str],
    lengths: dict[frozenset[str], sympy.Expr],
    angles: dict[tuple[str, frozenset[str]], Fraction],
    facts: tuple[Fact, ...],
) -> AreaResult | None:
    """(1/2)*a*b*sin(C) from two certified sides and the certified angle between them.

    **This is the primitive that makes the mod-pi hazard harmless.** `angles` holds a directed
    value mod pi, so the true vertex angle is either theta or pi - theta -- and
    sin(theta) = sin(pi - theta), so both give the same area. That invariance is asserted by a
    test, because it is the property that lets this run on an unresolved angle at all.
    """
    for apex in tri:
        others = tuple(p for p in tri if p != apex)
        theta = angles.get((apex, frozenset(others)))
        if theta is None:
            continue
        side1, side2 = lengths.get(_pair(apex, others[0])), lengths.get(_pair(apex, others[1]))
        if side1 is None or side2 is None:
            continue
        radians = sympy.pi * sympy.Rational(theta.numerator, theta.denominator)
        value = sympy.simplify(sympy.Rational(1, 2) * side1 * side2 * sympy.sin(radians))
        if value == 0:
            return None
        return AreaResult(exact=sympy.Abs(value), route="area_sas", inputs=_facts_used(facts, tri))
    return None


def _facts_used(facts: tuple[Fact, ...], tri: tuple[str, str, str]) -> tuple[Fact, ...]:
    """The certified facts wholly about this triangle. These are premises Stage 6 must keep."""
    points = set(tri)
    return tuple(f for f in facts if f.args and set(f.args) <= points)


def triangle_area(tri: tuple[str, str, str], facts: tuple[Fact, ...]) -> AreaResult | None:
    """Exact area of a triangle, or None when the engine did not certify enough to find one.

    Primitives are tried cheapest-first, and the order is deliberate: the right-angle route uses
    two facts, Heron three, and SAS three including an angle. Returning None is ordinary
    attrition -- most triangles in a figure have no certified sides at all.
    """
    if len(set(tri)) != 3:
        return None
    lengths = certified_lengths(facts)
    return (
        _right_angle_area(tri, lengths, certified_right_angles(facts), facts)
        or _heron(tri, lengths, facts)
        or _sas(tri, lengths, certified_vertex_angles(facts), facts)
    )


# ----------------------------------------------------------------------------------------
# Verification (docs/10 §10.8) -- confirms, never supplies
# ----------------------------------------------------------------------------------------


def shoelace(points: tuple[tuple[float, float], ...]) -> float:
    """Polygon area from coordinates. The independent numeric route, used only to check."""
    n = len(points)
    total = sum(
        points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    )
    return abs(total) / 2


def verify(result: AreaResult, tri: tuple[str, str, str], coords: Coords) -> AreaResult:
    """Check an exact area against the reference diagram, or raise.

    Raising rather than returning False is the point: a mismatch means the layer produced a
    wrong number, and nothing downstream can catch it -- `bank/validate.py` re-derives *engine*
    facts on a second engine and is structurally blind to this arithmetic (docs/10 §10.8).
    """
    missing = [p for p in tri if p not in coords]
    if missing:
        raise AreaVerificationError(f"{result.route}: no coordinates for {missing}")
    numeric = shoelace(tuple(coords[p] for p in tri))
    exact = result.approx
    if not math.isfinite(exact):
        raise AreaVerificationError(f"{result.route}: non-finite exact value {result.exact}")
    if abs(exact - numeric) > AREA.verification_tolerance * max(1.0, numeric):
        raise AreaVerificationError(
            f"{result.route} on {tri}: exact {result.exact} = {exact!r} disagrees with the "
            f"reference diagram's {numeric!r} (tolerance "
            f"{AREA.verification_tolerance})"
        )
    return result


def area_of(
    tri: tuple[str, str, str], facts: tuple[Fact, ...], coords: Coords
) -> AreaResult | None:
    """Compute and verify. The entry point; returns None on attrition, raises on a wrong value."""
    result = triangle_area(tri, facts)
    return None if result is None else verify(result, tri, coords)
