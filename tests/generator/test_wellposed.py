"""Stage 8: the well-posedness gate (docs/04).

The gate's value is entirely in what it rejects, so the tests that matter are the negative ones —
including a real underdetermined puzzle found by the very first batch run, kept here as a fixture.
"""

from __future__ import annotations

import dataclasses
from fractions import Fraction

import pytest

from geoforge.generator import quantities, wellposed
from geoforge.generator.construction import Construction, Step
from geoforge.generator.extract import extract_goals
from geoforge.generator.traceback import Derivation, derive
from geoforge.generator.translation import translate
from geoforge.generator.wellposed import WellPosedReason
from geoforge.solvers import get_backend
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import Fact, FactKind, SolveOptions

THALES = "a b = segment a b; o = midpoint o a b; c = on_circle c o a"

#: Found by the first M5 batch run at seed 42000014, and the reason docs/04 Stage 8 item 3 was
#: amended (docs/07 T13). Every stated premise and every recorded configuration fact holds in a
#: resampled figure, and the answer is still 75° in one and 15° in the other.
UNDERDETERMINED = (
    "a b c d = eqdia_quadrangle a b c d; e f = square e f a b; "
    "g h = contri g h b d e a; i = eq_triangle i a f; j = on_circum j g e d"
)
UNDERDETERMINED_SEED = 42000014


@pytest.fixture(scope="module")
def backend() -> SolverBackend:
    return get_backend()


def _parse(jgex: str) -> Construction:
    steps = []
    for clause in jgex.split("; "):
        lhs, _, rhs = clause.partition(" = ")
        tokens = rhs.split()
        steps.append(
            Step(construction=tokens[0], outputs=tuple(lhs.split()), args=tuple(tokens[1:]))
        )
    return Construction(steps=tuple(steps))


def _pipeline(backend: SolverBackend, jgex: str, seed: int, goal_id: str | None = None):  # type: ignore[no-untyped-def]
    opts = SolveOptions(seed=seed)
    construction = _parse(jgex)
    figure = backend.realize(construction.to_spec(), opts)
    coords = figure.coords()
    for goal in extract_goals(backend, figure, opts, reject_sight_readable=False).goals:
        if goal_id is not None and goal.fact.fact_id != goal_id:
            continue
        derivation = derive(backend, figure.points, goal.proof_dag, goal.fact, opts)
        assert derivation is not None
        translation = translate(derivation.subdag, coords)
        # Through the registry, exactly as Stage 8 does: the gate takes a `Claim`, not a
        # vertex angle, since docs/10 A4.
        claim = quantities.get(goal.quantity_type).claim_of(goal.fact, coords)
        assert claim is not None
        return construction, derivation, translation, claim, coords
    raise AssertionError("no goal extracted")


class TestWellPosedPuzzles:
    def test_thales_is_well_posed(self, backend: SolverBackend) -> None:
        construction, derivation, translation, claim, coords = _pipeline(backend, THALES, 42)
        verdict = wellposed.check(backend, construction, derivation, translation, claim, coords, 42)
        assert verdict.ok
        assert verdict.samples_accepted >= 1
        assert verdict.reason is None

    def test_verdict_reports_how_many_samples_it_used(self, backend: SolverBackend) -> None:
        """A gate that certifies on zero samples certifies nothing."""
        construction, derivation, translation, claim, coords = _pipeline(backend, THALES, 42)
        verdict = wellposed.check(backend, construction, derivation, translation, claim, coords, 42)
        assert verdict.samples_accepted + verdict.samples_rejected > 0


class TestUnderdetermined:
    """The case the gate exists for, and the one that changed docs/04 Stage 8."""

    def test_underdetermined_goal_is_caught(self, backend: SolverBackend) -> None:
        construction, derivation, translation, claim, coords = _pipeline(
            backend, UNDERDETERMINED, UNDERDETERMINED_SEED, "aconst:b:i:a:b=5/12"
        )
        verdict = wellposed.check(
            backend,
            construction,
            derivation,
            translation,
            claim,
            coords,
            UNDERDETERMINED_SEED,
        )
        assert not verdict.ok
        assert verdict.reason in (
            WellPosedReason.GOAL_UNDERDETERMINED,
            WellPosedReason.STEP_UNDERDETERMINED,
        )

    def test_premises_and_configuration_really_do_hold_in_the_other_figure(
        self, backend: SolverBackend
    ) -> None:
        """Pins *why* this puzzle is underdetermined rather than merely rejected.

        Everything the puzzle states is true of both figures, and the answer still differs — so
        the statement, not the sampling, is what fails to pin the answer. If this ever starts
        failing, the recorded facts have become a complete description and the amendment to
        docs/04 Stage 8 should be revisited.
        """
        construction, derivation, _, _, _ = _pipeline(
            backend, UNDERDETERMINED, UNDERDETERMINED_SEED, "aconst:b:i:a:b=5/12"
        )
        other = backend.realize(
            construction.to_spec(), SolveOptions(seed=UNDERDETERMINED_SEED + 1_000_003)
        )
        stated = derivation.premises + derivation.configuration
        assert all(backend.check_facts(other.points, stated))
        assert not all(backend.check_facts(other.points, (derivation.goal,)))

    def test_underdetermination_is_not_a_soundness_failure(self, backend: SolverBackend) -> None:
        """docs/07 T13: this is the gate working. Counting it as a build-failing bug would cry
        wolf and bury the one failure that does indict the engine."""
        construction, derivation, translation, claim, coords = _pipeline(
            backend, UNDERDETERMINED, UNDERDETERMINED_SEED, "aconst:b:i:a:b=5/12"
        )
        verdict = wellposed.check(
            backend,
            construction,
            derivation,
            translation,
            claim,
            coords,
            UNDERDETERMINED_SEED,
        )
        assert verdict.is_underdetermined
        assert not verdict.is_soundness_failure
        assert verdict.reproduction, "a discard still files a reproduction case for analysis"


class TestSoundnessFailure:
    def test_engine_contradicting_its_own_diagram_fails_the_build(
        self, backend: SolverBackend
    ) -> None:
        """The one verdict that indicts the engine rather than the puzzle. Simulated by claiming a
        goal value the reference figure does not show — exactly what an unsound derivation would
        hand us."""
        construction, derivation, translation, claim, coords = _pipeline(backend, THALES, 42)
        wrong = Fact(kind=derivation.goal.kind, args=derivation.goal.args, value=Fraction(1, 3))
        corrupted = Derivation(
            goal=wrong,
            subdag=derivation.subdag,
            premises=derivation.premises,
            configuration=derivation.configuration,
            dropped_premises=derivation.dropped_premises,
        )
        verdict = wellposed.check(backend, construction, corrupted, translation, claim, coords, 42)
        assert not verdict.ok
        assert verdict.reason is WellPosedReason.ENGINE_CONTRADICTS_DIAGRAM
        assert verdict.is_soundness_failure
        assert verdict.reproduction


class TestPublishedAnswerMatchesTheFigure:
    def test_answer_disagreeing_with_the_reference_figure_is_rejected(
        self, backend: SolverBackend
    ) -> None:
        """If the published answer is not what the shipped figure shows, every later comparison
        is against the wrong number and resampling would never notice."""
        construction, derivation, translation, claim, coords = _pipeline(backend, THALES, 42)
        verdict = wellposed.check(
            backend,
            construction,
            derivation,
            translation,
            dataclasses.replace(claim, approx=31.0, exact="31", display="31°"),
            coords,
            42,
        )
        assert not verdict.ok
        assert verdict.reason is WellPosedReason.UNMEASURABLE


class TestConfigurationMatching:
    def test_a_flipped_sample_is_discarded_not_counted_against_the_puzzle(
        self, backend: SolverBackend
    ) -> None:
        """A configuration flip is a legitimately different figure. Treating it as evidence of
        ill-posedness would reject nearly every good puzzle."""
        construction, derivation, translation, claim, coords = _pipeline(backend, THALES, 42)
        impossible = derivation.configuration + (
            Fact(kind=FactKind.COLLINEAR, args=("a", "b", "c")),
        )
        forced = Derivation(
            goal=derivation.goal,
            subdag=derivation.subdag,
            premises=derivation.premises,
            configuration=impossible,
            dropped_premises=derivation.dropped_premises,
        )
        verdict = wellposed.check(backend, construction, forced, translation, claim, coords, 42)
        assert not verdict.ok
        assert verdict.reason is WellPosedReason.TOO_FEW_SAMPLES
        assert verdict.samples_rejected > 0
        assert not verdict.is_soundness_failure
