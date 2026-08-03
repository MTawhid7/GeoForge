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
    """Two features take one value across the whole corpus. Asserted, not hidden.

    A constant feature contributes a fixed offset and no discrimination. Leaving that
    undocumented invites someone to retune its weight and conclude the model is broken when
    nothing moves.
    """

    def test_goal_given_distance_is_always_zero(self, candidates: list[CandidatePuzzle]) -> None:
        """Cause: figures run 3-8 points and the premises name nearly all of them, so the goal's
        points are always among the givens' points. The feature discriminates on larger figures
        and is kept for them (docs/05 §5.3)."""
        assert {c.features.goal_given_distance for c in candidates} == {0}

    def test_nice_penalty_is_constant_because_the_sampler_only_makes_round_angles(
        self, candidates: list[CandidatePuzzle]
    ) -> None:
        """Cause: `sample_construction` is never passed a band, so every construction draws its
        given angles from the *easy* palette — multiples of 10 (`GENERATION.nice_angle_degrees`).
        Band-targeted sampling is M6; until then every answer is round and the penalty cannot
        tell puzzles apart. It is the same plumbing gap, seen from the other end."""
        assert len({c.features.nice_penalty for c in candidates}) == 1

    def test_no_answer_is_telegraphed_by_a_given(self, candidates: list[CandidatePuzzle]) -> None:
        """The discriminating half of the penalty. Zero hits, and Stage 5's `already_given`
        rejection is why — but that one compares *facts*, and this compares *values*, so they
        are not the same check and this one is worth keeping."""
        from geoforge.scoring.features import _degrees

        for candidate in candidates:
            goal = _degrees(candidate.derivation.goal)
            givens = {_degrees(f) for f in candidate.derivation.premises}
            assert goal is None or goal not in givens, candidate.id


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
