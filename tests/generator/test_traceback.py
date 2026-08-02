"""Stage 6: traceback, premise minimization, figure pruning (docs/04).

The sub-DAG selection and pruning tests are engine-free — a hand-built DAG is the only way to
put two competing derivations of the same fact in front of the selector and check which one it
takes. The minimization tests need the engine, because "does the goal still follow?" is exactly
the question only the engine can answer.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from geoforge.generator.construction import Construction, Step
from geoforge.generator.extract import extract_goals
from geoforge.generator.traceback import (
    derive,
    minimal_subdag,
    minimize_premises,
    prune_figure,
)
from geoforge.solvers import ProblemSpec, get_backend
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import (
    Fact,
    FactKind,
    Justification,
    JustificationKind,
    ProofDAG,
    ProofStep,
    SolveOptions,
)

OPTS = SolveOptions(seed=42)

THALES = "a b = segment a b; o = midpoint o a b; c = on_circle c o a"
INSCRIBED = "a b = segment a b; c = s_angle a b c 50o; o = circle o a b c; d = on_circum d a b c"


@pytest.fixture(scope="module")
def backend() -> SolverBackend:
    return get_backend()


# ---------------------------------------------------------------------------------------
# Sub-DAG selection, over a hand-built DAG
# ---------------------------------------------------------------------------------------

PREMISE = Fact(kind=FactKind.MIDPOINT, args=("o", "a", "b"))
CONFIG = Fact(kind=FactKind.N_COLLINEAR, args=("a", "b", "c"))
TRIVIAL = Fact(kind=FactKind.EQUAL_ANGLES, args=("a", "o", "c", "o", "a", "o", "c", "o"))
MIDDLE = Fact(kind=FactKind.CONGRUENT, args=("a", "o", "c", "o"))
GOAL = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "c", "b", "c"), value=Fraction(1, 2))

RULE = Justification(kind=JustificationKind.RULE_APPLICATION, rule_id="r01")
OTHER = Justification(kind=JustificationKind.RULE_APPLICATION, rule_id="r02")


def _dag_with_two_routes() -> ProofDAG:
    """One goal, two derivations: a one-step route and a two-step detour."""
    short = ProofStep(conclusion=GOAL.fact_id, premises=(PREMISE.fact_id,), justification=RULE)
    long_a = ProofStep(
        conclusion=MIDDLE.fact_id, premises=(PREMISE.fact_id, TRIVIAL.fact_id), justification=OTHER
    )
    long_b = ProofStep(
        conclusion=GOAL.fact_id, premises=(MIDDLE.fact_id, CONFIG.fact_id), justification=OTHER
    )
    return ProofDAG(
        facts=(PREMISE, CONFIG, TRIVIAL, MIDDLE, GOAL),
        steps=(long_a, long_b, short),
        assumptions=(PREMISE.fact_id,),
        numerical_checks=(CONFIG.fact_id,),
        trivial=(TRIVIAL.fact_id,),
        proved_goals=(GOAL.fact_id,),
        unproved_goals=(),
    )


class TestSubDagSelection:
    def test_cheapest_derivation_wins(self) -> None:
        subdag = minimal_subdag(_dag_with_two_routes(), GOAL.fact_id)
        assert subdag is not None
        assert len(subdag.steps) == 1
        assert subdag.premises == (PREMISE,)

    def test_leaves_are_classified(self) -> None:
        """Premises, configuration facts and tautologies are three different things."""
        dag = _dag_with_two_routes()
        # Force the long route by removing the short one.
        long_only = ProofDAG(
            facts=dag.facts,
            steps=dag.steps[:2],
            assumptions=dag.assumptions,
            numerical_checks=dag.numerical_checks,
            trivial=dag.trivial,
            proved_goals=dag.proved_goals,
            unproved_goals=(),
        )
        subdag = minimal_subdag(long_only, GOAL.fact_id)
        assert subdag is not None
        assert subdag.premises == (PREMISE,)
        assert subdag.configuration == (CONFIG,)
        assert subdag.trivial == (TRIVIAL,)

    def test_missing_goal_returns_none(self) -> None:
        absent = Fact(kind=FactKind.CONSTANT_ANGLE, args=("x", "y", "z", "w"), value=Fraction(1, 3))
        assert minimal_subdag(_dag_with_two_routes(), absent.fact_id) is None

    def test_selection_is_deterministic(self) -> None:
        dag = _dag_with_two_routes()
        assert minimal_subdag(dag, GOAL.fact_id) == minimal_subdag(dag, GOAL.fact_id)


# ---------------------------------------------------------------------------------------
# Premise minimization, against the engine
# ---------------------------------------------------------------------------------------


class TestPremiseMinimization:
    def test_redundant_premise_is_dropped(self, backend: SolverBackend) -> None:
        """In the inscribed-angle figure, `d` sits on the circle but takes no part in proving
        an angle among a, b, c, o — so `cyclic a b c d` must not survive as a given."""
        figure = backend.realize(ProblemSpec(construction=INSCRIBED), OPTS)
        goal = extract_goals(backend, figure, OPTS, max_goals=1).goals[0]
        derivation = derive(backend, figure.points, goal.result.proof_dag, goal.fact, OPTS)
        assert derivation is not None
        assert any(f.kind is FactKind.CYCLIC for f in derivation.dropped_premises)
        assert all(f.kind is not FactKind.CYCLIC for f in derivation.premises)

    def test_necessary_premises_survive(self, backend: SolverBackend) -> None:
        figure = backend.realize(ProblemSpec(construction=THALES), OPTS)
        goal = extract_goals(backend, figure, OPTS).goals[0]
        derivation = derive(backend, figure.points, goal.result.proof_dag, goal.fact, OPTS)
        assert derivation is not None
        assert derivation.premises
        kinds = {f.kind for f in derivation.premises}
        assert FactKind.MIDPOINT in kinds

    def test_configuration_facts_are_never_minimized(self, backend: SolverBackend) -> None:
        """The soundness property this whole stage exists to protect (docs/04 Stage 6).

        Configuration facts are checked numerically and consumed by no rule, so a minimizer
        that treats every premise alike drops all of them — and ships a puzzle whose answer
        depends on a configuration nobody stated.
        """
        figure = backend.realize(ProblemSpec(construction=THALES), OPTS)
        goal = extract_goals(backend, figure, OPTS).goals[0]
        subdag = minimal_subdag(goal.result.proof_dag, goal.fact.fact_id)
        assert subdag is not None
        assert subdag.configuration, "fixture must exercise configuration facts"

        outcome = minimize_premises(
            backend, figure.points, subdag.premises, subdag.configuration, goal.fact, OPTS
        )
        derivation = derive(backend, figure.points, goal.result.proof_dag, goal.fact, OPTS)
        assert derivation is not None
        assert set(derivation.configuration) == set(subdag.configuration)
        assert all(not f.is_configuration for f in outcome.kept)

    def test_minimization_is_deterministic(self, backend: SolverBackend) -> None:
        figure = backend.realize(ProblemSpec(construction=INSCRIBED), OPTS)
        goal = extract_goals(backend, figure, OPTS, max_goals=1).goals[0]
        runs = [
            derive(backend, figure.points, goal.result.proof_dag, goal.fact, OPTS) for _ in range(2)
        ]
        assert runs[0] is not None and runs[1] is not None
        assert runs[0].premises == runs[1].premises
        assert runs[0].dropped_premises == runs[1].dropped_premises

    def test_surviving_proof_only_cites_surviving_premises(self, backend: SolverBackend) -> None:
        """After minimization the recorded proof must be the proof from what is left, or a
        solution step could cite a given the puzzle no longer states."""
        figure = backend.realize(ProblemSpec(construction=INSCRIBED), OPTS)
        goal = extract_goals(backend, figure, OPTS, max_goals=1).goals[0]
        derivation = derive(backend, figure.points, goal.result.proof_dag, goal.fact, OPTS)
        assert derivation is not None
        stated = set(derivation.premises) | set(derivation.configuration)
        assert set(derivation.subdag.premises) <= stated

    def test_unprovable_goal_is_reported_not_raised(self, backend: SolverBackend) -> None:
        """Upstream BUG-3 regression: newclid raises ValueError where it means "unproven".

        During minimization "the goal no longer follows" is the single most common answer, so
        it has to arrive as a result rather than an exception.
        """
        figure = backend.realize(ProblemSpec(construction=THALES), OPTS)
        goal = extract_goals(backend, figure, OPTS).goals[0]
        outcome = minimize_premises(backend, figure.points, (), (), goal.fact, OPTS)
        assert outcome.engine_errors == ()


# ---------------------------------------------------------------------------------------
# Figure pruning
# ---------------------------------------------------------------------------------------


def _construction() -> Construction:
    return Construction(
        steps=(
            Step(construction="segment", outputs=("a", "b"), args=("a", "b")),
            Step(construction="midpoint", outputs=("o",), args=("o", "a", "b")),
            Step(construction="on_circle", outputs=("c",), args=("c", "o", "a")),
            Step(construction="on_bline", outputs=("x",), args=("x", "a", "b")),
        )
    )


class TestFigurePruning:
    def test_unreferenced_scaffolding_is_dropped(self) -> None:
        pruning = prune_figure(_construction(), frozenset({"a", "b", "c"}))
        assert 3 not in pruning.kept_steps
        assert pruning.dropped_steps == (3,)

    def test_dependencies_are_kept_transitively(self) -> None:
        """Keeping c means keeping o, which defines it — a figure cannot draw a point whose
        scaffolding was removed."""
        pruning = prune_figure(_construction(), frozenset({"c"}))
        assert "o" in pruning.kept_points
        assert "a" in pruning.kept_points
        assert pruning.kept_steps == (0, 1, 2)

    def test_nothing_needed_drops_everything(self) -> None:
        pruning = prune_figure(_construction(), frozenset())
        assert pruning.kept_steps == ()

    def test_pruned_construction_is_rebuildable(self) -> None:
        pruning = prune_figure(_construction(), frozenset({"a", "b", "c"}))
        pruned = pruning.construction(_construction())
        assert pruned.to_jgex() == ("a b = segment a b; o = midpoint o a b; c = on_circle c o a")

    def test_pruned_figure_still_realizes(self, backend: SolverBackend) -> None:
        """The point of the exercise: what survives must still be a drawable figure."""
        pruning = prune_figure(_construction(), frozenset({"a", "b", "c"}))
        figure = backend.realize(pruning.construction(_construction()).to_spec(), OPTS)
        assert figure.ok
