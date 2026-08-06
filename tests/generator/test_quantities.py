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
    FigureView,
    enabled_types,
    propose_angles,
    registry,
    snap_to_integer_degrees,
)
from geoforge.solvers.types import Fact, FactKind, ProofDAG

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

    def test_types_arrive_as_registrations_not_as_branches(self) -> None:
        """Guards the roadmap: length/ratio (docs/09 P3) must arrive as registrations here, the
        way `area` did (docs/10 A3), and not as branches elsewhere in the pipeline."""
        assert sorted(registry()) == ["angle", "area"]

    def test_answer_formats_as_degrees(self) -> None:
        assert ANGLE.format_answer(_angle_fact(Fraction(1, 2))) == "90"
        assert ANGLE.format_answer(_angle_fact(Fraction(40, 180))) == "40"


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


def view(coords: dict[str, tuple[float, float]]) -> FigureView:
    """Wrap bare coordinates for `propose_angles`.

    The extractor takes a `FigureView` since 2026-08-06 (docs/04 §QTR) so that a quantity the
    engine cannot evaluate can read certified facts. `angle` reads only the coordinates, so
    these fixtures pass no facts — which is itself worth asserting: an angle extractor that
    started depending on facts would be a design change, not a refactor.
    """
    return FigureView(coords=coords, facts=())


class TestAngleProposals:
    def test_finds_the_round_angles(self) -> None:
        by_subject = {p.subject: p for p in propose_angles(view(RIGHT_ISOSCELES))}
        assert set(by_subject) == {("b", "a", "c"), ("a", "b", "c"), ("a", "c", "b")}
        assert by_subject[("b", "a", "c")].fact.degrees() == 90
        assert by_subject[("a", "b", "c")].fact.degrees() == 45

    def test_generic_figure_proposes_nothing(self) -> None:
        assert propose_angles(view(GENERIC)) == ()

    def test_fact_value_equals_the_vertex_angle(self) -> None:
        """The spelling must be chosen so the directed fact's value *is* the vertex angle, not
        its supplement — otherwise the puzzle's answer would differ from what is proved."""
        for proposal in propose_angles(view(RIGHT_ISOSCELES)):
            u, vertex, v = proposal.subject
            expected = _vertex_degrees(RIGHT_ISOSCELES, u, vertex, v)
            assert proposal.fact.degrees() == pytest.approx(expected, abs=1e-9)

    def test_proposals_are_constant_angle_facts(self) -> None:
        for proposal in propose_angles(view(RIGHT_ISOSCELES)):
            assert proposal.fact.kind is FactKind.CONSTANT_ANGLE
            assert proposal.fact.value is not None

    def test_proposals_are_deterministic_and_sorted(self) -> None:
        first, second = propose_angles(view(RIGHT_ISOSCELES)), propose_angles(view(RIGHT_ISOSCELES))
        assert first == second
        assert list(first) == sorted(first)

    def test_scale_invariant(self) -> None:
        """A figure drawn a thousand times larger is the same figure."""
        big = {name: (x * 1000, y * 1000) for name, (x, y) in RIGHT_ISOSCELES.items()}
        assert [p.fact.degrees() for p in propose_angles(view(big))] == [
            p.fact.degrees() for p in propose_angles(view(RIGHT_ISOSCELES))
        ]

    def test_obtuse_angle_is_proposed_as_obtuse(self) -> None:
        """An angle of 135 degrees must not be proposed as its 45-degree supplement."""
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (-1.0, 1.0)}
        by_subject = {p.subject: p for p in propose_angles(view(coords))}
        assert by_subject[("b", "a", "c")].fact.degrees() == 135


def _vertex_degrees(coords: dict[str, tuple[float, float]], u: str, vertex: str, v: str) -> float:
    ax, ay = coords[vertex]
    ux, uy = coords[u][0] - ax, coords[u][1] - ay
    vx, vy = coords[v][0] - ax, coords[v][1] - ay
    cosine = (ux * vx + uy * vy) / (math.hypot(ux, uy) * math.hypot(vx, vy))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


class TestFigureViewSeam:
    """The §QTR seam every quantity type reaches through (widened 2026-08-06).

    `angle` measures the diagram and lets the engine verify, so it needs only coordinates. Any
    quantity the engine cannot evaluate -- `area` is the first -- must read what was *certified*
    instead, because re-deriving geometry from coordinates is what docs/02 invariant 4 forbids.
    These tests pin the seam so a later change cannot quietly narrow it back.
    """

    def test_the_view_carries_facts_as_well_as_coordinates(self) -> None:
        from geoforge.solvers.types import Fact, FactKind

        fact = Fact(kind=FactKind.PERPENDICULAR, args=("a", "b", "a", "c"))
        v = FigureView(coords={"a": (0.0, 0.0)}, facts=(fact,))
        assert v.coords == {"a": (0.0, 0.0)}
        assert v.facts == (fact,)

    def test_angle_ignores_facts(self) -> None:
        """Passing facts must not change what `angle` proposes -- it reads the diagram only."""
        from geoforge.solvers.types import Fact, FactKind

        noise = (Fact(kind=FactKind.PERPENDICULAR, args=("a", "b", "a", "c")),)
        assert propose_angles(view(RIGHT_ISOSCELES)) == propose_angles(
            FigureView(coords=RIGHT_ISOSCELES, facts=noise)
        )

    def test_every_registered_type_accepts_a_view(self) -> None:
        """The registry's contract, not angle's: no extractor may take bare coordinates."""
        from geoforge.generator.quantities import enabled_types

        empty = FigureView(coords={}, facts=())
        for quantity_type in enabled_types():
            assert quantity_type.goal_extractor(empty) == ()


ANGLE_FIXTURE_FACT = Fact(
    kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "a", "c"), value=Fraction(1, 3)
)

_EMPTY_DAG = ProofDAG(
    facts=(),
    steps=(),
    assumptions=(),
    numerical_checks=(),
    trivial=(),
    proved_goals=(),
    unproved_goals=(),
)


def _angle_fact(value: Fraction) -> Fact:
    return Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "a", "c"), value=value)


class TestVerifierSeam:
    """How a proposal is shown true is the TYPE's business (docs/04 §QTR, added 2026-08-06).

    `angle` uses the engine. A quantity the engine has no predicate for -- `area` is the first,
    since no engine in the lineage has one (docs/03 §3.7) -- supplies its own verifier, and that
    is what keeps such a type a registration rather than a branch inside Stage 5.
    """

    def test_every_registered_type_has_a_verifier(self) -> None:
        from geoforge.generator.quantities import enabled_types

        for quantity_type in enabled_types():
            assert callable(quantity_type.verifier)

    def test_angle_uses_the_engine_verifier(self) -> None:
        from geoforge.generator.quantities import ANGLE, verify_with_engine

        assert ANGLE.verifier is verify_with_engine

    def test_a_type_may_override_the_verifier(self) -> None:
        """The point of the field: overriding must not require touching the pipeline."""
        from dataclasses import replace

        from geoforge.generator.quantities import ANGLE, Verification

        sentinel = Verification(fact=ANGLE_FIXTURE_FACT, evidence=(), proof_dag=_EMPTY_DAG)

        def always(_backend, _figure, _proposal, _opts):  # type: ignore[no-untyped-def]
            return sentinel

        overridden = replace(ANGLE, verifier=always)
        assert overridden.verifier(None, None, None, None) is sentinel  # type: ignore[arg-type]
        # The registered type is untouched -- `replace` returns a copy.
        from geoforge.generator.quantities import verify_with_engine

        assert ANGLE.verifier is verify_with_engine

    def test_verification_carries_evidence_for_stage_six(self) -> None:
        """`evidence` is not bookkeeping: those are premises minimization must not drop."""
        from geoforge.generator.quantities import Verification

        verification = Verification(
            fact=ANGLE_FIXTURE_FACT, evidence=(ANGLE_FIXTURE_FACT,), proof_dag=_EMPTY_DAG
        )
        assert verification.evidence == (ANGLE_FIXTURE_FACT,)
        assert verification.result is None


class TestAreaRegistration:
    """`area` is a registration, not a branch (docs/10 A3).

    The claim this class exists to keep honest: enabling a quantity the *engine cannot evaluate*
    required widening three §QTR signatures — `goal_extractor` to a `FigureView`, a `verifier`
    field, `format_answer` to a `Fact` — and no `if quantity_type == "area"` anywhere else.
    """

    EQUILATERAL_FACTS = (
        Fact(kind=FactKind.CONSTANT_LENGTH, args=("a", "b"), value=Fraction(2)),
        Fact(kind=FactKind.CONSTANT_LENGTH, args=("b", "c"), value=Fraction(2)),
        Fact(kind=FactKind.CONSTANT_LENGTH, args=("a", "c"), value=Fraction(2)),
    )
    EQUILATERAL_COORDS = {
        "a": (0.0, 0.0),
        "b": (2.0, 0.0),
        "c": (1.0, math.sqrt(3.0)),
    }

    def test_area_declares_all_the_qtr_fields(self) -> None:
        from geoforge.generator.quantities import AREA

        assert AREA.fact_kind is FactKind.AREA
        assert AREA.is_scale_pinned, "an area has dimension 2 — one given must fix the scale"
        assert AREA.template_family == "area"
        assert AREA.marks and AREA.nice_values("easy")

    def test_it_proposes_an_irrational_answer_angle_could_never_reach(self) -> None:
        """The whole reason the layer exists. `aconst` holds a `Fraction` (docs/07 T18), so no
        angle puzzle can answer sqrt(3); an equilateral triangle of side 2 has area exactly
        that, one multiplication from facts the engine hands over for free."""
        from geoforge.generator.quantities import propose_areas

        proposals = propose_areas(
            FigureView(coords=self.EQUILATERAL_COORDS, facts=self.EQUILATERAL_FACTS)
        )
        assert len(proposals) == 1
        assert proposals[0].fact.exact == "sqrt(3)"
        assert proposals[0].fact.value is None, "a surd is not a Fraction, which is the point"
        assert proposals[0].subject == ("a", "b", "c")

    def test_the_extractor_reads_facts_and_not_coordinates(self) -> None:
        """Inverted from `angle`, which measures the diagram. Coordinates alone determine an
        area numerically, and computing one from them would be deriving from numerics."""
        from geoforge.generator.quantities import propose_areas

        assert propose_areas(FigureView(coords=self.EQUILATERAL_COORDS, facts=())) == ()

    def test_a_diagram_that_disagrees_raises_rather_than_being_skipped(self) -> None:
        from geoforge.generator.area import AreaVerificationError
        from geoforge.generator.quantities import propose_areas

        lying = dict(self.EQUILATERAL_COORDS) | {"c": (1.0, 40.0)}
        with pytest.raises(AreaVerificationError):
            propose_areas(FigureView(coords=lying, facts=self.EQUILATERAL_FACTS))

    def test_the_verifier_returns_a_derivation_with_no_engine_result(self) -> None:
        from geoforge.generator.quantities import AREA, propose_areas, verify_area
        from geoforge.solvers.types import RealizedFigure, SolveOptions

        figure = RealizedFigure(
            points=tuple((n, x, y) for n, (x, y) in sorted(self.EQUILATERAL_COORDS.items())),
            declared=self.EQUILATERAL_FACTS,
        )
        proposal = propose_areas(FigureView(coords=figure.coords(), facts=figure.declared))[0]
        verification = AREA.verifier(None, figure, proposal, SolveOptions())  # type: ignore[arg-type]
        assert verification is not None
        assert verification.result is None, "no engine has an area predicate"
        assert verification.proof_dag.steps, "but there is still a derivation to translate"
        assert set(verification.evidence) == set(self.EQUILATERAL_FACTS)
        del verify_area  # imported to assert it is what the registry holds, below

    def test_the_registry_holds_the_area_verifier(self) -> None:
        from geoforge.generator.quantities import AREA, verify_area, verify_with_engine

        assert AREA.verifier is verify_area
        assert ANGLE.verifier is verify_with_engine

    def test_it_returns_none_when_the_facts_do_not_determine_the_area(self) -> None:
        """Ordinary attrition, and it must stay distinguishable from a crash."""
        from geoforge.generator.quantities import AREA, Proposal
        from geoforge.solvers.types import RealizedFigure, SolveOptions

        figure = RealizedFigure(
            points=tuple((n, x, y) for n, (x, y) in sorted(self.EQUILATERAL_COORDS.items())),
            declared=(),
        )
        proposal = Proposal(
            quantity_type="area",
            fact=Fact(kind=FactKind.AREA, args=("a", "b", "c"), exact="sqrt(3)"),
            subject=("a", "b", "c"),
            measured=1.732,
        )
        assert AREA.verifier(None, figure, proposal, SolveOptions()) is None  # type: ignore[arg-type]

    def test_the_answer_formats_as_the_exact_surd(self) -> None:
        from geoforge.generator.quantities import AREA

        fact = Fact(kind=FactKind.AREA, args=("a", "b", "c"), exact="3*sqrt(3)/4")
        assert AREA.format_answer(fact) == "3*sqrt(3)/4"

    def test_enumeration_is_restricted_to_points_the_layer_can_reach(self) -> None:
        """The enumeration is cubic in the point count, so a figure of scaffolding must not
        cost a triangle-by-triangle sympy pass."""
        from geoforge.generator.quantities import propose_areas

        crowded = dict(self.EQUILATERAL_COORDS) | {
            name: (float(i), 7.0) for i, name in enumerate("defghijklmnop")
        }
        proposals = propose_areas(FigureView(coords=crowded, facts=self.EQUILATERAL_FACTS))
        assert [p.subject for p in proposals] == [("a", "b", "c")]
