"""Directed line-to-line angles → vertex angles (docs/03 §3.5 item 2c).

Pure functions over coordinates, so the supplement ambiguity — the thing that makes this the
translator's central job — can be tested at both of its answers.
"""

from __future__ import annotations

from fractions import Fraction

from geoforge.generator.translation.vertex_angles import (
    label,
    resolve_value,
    shared_point,
    to_vertex_angle,
)

#: B at the origin with A due east and C due north: ∠ABC = 90°.
SQUARE_CORNER = {"a": (1.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 1.0)}

#: ∠ABC = 135°, whose directed line-to-line angle is 45° — the ambiguity, concretely.
OBTUSE = {"a": (1.0, 0.0), "b": (0.0, 0.0), "c": (-1.0, 1.0)}


class TestConversion:
    def test_lines_meeting_at_a_point_give_a_vertex_angle(self) -> None:
        angle = to_vertex_angle(("b", "a", "b", "c"), SQUARE_CORNER)
        assert angle is not None
        assert (angle.p, angle.vertex, angle.q) == ("a", "b", "c")

    def test_point_order_within_a_line_does_not_matter(self) -> None:
        """A line has no direction, so `ba` and `ab` name the same line."""
        first = to_vertex_angle(("b", "a", "b", "c"), SQUARE_CORNER)
        second = to_vertex_angle(("a", "b", "b", "c"), SQUARE_CORNER)
        assert first == second

    def test_non_incident_lines_have_no_vertex_angle(self) -> None:
        """A real angle, but one with no ∠ABC spelling: the step naming it is untranslatable
        rather than awkwardly worded."""
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.0, 1.0), "d": (1.0, 1.0)}
        assert to_vertex_angle(("a", "b", "c", "d"), coords) is None

    def test_two_shared_points_are_the_same_line(self) -> None:
        assert shared_point(("a", "b"), ("a", "b")) is None

    def test_label_uppercases_for_the_player(self) -> None:
        assert label("a") == "A"
        assert label("a1") == "A1"


class TestSupplementResolution:
    def test_acute_reading_is_chosen_when_the_figure_is_acute(self) -> None:
        angle = to_vertex_angle(("b", "a", "b", "c"), OBTUSE)
        assert angle is not None
        # 45° directed; the figure shows 135°, so the vertex angle is the supplement.
        resolved = resolve_value(angle, Fraction(1, 4), OBTUSE)
        assert resolved is not None
        assert resolved.degrees == 135

    def test_right_angle_is_its_own_supplement(self) -> None:
        angle = to_vertex_angle(("b", "a", "b", "c"), SQUARE_CORNER)
        assert angle is not None
        resolved = resolve_value(angle, Fraction(1, 2), SQUARE_CORNER)
        assert resolved is not None
        assert resolved.degrees == 90

    def test_value_matching_neither_reading_is_refused(self) -> None:
        """A directed value the figure contradicts is never a rounding problem. Refusing beats
        emitting an angle that disagrees with the diagram the player is looking at."""
        angle = to_vertex_angle(("b", "a", "b", "c"), SQUARE_CORNER)
        assert angle is not None
        assert resolve_value(angle, Fraction(1, 6), SQUARE_CORNER) is None


class TestRendering:
    def test_text_and_highlight_follow_the_normative_grammar(self) -> None:
        """docs/02: `angle:<P>:<VERTEX>:<P>` and nothing else."""
        angle = to_vertex_angle(("b", "a", "b", "c"), SQUARE_CORNER)
        assert angle is not None
        assert angle.text == "∠ABC"
        assert angle.highlight == "angle:A:B:C"
