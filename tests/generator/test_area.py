"""The area layer's arithmetic (docs/10 step A2).

These are unit tests over hand-built `Fact`s rather than engine runs: the module's whole job is
arithmetic on certified quantities, so its inputs are facts and its contract is testable without
a solver. `TestAgainstTheEngine` closes the loop by taking the facts from a real realization.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest
import sympy

from geoforge.generator.area import (
    AreaVerificationError,
    area_of,
    certified_lengths,
    certified_right_angles,
    certified_vertex_angles,
    shoelace,
    triangle_area,
)
from geoforge.solvers.types import Fact, FactKind


def lconst(u: str, v: str, value: int | Fraction) -> Fact:
    return Fact(kind=FactKind.CONSTANT_LENGTH, args=(u, v), value=Fraction(value))


def l2const(u: str, v: str, value: int | Fraction) -> Fact:
    return Fact(kind=FactKind.SQUARED_CONSTANT_LENGTH, args=(u, v), value=Fraction(value))


def perp(a: str, b: str, c: str, d: str) -> Fact:
    return Fact(kind=FactKind.PERPENDICULAR, args=(a, b, c, d))


def aconst(a: str, b: str, c: str, d: str, value: Fraction) -> Fact:
    return Fact(kind=FactKind.CONSTANT_ANGLE, args=(a, b, c, d), value=value)


class TestReadingCertifiedQuantities:
    def test_lconst_and_l2const_both_give_a_length(self) -> None:
        lengths = certified_lengths((lconst("a", "b", 4), l2const("a", "c", 3)))
        assert lengths[frozenset(("a", "b"))] == 4
        # l2const states the SQUARE, so it yields an irrational side directly.
        assert lengths[frozenset(("a", "c"))] == sympy.sqrt(3)

    def test_lconst_wins_over_l2const_for_the_same_segment(self) -> None:
        """Both are exact, so either is sound; preferring lconst keeps the value in the form the
        puzzle will state it in."""
        lengths = certified_lengths((l2const("a", "b", 16), lconst("a", "b", 4)))
        assert lengths[frozenset(("a", "b"))] == 4

    def test_right_angle_is_keyed_by_its_apex(self) -> None:
        assert certified_right_angles((perp("a", "b", "a", "c"),)) == {("a", frozenset(("b", "c")))}

    def test_perpendicular_lines_that_do_not_meet_at_a_vertex_are_ignored(self) -> None:
        """`perp a b c d` pins a triangle's angle only when the two lines share a point."""
        assert certified_right_angles((perp("a", "b", "c", "d"),)) == set()

    def test_vertex_angle_is_keyed_by_its_apex(self) -> None:
        angles = certified_vertex_angles((aconst("a", "b", "a", "c", Fraction(1, 3)),))
        assert angles == {("a", frozenset(("b", "c"))): Fraction(1, 3)}


class TestPrimitives:
    def test_right_triangle(self) -> None:
        result = triangle_area(
            ("a", "b", "c"), (lconst("a", "b", 4), lconst("a", "c", 3), perp("a", "b", "a", "c"))
        )
        assert result is not None
        assert result.route == "area_right_triangle"
        assert result.exact == 6
        assert not result.is_irrational

    def test_heron_on_an_equilateral_gives_an_irrational_area(self) -> None:
        """The cheapest irrational answer the pipeline can reach: (sqrt3/4)s^2 at s=2."""
        result = triangle_area(
            ("a", "b", "c"), (lconst("a", "b", 2), lconst("b", "c", 2), lconst("a", "c", 2))
        )
        assert result is not None
        assert result.route == "area_heron"
        assert sympy.simplify(result.exact - sympy.sqrt(3)) == 0
        assert result.is_irrational

    def test_sas_gives_an_irrational_area(self) -> None:
        result = triangle_area(
            ("a", "b", "c"),
            (lconst("a", "b", 2), lconst("a", "c", 2), aconst("a", "b", "a", "c", Fraction(1, 3))),
        )
        assert result is not None
        assert result.route == "area_sas"
        assert sympy.simplify(result.exact - sympy.sqrt(3)) == 0

    def test_returns_none_when_nothing_is_certified(self) -> None:
        """Ordinary attrition: most triangles in a figure have no certified sides."""
        assert triangle_area(("a", "b", "c"), ()) is None

    def test_returns_none_with_only_two_sides_and_no_angle(self) -> None:
        assert triangle_area(("a", "b", "c"), (lconst("a", "b", 2), lconst("a", "c", 2))) is None

    def test_degenerate_triple_is_refused_rather_than_returned_as_zero(self) -> None:
        """Sides 1, 2, 3 are collinear; a zero-area 'region' is not a puzzle."""
        assert (
            triangle_area(
                ("a", "b", "c"), (lconst("a", "b", 1), lconst("b", "c", 2), lconst("a", "c", 3))
            )
            is None
        )

    def test_repeated_vertex_is_not_a_triangle(self) -> None:
        assert triangle_area(("a", "a", "b"), (lconst("a", "b", 2),)) is None


class TestModPiInvariance:
    """The hazard doc 10 §10.5 is built around.

    `aconst` is a DIRECTED angle mod pi, so a stated 60 degrees may realize as a 120 degree
    vertex angle. `_sas` is allowed to use it unresolved only because sin(theta) = sin(pi - theta)
    makes the area identical. If that ever stops holding, this test fails and the primitive must
    start resolving against configuration facts.
    """

    @pytest.mark.parametrize("numerator,denominator", [(1, 3), (2, 3), (1, 4), (3, 4), (5, 6)])
    def test_supplementary_angles_give_the_same_area(
        self, numerator: int, denominator: int
    ) -> None:
        theta = Fraction(numerator, denominator)
        supplement = Fraction(1) - theta
        sides = (lconst("a", "b", 3), lconst("a", "c", 5))
        first = triangle_area(("a", "b", "c"), (*sides, aconst("a", "b", "a", "c", theta)))
        second = triangle_area(("a", "b", "c"), (*sides, aconst("a", "b", "a", "c", supplement)))
        assert first is not None and second is not None
        assert sympy.simplify(first.exact - second.exact) == 0

    def test_a_right_angle_is_its_own_supplement(self) -> None:
        """Which is exactly why no directed-angle fixture may use one (ONBOARDING gotcha 6)."""
        assert Fraction(1, 2) == Fraction(1) - Fraction(1, 2)


class TestVerification:
    """Numerics VERIFY, never derive -- and a disagreement raises rather than discards."""

    RIGHT = (lconst("a", "b", 4), lconst("a", "c", 3), perp("a", "b", "a", "c"))
    COORDS = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (0.0, 3.0)}

    def test_shoelace_matches_the_exact_value(self) -> None:
        assert shoelace(((0.0, 0.0), (4.0, 0.0), (0.0, 3.0))) == pytest.approx(6.0)

    def test_area_of_returns_the_verified_result(self) -> None:
        result = area_of(("a", "b", "c"), self.RIGHT, self.COORDS)
        assert result is not None and result.exact == 6

    def test_a_wrong_value_raises_rather_than_passing(self) -> None:
        """The load-bearing test. `bank/validate.py` re-derives ENGINE facts on a second engine
        and is structurally blind to this arithmetic (docs/10 §10.8), so if a mis-certified
        premise produces a wrong area, nothing downstream will catch it."""
        lying = {"a": (0.0, 0.0), "b": (40.0, 0.0), "c": (0.0, 3.0)}
        with pytest.raises(AreaVerificationError, match="disagrees with the reference diagram"):
            area_of(("a", "b", "c"), self.RIGHT, lying)

    def test_missing_coordinates_raise(self) -> None:
        with pytest.raises(AreaVerificationError, match="no coordinates"):
            area_of(("a", "b", "c"), self.RIGHT, {"a": (0.0, 0.0)})


class TestAgainstTheEngine:
    """Close the loop: take the facts from a real realization, not from hand-built ones."""

    def test_equilateral_area_from_engine_certified_facts(self) -> None:
        from geoforge.solvers.interface import get_backend
        from geoforge.solvers.types import ProblemSpec, SolveOptions

        backend = get_backend()
        figure = backend.realize(
            ProblemSpec(
                construction="a = free a; b = lconst b a 2; c = lconst c a 2, lconst c b 2"
            ),
            SolveOptions(seed=42),
        )
        coords = {name: (x, y) for name, x, y in figure.points}
        result = area_of(("a", "b", "c"), tuple(figure.declared), coords)

        assert result is not None, "engine certified three sides; Heron should have fired"
        assert sympy.simplify(result.exact - sympy.sqrt(3)) == 0
        assert result.is_irrational, "the whole point: an answer no engine can represent"
        assert result.approx == pytest.approx(math.sqrt(3))


class TestDecomposition:
    """Area by ratio against a larger triangle (docs/10 §10.5).

    The direct primitives compute 0 of 20 sub-triangle areas on a decorated figure, because the
    sub-triangle's sides are irrational and `lconst` holds a `Fraction`. Decomposition needs no
    length at all, which is the whole point.
    """

    SAS = (
        lconst("a", "b", 6),
        lconst("a", "c", 2),
        aconst("a", "b", "a", "c", Fraction(1, 3)),
    )

    def midp(self, m: str, u: str, v: str) -> Fact:
        return Fact(kind=FactKind.MIDPOINT, args=(m, u, v))

    def test_a_median_halves_the_triangle(self) -> None:
        whole = triangle_area(("a", "b", "c"), self.SAS)
        half = triangle_area(("a", "b", "m"), (*self.SAS, self.midp("m", "b", "c")))
        assert whole is not None and half is not None
        assert half.route == "area_median_split"
        assert sympy.simplify(half.exact - whole.exact / 2) == 0

    def test_it_works_from_either_endpoint_of_the_split_segment(self) -> None:
        facts = (*self.SAS, self.midp("m", "b", "c"))
        for region in (("a", "b", "m"), ("a", "c", "m")):
            result = triangle_area(region, facts)
            assert result is not None, region
            assert result.route == "area_median_split"

    def test_two_midpoints_compose_to_a_quarter(self) -> None:
        """Depth > 1: the medial sub-triangle is a quarter of the original."""
        facts = (*self.SAS, self.midp("m", "b", "c"), self.midp("n", "b", "m"))
        whole = triangle_area(("a", "b", "c"), self.SAS)
        quarter = triangle_area(("a", "b", "n"), facts)
        assert whole is not None and quarter is not None
        assert sympy.simplify(quarter.exact - whole.exact / 4) == 0

    def test_the_midpoint_fact_is_kept_as_a_consumed_input(self) -> None:
        """It is a premise the puzzle must state and Stage 6 must not drop."""
        result = triangle_area(("a", "b", "m"), (*self.SAS, self.midp("m", "b", "c")))
        assert result is not None
        assert any(f.kind is FactKind.MIDPOINT for f in result.inputs)

    def test_a_midpoint_of_an_uncomputable_parent_yields_nothing(self) -> None:
        """Decomposition is not a way to conjure an area the parent never had."""
        assert triangle_area(("a", "b", "m"), (self.midp("m", "b", "c"),)) is None

    def test_decomposition_terminates_on_cyclic_midpoint_facts(self) -> None:
        """A bound is required, not merely tidy: these facts are mutually recursive."""
        facts = (*self.SAS, self.midp("m", "b", "n"), self.midp("n", "b", "m"))
        assert triangle_area(("a", "b", "m"), facts) is None

    def test_verified_against_the_engine_and_the_diagram(self) -> None:
        from geoforge.solvers.interface import get_backend
        from geoforge.solvers.types import ProblemSpec, SolveOptions

        backend = get_backend()
        figure = backend.realize(
            ProblemSpec(
                construction=(
                    "a = free a; b = lconst b a 6; c = s_angle b a c 60o, lconst c a 2;"
                    " m = midpoint m b c"
                )
            ),
            SolveOptions(seed=42),
        )
        coords = {name: (x, y) for name, x, y in figure.points}
        # area_of verifies against the diagram and raises on disagreement.
        result = area_of(("a", "b", "m"), tuple(figure.declared), coords)
        assert result is not None
        assert result.route == "area_median_split"
        assert sympy.simplify(result.exact - 3 * sympy.sqrt(3) / 2) == 0
        assert result.is_irrational
