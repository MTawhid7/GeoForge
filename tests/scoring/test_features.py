"""The docs/05 §5.1 features, over the real corpus and over hand-built edge cases.

The corpus tests are the ones that would catch a feature quietly measuring the wrong graph;
the unit tests are the ones that can reach values the corpus never produces.

Two measured facts are asserted rather than left as folklore, because both look like bugs to
someone reading the numbers cold: `goal_given_distance` is 0 for every puzzle this pipeline
currently makes, and `nice_penalty` takes exactly one value. Both have causes, both are
recorded, and both are things a future sampler change should be allowed to break loudly.
"""

from __future__ import annotations

import pytest

from geoforge.config import FILTERS, SCORING
from geoforge.generator.batch import BatchReport, CandidatePuzzle, run
from geoforge.generator.translation.templates import ALGEBRAIC, is_geometric
from geoforge.scoring.features import measure

BATCH_N = 300
SEED = 42


@pytest.fixture(scope="module")
def report() -> BatchReport:
    return run(BATCH_N, SEED)


@pytest.fixture(scope="module")
def candidates(report: BatchReport) -> list[CandidatePuzzle]:
    assert report.puzzles, "no puzzles: every assertion below would be vacuous"
    return report.puzzles


class TestAgainstTheCorpus:
    def test_features_are_measured_over_the_minimal_subdag(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        """The graph docs/05 §5.1 names. Reading the whole solve instead would publish
        conceptual variety the shipped solution never shows (the F-2 defect, in feature form)."""
        for candidate in candidates:
            subdag = candidate.derivation.subdag
            assert candidate.features.depth == subdag.depth
            assert candidate.features.width == subdag.width
            assert candidate.features.distinct_rules == subdag.distinct_rules

    def test_published_steps_matches_the_translation(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates:
            assert candidate.features.published_steps == len(candidate.translation.steps)

    def test_geometric_steps_excludes_the_algebraic_idiom(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates:
            expected = sum(1 for s in candidate.translation.steps if is_geometric(s.rule))
            assert candidate.features.geometric_steps == expected

    def test_the_algebraic_idiom_really_is_everywhere(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        """MEASURED: `combine` appears in 118 of 118 puzzles at seed 42. This is the fact that
        forced the monotony filter to count geometric steps — a rule in every single puzzle
        measures how often the engine did arithmetic, not whether a solution is repetitive."""
        with_algebra = sum(
            1 for c in candidates if any(s.rule in ALGEBRAIC for s in c.translation.steps)
        )
        assert with_algebra == len(candidates)

    def test_every_surviving_puzzle_passes_every_filter(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        from geoforge.scoring.filters import check

        for candidate in candidates:
            assert check(candidate.features).ok, candidate.id

    def test_the_figure_measured_is_the_figure_drawn(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        """`n_points` must count the *pruned* construction. Counting the unpruned one would
        let scaffolding nobody sees push a puzzle over the complexity filter."""
        for candidate in candidates:
            assert candidate.features.n_points == len(candidate.pruned.points)
            assert candidate.features.n_points <= FILTERS.max_points

    def test_measurement_is_a_pure_function(self, candidates: list[CandidatePuzzle]) -> None:
        for candidate in candidates[:5]:
            again = measure(candidate.derivation, candidate.translation, candidate.pruned)
            assert again == candidate.features

    def test_scores_are_in_range_and_bands_agree_with_them(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        from geoforge.scoring.score import band_for

        for candidate in candidates:
            assert 0.0 <= candidate.score <= SCORING.scale
            assert candidate.band == band_for(candidate.score)
            assert candidate.puzzle.difficulty.score == candidate.score


class TestMeasuredConstants:
    """Which features actually vary across the corpus. Asserted, not hidden.

    A constant feature contributes a fixed offset and no discrimination. Leaving that
    undocumented invites someone to retune its weight and conclude the model is broken when
    nothing moves.

    **Rewritten in Phase 3 M4, because M4 existed to break two of these.** The previous version
    asserted that `nice_penalty` took exactly one value and that no answer was ever telegraphed
    by a given, and named the cause in its own docstring: the batch runner never passed a band
    to `sample_construction`, so every construction drew its angles from the easy palette. Both
    are now false, which is the point — a test that pins a defect has to be updated when the
    defect is fixed, or it starts defending it.
    """

    def test_goal_given_distance_is_always_zero(self, candidates: list[CandidatePuzzle]) -> None:
        """Cause: figures run 3-8 points and the premises name nearly all of them, so the goal's
        points are always among the givens' points. The feature discriminates on larger figures
        and is kept for them (docs/05 §5.3). Unchanged by M4 — the profiles widened the step
        range but not enough to separate goal from givens."""
        assert {c.features.goal_given_distance for c in candidates} == {0}

    def test_nice_penalty_now_varies(self, candidates: list[CandidatePuzzle]) -> None:
        """The band reaches the sampler, so the penalty can finally tell puzzles apart.

        This is the assertion the old `..._is_constant_because_the_sampler_only_makes_round_
        angles` becomes. With the band threaded through (docs/04 Stage 1) and the upper bands
        drawing non-round givens (docs/07 T18), a weight on `nice_penalty` does something for
        the first time.
        """
        assert len({c.features.nice_penalty for c in candidates}) > 1

    def test_an_answer_equal_to_a_given_is_possible_and_penalised(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        """The discriminating half of the penalty, which now has something to discriminate.

        Previously zero hits corpus-wide. Once Stage 2 states real angles, a puzzle can state
        50 degrees and answer 50 degrees at a different vertex — not caught by Stage 5's
        `already_given`, which compares *facts* rather than *values*, and exactly what the
        penalty is for. Asserted as "the penalty reflects it" rather than "it never happens",
        because it does happen and pretending otherwise is how the check rots.
        """
        from geoforge.scoring.features import _degrees

        for candidate in candidates:
            goal = _degrees(candidate.derivation.goal)
            givens = {_degrees(f) for f in candidate.derivation.premises}
            if goal is not None and goal in givens:
                assert candidate.features.nice_penalty > 0.0, (
                    f"{candidate.id}: answer {goal} is stated among the givens and pays nothing"
                )


class TestAuxiliaryDetectionCannotFire:
    """Phase 3 M5. docs/05 §5.1a specified `requires_auxiliary` as
    `subdag.points() - needed_points()` and framed a zero reading as a fact about the corpus
    ("expected near-zero on current output; that measurement is a deliverable"). It is not a fact
    about the corpus — the quantity cannot be non-empty, and these tests pin why.

    They are written to **fail loudly** if that ever changes. A pipeline that could produce a
    genuine auxiliary point would break `test_no_puzzle_needs_a_point_its_givens_do_not_name`,
    and that break would be the good news doc 07 L1 is waiting for, not a regression.
    """

    def test_no_puzzle_needs_a_point_its_givens_do_not_name(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates:
            derivation = candidate.derivation
            assert not derivation.subdag.points() - derivation.needed_points(), candidate.id

    def test_the_reason_is_containment_not_luck(self, candidates: list[CandidatePuzzle]) -> None:
        """Every sub-DAG point enters through one of the sub-DAG's own leaves.

        Forward chaining binds a rule's conclusion only to points its premises already name, so
        the fact set cannot introduce a point from nowhere. `needed_points()` covers the premises
        and configuration but not the tautologies, which is the single gap through which the
        difference could in principle be non-empty — and it never is, because a tautology names
        points the derivation is already about.
        """
        for candidate in candidates:
            subdag = candidate.derivation.subdag
            leaves = frozenset(
                arg
                for fact in (*subdag.premises, *subdag.configuration, *subdag.trivial)
                for arg in fact.args
            )
            assert subdag.points() <= leaves | frozenset(candidate.derivation.goal.args)

    def test_it_reports_empty_even_on_a_real_auxiliary_construction(self) -> None:
        """The case that settles it. `langley_with_auxiliary` is the one construction in this
        repo that genuinely cannot be solved without an auxiliary line, and it is spelled with
        the line included (docs/03 §3.3).

        The metric still reports empty, because the auxiliary point is named by a premise
        (`aconst:a:c:a:d=1/9`). Any constructed point becomes a stated given the moment the proof
        uses it, so the metric is blind to exactly the thing it is named for — which is a
        statement about the definition, not about this fixture.
        """
        from geoforge.generator.traceback import derive
        from geoforge.solvers.interface import get_backend
        from geoforge.solvers.types import SolveOptions
        from tests.solvers.corpus import CORPUS

        backend = get_backend()
        opts = SolveOptions(seed=SEED)
        result = backend.solve(CORPUS["langley_with_auxiliary"], opts)
        assert result.proof_dag.proved_goals, "the fixture must still solve"

        goal_id = result.proof_dag.proved_goals[0]
        goal = result.proof_dag.index()[goal_id]
        derivation = derive(backend, result.numeric_model, result.proof_dag, goal, opts)
        assert derivation is not None

        assert "d" in derivation.subdag.points(), "the auxiliary point must be in the proof"
        assert "d" in derivation.needed_points(), "and it is named by a premise, which is the point"
        assert not derivation.subdag.points() - derivation.needed_points()


class TestUnusedPoints:
    """The replacement feature: drawn points the proof does not need."""

    def test_it_matches_its_definition(self, candidates: list[CandidatePuzzle]) -> None:
        for candidate in candidates:
            expected = frozenset(candidate.pruned.points) - candidate.derivation.needed_points()
            assert candidate.features.unused_points == len(expected), candidate.id

    def test_it_is_bounded_by_the_drawn_figure(self, candidates: list[CandidatePuzzle]) -> None:
        for candidate in candidates:
            assert 0 <= candidate.features.unused_points <= candidate.features.n_points

    def test_it_actually_varies(self, candidates: list[CandidatePuzzle]) -> None:
        """Unlike the feature it replaces. If this ever collapses to a single value it has become
        another fixed offset and should be removed rather than left looking like a signal."""
        assert len({c.features.unused_points for c in candidates}) > 1

    def test_it_carries_no_weight_in_the_score(self) -> None:
        """The regression that matters, and the reason this test exists at all.

        `unused_points` looks like a difficulty feature and is not one. Measured over 163 puzzles
        at seed 42 it correlates **+0.777 with figure size** and -0.05 to -0.15 with depth, width,
        distinct_rules, branch_join and the score itself; mean unused is 1.80 in easy and 2.11 in
        hard but 0.00 in expert. Weighting it positively would score big rambling figures as hard
        — the same anti-correlation doc 07 T19 records for proof depth, which is the mistake this
        whole phase exists to undo.

        So: adding a weight must break a test and force whoever does it to re-measure first.
        """
        assert "unused_points" not in SCORING.weights
        assert "unused_points" not in SCORING.ranges


class TestBranchJoins:
    def test_a_join_needs_two_derived_premises(self, candidates: list[CandidatePuzzle]) -> None:
        """Premises do not count: a step resting on two givens is one idea, not a join of two
        independent sub-arguments. So the count can never exceed the number of steps."""
        for candidate in candidates:
            assert 0 <= candidate.features.branch_join <= candidate.features.width

    def test_the_corpus_actually_contains_joins(self, candidates: list[CandidatePuzzle]) -> None:
        """A feature that is always zero is a weight doing nothing. MEASURED: 41 of 105 puzzles
        have at least one join, up to 5."""
        assert max(c.features.branch_join for c in candidates) > 0
