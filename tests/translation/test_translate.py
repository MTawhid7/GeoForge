"""Stage 7: the readability gate and the solutions that pass it (docs/04, docs/03 §3.5).

The golden solutions are engine-backed and written out in full. They are the product: if one of
them changes, a player's reading experience changed, and that should be a deliberate edit rather
than a diff nobody looked at.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

import pytest

from geoforge.generator.extract import extract_goals
from geoforge.generator.traceback import SubDAG, derive
from geoforge.generator.translation import FailureReason, translate, unspeakable_givens
from geoforge.generator.translation.phrases import Phrase, describe
from geoforge.solvers import ProblemSpec, get_backend
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import (
    Fact,
    FactKind,
    Justification,
    JustificationKind,
    ProofStep,
    SolveOptions,
)
from tests.translation.test_phrases import HIGHLIGHT_GRAMMAR

OPTS = SolveOptions(seed=42)

THALES = "a b = segment a b; o = midpoint o a b; c = on_circle c o a"
INSCRIBED = "a b = segment a b; c = s_angle a b c 50o; o = circle o a b c; d = on_circum d a b c"


@pytest.fixture(scope="module")
def backend() -> SolverBackend:
    return get_backend()


def solve(backend: SolverBackend, jgex: str):  # type: ignore[no-untyped-def]
    figure = backend.realize(ProblemSpec(construction=jgex), OPTS)
    goal = extract_goals(backend, figure, OPTS, max_goals=1, reject_sight_readable=False).goals[0]
    derivation = derive(backend, figure.points, goal.result.proof_dag, goal.fact, OPTS)
    assert derivation is not None
    return figure, goal, derivation, translate(derivation.subdag, figure.coords())


class TestGoldenSolutions:
    def test_thales(self, backend: SolverBackend) -> None:
        """docs/03 §3.5: translation is compression. Ten machine steps, six sentences."""
        _, goal, derivation, translation = solve(backend, THALES)
        assert goal.fact.degrees() == 90
        assert translation.ok
        assert len(derivation.subdag.steps) == 10
        assert [step.text for step in translation.steps] == [
            "AO = CO, so the base angles are equal: ∠CAO = ∠OCA.",
            "O is the midpoint of AB, so AB = 2 · AO.",
            "O is the midpoint of AB, so AB = 2 · BO.",
            "Combining AO = CO, AB = 2 · AO and AB = 2 · BO, we get BO = CO.",
            "BO = CO, so the base angles are equal: ∠CBO = ∠OCB.",
            "Combining ∠CAO = ∠OCA and ∠CBO = ∠OCB, we get ∠ACB = 90°.",
        ]

    def test_inscribed_angle(self, backend: SolverBackend) -> None:
        _, goal, _, translation = solve(backend, INSCRIBED)
        assert translation.ok
        assert translation.steps[0].text == (
            "O is the centre of the circle through A, B and C, "
            "so radii of that circle are equal: AO = CO."
        )
        assert translation.steps[-1].text.endswith("we get ∠OCA = 40°.")

    def test_no_machine_idiom_reaches_the_player(self, backend: SolverBackend) -> None:
        """No triangle similar to itself, and no ratio of a segment to itself."""
        for jgex in (THALES, INSCRIBED):
            _, _, _, translation = solve(backend, jgex)
            for step in translation.steps:
                assert not re.search(r"triangles (\w+) and \1 are", step.text)
                assert not re.search(r"(\b\w\w\b) : \1\b", step.text)


class TestStepStructure:
    def test_steps_are_numbered_from_one(self, backend: SolverBackend) -> None:
        _, _, _, translation = solve(backend, THALES)
        assert [s.step for s in translation.steps] == list(range(1, len(translation.steps) + 1))

    def test_premises_are_established_before_they_are_used(self, backend: SolverBackend) -> None:
        """A reader cannot follow a step that rests on something stated later."""
        _, _, derivation, translation = solve(backend, THALES)
        derived_by = {step.conclusion for step in derivation.subdag.steps}
        established: set[str] = set()
        by_conclusion = {s.conclusion: s for s in derivation.subdag.steps}
        for step in translation.steps:
            proof_step = by_conclusion[step.derives]
            for premise in proof_step.premises:
                if premise in derived_by:
                    assert premise in established or premise not in {
                        s.derives for s in translation.steps
                    }, f"step {step.step} uses {premise} before it is established"
            established.add(step.derives)

    def test_final_step_derives_the_goal(self, backend: SolverBackend) -> None:
        _, goal, _, translation = solve(backend, THALES)
        assert translation.steps[-1].derives == goal.fact.fact_id

    def test_highlights_follow_the_normative_grammar(self, backend: SolverBackend) -> None:
        for jgex in (THALES, INSCRIBED):
            _, _, _, translation = solve(backend, jgex)
            for step in translation.steps:
                assert step.highlights
                for highlight in step.highlights:
                    assert HIGHLIGHT_GRAMMAR.match(highlight), highlight

    def test_rule_is_a_template_id_not_an_engine_rule(self, backend: SolverBackend) -> None:
        """`solution[].rule` is public API and must not leak `r53` at a player."""
        _, _, _, translation = solve(backend, THALES)
        for step in translation.steps:
            assert not re.match(r"^r\d+$", step.rule)

    def test_translation_is_deterministic(self, backend: SolverBackend) -> None:
        first = solve(backend, THALES)[3]
        second = solve(backend, THALES)[3]
        assert first == second


class TestTheGate:
    """docs/03 §3.5 item 3: a puzzle ships only if *every* step translates."""

    def _subdag(self, justification: Justification, n_premises: int) -> SubDAG:
        premises = tuple(
            Fact(kind=FactKind.CONGRUENT, args=("a", "b", f"c{i}", "d")) for i in range(n_premises)
        )
        goal = Fact(kind=FactKind.CONSTANT_ANGLE, args=("b", "a", "b", "c"), value=Fraction(1, 2))
        step = ProofStep(
            conclusion=goal.fact_id,
            premises=tuple(p.fact_id for p in premises),
            justification=justification,
        )
        return SubDAG(
            goal=goal.fact_id,
            facts=(*premises, goal),
            steps=(step,),
            premises=premises,
            configuration=(),
        )

    def test_unknown_rule_fails_the_gate(self) -> None:
        subdag = self._subdag(
            Justification(
                kind=JustificationKind.RULE_APPLICATION, rule_id="r99", rule_name="Mystery"
            ),
            1,
        )
        translation = translate(subdag, {"a": (1.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 1.0)})
        assert not translation.ok
        assert translation.failures[0].reason is FailureReason.UNKNOWN_RULE
        assert "r99" in translation.failures[0].detail, "the discard log must name the rule"

    def test_overlong_ar_chain_fails_the_gate(self) -> None:
        """Phase 0 measured the budget at 5 premises: no wording makes a 14-premise linear
        combination readable."""
        subdag = self._subdag(
            Justification(kind=JustificationKind.AR_DEDUCTION, ar_reason="Angle Chasing"), 9
        )
        translation = translate(subdag, {"a": (1.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 1.0)})
        assert not translation.ok
        assert translation.failures[0].reason is FailureReason.AR_CHAIN_TOO_LONG

    def test_ar_chain_within_budget_passes(self) -> None:
        subdag = self._subdag(
            Justification(kind=JustificationKind.AR_DEDUCTION, ar_reason="Angle Chasing"), 3
        )
        translation = translate(subdag, {"a": (1.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 1.0)})
        assert translation.ok
        assert translation.steps[0].rule == "combine"

    def test_unspeakable_conclusion_fails_the_gate(self) -> None:
        """An angle between two lines that never meet has no ∠ABC spelling."""
        premise = Fact(kind=FactKind.CONGRUENT, args=("a", "b", "c", "d"))
        goal = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "c", "d"), value=Fraction(1, 4))
        subdag = SubDAG(
            goal=goal.fact_id,
            facts=(premise, goal),
            steps=(
                ProofStep(
                    conclusion=goal.fact_id,
                    premises=(premise.fact_id,),
                    justification=Justification(
                        kind=JustificationKind.AR_DEDUCTION, ar_reason="Angle Chasing"
                    ),
                ),
            ),
            premises=(premise,),
            configuration=(),
        )
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.0, 1.0), "d": (1.0, 1.0)}
        translation = translate(subdag, coords)
        assert not translation.ok
        assert translation.failures[0].reason is FailureReason.UNSPEAKABLE_CONCLUSION

    def test_an_unspeakable_given_fails_the_gate(self) -> None:
        """The half `translate` cannot see: a *stated given* with no human phrasing.

        `aconst a c d e` is a directed angle between lines AC and DE, which share no named
        point, so there is no ∠ABC to write. It reached shipped output before Phase 2 —
        gf-000042000213-1 carried exactly this fact among its givens — because the gate only
        ever looked at steps. A puzzle missing one of its hypotheses is unshippable however
        readable its proof is.
        """
        mute = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "c", "d", "e"), value=Fraction(1, 9))
        coords = {
            "a": (0.0, 0.0),
            "c": (1.0, 0.0),
            "d": (0.0, 1.0),
            "e": (1.0, 1.6),
        }
        failures = unspeakable_givens([mute], coords)
        assert failures
        assert failures[0].reason is FailureReason.UNSPEAKABLE_GIVEN
        assert failures[0].detail == mute.fact_id, "the discard log must name the given"

    def test_a_speakable_given_passes(self) -> None:
        """The near-miss: same fact kind and same value, on two lines that *do* meet at a named
        point. Without this the gate could reject every `aconst` and still look correct.

        The coordinates have to realize the stated 20° at C, because the renderer resolves the
        directed value against the diagram to decide between ∠ACE and its supplement.
        """
        spoken = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "c", "c", "e"), value=Fraction(1, 9))
        twenty = math.radians(20)
        coords = {"a": (1.0, 0.0), "c": (0.0, 0.0), "e": (math.cos(twenty), math.sin(twenty))}
        assert unspeakable_givens([spoken], coords) == ()
        assert describe(spoken, coords) == Phrase(text="∠ACE = 20°", highlights=("angle:A:C:E",))

    def test_configuration_facts_would_fail_and_must_not_be_passed(self) -> None:
        """Why the call site passes the minimized premises and not every leaf.

        `is_speakable` refuses configuration facts on purpose — "A, B and C are not collinear"
        says what the figure already shows. So handing them to this gate flags every one of
        them, and since nearly every puzzle carries at least one, the batch would empty out.
        The gate is deliberately not defensive about this: it asks "can this be stated?", and
        deciding *what the puzzle states* belongs to Stage 6, not here.
        """
        config = Fact(kind=FactKind.N_COLLINEAR, args=("a", "b", "c"))
        assert config.is_configuration
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.0, 1.0)}
        assert unspeakable_givens([config], coords), "the hazard this test documents"

    def test_suppressed_steps_are_not_failures(self, backend: SolverBackend) -> None:
        """Engine bookkeeping is dropped from the text, and the puzzle still ships."""
        _, _, _, translation = solve(backend, THALES)
        assert translation.suppressed > 0
        assert translation.ok
        assert not translation.failures


class TestFigurePruningInput:
    def test_highlighted_points_are_offered_to_stage_six(self, backend: SolverBackend) -> None:
        """docs/04 Stage 6: pruning must keep anything a solution step highlights, because a step
        may name a segment its premises only imply."""
        _, _, derivation, translation = solve(backend, THALES)
        needed = derivation.needed_points() | translation.highlighted_points()
        assert {"a", "b", "c", "o"} <= needed
