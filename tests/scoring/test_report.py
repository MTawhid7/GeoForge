"""The calibration protocol as a callable (docs/05 §5.1).

docs/05 requires a stratified 50-puzzle spot check on every bank build, and says weight changes
must cite one. These tests hold the sampler to the properties that make such a citation worth
anything: it must be reproducible, it must reach the thin bands, and it must report a band that
nothing landed in rather than omitting it.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoforge.scoring.features import Features
from geoforge.scoring.report import distribution, spot_check
from geoforge.scoring.score import BAND_ORDER

FEATURES = Features(
    depth=5,
    width=6,
    distinct_rules=4,
    tier_max=3,
    tier_mix=2,
    branch_join=1,
    nice_penalty=0.5,
    published_steps=5,
    geometric_steps=4,
    distinct_templates=3,
    rule_share_max=0.5,
    n_points=5,
    n_circles=0,
    n_premises=3,
    construction_steps=4,
    goal_given_distance=0,
    unused_points=0,
)


@dataclass(frozen=True)
class Stub:
    id: str
    band: str
    score: float
    features: Features = FEATURES
    full_depth: int = 0


def corpus() -> list[Stub]:
    """Deliberately lopsided, like the real one: 90 easy against 2 hard and no expert."""
    return (
        [Stub(f"e{i:03d}", "easy", 1.5) for i in range(90)]
        + [Stub(f"m{i:03d}", "medium", 4.0) for i in range(8)]
        + [Stub(f"h{i:03d}", "hard", 6.0) for i in range(2)]
    )


class TestSpotCheck:
    def test_it_is_reproducible(self) -> None:
        """A citation is worthless if the batch it names cannot be reproduced."""
        assert spot_check(corpus(), 30, seed=7) == spot_check(corpus(), 30, seed=7)

    def test_a_different_seed_gives_a_different_sample(self) -> None:
        assert spot_check(corpus(), 30, seed=7) != spot_check(corpus(), 30, seed=8)

    def test_it_reaches_the_thin_bands(self) -> None:
        """The point of stratifying. A uniform sample of a 90/8/2 corpus is 90% easy and says
        nothing about the cuts that actually matter."""
        bands = {row["band"] for row in spot_check(corpus(), 30, seed=7)}
        assert bands == {"easy", "medium", "hard"}

    def test_it_carries_the_evidence_behind_the_band(self) -> None:
        """ "Record the perceived band" needs the features on the page; otherwise disagreeing
        with a band means re-deriving it by hand."""
        row = spot_check(corpus(), 30, seed=7)[0]
        for key in ("score", "depth", "distinct_rules", "tier_max", "branch_join", "elegance"):
            assert key in row
        assert row["perceived_band"] == "", "the human column must start empty"

    def test_it_samples_no_more_than_a_band_holds(self) -> None:
        sample = spot_check(corpus(), 500, seed=7)
        assert len(sample) == len(corpus())

    def test_an_empty_corpus_is_an_empty_sample(self) -> None:
        assert spot_check([], 50) == []


class TestDistribution:
    def test_it_names_the_bands_nothing_reached(self) -> None:
        """The number that decides whether a cut is unreachable or the sampler is thin — and
        docs/07 T10 forbids answering that by lowering the cut."""
        assert distribution(corpus())["empty_bands"] == ["expert"]

    def test_it_says_how_far_the_best_puzzle_is_from_the_cut_it_missed(self) -> None:
        """ "One point short" and "four points short" call for opposite responses."""
        headroom = distribution(corpus())["headroom_to_next_cut"]
        assert headroom == {"expert": 1.5}

    def test_it_names_features_that_never_vary(self) -> None:
        """A constant feature contributes a fixed offset and no discrimination. Two of them are
        constant on the real corpus, and finding that out by retuning a weight and watching
        nothing happen is the expensive way."""
        constant = distribution(corpus())["constant_features"]
        assert "nice_penalty" in constant
        assert "goal_given_distance" in constant

    def test_it_reports_saturation(self) -> None:
        """A feature pinned at the top of its range has stopped discriminating upward, which is
        a reason to widen the range rather than to reweight it."""
        stats = distribution(corpus())["features"]["depth"]
        assert stats["saturated"] == 0
        assert stats["range"] == [3.0, 10.0]

    def test_an_empty_corpus_does_not_divide_by_zero(self) -> None:
        assert distribution([])["puzzles"] == 0

    def test_every_band_in_the_order_can_be_reported(self) -> None:
        full = [Stub(f"{b}{i}", b, 1.0) for b in BAND_ORDER for i in range(2)]
        assert distribution(full)["empty_bands"] == []
