"""Stage 5: numeric-propose / symbolic-verify goal extraction (docs/04, docs/03 §3.3a).

Engine-backed. The central property under test is that **symbolic verification decides**: a
value the diagram shows but the premises do not force must be rejected, no matter how round it
looks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from geoforge.config import GENERATION
from geoforge.generator.extract import (
    ExtractionReason,
    extract_goals,
    propose,
)
from geoforge.solvers import ProblemSpec, get_backend
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import PremiseSpec, RealizedFigure, SolveOptions

OPTS = SolveOptions(seed=42)

#: Phase 0 fixtures. The last two are the underdetermined cases: their diagrams show a
#: perfectly definite angle that the premises do not force (spikes/p0/REPORT.md S1b).
FIGURES = {
    "thales": "a b = segment a b; o = midpoint o a b; c = on_circle c o a",
    "inscribed": (
        "a b = segment a b; c = s_angle a b c 50o; o = circle o a b c; d = on_circum d a b c"
    ),
    "tangent_chord": "o a = segment o a; b = on_circle b o a; x = lc_tangent x a o",
    "circum_generic": "a b c = triangle a b c; o = circle o a b c; d = on_circum d a b c",
}


@pytest.fixture(scope="module")
def backend() -> SolverBackend:
    return get_backend()


def realize(backend: SolverBackend, name: str) -> RealizedFigure:
    return backend.realize(ProblemSpec(construction=FIGURES[name]), OPTS)


class TestVerificationDecides:
    def test_thales_right_angle_is_extracted(self, backend: SolverBackend) -> None:
        # `reject_sight_readable=False`: Thales' answer is a right angle, which the product
        # policy rejects (docs/07 T5). This test is about verification, not the policy.
        report = extract_goals(
            backend, realize(backend, "thales"), OPTS, reject_sight_readable=False
        )
        assert len(report.goals) == 1
        goal = report.goals[0]
        assert goal.subject == ("a", "c", "b"), "the right angle is the one at c, on the circle"
        assert goal.fact.degrees() == 90

    def test_a_true_goal_is_rejected_without_its_premises(self, backend: SolverBackend) -> None:
        """The load-bearing test for docs/02 invariant 4.

        Thales' right angle is true of the diagram whatever we tell the engine. Asked to prove
        it from no premises at all, the engine must fail — if it succeeded, verification would
        be reading the coordinates rather than the hypotheses, and every "verified" goal in the
        bank would be worth nothing.
        """
        figure = realize(backend, "thales")
        goal = extract_goals(backend, figure, OPTS, reject_sight_readable=False).goals[0]
        without = backend.solve_facts(
            PremiseSpec(points=figure.points, premises=(), goals=(goal.fact,)), OPTS
        )
        assert not without.solved

    def test_underdetermined_angles_are_not_proposed(self, backend: SolverBackend) -> None:
        """Phase 0 regression (tangent-chord, generic circumcircle).

        Both figures show angles that `get_quotient` snapped to a "nice" rational — 17/19 for
        the tangent-chord — which then cost an engine call to reject. Under an integer-degree
        filter they are never proposed: no candidate here claims a value the premises leave
        free.
        """
        for name in ("tangent_chord", "circum_generic"):
            figure = realize(backend, name)
            for proposal in propose(figure):
                verified = backend.solve_facts(
                    PremiseSpec(
                        points=figure.points,
                        premises=figure.declared,
                        goals=(proposal.fact,),
                    ),
                    OPTS,
                )
                assert verified.solved, f"{name}: proposed {proposal.key} but it is not forced"

    def test_generic_triangle_yields_no_goal(self, backend: SolverBackend) -> None:
        report = extract_goals(backend, realize(backend, "circum_generic"), OPTS)
        assert report.goals == ()


class TestFiltering:
    def test_a_stated_given_is_not_a_puzzle(self, backend: SolverBackend) -> None:
        """The inscribed figure states angle ABC = 50 degrees. "Find angle ABC" is not a
        question. Catching it requires comparing *canonical* facts: the engine reorders an
        angle's points, so the proposal's own spelling need not match the given's."""
        report = extract_goals(backend, realize(backend, "inscribed"), OPTS)
        reasons = [reason for _, reason in report.rejected]
        assert ExtractionReason.ALREADY_GIVEN in reasons
        assert all(goal.fact.degrees() != 50 for goal in report.goals)

    def test_shallow_goals_are_filtered(self, backend: SolverBackend) -> None:
        figure = realize(backend, "inscribed")
        # Both uncapped, or the goal limit would mask the filter's effect.
        unfiltered = extract_goals(backend, figure, OPTS, max_goals=99, require_interesting=False)
        filtered = extract_goals(backend, figure, OPTS, max_goals=99)
        assert len(filtered.goals) < len(unfiltered.goals)
        assert all(goal.depth >= 3 for goal in filtered.goals)

    def test_goal_count_is_capped(self, backend: SolverBackend) -> None:
        report = extract_goals(backend, realize(backend, "inscribed"), OPTS, max_goals=1)
        assert len(report.goals) == 1
        assert ExtractionReason.SURPLUS in [reason for _, reason in report.rejected]

    def test_best_goal_wins_not_the_first(self, backend: SolverBackend) -> None:
        """Selection must rank candidates, not take them in enumeration order."""
        figure = realize(backend, "inscribed")
        all_goals = extract_goals(backend, figure, OPTS, max_goals=99).goals
        best = extract_goals(backend, figure, OPTS, max_goals=1).goals[0]
        assert best.depth == max(goal.depth for goal in all_goals)

    def test_report_accounts_for_every_proposal(self, backend: SolverBackend) -> None:
        """Attrition must reconcile: nothing may vanish unexplained (docs/04)."""
        for name in FIGURES:
            report = extract_goals(backend, realize(backend, name), OPTS)
            assert len(report.goals) + len(report.rejected) == report.proposed


class TestDeterminism:
    def test_same_figure_yields_the_same_goals(self, backend: SolverBackend) -> None:
        figure = realize(backend, "inscribed")
        first = extract_goals(backend, figure, OPTS)
        second = extract_goals(backend, figure, OPTS)
        assert [g.fact for g in first.goals] == [g.fact for g in second.goals]
        assert first.rejected == second.rejected


class TestSightReadableAnswersAreRejected:
    """docs/07 T5: 45 and 90 degrees are *recognised* off a to-scale figure, not measured.

    A gate that never fires is untested, and this one is easy to break silently — it lives one
    `if` away from the ranking that used to concentrate exactly these answers. So it is asserted
    firing, not firing, and not over-firing.
    """

    def test_thales_right_angle_is_rejected(self, backend: SolverBackend) -> None:
        """The canonical case: the angle in a semicircle is 90 degrees and always was."""
        report = extract_goals(backend, realize(backend, "thales"), OPTS)
        assert not report.goals
        assert any(reason is ExtractionReason.SIGHT_READABLE for _, reason in report.rejected), (
            f"expected a sight_readable rejection, got {report.counts()}"
        )

    def test_the_same_goal_survives_with_the_policy_off(self, backend: SolverBackend) -> None:
        """The near-miss. Without this, the test above passes on an extractor that returns
        nothing at all."""
        report = extract_goals(
            backend, realize(backend, "thales"), OPTS, reject_sight_readable=False
        )
        assert len(report.goals) == 1
        assert report.goals[0].fact.degrees() == 90
        assert not any(reason is ExtractionReason.SIGHT_READABLE for _, reason in report.rejected)

    def test_an_awkward_answer_is_kept(self, backend: SolverBackend) -> None:
        """The other near-miss: the gate must reject *those two values*, not every answer.

        The inscribed figure is built on a 50-degree given, so its derivable angles are not
        multiples of 45.
        """
        report = extract_goals(backend, realize(backend, "inscribed"), OPTS)
        assert report.goals, f"nothing survived: {report.counts()}"
        for goal in report.goals:
            assert goal.fact.degrees() not in GENERATION.rejected_answer_degrees

    def test_a_non_integer_answer_is_never_rejected(self) -> None:
        """`Fact.value` is a `Fraction` of pi (docs/07 T18), so a value that is not a whole
        number of degrees is a genuinely awkward angle — the best kind of answer, and one an
        integer-only membership test must not accidentally match."""
        from fractions import Fraction

        from geoforge.generator.extract import _answer_degrees

        class _Stub:
            def __init__(self, value: Fraction | None) -> None:
                self.fact = SimpleNamespace(value=value)

        assert _answer_degrees(_Stub(Fraction(1, 7))) is None  # type: ignore[arg-type]
        assert _answer_degrees(_Stub(None)) is None  # type: ignore[arg-type]
        assert _answer_degrees(_Stub(Fraction(1, 2))) == 90  # type: ignore[arg-type]
        assert _answer_degrees(_Stub(Fraction(1, 4))) == 45  # type: ignore[arg-type]
