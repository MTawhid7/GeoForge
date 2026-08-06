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
    Certified,
    area_of,
    certified_lengths,
    certified_right_angles,
    certified_vertex_angles,
    display_text,
    exact_text,
    proof_dag,
    shoelace,
    triangle_area,
    verify,
)
from geoforge.solvers.types import Fact, FactKind, fact_from_id


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
        assert lengths[frozenset(("a", "b"))].value == 4
        # l2const states the SQUARE, so it yields an irrational side directly.
        assert lengths[frozenset(("a", "c"))].value == sympy.sqrt(3)

    def test_lconst_wins_over_l2const_for_the_same_segment(self) -> None:
        """Both are exact, so either is sound; preferring lconst keeps the value in the form the
        puzzle will state it in."""
        lengths = certified_lengths((l2const("a", "b", 16), lconst("a", "b", 4)))
        assert lengths[frozenset(("a", "b"))].value == 4

    def test_right_angle_is_keyed_by_its_apex(self) -> None:
        fact = perp("a", "b", "a", "c")
        rights = certified_right_angles((fact,))
        assert rights.keys() == {("a", frozenset(("b", "c")))}
        # The witnessing fact travels with the angle: a route that uses it has to state it.
        assert rights[("a", frozenset(("b", "c")))] == fact

    def test_perpendicular_lines_that_do_not_meet_at_a_vertex_are_ignored(self) -> None:
        """`perp a b c d` pins a triangle's angle only when the two lines share a point."""
        assert certified_right_angles((perp("a", "b", "c", "d"),)) == {}

    def test_vertex_angle_is_keyed_by_its_apex(self) -> None:
        fact = aconst("a", "b", "a", "c", Fraction(1, 3))
        angles = certified_vertex_angles((fact,))
        assert angles.keys() == {("a", frozenset(("b", "c")))}
        assert angles[("a", frozenset(("b", "c")))] == Certified(Fraction(1, 3), fact)


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


class TestCevianSplit:
    """[ABP] = [ABX] * PY/XY when P sits on a cevian (docs/10 §10.5).

    The rule exists because the engine certifies `rconst X P P Y` but cannot certify
    `rconst P Y X Y`: AR chases ratios multiplicatively and cannot do XY = XP + PY. MEASURED on a
    centroid figure -- `rconst c g g m 2/1` proves, `rconst g m c m 1/3` does not.
    """

    BASE = (
        lconst("a", "b", 6),
        lconst("a", "c", 4),
        aconst("a", "b", "a", "c", Fraction(1, 3)),
    )

    def coll(self, *pts: str) -> Fact:
        return Fact(kind=FactKind.COLLINEAR, args=pts)

    def midp(self, m: str, u: str, v: str) -> Fact:
        return Fact(kind=FactKind.MIDPOINT, args=(m, u, v))

    def rconst(self, w: str, x: str, y: str, z: str, value: int) -> Fact:
        return Fact(kind=FactKind.CONSTANT_RATIO, args=(w, x, y, z), value=Fraction(value))

    def test_centroid_cuts_one_third(self) -> None:
        facts = (
            *self.BASE,
            self.midp("m", "a", "b"),
            self.coll("c", "g", "m"),
            self.rconst("c", "g", "g", "m", 2),
        )
        whole = triangle_area(("a", "b", "c"), self.BASE)
        third = triangle_area(("a", "b", "g"), facts)
        assert whole is not None and third is not None
        assert third.route == "area_cevian_split"
        assert sympy.simplify(third.exact - whole.exact / 3) == 0

    def test_the_ratio_fact_is_kept_as_a_consumed_input(self) -> None:
        facts = (
            *self.BASE,
            self.midp("m", "a", "b"),
            self.coll("c", "g", "m"),
            self.rconst("c", "g", "g", "m", 2),
        )
        result = triangle_area(("a", "b", "g"), facts)
        assert result is not None
        assert any(f.kind is FactKind.CONSTANT_RATIO for f in result.inputs)

    def test_it_refuses_when_the_foot_is_not_on_the_base_line(self) -> None:
        """Y must lie on AB, or the two triangles do not share a base and the ratio is wrong."""
        facts = (
            *self.BASE,
            self.coll("c", "g", "m"),
            self.rconst("c", "g", "g", "m", 2),
        )
        assert triangle_area(("a", "b", "g"), facts) is None

    def test_it_refuses_without_certified_collinearity(self) -> None:
        facts = (
            *self.BASE,
            self.midp("m", "a", "b"),
            self.rconst("c", "g", "g", "m", 2),
        )
        assert triangle_area(("a", "b", "g"), facts) is None


class TestPreciseInputs:
    """A route reports what it consumed, not everything lying around (docs/10 A3).

    An earlier version pooled "every fact wholly about this triangle" into `inputs`. That is
    over-collection, and it is not cosmetic: those facts become the puzzle's stated givens, and
    docs/05 filter 5 treats a stated-but-unused given as a *bug* that fails the run rather than
    as attrition. It also inflates the figure, since Stage 6 prunes to the points the surviving
    facts mention.
    """

    def test_sas_consumes_two_sides_and_one_angle_and_nothing_else(self) -> None:
        facts = (
            lconst("a", "b", 6),
            lconst("a", "c", 4),
            aconst("a", "b", "a", "c", Fraction(1, 3)),
            # Both about this triangle, and neither used: the pooled version swept them in.
            Fact(kind=FactKind.N_COLLINEAR, args=("a", "b", "c")),
            aconst("b", "a", "b", "c", Fraction(1, 4)),
        )
        result = triangle_area(("a", "b", "c"), facts)
        assert result is not None and result.route == "area_sas"
        assert {f.fact_id for f in result.inputs} == {
            lconst("a", "b", 6).fact_id,
            lconst("a", "c", 4).fact_id,
            aconst("a", "b", "a", "c", Fraction(1, 3)).fact_id,
        }

    def test_a_recursive_route_keeps_its_own_step_separate_from_its_parents(self) -> None:
        """`inputs` is this step's premises; the parent's live on the parent."""
        facts = (
            lconst("a", "b", 6),
            lconst("a", "c", 4),
            aconst("a", "b", "a", "c", Fraction(1, 3)),
            Fact(kind=FactKind.MIDPOINT, args=("m", "b", "c")),
        )
        result = triangle_area(("a", "b", "m"), facts)
        assert result is not None and result.route == "area_median_split"
        assert [f.kind for f in result.inputs] == [FactKind.MIDPOINT]
        assert len(result.parents) == 1
        assert result.parents[0].route == "area_sas"
        # ...but the whole derivation's premises are still reachable in one place.
        assert {f.kind for f in result.all_inputs} == {
            FactKind.MIDPOINT,
            FactKind.CONSTANT_LENGTH,
            FactKind.CONSTANT_ANGLE,
        }


class TestProofDAG:
    """The decomposition, rendered as the structure the rest of the pipeline speaks (docs/10 A3).

    Stage 6 minimizes a proof DAG and M4 translates its steps. An area has no *engine* proof,
    so the layer emits its own — which is what lets `area` be a registration in the QTR rather
    than a branch in traceback, translation, pruning and scoring.
    """

    FACTS = (
        lconst("a", "b", 6),
        lconst("a", "c", 4),
        aconst("a", "b", "a", "c", Fraction(1, 3)),
        Fact(kind=FactKind.MIDPOINT, args=("m", "b", "c")),
    )

    def test_each_route_becomes_one_step(self) -> None:
        result = triangle_area(("a", "b", "m"), self.FACTS)
        assert result is not None
        dag = proof_dag(result)
        # Steps are sorted canonically (by conclusion id) for determinism, not by reading order.
        assert {s.justification.rule_id for s in dag.steps} == {"area_median_split", "area_sas"}
        assert dag.proved_goals == (result.fact.fact_id,)
        assert dag.depth() == 2, "the median step stands on the SAS step"

    def test_the_intermediate_area_is_a_conclusion_and_not_an_assumption(self) -> None:
        """The parent area is *derived*, so it must not appear in the premise pool — a puzzle
        that states [ABC] as a given has given away its own answer."""
        result = triangle_area(("a", "b", "m"), self.FACTS)
        assert result is not None
        dag = proof_dag(result)
        assert not any(fid.startswith("area:") for fid in dag.assumptions)
        concluded = {s.conclusion for s in dag.steps}
        assert result.parents[0].fact.fact_id in concluded

    def test_assumptions_are_exactly_the_engine_facts_consumed(self) -> None:
        result = triangle_area(("a", "b", "m"), self.FACTS)
        assert result is not None
        dag = proof_dag(result)
        assert set(dag.assumptions) == {f.fact_id for f in result.all_inputs}

    def test_configuration_facts_are_separated_from_premises(self) -> None:
        """`minimize_premises` never drops a configuration fact, and it can only honour that if
        the DAG puts them in `numerical_checks` (docs/04 Stage 6)."""
        ncoll = Fact(kind=FactKind.N_COLLINEAR, args=("a", "b", "c"))
        facts = (*self.FACTS, ncoll)
        # Force the configuration fact into a route's inputs via the cevian rule, which states
        # its incidence witness; here the simpler check is that nothing mis-files a config fact.
        result = triangle_area(("a", "b", "m"), facts)
        assert result is not None
        dag = proof_dag(result)
        assert all(not fact_from_id(fid).is_configuration for fid in dag.assumptions)

    def test_the_dag_survives_a_round_trip_through_fact_ids(self) -> None:
        """Every fact in a layer DAG must parse back from its id, because the bank validator
        reads emitted JSON and never sees these objects."""
        result = triangle_area(("a", "b", "m"), self.FACTS)
        assert result is not None
        for fact in proof_dag(result).facts:
            assert fact_from_id(fact.fact_id) == fact

    def test_a_three_deep_decomposition_produces_three_steps(self) -> None:
        facts = (
            *self.FACTS,
            Fact(kind=FactKind.MIDPOINT, args=("n", "a", "b")),
        )
        result = triangle_area(("n", "b", "m"), facts)
        assert result is not None
        dag = proof_dag(result)
        assert len(dag.steps) == 3
        assert dag.depth() == 3

    def test_verification_checks_every_intermediate_not_just_the_answer(self) -> None:
        """A wrong intermediate that later cancels would ship a right number with a wrong
        solution, and the solution is what the player reads."""
        result = triangle_area(("a", "b", "m"), self.FACTS)
        assert result is not None
        good = {"a": (0.0, 0.0), "b": (6.0, 0.0), "c": (2.0, 2.0 * math.sqrt(3.0))}
        good["m"] = ((good["b"][0] + good["c"][0]) / 2, (good["b"][1] + good["c"][1]) / 2)
        verify(result, good)  # the honest figure passes
        # Move only the parent's third vertex: [abm] is untouched, [abc] is not.
        bad = dict(good)
        bad["c"] = (2.0, 9.0)
        with pytest.raises(AreaVerificationError, match="area_sas"):
            verify(result, bad)


class TestExactAndDisplayText:
    """`exact` is for comparison, `display` is for reading, and they are not the same string
    (docs/02 keeps `exact`, `approx` and `display` apart)."""

    CASES = (
        ("sqrt(3)", "1*sqrt(3)", "√3"),
        ("3*sqrt(2)", "3*sqrt(2)", "3√2"),
        ("25*sqrt(3)/4", "25/4*sqrt(3)", "25√3/4"),
        ("25*sqrt(2)/16", "25/16*sqrt(2)", "25√2/16"),
        ("6", "6", "6"),
        ("3/2", "3/2", "3/2"),
    )

    @pytest.mark.parametrize("source,exact,shown", CASES)
    def test_rendering(self, source: str, exact: str, shown: str) -> None:
        value = sympy.sympify(source)
        assert exact_text(value) == exact
        assert display_text(value) == shown

    @pytest.mark.parametrize("source,exact,_shown", CASES)
    def test_exact_text_satisfies_the_schema_grammar(
        self, source: str, exact: str, _shown: str
    ) -> None:
        """The reason `exact_text` exists at all. SymPy prints `25*sqrt(3)/4`; the schema's term
        is coefficient-first, so the same number must be written `25/4*sqrt(3)`. Getting this
        wrong fails at the schema boundary with a puzzle already built."""
        from geoforge.schema import _EXACT_TERM, _split_terms

        assert all(_EXACT_TERM.match(term) for term in _split_terms(exact))
        assert float(sympy.sympify(exact)) == pytest.approx(float(sympy.sympify(source)))

    def test_a_value_outside_the_closed_grammar_is_refused(self) -> None:
        from geoforge.generator.area import UnrepresentableArea

        with pytest.raises(UnrepresentableArea):
            exact_text(sympy.cbrt(2))

    def test_the_fact_carries_the_schema_form_not_sympys(self) -> None:
        facts = (
            lconst("a", "b", 5),
            lconst("a", "c", 5),
            aconst("a", "b", "a", "c", Fraction(2, 3)),
        )
        result = triangle_area(("a", "b", "c"), facts)
        assert result is not None
        assert result.fact.exact == "25/4*sqrt(3)"
        assert result.display == "25√3/4"


class TestRegionCanonicalOrder:
    """MEASURED: without this, `_decompose` emitted `[ACB]` where the extractor asked for
    `[ABC]` — one region, two fact ids, two DAG nodes that never share, two identical puzzles.
    """

    def test_a_triangles_vertices_are_sorted(self) -> None:
        facts = (
            lconst("a", "b", 6),
            lconst("a", "c", 2),
            aconst("a", "b", "a", "c", Fraction(1, 4)),
            Fact(kind=FactKind.MIDPOINT, args=("m", "b", "c")),
        )
        result = triangle_area(("a", "m", "c"), facts)
        assert result is not None
        assert result.region == ("a", "c", "m")
        assert result.parents[0].region == ("a", "b", "c"), "the parent is canonical too"

    def test_the_two_spellings_are_one_fact(self) -> None:
        facts = (lconst("a", "b", 2), lconst("b", "c", 2), lconst("a", "c", 2))
        first = triangle_area(("a", "b", "c"), facts)
        second = triangle_area(("c", "b", "a"), facts)
        assert first is not None and second is not None
        assert first.fact.fact_id == second.fact.fact_id
