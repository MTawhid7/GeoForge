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
from geoforge.solvers.types import (
    Fact,
    FactId,
    FactKind,
    Justification,
    JustificationKind,
    ProofDAG,
    ProofStep,
)

Coords = Mapping[str, tuple[float, float]]


class UnrepresentableArea(RuntimeError):
    """The exact value falls outside the schema's closed exact-value grammar (docs/02).

    The grammar is a sum of `a/b*sqrt(c)` terms, and it is closed on purpose: a value the schema
    cannot parse is a value nobody can promise the frontend will render or compare correctly. So
    a cube root or a nested radical is **attrition**, not something to smuggle through as a
    float. Nothing the current routes produce hits this — ½ab·sin(C) at the template angles and
    Heron on integer sides both land in quadratic surds — but the day a route reaches further,
    this is where it stops.
    """


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
    """An exact area, the route that produced it, and everything that route stood on.

    **A node in a derivation tree, not a bare value** (docs/10 A3). The recursive routes --
    `area_median_split`, `area_cevian_split` -- compute one region's area from another's, and
    an earlier version flattened that chain into a single result with a pooled `inputs` tuple.
    That threw away the only structure the pipeline downstream of Stage 5 has to work with:
    Stage 6 minimizes a proof DAG and M4 translates its steps, so a layer whose reasoning is
    invisible cannot produce a puzzle with a solution. Keeping `parents` is what lets
    `proof_dag` reconstitute the argument as steps the rest of the pipeline already handles.
    """

    region: tuple[str, ...]
    """The polygon this is the area of. Its own identity, and what `verify` checks against."""
    exact: sympy.Expr
    """The exact value. May be irrational -- that is the point of the layer."""
    route: str
    """Which primitive produced it; becomes the solution step's rule id."""
    inputs: tuple[Fact, ...]
    """The engine facts **this step** consumed -- not its parents' (those are reachable through
    `parents`). Precise rather than pooled: an over-collected input becomes a given the puzzle
    states and never uses, which docs/05 filter 5 treats as a bug rather than attrition."""
    parents: tuple[AreaResult, ...] = ()
    """Areas this one was computed from. Empty for a direct route."""

    def __post_init__(self) -> None:
        """Canonicalize a triangle's vertex order.

        MEASURED: without this, `_decompose` builds its parent as `(apex, near, far)` and emits
        `[ACB]` where the extractor asked for `[ABC]` — the same region, two `fact_id`s, and so
        two proof-DAG nodes that never share and two puzzles that are the same puzzle. Sound
        because area is invariant under permuting a *triangle's* vertices.

        Guarded on `len == 3` rather than applied blindly: for a polygon the vertex order *is*
        the boundary, and sorting one would silently compute the area of a different shape.
        """
        if len(self.region) == 3:
            object.__setattr__(self, "region", tuple(sorted(self.region)))

    @property
    def approx(self) -> float:
        return float(self.exact)

    @property
    def is_irrational(self) -> bool:
        """True when the value is not a rational number -- the answers angle cannot reach."""
        return not sympy.nsimplify(self.exact).is_rational

    @property
    def fact(self) -> Fact:
        """This area as a `Fact`, so everything downstream of Stage 5 can hold it."""
        return Fact(kind=FactKind.AREA, args=self.region, exact=exact_text(self.exact))

    @property
    def display(self) -> str:
        """The player-facing rendering, e.g. `25√3/4` (docs/02 keeps this separate from
        `exact`)."""
        return display_text(self.exact)

    def walk(self) -> tuple[AreaResult, ...]:
        """This result and every ancestor, deepest first. Deterministic."""
        out: list[AreaResult] = []
        for parent in self.parents:
            out.extend(parent.walk())
        out.append(self)
        return tuple(out)

    @property
    def all_inputs(self) -> tuple[Fact, ...]:
        """Every engine fact the whole derivation consumed, deduplicated and sorted.

        These are premises the puzzle must state and Stage 6 must not minimize away.
        """
        return tuple(sorted({fact for node in self.walk() for fact in node.inputs}))


# ----------------------------------------------------------------------------------------
# Rendering an exact value (docs/02 answer policy)
# ----------------------------------------------------------------------------------------


def _terms(value: sympy.Expr) -> tuple[tuple[sympy.Rational, int], ...]:
    """Split an exact value into `(rational coefficient, radicand)` terms, radicand 1 for none.

    Raises `UnrepresentableArea` for anything outside the schema's grammar. Doing the check here,
    structurally on the SymPy expression, rather than by pattern-matching the printed string: a
    printer change would silently alter what a regex accepts, and this is the boundary between
    "an exact value" and "a string we hope parses".
    """
    out: list[tuple[sympy.Rational, int]] = []
    for term in sympy.Add.make_args(sympy.expand(value)):
        coeff, rest = term.as_coeff_Mul()
        if not coeff.is_Rational:
            raise UnrepresentableArea(f"{value} has a non-rational coefficient in {term}")
        if rest == sympy.Integer(1):
            out.append((sympy.Rational(coeff), 1))
            continue
        power: sympy.Pow | None = rest if isinstance(rest, sympy.Pow) else None
        if (
            power is None
            or power.exp != sympy.Rational(1, 2)
            or not power.base.is_Integer
            or power.base <= 0
        ):
            raise UnrepresentableArea(
                f"{value} is outside the closed exact-value grammar (docs/02): {term}"
            )
        out.append((sympy.Rational(coeff), int(power.base)))
    return tuple(out)


def exact_text(value: sympy.Expr) -> str:
    """The `exact` string, in the schema's closed grammar (docs/02).

    **Not `str(expr)`.** SymPy prints `25*sqrt(3)/4`, and the grammar's term is
    `-?\\d+(/\\d+)?(\\*sqrt\\(\\d+\\))?` — coefficient first, radical last — so the same number
    has to be written `25/4*sqrt(3)`. Getting this wrong would not fail here; it would fail at
    the schema boundary with a puzzle already built, which is the expensive place to find out.

    This string is also the fact id (`area:a:b:c=25/4*sqrt(3)`), so it has to be canonical: two
    spellings of one area would be two facts to every consumer that compares ids.
    """
    parts: list[str] = []
    for coeff, radicand in _terms(value):
        head = str(coeff.p) if coeff.q == 1 else f"{coeff.p}/{coeff.q}"
        term = head if radicand == 1 else f"{head}*sqrt({radicand})"
        parts.append(term if not parts or term.startswith("-") else f"+{term}")
    return "".join(parts)


def display_text(value: sympy.Expr) -> str:
    """The player-facing rendering: `25/4*sqrt(3)` becomes `25√3/4`.

    Separate from `exact_text` because docs/02 keeps `exact`, `approx` and `display` apart —
    one is for comparison, one is for reading. The denominator trails the radical the way it is
    written by hand.
    """
    parts: list[str] = []
    for coeff, radicand in _terms(value):
        sign = "-" if coeff < 0 else ("+" if parts else "")
        numerator, denominator = abs(coeff.p), coeff.q
        if radicand == 1:
            body = str(numerator)
        else:
            head = "" if numerator == 1 else str(numerator)
            body = f"{head}√{radicand}"
        parts.append(f"{sign}{body}" if denominator == 1 else f"{sign}{body}/{denominator}")
    return "".join(parts)


# ----------------------------------------------------------------------------------------
# Reading certified quantities out of the engine's facts
# ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Certified[T]:
    """A quantity the engine certified, together with the fact that certified it.

    The fact travels with the value because a route has to report exactly which premises it
    consumed (see `AreaResult.inputs`). Reading the value and then re-scanning the fact list to
    guess the source is how an over-collected input set gets built.
    """

    value: T
    fact: Fact


def _pair(u: str, v: str) -> frozenset[str]:
    return frozenset((u, v))


def certified_lengths(facts: tuple[Fact, ...]) -> dict[frozenset[str], Certified[sympy.Expr]]:
    """Segment lengths the engine certified, exactly.

    `lconst` gives the length; `l2const` gives its **square**, so it yields an irrational side
    directly (`l2const ab = 3` means |ab| = sqrt(3)). Nothing derives a squared constant
    (docs/07 T21), so l2const is only ever a given -- but a given is exactly what the layer
    needs, and it is the cheapest source of an irrational input we have.
    """
    out: dict[frozenset[str], Certified[sympy.Expr]] = {}
    for fact in facts:
        if fact.value is None or len(fact.args) != 2:
            continue
        key = _pair(*fact.args)
        if fact.kind is FactKind.CONSTANT_LENGTH:
            out[key] = Certified(sympy.nsimplify(_as_exact(fact.value)), fact)
        elif fact.kind is FactKind.SQUARED_CONSTANT_LENGTH and key not in out:
            out[key] = Certified(sympy.sqrt(_as_exact(fact.value)), fact)
    return out


def certified_right_angles(facts: tuple[Fact, ...]) -> dict[tuple[str, frozenset[str]], Fact]:
    """Right angles, as (apex, {other two points}).

    `perp a b c d` states line ab ⟂ line cd. It pins a triangle's angle only when the two lines
    meet at one of its vertices, which is the shared-point test below. Unlike `aconst` this
    carries no mod-pi ambiguity: a right angle is its own supplement, which is exactly why it is
    also the one angle no directed-angle fixture may use (ONBOARDING gotcha 6).
    """
    out: dict[tuple[str, frozenset[str]], Fact] = {}
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
            out.setdefault((apex, frozenset(far)), fact)
    return out


def certified_vertex_angles(
    facts: tuple[Fact, ...],
) -> dict[tuple[str, frozenset[str]], Certified[Fraction]]:
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
    out: dict[tuple[str, frozenset[str]], Certified[Fraction]] = {}
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
            out[(apex, frozenset(far))] = Certified(Fraction(str(fact.value)), fact)
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
    lengths: dict[frozenset[str], Certified[sympy.Expr]],
    rights: dict[tuple[str, frozenset[str]], Fact],
) -> AreaResult | None:
    """(1/2)*leg*leg at a certified right angle. Mod-pi safe: a right angle is unambiguous."""
    for apex in tri:
        others = tuple(p for p in tri if p != apex)
        right = rights.get((apex, frozenset(others)))
        if right is None:
            continue
        leg1, leg2 = lengths.get(_pair(apex, others[0])), lengths.get(_pair(apex, others[1]))
        if leg1 is None or leg2 is None:
            continue
        return AreaResult(
            region=tri,
            exact=sympy.simplify(sympy.Rational(1, 2) * leg1.value * leg2.value),
            route="area_right_triangle",
            inputs=(right, leg1.fact, leg2.fact),
        )
    return None


def _heron(
    tri: tuple[str, str, str],
    lengths: dict[frozenset[str], Certified[sympy.Expr]],
) -> AreaResult | None:
    """Heron's formula from three certified sides. No angle involved, so trivially mod-pi safe."""
    a, b, c = tri
    sides = [lengths.get(_pair(a, b)), lengths.get(_pair(b, c)), lengths.get(_pair(a, c))]
    if any(s is None for s in sides):
        return None
    x, y, z = sides
    assert x is not None and y is not None and z is not None
    s = (x.value + y.value + z.value) / 2
    value = sympy.simplify(sympy.sqrt(s * (s - x.value) * (s - y.value) * (s - z.value)))
    # A certified-but-degenerate triple gives zero area; that is not a puzzle.
    if value == 0 or not value.is_real:
        return None
    return AreaResult(region=tri, exact=value, route="area_heron", inputs=(x.fact, y.fact, z.fact))


def _sas(
    tri: tuple[str, str, str],
    lengths: dict[frozenset[str], Certified[sympy.Expr]],
    angles: dict[tuple[str, frozenset[str]], Certified[Fraction]],
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
        radians = sympy.pi * sympy.Rational(theta.value.numerator, theta.value.denominator)
        value = sympy.simplify(
            sympy.Rational(1, 2) * side1.value * side2.value * sympy.sin(radians)
        )
        if value == 0:
            return None
        return AreaResult(
            region=tri,
            exact=sympy.Abs(value),
            route="area_sas",
            inputs=(side1.fact, side2.fact, theta.fact),
        )
    return None


def _midpoint_splits(facts: tuple[Fact, ...]) -> tuple[tuple[tuple[str, str, str], Fact], ...]:
    """Certified midpoints, as ((m, u, v), fact) meaning m is the midpoint of segment uv."""
    return tuple(
        ((fact.args[0], fact.args[1], fact.args[2]), fact)
        for fact in facts
        if fact.kind is FactKind.MIDPOINT and len(fact.args) == 3
    )


def _incidence_witness(u: str, v: str, point: str, facts: tuple[Fact, ...]) -> Fact | None:
    """The fact certifying `point` lies on line uv, or None if nothing does.

    Returns the *witness* rather than a bare yes, because a route that leans on this incidence
    has to state it: a puzzle whose answer needs "y is on ab" and does not say so is
    under-determined, and Stage 8 would be the only thing standing between that and the bank.

    An endpoint is not handled here — it is on the line trivially and needs no premise, and the
    one caller excludes that case before asking.
    """
    for fact in facts:
        if fact.kind is FactKind.COLLINEAR and {u, v, point} <= set(fact.args):
            return fact
        if fact.kind is FactKind.MIDPOINT and len(fact.args) == 3:
            m, x, y = fact.args
            if m == point and {x, y} == {u, v}:
                return fact
    return None


def _cevian_split(
    tri: tuple[str, str, str], facts: tuple[Fact, ...], depth: int
) -> AreaResult | None:
    """Area by ratio when the apex sits on a cevian: [ABP] = [ABX] * PY/XY.

    Triangles ABP and ABX share the base AB, so their areas are in the ratio of the apexes'
    distances from AB. If P, X and Y are collinear with Y on line AB, that ratio is PY/XY --
    still no length required.

    **Why the arithmetic is ours and not the engine's.** The engine certifies `rconst X P P Y = k`
    (|XP|/|PY| = k) but *cannot* certify `rconst P Y X Y = 1/(k+1)`: AR chases ratios
    multiplicatively, and getting from XP/PY to PY/XY needs XY = XP + PY, an **addition** it does
    not do. MEASURED on a centroid figure: `rconst c g g m 2/1` proves, `rconst g m c m 1/3` does
    not. That one addition is exactly the kind of arithmetic-on-certified-quantities docs/07 T6
    permits, and doing it here is what unlocks the centroid.

    **The configuration assumption, stated rather than hidden.** `PY/XY = 1/(k+1)` assumes P lies
    *between* X and Y; outside that segment the relation differs. Betweenness is a configuration
    fact (docs/07 T2) and is not always certified, so this rule is sound only because `verify`
    checks the result against the reference diagram and raises on a mismatch. Templates are
    reviewed, so their configuration is known-good; a figure from elsewhere that violates it
    fails loudly rather than shipping a wrong answer.
    """
    if depth <= 0:
        return None
    for fact in facts:
        if fact.kind is not FactKind.CONSTANT_RATIO or fact.value is None or len(fact.args) != 4:
            continue
        x, p1, p2, y = fact.args
        if p1 != p2 or p1 not in tri or x == y:
            continue
        apex = p1
        base = tuple(q for q in tri if q != apex)
        if len(base) != 2 or y in base or x in base:
            continue
        foot = _incidence_witness(base[0], base[1], y, facts)
        if foot is None:
            continue
        cevian = next(
            (f for f in facts if f.kind is FactKind.COLLINEAR and {x, apex, y} <= set(f.args)),
            None,
        )
        if cevian is None:
            continue
        ratio = _as_exact(fact.value)
        if ratio == -1:
            continue
        parent = _triangle_area((x, base[0], base[1]), facts, depth - 1)
        if parent is None:
            continue
        return AreaResult(
            region=tri,
            exact=sympy.simplify(parent.exact / (ratio + 1)),
            route="area_cevian_split",
            inputs=(fact, cevian, foot),
            parents=(parent,),
        )
    return None


def _decompose(tri: tuple[str, str, str], facts: tuple[Fact, ...], depth: int) -> AreaResult | None:
    """Area by RATIO against a larger triangle, when a certified midpoint relates the two.

    This is what makes a decorated figure workable, and it is the difference between a puzzle
    and an arithmetic exercise. MEASURED: on an SAS-pinned triangle with a midpoint added, the
    direct primitives compute **0 of 20** sub-triangle areas -- because |bc| is irrational, so
    |bm| = |bc|/2 is unreachable and the median |am| more so, and `lconst` holds a `Fraction`
    and cannot express any of them.

    None of that is needed. If m is the midpoint of bc then triangles abm and abc share the apex
    a and the second has twice the base, so [abm] = (1/2)[abc] exactly -- an area-ratio argument
    over certified structure, using no length at all. Verified against the diagram on 6 of 6
    instantiations before this was written.

    This is the Chou-Gao-Zhang area-method idea that docs/03 §3.7 names as an alternative engine,
    used here as a decomposition rule rather than adopted as a backend.

    Recursion is depth-bounded so two midpoints compose (the medial triangle is a quarter) while
    a cyclic set of midpoint facts cannot spin.
    """
    if depth <= 0:
        return None
    for (m, u, v), midpoint in _midpoint_splits(facts):
        if m not in tri:
            continue
        rest = tuple(p for p in tri if p != m)
        if len(rest) != 2:
            continue
        # The triangle must have one of the segment's endpoints as a vertex; the parent is the
        # same triangle with the midpoint replaced by the far endpoint.
        for near, far in ((u, v), (v, u)):
            if near not in rest:
                continue
            apex = next((p for p in rest if p != near), None)
            if apex is None or apex in (u, v):
                continue
            parent = (apex, near, far)
            whole = _triangle_area(parent, facts, depth - 1)
            if whole is None:
                continue
            return AreaResult(
                region=tri,
                exact=sympy.simplify(whole.exact / 2),
                route="area_median_split",
                inputs=(midpoint,),
                parents=(whole,),
            )
    return None


def _triangle_area(
    tri: tuple[str, str, str], facts: tuple[Fact, ...], depth: int
) -> AreaResult | None:
    if len(set(tri)) != 3:
        return None
    lengths = certified_lengths(facts)
    return (
        _right_angle_area(tri, lengths, certified_right_angles(facts))
        or _heron(tri, lengths)
        or _sas(tri, lengths, certified_vertex_angles(facts))
        or _decompose(tri, facts, depth)
        or _cevian_split(tri, facts, depth)
    )


def triangle_area(tri: tuple[str, str, str], facts: tuple[Fact, ...]) -> AreaResult | None:
    """Exact area of a triangle, or None when the engine did not certify enough to find one.

    Primitives are tried cheapest-first, and the order is deliberate: the right-angle route uses
    two facts, Heron three, SAS three including an angle, and decomposition recurses. Returning
    None is ordinary attrition -- most triangles in a figure have no certified sides at all.
    """
    return _triangle_area(tri, facts, AREA.max_decomposition_depth)


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


def verify(result: AreaResult, coords: Coords) -> AreaResult:
    """Check an exact area against the reference diagram, or raise.

    Raising rather than returning False is the point: a mismatch means the layer produced a
    wrong number, and nothing downstream can catch it -- `bank/validate.py` re-derives *engine*
    facts on a second engine and is structurally blind to this arithmetic (docs/10 §10.8).

    **Every node in the derivation is checked, not just the answer.** A wrong intermediate that
    a later step happens to cancel out would otherwise ship a correct number attached to a
    solution that does not hold -- and the solution is what the player reads.
    """
    for node in result.walk():
        missing = [p for p in node.region if p not in coords]
        if missing:
            raise AreaVerificationError(f"{node.route}: no coordinates for {missing}")
        numeric = shoelace(tuple(coords[p] for p in node.region))
        exact = node.approx
        if not math.isfinite(exact):
            raise AreaVerificationError(f"{node.route}: non-finite exact value {node.exact}")
        if abs(exact - numeric) > AREA.verification_tolerance * max(1.0, numeric):
            raise AreaVerificationError(
                f"{node.route} on {node.region}: exact {node.exact} = {exact!r} disagrees with "
                f"the reference diagram's {numeric!r} (tolerance "
                f"{AREA.verification_tolerance})"
            )
    return result


def area_of(
    tri: tuple[str, str, str], facts: tuple[Fact, ...], coords: Coords
) -> AreaResult | None:
    """Compute and verify. The entry point; returns None on attrition, raises on a wrong value."""
    result = triangle_area(tri, facts)
    return None if result is None else verify(result, coords)


# ----------------------------------------------------------------------------------------
# The decomposition as a proof DAG (docs/10 A3)
# ----------------------------------------------------------------------------------------


def proof_dag(result: AreaResult) -> ProofDAG:
    """Reconstitute the decomposition as a `ProofDAG`, so Stage 6 onward needs no special case.

    This is the hinge of A3. Everything after Stage 5 -- premise minimization, the translator,
    figure pruning, the difficulty features -- is written against a proof DAG, and an area has
    no *engine* proof because no engine has an area predicate. The alternative was to teach
    each of those stages about areas; this instead teaches the area layer to speak their
    language, and it costs nothing because the layer already knows its own reasoning: each
    `AreaResult` is one step, its `inputs` are that step's premises, and its `parents` are the
    intermediate areas it stands on.

    The rule ids are the route names (`area_sas`, `area_median_split`, `area_cevian_split`),
    which makes them public API under CLAUDE.md's step-`rule` rule -- they need M4 templates
    before a puzzle built this way can render its solution.

    Justification is `RULE_APPLICATION`, not a new kind. A route *is* a theorem application --
    "the median halves the area" is a rule with premises and a conclusion -- and inventing a
    kind for it would only make every consumer grow a branch for the same thing.
    """
    nodes = result.walk()
    facts: dict[FactId, Fact] = {}
    steps: list[ProofStep] = []
    assumptions: list[FactId] = []
    configuration: list[FactId] = []

    for node in nodes:
        conclusion = node.fact
        facts[conclusion.fact_id] = conclusion
        premises: list[FactId] = []
        for source in (*node.inputs, *(p.fact for p in node.parents)):
            facts[source.fact_id] = source
            premises.append(source.fact_id)
            if source.is_layer:
                continue  # an intermediate area, concluded by another step
            target = configuration if source.is_configuration else assumptions
            if source.fact_id not in target:
                target.append(source.fact_id)
        steps.append(
            ProofStep(
                conclusion=conclusion.fact_id,
                premises=tuple(sorted(set(premises))),
                justification=Justification(
                    kind=JustificationKind.RULE_APPLICATION,
                    rule_id=node.route,
                    rule_name=_ROUTE_NAMES.get(node.route, node.route),
                ),
            )
        )

    return ProofDAG(
        facts=tuple(sorted(facts.values())),
        steps=tuple(sorted(steps)),
        assumptions=tuple(sorted(assumptions)),
        numerical_checks=tuple(sorted(configuration)),
        trivial=(),
        proved_goals=(result.fact.fact_id,),
        unproved_goals=(),
    )


#: Human descriptions of the routes, seeding M4's templates the way an engine's `rule_name`
#: does for a DDAR rule (docs/03 §3.5).
_ROUTE_NAMES: dict[str, str] = {
    "area_right_triangle": "Half the product of the legs of a right triangle",
    "area_heron": "Heron's formula from three sides",
    "area_sas": "Half the product of two sides and the sine of the angle between them",
    "area_median_split": "A median halves the area of a triangle",
    "area_cevian_split": "Triangles on a common base have areas in the ratio of their heights",
}
