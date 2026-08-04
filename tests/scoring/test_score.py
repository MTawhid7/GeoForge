"""The difficulty score and its bands (docs/05 §5.1).

Two properties the model has to have whatever the weights are, and one the doc states outright:
the score must rise with every feature it calls harder, banding must cover [0, scale] with no
gap, and both sides of every cut must land where the doc says.

The weights themselves are not asserted. They are explicitly not the contract (docs/05 preamble)
and pinning them here would turn every recalibration into a test edit, which is how a test
suite starts arguing against the thing it is meant to protect.
"""

from __future__ import annotations

import dataclasses

import pytest

from geoforge.config import BANDING, SCORING
from geoforge.scoring.features import Features
from geoforge.scoring.score import BAND_ORDER, band_for, normalized, score

BASE = Features(
    depth=4,
    width=5,
    distinct_rules=4,
    tier_max=2,
    tier_mix=1,
    branch_join=0,
    nice_penalty=0.0,
    published_steps=3,
    geometric_steps=2,
    distinct_templates=2,
    rule_share_max=0.5,
    n_points=5,
    n_circles=0,
    n_premises=3,
    construction_steps=4,
    goal_given_distance=0,
    unused_points=0,
)

#: Every feature the score reads, with a value above and below BASE's.
SCORED_FEATURES = ("depth", "width", "distinct_rules", "tier_max", "tier_mix", "branch_join")


def with_(**changes: object) -> Features:
    return dataclasses.replace(BASE, **changes)  # type: ignore[arg-type]


class TestMonotonicity:
    @pytest.mark.parametrize("name", SCORED_FEATURES)
    def test_score_rises_with_every_hard_feature(self, name: str) -> None:
        """docs/05 §5.1 calls each of these a difficulty signal. A model where one of them
        lowers the score is not the model the doc describes, whatever it scores on average."""
        low = score(with_(**{name: getattr(BASE, name)}))
        high = score(with_(**{name: getattr(BASE, name) + 1}))
        assert high.value > low.value, f"{name} did not raise the score"

    def test_the_penalty_lowers_the_score(self) -> None:
        assert score(with_(nice_penalty=1.0)).value < score(BASE).value

    def test_the_penalty_cannot_push_a_score_below_zero(self) -> None:
        floor = with_(depth=3, width=3, distinct_rules=2, tier_max=1, tier_mix=1, branch_join=0)
        assert score(dataclasses.replace(floor, nice_penalty=1.0)).value == 0.0

    def test_a_saturating_feature_stops_adding(self) -> None:
        """Past the top of its range a feature is capped, so an absurd value cannot dominate."""
        _, hi = SCORING.ranges["depth"]
        assert score(with_(depth=int(hi))).value == score(with_(depth=int(hi) * 3)).value


class TestNormalization:
    def test_the_floor_of_a_range_scores_zero(self) -> None:
        """Clearing a bar the filters required is worth nothing (docs/05 §5.2 floors are the
        §5.1 range floors); otherwise every shippable puzzle starts with free points."""
        for name, (lo, _) in SCORING.ranges.items():
            assert normalized(name, lo) == 0.0

    def test_the_top_of_a_range_scores_one(self) -> None:
        for name, (_, hi) in SCORING.ranges.items():
            assert normalized(name, hi) == 1.0

    def test_values_outside_the_range_are_clamped(self) -> None:
        assert normalized("depth", -5) == 0.0
        assert normalized("depth", 1000) == 1.0

    def test_weights_sum_to_one(self) -> None:
        """What makes the raw sum a fraction of the scale, so `nice_penalty_weight` means
        'this fraction of the whole scale' rather than an unanchored number of points."""
        assert sum(SCORING.weights.values()) == pytest.approx(1.0)

    def test_every_weighted_feature_has_a_range(self) -> None:
        assert set(SCORING.weights) == set(SCORING.ranges)


class TestBanding:
    def test_bands_tile_the_scale(self) -> None:
        """Total over [0, scale]: every score has a band, with no gap and no overlap."""
        step = SCORING.scale / 400
        value = 0.0
        while value <= SCORING.scale:
            assert band_for(value) in BAND_ORDER
            value += step

    def test_banding_is_monotone(self) -> None:
        ranks = [BAND_ORDER.index(band_for(v / 20)) for v in range(0, int(SCORING.scale) * 20 + 1)]
        assert ranks == sorted(ranks)

    @pytest.mark.parametrize("band", BAND_ORDER)
    def test_both_sides_of_every_cut(self, band: str) -> None:
        """A cut asserted only from above passes on a banding that ignores it."""
        cut = BANDING.cuts[band]
        assert band_for(cut) == band
        if cut > 0:
            below = BAND_ORDER[BAND_ORDER.index(band) - 1]
            assert band_for(cut - 1e-9) == below

    def test_zero_is_the_easiest_band_and_the_top_is_the_hardest(self) -> None:
        assert band_for(0.0) == BAND_ORDER[0]
        assert band_for(SCORING.scale) == BAND_ORDER[-1]

    def test_cuts_name_only_real_bands(self) -> None:
        assert set(BANDING.cuts) == set(BAND_ORDER)


class TestExplainability:
    def test_contributions_account_for_the_score(self) -> None:
        """The calibration protocol has to say *why* a puzzle landed in a band, so the parts
        must add up to the whole rather than being a decorative breakdown."""
        result = score(BASE)
        assert sum(result.contributions.values()) - result.penalty == pytest.approx(
            result.value, abs=0.01
        )

    def test_every_scored_feature_is_named_in_the_breakdown(self) -> None:
        assert set(score(BASE).contributions) == set(SCORED_FEATURES)
