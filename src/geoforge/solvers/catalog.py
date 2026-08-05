"""Engine-neutral catalogue of construction primitives (docs/03 §3.4).

The sampler needs to know each primitive's shape — which arguments are existing points, which
are newly introduced, and which are numeric parameters. That knowledge lives inside the
engine, so it is exposed here rather than imported directly by `generator/`: nothing outside
`solvers/` may import engine code (docs/02 invariant 1). A future backend supplies its own
catalogue and the sampler is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

#: Constructions whose spare arguments are numeric values rather than points.
#: Kept as an explicit whitelist: a construction with unclassified leftover arguments is
#: excluded from the catalogue instead of being guessed at (see `_build_catalog`).
_NUMERIC_PARAM_CONSTRUCTIONS: frozenset[str] = frozenset(
    {"aconst", "s_angle", "lconst", "l2const", "rconst", "rconst2", "r2const"}
)

#: Predicates that put a circle the renderer will actually **draw** into the figure. This is
#: deliberately the same pair `generator/emit.py::circles_of` honours, because a primitive whose
#: circle is never drawn carries none of the difficulty the sampler bias exists to buy.
#:
#: **Corrected in Phase 3 M4 — it used to include `cong`, and that one keyword produced the
#: first bank.** A JGEX circle *is* expressed with `cong` ("equidistant from a centre"), so the
#: keyword looked right; but `cong` is also how every square, rhombus, parallelogram, isosceles
#: triangle and reflection is expressed. It flagged **37 of 87** primitives, 18 of them with no
#: circle in them at all, so `GENERATION.band_profiles[...].circle_weight` was in practice a 2x
#: bias toward equal-length symmetry generators. Measured consequence at seed 42: the top
#: primitives were `nsquare`, `square`, `psquare`, `parallelogram`, `risos`, 71 of 98 answers
#: were 45 degrees, and **not one figure contained a circle**.
#:
#: Matching is on the predicate head token, not a substring: `on_circle` is a *construction*
#: name whose only predicate is `cong`, and a substring test would flag it for a circle it
#: never declares.
_CIRCLE_PREDICATES: frozenset[str] = frozenset({"circle", "cyclic"})

#: Primitives that put a **stated angle value** into the figure — the givens an angle-chase
#: puzzle is actually chased from. Named rather than derived: they are exactly the angle members
#: of `_NUMERIC_PARAM_CONSTRUCTIONS`, and a primitive whose numeric argument is a length or a
#: ratio states nothing about an angle.
#:
#: MEASURED Phase 3 M4, and it is why the per-band angle palette had almost no effect: with both
#: of these at pick weight 1.0 among 62 usable extensions, only **2 of 22** surviving puzzles
#: stated an angle value at all. The rest answer 45 degrees because the figure contains a square,
#: not because anyone was told an angle.
_ANGLE_VALUE_CONSTRUCTIONS: frozenset[str] = frozenset({"s_angle", "aconst"})

#: Primitives that put a **closed polygonal region** into the figure — the regions an area puzzle
#: can ask about (docs/10 §10.7). Named explicitly rather than derived from predicate heads,
#: because there is no predicate meaning "this is a quadrilateral": a trapezoid declares `para`
#: and a square declares `cong` and `perp`, exactly like a dozen primitives that bound no region
#: at all. Deriving this flag is the mistake `_CIRCLE_PREDICATES` records below — `cong` looked
#: like a circle and flagged 37 of 87 primitives.
#:
#: Triangles are deliberately included even though three points always bound a region: what earns
#: their place is that these particular triangles have *known* shape, so their area is exact.
#: `ieq_triangle` is the single most valuable entry — an equilateral triangle of side s has area
#: (sqrt3/4)s^2, which is the cheapest irrational answer the pipeline can reach.
#:
#: MEASURED 2026-08-05, seed 42 (docs/10 §10.2): across 300 grown expert constructions these
#: appear 10-20 times each against `circle` at 283, so at pick weight 1.0 a 6-step figure almost
#: never contains one. Across the 635 seeded configurations the polygon families are worse —
#: `r_trapezoid` and `eqdia_quadrangle` appear **zero** times, `pentagon` once, `rectangle` once.
#: Neither source supplies regions on its own; that is what `BandProfile.region_weight` is for.
_REGION_CONSTRUCTIONS: frozenset[str] = frozenset(
    {
        # triangles of known shape -> exact area, and the sqrt3 family
        "ieq_triangle",
        "eq_triangle",
        "iso_triangle",
        "iso_triangle0",
        "iso_triangle_vertex",
        "r_triangle",
        "risos",
        "triangle12",
        # quadrilaterals
        "trapezoid",
        "iso_trapezoid",
        "iso_trapezoid2",
        "r_trapezoid",
        "quadrangle",
        "eq_quadrangle",
        "eqdia_quadrangle",
        "rectangle",
        "parallelogram",
        "square",
        "isquare",
        # higher polygons
        "pentagon",
    }
)

#: Primitives that put a **stated length value** into the figure. Area is the first dimensional
#: quantity (docs/07 T7), so it needs a pinned scale where angle forbids one; these are the
#: length members of `_NUMERIC_PARAM_CONSTRUCTIONS`, on the same reasoning that separates
#: `_ANGLE_VALUE_CONSTRUCTIONS` from the ratio ones.
#:
#: `l2const` states a *squared* length. It is included because stating one is sound and gives an
#: irrational side directly — but note nothing DERIVES a squared constant (docs/07 T21), so it is
#: only ever a given, never an answer.
_LENGTH_VALUE_CONSTRUCTIONS: frozenset[str] = frozenset({"lconst", "l2const"})


@dataclass(frozen=True, slots=True, order=True)
class ConstructionDef:
    """One construction primitive, described without reference to any engine type."""

    name: str
    input_points: tuple[str, ...]
    """Placeholder names for points that must already exist."""
    output_points: tuple[str, ...]
    """Placeholder names for points this primitive introduces."""
    numeric_params: tuple[str, ...]
    """Placeholder names for numeric arguments, e.g. the angle in `s_angle a b x y`."""
    arg_order: tuple[str, ...]
    """Full argument order, needed to render the clause correctly."""
    is_seed: bool
    """True when the primitive needs no existing points, so it can start a figure."""
    introduces_circle: bool
    """True when the primitive declares a circle the renderer will draw."""
    states_angle_value: bool
    """True when the primitive puts a stated angle value into the figure."""
    bounds_region: bool
    """True when the primitive puts a closed polygonal region into the figure (docs/10 §10.7)."""
    states_length_value: bool
    """True when the primitive puts a stated length value into the figure — the scale pinning a
    dimensional quantity needs (docs/07 T7, docs/10 §10.6)."""

    @property
    def arity(self) -> int:
        return len(self.input_points)


@lru_cache(maxsize=1)
def catalog() -> dict[str, ConstructionDef]:
    """The available primitives, keyed by name. Cached: the underlying data is static."""
    return _build_catalog()


def _build_catalog() -> dict[str, ConstructionDef]:
    from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS_BY_NAME

    out: dict[str, ConstructionDef] = {}
    for raw_name, definition in ALL_JGEX_CONSTRUCTIONS_BY_NAME.items():
        name = str(getattr(raw_name, "value", raw_name))
        inputs = tuple(str(a) for a in definition.input_points)
        outputs = tuple(str(a) for a in definition.output_points)
        args = tuple(str(a) for a in definition.args)
        leftover = tuple(a for a in args if a not in inputs and a not in outputs)

        if leftover and name not in _NUMERIC_PARAM_CONSTRUCTIONS:
            # Unclassified arguments: we cannot tell a point from a value, and guessing
            # would emit malformed clauses. Skip rather than risk it.
            continue
        if not outputs:
            continue

        out[name] = ConstructionDef(
            name=name,
            input_points=inputs,
            output_points=outputs,
            numeric_params=leftover,
            arg_order=args,
            is_seed=not inputs,
            introduces_circle=bool(_predicates_of(definition) & _CIRCLE_PREDICATES),
            states_angle_value=name in _ANGLE_VALUE_CONSTRUCTIONS,
            bounds_region=name in _REGION_CONSTRUCTIONS,
            states_length_value=name in _LENGTH_VALUE_CONSTRUCTIONS,
        )
    return out


def _predicates_of(definition: object) -> frozenset[str]:
    """The predicate heads a construction declares.

    A JGEX clause reads `<outputs> = <pred args>, <pred args>`, so the heads are the first
    token of each comma-separated term on the right of the `=`.
    """
    heads: set[str] = set()
    for clause in getattr(definition, "clauses", ()):
        _, _, rhs = str(clause).partition("=")
        for term in rhs.split(","):
            tokens = term.split()
            if tokens:
                heads.add(tokens[0])
    return frozenset(heads)


def seeds() -> tuple[ConstructionDef, ...]:
    """Primitives that can start a figure, sorted for determinism."""
    return tuple(sorted(d for d in catalog().values() if d.is_seed))


def extensions() -> tuple[ConstructionDef, ...]:
    """Primitives that extend an existing figure, sorted for determinism."""
    return tuple(sorted(d for d in catalog().values() if not d.is_seed))
