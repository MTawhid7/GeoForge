"""The quantity-type registry and the angle extractor (docs/04 §QTR).

No engine here: these are pure functions over coordinates, which is what makes the snapping
threshold testable at its boundary.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from geoforge.config import EXTRACTION
from geoforge.generator import quantities
from geoforge.generator.quantities import (
    ANGLE,
    Dimension,
    Exactness,
    enabled_types,
    propose_angles,
    registry,
    snap_to_integer_degrees,
)
from geoforge.solvers.types import FactKind

#: A right isosceles triangle: angles 90, 45, 45 at a, b, c.
RIGHT_ISOSCELES = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.0, 1.0)}

#: Nothing round about it.
GENERIC = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.317, 0.891)}


class TestRegistry:
    def test_angle_is_registered_with_all_six_qtr_fields(self) -> None:
        """docs/04 §QTR: enabling a type means registering these six things."""
        assert ANGLE.goal_extractor is not None
        assert ANGLE.dimension is Dimension.SCALE_FREE
        assert ANGLE.nice_values("easy")
        assert ANGLE.answer_policy.exactness is Exactness.INTEGER
        assert ANGLE.template_family == "angle"
        assert ANGLE.marks

    def test_angle_is_scale_free(self) -> None:
        """Scale-free types must take no length given (docs/04 Stage 2 scale pinning)."""
        assert not ANGLE.is_scale_pinned

    def test_registry_is_deterministic(self) -> None:
        assert [t.name for t in enabled_types()] == sorted(registry())

    def test_unknown_type_names_its_alternatives(self) -> None:
        with pytest.raises(ValueError, match="angle"):
            quantities.get("shaded_area")

    def test_phase_one_registers_angle_only(self) -> None:
        """Guards the roadmap: length/ratio/area (docs/09 P3/P5) must arrive as registrations
        here, not as branches elsewhere in the pipeline."""
        assert sorted(registry()) == ["angle"]

    def test_answer_formats_as_degrees(self) -> None:
        assert ANGLE.format_answer(Fraction(1, 2)) == "90"
        assert ANGLE.format_answer(Fraction(40, 180)) == "40"


class TestSnapping:
    def test_exact_value_snaps(self) -> None:
        assert snap_to_integer_degrees(45.0) == 45

    def test_value_within_tolerance_snaps(self) -> None:
        assert snap_to_integer_degrees(45.0 + EXTRACTION.angle_snap_tolerance_degrees / 2) == 45

    def test_value_outside_tolerance_is_rejected(self) -> None:
        assert snap_to_integer_degrees(45.0 + EXTRACTION.angle_snap_tolerance_degrees * 10) is None

    def test_junk_angle_is_rejected(self) -> None:
        """The Phase 0 tangent-chord angle. `newclid.tools.get_quotient` snapped this to 17/19
        because its tolerance is relative; an absolute integer-degree filter does not."""
        assert snap_to_integer_degrees(161.0526315789) is None

    def test_degenerate_angles_are_rejected(self) -> None:
        """0 and 180 degrees mean a degenerate figure, not a puzzle."""
        assert snap_to_integer_degrees(0.0) is None
        assert snap_to_integer_degrees(180.0) is None


class TestAngleProposals:
    def test_finds_the_round_angles(self) -> None:
        by_subject = {p.subject: p for p in propose_angles(RIGHT_ISOSCELES)}
        assert set(by_subject) == {("b", "a", "c"), ("a", "b", "c"), ("a", "c", "b")}
        assert by_subject[("b", "a", "c")].fact.degrees() == 90
        assert by_subject[("a", "b", "c")].fact.degrees() == 45

    def test_generic_figure_proposes_nothing(self) -> None:
        assert propose_angles(GENERIC) == ()

    def test_fact_value_equals_the_vertex_angle(self) -> None:
        """The spelling must be chosen so the directed fact's value *is* the vertex angle, not
        its supplement — otherwise the puzzle's answer would differ from what is proved."""
        for proposal in propose_angles(RIGHT_ISOSCELES):
            u, vertex, v = proposal.subject
            expected = _vertex_degrees(RIGHT_ISOSCELES, u, vertex, v)
            assert proposal.fact.degrees() == pytest.approx(expected, abs=1e-9)

    def test_proposals_are_constant_angle_facts(self) -> None:
        for proposal in propose_angles(RIGHT_ISOSCELES):
            assert proposal.fact.kind is FactKind.CONSTANT_ANGLE
            assert proposal.fact.value is not None

    def test_proposals_are_deterministic_and_sorted(self) -> None:
        first, second = propose_angles(RIGHT_ISOSCELES), propose_angles(RIGHT_ISOSCELES)
        assert first == second
        assert list(first) == sorted(first)

    def test_scale_invariant(self) -> None:
        """A figure drawn a thousand times larger is the same figure."""
        big = {name: (x * 1000, y * 1000) for name, (x, y) in RIGHT_ISOSCELES.items()}
        assert [p.fact.degrees() for p in propose_angles(big)] == [
            p.fact.degrees() for p in propose_angles(RIGHT_ISOSCELES)
        ]

    def test_obtuse_angle_is_proposed_as_obtuse(self) -> None:
        """An angle of 135 degrees must not be proposed as its 45-degree supplement."""
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (-1.0, 1.0)}
        by_subject = {p.subject: p for p in propose_angles(coords)}
        assert by_subject[("b", "a", "c")].fact.degrees() == 135


def _vertex_degrees(coords: dict[str, tuple[float, float]], u: str, vertex: str, v: str) -> float:
    ax, ay = coords[vertex]
    ux, uy = coords[u][0] - ax, coords[u][1] - ay
    vx, vy = coords[v][0] - ax, coords[v][1] - ay
    cosine = (ux * vx + uy * vy) / (math.hypot(ux, uy) * math.hypot(vx, vy))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
