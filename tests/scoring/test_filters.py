"""The docs/05 §5.2 hard rejection filters.

**Every filter gets a reject/near-miss pair.** A filter asserted only on a clear reject passes
on an implementation that rejects everything, and a threshold asserted only from one side is a
threshold nobody has checked. So each test names a value that must be refused and the adjacent
value that must be kept.

Filter 5 gets more than that. It is supposed to be unreachable — measured over 1,200
constructions at seed 42 it never fires — and "a gate that never fires is untested" applies
hardest to the gate that is meant never to fire. It is made to fire here on purpose.
"""

from __future__ import annotations

import dataclasses

import pytest

from geoforge.config import FILTERS
from geoforge.generator.traceback import Derivation, SubDAG
from geoforge.scoring.features import Features
from geoforge.scoring.filters import (
    Rejection,
    UnusedGivenBug,
    assert_every_given_is_used,
    check,
    unused_givens,
)
from geoforge.solvers.types import Fact, FactKind

GOOD = Features(
    depth=5,
    width=6,
    distinct_rules=4,
    tier_max=3,
    tier_mix=2,
    branch_join=1,
    nice_penalty=0.0,
    published_steps=5,
    geometric_steps=4,
    distinct_templates=3,
    rule_share_max=0.5,
    n_points=5,
    n_circles=1,
    n_premises=3,
    construction_steps=4,
    goal_given_distance=0,
)


def with_(**changes: object) -> Features:
    return dataclasses.replace(GOOD, **changes)  # type: ignore[arg-type]


def reasons(features: Features) -> set[Rejection]:
    return set(check(features).rejections)


class TestNothingRejectsAGoodPuzzle:
    def test_the_baseline_survives(self) -> None:
        """The near-miss for the whole module: without it every pair below could pass on a
        filter that rejects unconditionally."""
        assert check(GOOD).ok


class TestFilter1TooShallow:
    def test_below_the_depth_floor_is_rejected_and_at_it_is_kept(self) -> None:
        assert Rejection.TOO_SHALLOW in reasons(with_(depth=FILTERS.min_depth - 1))
        assert Rejection.TOO_SHALLOW not in reasons(with_(depth=FILTERS.min_depth))

    def test_below_the_rule_floor_is_rejected_and_at_it_is_kept(self) -> None:
        low = FILTERS.min_distinct_rules
        assert Rejection.TOO_SHALLOW in reasons(with_(distinct_rules=low - 1))
        assert Rejection.TOO_SHALLOW not in reasons(with_(distinct_rules=low))


class TestFilter2ReadOffThePicture:
    def test_a_solution_of_pure_algebra_is_rejected(self) -> None:
        """MEASURED: all 4 such puzzles in 118 are a single `combine` sentence at depth 3 —
        the answer follows from the givens by arithmetic with no geometry in between."""
        assert Rejection.READ_OFF_THE_PICTURE in reasons(with_(geometric_steps=0))

    def test_one_geometric_step_is_enough(self) -> None:
        assert Rejection.READ_OFF_THE_PICTURE not in reasons(with_(geometric_steps=1))


class TestFilter3Monotonous:
    def test_a_dominated_solution_is_rejected(self) -> None:
        share = FILTERS.max_rule_share
        assert Rejection.MONOTONOUS in reasons(with_(rule_share_max=share + 0.01))

    def test_exactly_at_the_threshold_is_kept(self) -> None:
        """docs/05 says "> 60%", so 60% itself is not monotonous. The difference matters: at
        0.6 the filter takes 8 of 118 and at 0.75 it takes none at all."""
        assert Rejection.MONOTONOUS not in reasons(with_(rule_share_max=FILTERS.max_rule_share))

    def test_a_short_solution_is_not_monotonous_by_arithmetic(self) -> None:
        """`measure` reports 0 below `min_steps_for_share`, so a one-step solution never
        arrives here as "100% one rule". This pins the consequence: 66 of 118 measured puzzles
        have exactly one geometric step and none of them may be rejected for it."""
        from geoforge.scoring.features import _rule_share

        assert _rule_share(("isosceles_base_angles",)) == 0.0
        assert _rule_share(("isosceles_base_angles", "isosceles_base_angles")) == 0.0
        many = ("isosceles_base_angles",) * FILTERS.min_steps_for_share
        assert _rule_share(many) == 1.0


class TestFilter4FigureComplexity:
    def test_too_few_points_is_rejected_and_the_floor_is_kept(self) -> None:
        assert Rejection.FIGURE_TOO_SIMPLE in reasons(with_(n_points=FILTERS.min_points - 1))
        assert Rejection.FIGURE_TOO_SIMPLE not in reasons(with_(n_points=FILTERS.min_points))

    def test_too_many_points_is_rejected_and_the_ceiling_is_kept(self) -> None:
        assert Rejection.FIGURE_TOO_COMPLEX in reasons(with_(n_points=FILTERS.max_points + 1))
        assert Rejection.FIGURE_TOO_COMPLEX not in reasons(with_(n_points=FILTERS.max_points))

    def test_too_many_circles_is_rejected_and_the_ceiling_is_kept(self) -> None:
        assert Rejection.TOO_MANY_CIRCLES in reasons(with_(n_circles=FILTERS.max_circles + 1))
        assert Rejection.TOO_MANY_CIRCLES not in reasons(with_(n_circles=FILTERS.max_circles))

    def test_the_two_ends_are_distinguishable(self) -> None:
        """One `figure_complexity` reason would leave the attrition report unable to say which
        end of the range was hit, which is the only actionable part of the number."""
        assert reasons(with_(n_points=1)) != reasons(with_(n_points=99))


class TestFilter5UnusedGiven:
    """docs/05: "must be impossible after Stage-6 minimization; a hit is a bug report".

    MEASURED: it never fires on real output — 0 hits across 1,200 constructions at seed 42.
    That makes these the only tests that can say the check works at all.
    """

    def _fact(self, fact_id: str) -> Fact:
        kind, rest = fact_id.split(":", 1)
        return Fact(kind=FactKind(kind), args=tuple(rest.split(":")))

    def _derivation(self, stated: list[str], used: list[str]) -> Derivation:
        goal = self._fact("aconst:a:b:b:c")
        subdag = SubDAG(
            goal=goal.fact_id,
            facts=(),
            steps=(),
            premises=tuple(self._fact(f) for f in used),
            configuration=(),
        )
        return Derivation(
            goal=goal,
            subdag=subdag,
            premises=tuple(self._fact(f) for f in stated),
            configuration=(),
            dropped_premises=(),
        )

    def test_it_raises_rather_than_returning_a_verdict(self) -> None:
        """A returned verdict would be counted as attrition and disappear into a report line,
        which is the same as not noticing."""
        derivation = self._derivation(
            stated=["cong:a:b:a:c", "para:a:b:c:d"], used=["cong:a:b:a:c"]
        )
        with pytest.raises(UnusedGivenBug, match="para:a:b:c:d"):
            assert_every_given_is_used(derivation)

    def test_it_names_the_offending_given(self) -> None:
        derivation = self._derivation(
            stated=["cong:a:b:a:c", "para:a:b:c:d"], used=["cong:a:b:a:c"]
        )
        assert unused_givens(derivation) == ("para:a:b:c:d",)

    def test_it_stays_quiet_when_every_given_is_used(self) -> None:
        """The near-miss: without it the test above passes on a check that always raises."""
        derivation = self._derivation(stated=["cong:a:b:a:c"], used=["cong:a:b:a:c"])
        assert unused_givens(derivation) == ()
        assert_every_given_is_used(derivation)

    def test_a_given_the_proof_derives_still_counts_as_unused(self) -> None:
        """A premise that is a *conclusion* of some step is a premise the puzzle did not need
        to state — which is precisely what this filter is looking for. Widening "used" to
        include facts a sentence mentions would hide it."""
        derivation = self._derivation(stated=["cong:a:b:a:c"], used=[])
        assert unused_givens(derivation) == ("cong:a:b:a:c",)
