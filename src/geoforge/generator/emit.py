"""Stage 9: pipeline objects → a schema-v2 `Puzzle` (docs/04 Stage 9, docs/02).

This is where a derivation stops being generator state and becomes the artifact. Everything
the player sees is decided here, from facts that are already proved — nothing in this module
derives anything.

Two seams worth knowing about.

**Display coordinates are a parameter.** `assemble` is handed the coordinates to draw at. Today
the batch runner hands it the reference figure's, framed into the viewbox; `bank/layout.py`
later picks a better instantiation and calls the same function. That keeps "what a puzzle is"
in one place while "which drawing of it" stays a separate decision.

**Givens are rendered, not re-worded.** `phrases.describe` already turns a fact into the
sentence and the highlights the solution steps use, with vertex angles disambiguated by the
reference diagram. Givens go through it too, so a hypothesis and a step that cites it read the
same way. A fact it refuses has no display string and its puzzle was already discarded at the
Stage 7 gate (`translate.unspeakable_givens`).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction

from geoforge import schema
from geoforge.config import LAYOUT
from geoforge.generator import quantities
from geoforge.generator.construction import Construction
from geoforge.generator.traceback import Derivation
from geoforge.generator.translation import Translation
from geoforge.generator.translation.phrases import angle_of, describe
from geoforge.generator.translation.vertex_angles import VertexAngle
from geoforge.schema import (
    AngleArc,
    DisplayCircle,
    DisplayPoint,
    ExactValue,
    Figure,
    Given,
    Goal,
    GoalInput,
    Marks,
    Quantity,
    SchemaError,
)
from geoforge.solvers.types import Fact, FactKind

Coords = Mapping[str, tuple[float, float]]


# --------------------------------------------------------------------------------------
# Framing
# --------------------------------------------------------------------------------------


def frame(coords: Coords) -> dict[str, tuple[float, float]]:
    """Fit a figure into the viewbox by a **similarity transform only**.

    Uniform scale, translation, and a y-flip from maths convention (y up) to SVG's (y down).
    Choosing the pose is `bank.layout`'s job; this only fits the result to the box.

    The y-flip is a reflection, and that is safe: everything the puzzle publishes is
    *undirected* — vertex angles, distances, congruences — all of which a mirror preserves.
    What a reflection does negate is a directed line-to-line angle, and those appear only in
    `derives` and `goal.fact`, which are trace handles over the **reference** figure. Cross-
    engine validation reads `reference_figure` and never this one (docs/04 §V), so nothing
    downstream sees the flip.

    What is *not* optional is that the transform be a similarity. Every premise is a metric
    statement about this point set, so anything else breaks one (docs/06 §6.3, docs/07 T5).
    """
    if not coords:
        raise SchemaError("cannot frame an empty figure")
    xs = [p[0] for p in coords.values()]
    ys = [p[1] for p in coords.values()]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    margin = LAYOUT.margin_fraction
    usable_w = LAYOUT.viewbox_width * (1 - 2 * margin)
    usable_h = LAYOUT.viewbox_height * (1 - 2 * margin)
    scale = min(
        usable_w / width if width > 0 else math.inf,
        usable_h / height if height > 0 else math.inf,
    )
    if not math.isfinite(scale):
        # A single point, or all points coincident: degenerate figures are Stage 3's business,
        # so reaching here means a gate is missing rather than that we should invent a scale.
        raise SchemaError("figure has zero extent in both directions")

    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    ox, oy = LAYOUT.viewbox_width / 2, LAYOUT.viewbox_height / 2
    return {name: (ox + (x - cx) * scale, oy - (y - cy) * scale) for name, (x, y) in coords.items()}


# --------------------------------------------------------------------------------------
# Figure elements
# --------------------------------------------------------------------------------------


def _seg_id(a: str, b: str) -> tuple[str, str]:
    """A segment id, ordered so `A:B` and `B:A` are the same drawn line."""
    first, second = sorted((schema.display_label(a), schema.display_label(b)))
    return first, second


def segments_of(
    pruned: Construction,
    givens: Sequence[Fact],
    highlights: Sequence[str],
    goal_angle: VertexAngle,
) -> tuple[tuple[str, str], ...]:
    """Which segments the figure draws.

    Three sources, each answering a different failure:

    1. **Every `seg:` a given or a solution step highlights**, plus the goal angle's two rays.
       If the text names it, the figure must show it — otherwise a step highlights nothing.
    2. **Maximal chords through each collinear set.** Three collinear points drawn as two
       abutting segments is a rendering artefact, not a figure.
    3. **Polygon skeletons** the construction declares. A `triangle a b c` whose text happens
       to mention only AB would otherwise be drawn as a lone segment with two loose points.

    Source 3 reads a hand-reviewed table rather than parsing clauses, for the same reason the
    translation whitelist is hand-reviewed: a primitive nobody has read is a primitive nobody
    can vouch for the drawing of.
    """
    out: set[tuple[str, str]] = set()
    for highlight in highlights:
        parts = highlight.split(":")
        if parts[0] == "seg":
            out.add((min(parts[1], parts[2]), max(parts[1], parts[2])))
    out.add(_seg_id(goal_angle.p, goal_angle.vertex))
    out.add(_seg_id(goal_angle.q, goal_angle.vertex))

    for fact in givens:
        if fact.kind in (FactKind.COLLINEAR, FactKind.MIDPOINT):
            points = sorted(set(fact.args))
            for i, first in enumerate(points):
                for second in points[i + 1 :]:
                    out.add(_seg_id(first, second))

    out.update(_skeleton_segments(pruned))
    return tuple(sorted(out))


#: Construction primitives whose figure is a closed polygon, and how many of their leading
#: arguments form it. Hand-reviewed: an unlisted primitive draws nothing on its own account.
POLYGON_ARITY: Mapping[str, int] = {
    "triangle": 3,
    "triangle12": 3,
    "r_triangle": 3,
    "risos": 3,
    "ieq_triangle": 3,
    "iso_triangle": 3,
    "iso_triangle0": 3,
    "eq_triangle": 3,
    "segment": 2,
    "square": 4,
    "isquare": 4,
    "rectangle": 4,
    "quadrangle": 4,
    "eq_quadrangle": 4,
    "eqdia_quadrangle": 4,
    "trapezoid": 4,
    "iso_trapezoid": 4,
    "parallelogram": 4,
    "pentagon": 5,
}


def _skeleton_segments(pruned: Construction) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    drawn = set(pruned.points)
    for step in pruned.steps:
        arity = POLYGON_ARITY.get(step.construction)
        if arity is None:
            continue
        corners = [a for a in step.args if a in drawn][:arity]
        if len(corners) < arity:
            continue
        for i, corner in enumerate(corners):
            out.add(_seg_id(corner, corners[(i + 1) % arity]))
    return out


def circles_of(declared: Sequence[Fact], coords: Coords) -> tuple[DisplayCircle, ...]:
    """Circles the construction declared, in display coordinates.

    Only `circle` (a named centre) and `cyclic` (four concyclic points) count. Notably *not*
    `cong`: `cong p o q o` says P and Q are equidistant from O, which is true of an isosceles
    triangle and of a reflection, and drawing a circle for each would put one in nearly every
    figure. Nor `ConstructionDef.introduces_circle`, which keys on the `cong` keyword because
    it exists to bias the *sampler*, not to decide what gets drawn.
    """
    out: list[DisplayCircle] = []
    for fact in sorted(declared, key=lambda f: f.fact_id):
        if not set(fact.args) <= set(coords):
            continue
        if fact.kind is FactKind.CIRCUMCENTER:
            centre, *through = fact.args
            cx, cy = coords[centre]
            radius = math.dist((cx, cy), coords[through[0]])
            out.append(
                DisplayCircle(
                    id=f"circle:{schema.display_label(centre)}:{schema.display_label(through[0])}",
                    cx=cx,
                    cy=cy,
                    r=radius,
                    center_point=schema.display_label(centre),
                    through=tuple(schema.display_label(p) for p in through),
                )
            )
        elif fact.kind is FactKind.CYCLIC and len(fact.args) >= 3:
            found = schema.circle_through(*(coords[p] for p in fact.args[:3]))
            if found is None:
                continue
            cx, cy, radius = found
            labels = tuple(schema.display_label(p) for p in fact.args)
            out.append(
                DisplayCircle(
                    id=f"circle:{labels[0]}:{labels[1]}",
                    cx=cx,
                    cy=cy,
                    r=radius,
                    center_point=None,
                    through=labels,
                )
            )
    return tuple(out)


# --------------------------------------------------------------------------------------
# Marks
# --------------------------------------------------------------------------------------


Pair = tuple[tuple[str, str], tuple[str, str]]


def _groups(pairs: Sequence[Pair]) -> tuple[tuple[str, ...], ...]:
    """Union-find over segment ids, so three equal segments get one tick style, not two."""
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(x: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for left, right in pairs:
        parent[find(left)] = find(right)

    clusters: dict[tuple[str, str], list[str]] = {}
    for member in sorted(parent):
        clusters.setdefault(find(member), []).append(f"{member[0]}:{member[1]}")
    return tuple(sorted(tuple(v) for v in clusters.values() if len(v) > 1))


def marks_of(givens: Sequence[Fact], goal_angle: VertexAngle, coords: Coords) -> Marks:
    """What the figure asserts visually, derived from the *stated* facts and nothing else.

    Each mark is a claim, so its only legitimate source is a given or the goal — the invariant
    `schema.Puzzle` re-checks structurally. A 90° `aconst` draws a square rather than an arc
    labelled `90°`, which is how anyone would draw it.
    """
    congruent: list[Pair] = []
    parallel: list[Pair] = []
    right: set[str] = set()
    arcs: list[AngleArc] = []

    for fact in sorted(givens, key=lambda f: f.fact_id):
        if fact.kind is FactKind.CONGRUENT and len(fact.args) == 4:
            a, b, c, d = fact.args
            congruent.append((_seg_id(a, b), _seg_id(c, d)))
        elif fact.kind is FactKind.PARALLEL and len(set(fact.args)) == 4:
            a, b, c, d = fact.args
            parallel.append((_seg_id(a, b), _seg_id(c, d)))
        elif fact.kind is FactKind.PERPENDICULAR or schema.is_right_angle(fact):
            angle = angle_of(fact, coords)
            if angle is not None:
                right.add(angle.highlight)
        elif fact.kind is FactKind.CONSTANT_ANGLE:
            angle = angle_of(fact, coords)
            if angle is not None and angle.degrees is not None:
                arcs.append(
                    AngleArc(
                        at=(
                            schema.display_label(angle.p),
                            schema.display_label(angle.vertex),
                            schema.display_label(angle.q),
                        ),
                        label=_degrees_text(angle.degrees),
                        kind="given",
                    )
                )

    arcs.append(
        AngleArc(
            at=(
                schema.display_label(goal_angle.p),
                schema.display_label(goal_angle.vertex),
                schema.display_label(goal_angle.q),
            ),
            label="?",
            kind="goal",
        )
    )
    return Marks(
        equal_segments=_groups(congruent),
        parallel=_groups(parallel),
        right_angles=tuple(sorted(right)),
        angle_arcs=tuple(arcs),
    )


def _degrees_text(degrees: Fraction) -> str:
    whole = degrees.numerator if degrees.denominator == 1 else degrees
    return f"{whole}°"


# --------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------


def assemble(
    puzzle_id: str,
    quantity_type: str,
    pruned: Construction,
    derivation: Derivation,
    translation: Translation,
    goal_angle: VertexAngle,
    reference_coords: Coords,
    difficulty: schema.Difficulty,
    *,
    display_coords: Coords | None = None,
    label_offsets: Mapping[str, tuple[float, float]] | None = None,
    declared: Sequence[Fact] = (),
    provenance: Mapping[str, object] | None = None,
) -> schema.Puzzle:
    """Build the shippable puzzle.

    `reference_coords` are the engine's, and every *sentence* is rendered against them: they
    are the diagram Stage 8 certified the wording over. `display_coords` are what gets drawn,
    and default to the reference figure framed into the viewbox.

    Keeping those two separate is what lets `bank.layout` choose a better drawing without any
    risk of changing what the puzzle says: it supplies coordinates and label offsets, and the
    text is rendered from the reference figure either way.
    """
    kind = quantities.get(quantity_type)
    drawn = frame(display_coords if display_coords is not None else reference_coords)

    givens = tuple(sorted(derivation.premises, key=lambda f: f.fact_id))
    rendered = [_given(fact, reference_coords) for fact in givens]

    steps = tuple(
        schema.Step(
            step=s.step, rule=s.rule, text=s.text, derives=str(s.derives), highlights=s.highlights
        )
        for s in translation.steps
    )
    highlights = [h for g in rendered for h in g.highlights] + [
        h for s in steps for h in s.highlights
    ]

    offsets = label_offsets or {}
    points = tuple(
        DisplayPoint(
            id=schema.display_label(name),
            x=drawn[name][0],
            y=drawn[name][1],
            label_dx=offsets.get(name, (0.0, 0.0))[0],
            label_dy=offsets.get(name, (0.0, 0.0))[1],
        )
        for name in sorted(drawn)
    )
    schema.display_labels(sorted(drawn))

    return schema.Puzzle(
        id=puzzle_id,
        quantity_type=quantity_type,
        difficulty=difficulty,
        figure=Figure(
            points=points,
            segments=segments_of(pruned, givens, highlights, goal_angle),
            circles=circles_of(declared, drawn),
            marks=marks_of(givens, goal_angle, reference_coords),
        ),
        given=tuple(rendered),
        goal=_goal(derivation.goal, goal_angle, kind),
        solution=steps,
        configuration=tuple(f.fact_id for f in derivation.configuration),
        reference_figure=schema.ReferenceFigure(
            points=tuple(
                schema.ReferencePoint(id=name, x=xy[0], y=xy[1])
                for name, xy in sorted(reference_coords.items())
                if name in set(pruned.points)
            )
        ),
        provenance=dict(provenance) if provenance is not None else None,
    )


def _given(fact: Fact, coords: Coords) -> Given:
    phrase = describe(fact, coords)
    if phrase is None:
        raise SchemaError(
            f"given {fact.fact_id} has no player-facing phrasing; the Stage 7 gate "
            "(translate.unspeakable_givens) should have discarded this puzzle"
        )
    angle = angle_of(fact, coords) if fact.kind is FactKind.CONSTANT_ANGLE else None
    if angle is not None and angle.degrees is not None:
        return Given(
            form="quantity",
            fact=fact.fact_id,
            display=phrase.text,
            highlights=phrase.highlights,
            quantity=Quantity(
                kind="angle",
                at=(
                    schema.display_label(angle.p),
                    schema.display_label(angle.vertex),
                    schema.display_label(angle.q),
                ),
            ),
            value=ExactValue(exact=_exact(angle.degrees), approx=float(angle.degrees)),
        )
    return Given(
        form="relation",
        fact=fact.fact_id,
        display=phrase.text,
        highlights=phrase.highlights,
    )


def _goal(fact: Fact, angle: VertexAngle, kind: quantities.QuantityType) -> Goal:
    if angle.degrees is None:  # pragma: no cover - the Stage 7 gate rejects these
        raise SchemaError(f"goal {fact.fact_id} has no resolved vertex-angle value")
    policy = kind.answer_policy
    exact = _exact(angle.degrees)
    return Goal(
        fact=fact.fact_id,
        question=angle.text,
        quantity=Quantity(
            kind=kind.name,
            at=(
                schema.display_label(angle.p),
                schema.display_label(angle.vertex),
                schema.display_label(angle.q),
            ),
        ),
        answer=ExactValue(exact=exact, approx=float(angle.degrees)),
        display=f"{exact}°",
        input=GoalInput(
            mode=policy.input_mode.value,
            exactness=policy.exactness.value,
            unit=policy.unit,
            tolerance=None,
        ),
    )


def _exact(degrees: Fraction) -> str:
    return str(degrees.numerator) if degrees.denominator == 1 else str(degrees)
