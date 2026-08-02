"""Stage 5: numeric-propose / symbolic-verify goal extraction (docs/04, docs/03 §3.3a).

Engine-backed. The central property under test is that **symbolic verification decides**: a
value the diagram shows but the premises do not force must be rejected, no matter how round it
looks.
"""

from __future__ import annotations

import pytest

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
        report = extract_goals(backend, realize(backend, "thales"), OPTS)
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
        goal = extract_goals(backend, figure, OPTS).goals[0]
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
