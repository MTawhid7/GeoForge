"""Typed construction layer (docs/03 §3.4)."""

from __future__ import annotations

from geoforge.generator.construction import (
    Construction,
    Step,
    fresh_point_names,
)


class TestPointNaming:
    def test_fresh_names_avoid_taken(self) -> None:
        assert fresh_point_names(frozenset({"a", "b"}), 2) == ("c", "d")

    def test_fresh_names_extend_past_the_alphabet(self) -> None:
        """Constructions can exceed 26 points, so naming must not silently collide."""
        taken = frozenset(chr(ord("a") + i) for i in range(26))
        assert fresh_point_names(taken, 2) == ("a1", "b1")

    def test_fresh_names_are_deterministic(self) -> None:
        assert fresh_point_names(frozenset({"a"}), 3) == fresh_point_names(frozenset({"a"}), 3)


class TestStep:
    def test_renders_jgex_clause(self) -> None:
        step = Step(construction="on_circum", outputs=("d",), args=("d", "a", "b", "c"))
        assert step.to_jgex() == "d = on_circum d a b c"

    def test_multi_output_seed_clause(self) -> None:
        step = Step(construction="triangle", outputs=("a", "b", "c"), args=("a", "b", "c"))
        assert step.to_jgex() == "a b c = triangle a b c"

    def test_numeric_values_detected(self) -> None:
        step = Step(construction="s_angle", outputs=("c",), args=("a", "b", "c", "30o"))
        assert step.numeric_values == ("30o",)


class TestConstruction:
    def _sample(self) -> Construction:
        return Construction(
            steps=(
                Step(construction="triangle", outputs=("a", "b", "c"), args=("a", "b", "c")),
                Step(construction="circle", outputs=("o",), args=("o", "a", "b", "c")),
            )
        )

    def test_points_in_introduction_order(self) -> None:
        assert self._sample().points == ("a", "b", "c", "o")

    def test_jgex_joins_clauses_with_semicolons(self) -> None:
        assert self._sample().to_jgex() == "a b c = triangle a b c; o = circle o a b c"

    def test_spec_round_trips_through_the_sal_wire_format(self) -> None:
        spec = self._sample().to_spec(goals=("aconst a b a c 1pi/3",))
        assert spec.to_jgex().endswith(" ? aconst a b a c 1pi/3")
        assert spec.construction == self._sample().to_jgex()

    def test_provenance_reproduces_the_construction(self) -> None:
        """Provenance must be enough to rebuild the figure (docs/02 invariant 2)."""
        construction = self._sample()
        assert construction.provenance() == construction.to_jgex()

    def test_circle_detection(self) -> None:
        assert self._sample().introduces_circle
        line_only = Construction(
            steps=(Step(construction="triangle", outputs=("a", "b", "c"), args=("a", "b", "c")),)
        )
        assert not line_only.introduces_circle
