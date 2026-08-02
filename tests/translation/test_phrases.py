"""Fact → phrase rendering, and the speakability rules.

Golden text: these assertions are what a player reads, so they are written out in full rather
than pattern-matched. A change here is a change to shipped product copy.
"""

from __future__ import annotations

import re
from fractions import Fraction

import pytest

from geoforge.generator.translation.phrases import Phrase, describe, is_speakable
from geoforge.solvers.types import Fact, FactKind

COORDS = {
    "a": (1.0, 0.0),
    "b": (0.0, 0.0),
    "c": (0.0, 1.0),
    "d": (2.0, 2.0),
    "o": (0.5, 0.5),
}

#: docs/02, normative. Nothing else may appear in `highlights`.
HIGHLIGHT_GRAMMAR = re.compile(
    r"^(point:[A-Z]\w*"
    r"|seg:[A-Z]\w*:[A-Z]\w*"
    r"|angle:[A-Z]\w*:[A-Z]\w*:[A-Z]\w*"
    r"|circle:[A-Z]\w*:[A-Z]\w*"
    r"|arc:[A-Z]\w*:[A-Z]\w*:[A-Z]\w*"
    r"|region:\w+)$"
)


def phrase_of(kind: FactKind, args: tuple[str, ...], value: Fraction | None = None) -> Phrase:
    result = describe(Fact(kind=kind, args=args, value=value), COORDS)
    assert result is not None, f"{kind} should be speakable"
    return result


class TestGoldenText:
    def test_congruent_segments(self) -> None:
        assert phrase_of(FactKind.CONGRUENT, ("a", "b", "c", "d")).text == "AB = CD"

    def test_constant_angle_reads_as_a_vertex_angle(self) -> None:
        phrase = phrase_of(FactKind.CONSTANT_ANGLE, ("b", "a", "b", "c"), Fraction(1, 2))
        assert phrase.text == "∠ABC = 90°"

    def test_equal_angles(self) -> None:
        phrase = phrase_of(FactKind.EQUAL_ANGLES, ("b", "a", "b", "c", "a", "b", "a", "c"))
        assert phrase.text == "∠ABC = ∠BAC"

    def test_collinear(self) -> None:
        assert phrase_of(FactKind.COLLINEAR, ("a", "b", "c")).text == "A, B and C are collinear"

    def test_midpoint(self) -> None:
        assert phrase_of(FactKind.MIDPOINT, ("o", "a", "b")).text == "O is the midpoint of AB"

    def test_perpendicular_prefers_the_vertex_reading(self) -> None:
        """ "∠ABC = 90°" beats "AB ⊥ CB" when the lines meet at a named point."""
        assert phrase_of(FactKind.PERPENDICULAR, ("b", "a", "b", "c")).text == "∠ABC = 90°"

    def test_perpendicular_falls_back_to_segments(self) -> None:
        assert phrase_of(FactKind.PERPENDICULAR, ("a", "b", "c", "d")).text == "AB ⊥ CD"

    def test_cyclic(self) -> None:
        phrase = phrase_of(FactKind.CYCLIC, ("a", "b", "c", "d"))
        assert phrase.text == "A, B, C and D lie on a circle"

    def test_circumcenter(self) -> None:
        phrase = phrase_of(FactKind.CIRCUMCENTER, ("o", "a", "b", "c"))
        assert phrase.text == "O is the centre of the circle through A, B and C"

    def test_integer_ratio_reads_as_a_multiple(self) -> None:
        phrase = phrase_of(FactKind.CONSTANT_RATIO, ("a", "b", "a", "o"), Fraction(2))
        assert phrase.text == "AB = 2 · AO"

    def test_fractional_ratio_reads_as_a_ratio(self) -> None:
        phrase = phrase_of(FactKind.CONSTANT_RATIO, ("a", "b", "a", "o"), Fraction(2, 3))
        assert phrase.text == "AB : AO = 2 : 3"

    def test_similar_triangles(self) -> None:
        phrase = phrase_of(FactKind.SIMTRI_REFLECT, ("a", "b", "c", "d", "b", "c"))
        assert phrase.text == "triangles ABC and DBC are similar"

    def test_congruent_triangles(self) -> None:
        phrase = phrase_of(FactKind.CONTRI_CLOCK, ("a", "b", "c", "d", "b", "c"))
        assert phrase.text == "triangles ABC and DBC are congruent"


class TestSpeakability:
    def test_configuration_facts_are_never_spoken(self) -> None:
        """They describe the figure, which the player can see. They stay premises of the puzzle
        for correctness (docs/04 Stage 6) — this is about prose, not truth."""
        for kind, args in (
            (FactKind.N_COLLINEAR, ("a", "b", "c")),
            (FactKind.DIFFERENT, ("a", "b")),
            (FactKind.SAME_CLOCK, ("a", "b", "c", "a", "b", "c")),
        ):
            fact = Fact(kind=kind, args=args)
            assert not is_speakable(fact)
            assert describe(fact, COORDS) is None

    def test_collinear_segments_are_not_called_parallel(self) -> None:
        """The engine reports `para a o b o` for two pieces of one straight line. Saying it out
        loud, next to a figure showing A, O and B in a row, reads as an error."""
        assert not is_speakable(Fact(kind=FactKind.PARALLEL, args=("a", "o", "b", "o")))
        assert is_speakable(Fact(kind=FactKind.PARALLEL, args=("a", "b", "c", "d")))

    def test_degenerate_equalities_are_not_spoken(self) -> None:
        """ "AO : CO = CO : AO" is a ratio nobody writes; it says AO = CO."""
        reciprocal = Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "o", "c", "o", "c", "o", "a", "o"))
        unit = Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "b", "a", "b", "c", "o", "a", "o"))
        assert not is_speakable(reciprocal)
        assert not is_speakable(unit)

    def test_unconvertible_angle_has_no_phrase(self) -> None:
        """An angle between two lines that do not meet at a named point."""
        fact = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "c", "d"), value=Fraction(1, 4))
        assert describe(fact, COORDS) is None


class TestHighlights:
    @pytest.mark.parametrize(
        ("kind", "args", "value"),
        [
            (FactKind.CONGRUENT, ("a", "b", "c", "d"), None),
            (FactKind.CONSTANT_ANGLE, ("b", "a", "b", "c"), Fraction(1, 2)),
            (FactKind.EQUAL_ANGLES, ("b", "a", "b", "c", "a", "b", "a", "c"), None),
            (FactKind.COLLINEAR, ("a", "b", "c"), None),
            (FactKind.MIDPOINT, ("o", "a", "b"), None),
            (FactKind.CYCLIC, ("a", "b", "c", "d"), None),
            (FactKind.CIRCUMCENTER, ("o", "a", "b", "c"), None),
            (FactKind.EQUAL_RATIOS, ("a", "b", "c", "d", "a", "c", "b", "d"), None),
            (FactKind.SIMTRI_CLOCK, ("a", "b", "c", "d", "b", "c"), None),
        ],
    )
    def test_every_highlight_matches_the_normative_grammar(
        self, kind: FactKind, args: tuple[str, ...], value: Fraction | None
    ) -> None:
        for highlight in phrase_of(kind, args, value).highlights:
            assert HIGHLIGHT_GRAMMAR.match(highlight), f"{highlight!r} is not a legal highlight id"
