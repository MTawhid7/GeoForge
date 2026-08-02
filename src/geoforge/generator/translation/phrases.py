"""Rendering a single `Fact` as a human phrase plus its figure highlights.

Two jobs beyond the obvious formatting:

**Vertex-angle conversion.** Every angle fact arrives as a directed line-to-line angle and has to be
converted before it can be spoken (`vertex_angles`). A fact that cannot be converted has no phrase,
which makes the step naming it untranslatable — attrition, never awkward prose.

**Speakability.** Some facts are true, load-bearing for the engine, and meaningless to a player.
Configuration facts (`ncoll`, `diff`, `sameclock`) describe the figure, which the player can see.
Worse, the engine calls two segments of one straight line "parallel": narrating `AO ∥ BO` when A, O
and B are collinear reads as an error. Those are dropped from the text rather than rendered.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from geoforge.generator.translation import idioms
from geoforge.generator.translation.vertex_angles import (
    Coords,
    VertexAngle,
    label,
    lines_of,
    resolve_value,
    to_vertex_angle,
)
from geoforge.solvers.types import Fact, FactKind


@dataclass(frozen=True, slots=True)
class Phrase:
    text: str
    highlights: tuple[str, ...] = ()


#: Renders one fact kind. None means "this instance cannot be spoken".
Renderer = Callable[[Fact, Coords], Phrase | None]


def _seg(a: str, b: str) -> str:
    return f"{label(a)}{label(b)}"


def _seg_highlight(a: str, b: str) -> str:
    return f"seg:{label(a)}:{label(b)}"


def _points(names: tuple[str, ...]) -> str:
    """'A, B and C' — an Oxford-comma-free list, as a sentence fragment."""
    shown = [label(n) for n in names]
    if len(shown) == 1:
        return shown[0]
    return f"{', '.join(shown[:-1])} and {shown[-1]}"


def is_speakable(fact: Fact) -> bool:
    """Whether a fact is worth putting in front of a player.

    Configuration facts are excluded: they say what the figure already shows, and stating
    "A, B and C are not collinear" as a step of the solution is noise. They remain premises of the
    puzzle for correctness (docs/04 Stage 6) — this is about prose, not about truth.
    """
    if fact.is_configuration:
        return False
    if fact.kind is FactKind.PARALLEL:
        # `para a o b o` where A, O, B are collinear: an artifact of the engine treating a line as
        # parallel to itself. Saying it out loud reads as a mistake.
        return len(set(fact.args)) == 4
    if fact.kind in (FactKind.EQUAL_ANGLES, FactKind.EQUAL_RATIOS):
        # "AJ : AJ = HJ : IJ" is a ratio nobody writes; it is HJ = IJ wearing a costume. The
        # idiom collapser removes the step that produced it, and this keeps the phrase itself
        # from leaking into a premise list elsewhere (idioms.is_degenerate_pair).
        return not idioms.is_degenerate_pair(fact)
    return True


def describe(fact: Fact, coords: Coords) -> Phrase | None:
    """Render one fact. None means it cannot be spoken — see `is_speakable` and the angle note."""
    if not is_speakable(fact):
        return None
    handler = _HANDLERS.get(fact.kind)
    return handler(fact, coords) if handler else None


def angle_of(fact: Fact, coords: Coords) -> VertexAngle | None:
    """The vertex angle a valued angle fact denotes, with its exact value attached."""
    angle = to_vertex_angle(fact.args, coords)
    if angle is None or fact.value is None:
        return angle
    return resolve_value(angle, fact.value, coords)


# --------------------------------------------------------------------------------------
# Per-kind renderers
# --------------------------------------------------------------------------------------


def _constant_angle(fact: Fact, coords: Coords) -> Phrase | None:
    angle = angle_of(fact, coords)
    if angle is None or angle.degrees is None:
        return None
    return Phrase(f"{angle.text} = {angle.degrees}°", (angle.highlight,))


def _equal_angles(fact: Fact, coords: Coords) -> Phrase | None:
    if len(fact.args) != 8:
        return None
    first = to_vertex_angle(fact.args[:4], coords)
    second = to_vertex_angle(fact.args[4:], coords)
    if first is None or second is None:
        return None
    return Phrase(f"{first.text} = {second.text}", (first.highlight, second.highlight))


def _congruent(fact: Fact, _: Coords) -> Phrase | None:
    a, b, c, d = fact.args
    return Phrase(f"{_seg(a, b)} = {_seg(c, d)}", (_seg_highlight(a, b), _seg_highlight(c, d)))


def _collinear(fact: Fact, _: Coords) -> Phrase:
    return Phrase(
        f"{_points(fact.args)} are collinear",
        tuple(f"point:{label(p)}" for p in fact.args),
    )


def _midpoint(fact: Fact, _: Coords) -> Phrase:
    m, a, b = fact.args
    return Phrase(
        f"{label(m)} is the midpoint of {_seg(a, b)}",
        (f"point:{label(m)}", _seg_highlight(a, b)),
    )


def _perpendicular(fact: Fact, coords: Coords) -> Phrase | None:
    pair = lines_of(fact.args)
    if pair is None:
        return None
    # Prefer the vertex reading when the lines meet at a named point: "∠ABC = 90°" beats
    # "AB ⊥ CB" for a reader.
    angle = to_vertex_angle(fact.args, coords)
    if angle is not None:
        return Phrase(f"{angle.text} = 90°", (angle.highlight,))
    (a, b), (c, d) = pair
    return Phrase(f"{_seg(a, b)} ⊥ {_seg(c, d)}", (_seg_highlight(a, b), _seg_highlight(c, d)))


def _parallel(fact: Fact, _: Coords) -> Phrase | None:
    pair = lines_of(fact.args)
    if pair is None:
        return None
    (a, b), (c, d) = pair
    return Phrase(f"{_seg(a, b)} ∥ {_seg(c, d)}", (_seg_highlight(a, b), _seg_highlight(c, d)))


def _circumcenter(fact: Fact, _: Coords) -> Phrase:
    center, *through = fact.args
    return Phrase(
        f"{label(center)} is the centre of the circle through {_points(tuple(through))}",
        (f"circle:{label(center)}:{label(through[0])}",) if through else (),
    )


def _cyclic(fact: Fact, _: Coords) -> Phrase:
    return Phrase(
        f"{_points(fact.args)} lie on a circle",
        tuple(f"point:{label(p)}" for p in fact.args),
    )


def _constant_ratio(fact: Fact, _: Coords) -> Phrase | None:
    if len(fact.args) != 4 or fact.value is None:
        return None
    a, b, c, d = fact.args
    return Phrase(
        f"{_seg(a, b)} = {fact.value} · {_seg(c, d)}"
        if fact.value.denominator == 1
        else f"{_seg(a, b)} : {_seg(c, d)} = {fact.value.numerator} : {fact.value.denominator}",
        (_seg_highlight(a, b), _seg_highlight(c, d)),
    )


def _constant_length(fact: Fact, _: Coords) -> Phrase | None:
    if len(fact.args) != 2 or fact.value is None:
        return None
    a, b = fact.args
    return Phrase(f"{_seg(a, b)} = {fact.value}", (_seg_highlight(a, b),))


def _equal_ratios(fact: Fact, _: Coords) -> Phrase | None:
    if len(fact.args) != 8:
        return None
    a, b, c, d, e, f, g, h = fact.args
    return Phrase(
        f"{_seg(a, b)} : {_seg(c, d)} = {_seg(e, f)} : {_seg(g, h)}",
        (
            _seg_highlight(a, b),
            _seg_highlight(c, d),
            _seg_highlight(e, f),
            _seg_highlight(g, h),
        ),
    )


def _triangle_pair(word: str) -> Renderer:
    def render(fact: Fact, _: Coords) -> Phrase | None:
        if len(fact.args) != 6:
            return None
        left = "".join(label(p) for p in fact.args[:3])
        right = "".join(label(p) for p in fact.args[3:])
        return Phrase(
            f"triangles {left} and {right} are {word}",
            tuple(f"point:{label(p)}" for p in fact.args),
        )

    return render


_HANDLERS: dict[FactKind, Renderer] = {
    FactKind.CONSTANT_ANGLE: _constant_angle,
    FactKind.EQUAL_ANGLES: _equal_angles,
    FactKind.CONGRUENT: _congruent,
    FactKind.COLLINEAR: _collinear,
    FactKind.MIDPOINT: _midpoint,
    FactKind.PERPENDICULAR: _perpendicular,
    FactKind.PARALLEL: _parallel,
    FactKind.CIRCUMCENTER: _circumcenter,
    FactKind.CYCLIC: _cyclic,
    FactKind.CONSTANT_RATIO: _constant_ratio,
    FactKind.CONSTANT_LENGTH: _constant_length,
    FactKind.EQUAL_RATIOS: _equal_ratios,
    FactKind.SIMTRI_CLOCK: _triangle_pair("similar"),
    FactKind.SIMTRI_REFLECT: _triangle_pair("similar"),
    FactKind.CONTRI_CLOCK: _triangle_pair("congruent"),
    FactKind.CONTRI_REFLECT: _triangle_pair("congruent"),
}
