"""Interestingness ranking and per-band selection (docs/05 §5.3).

Interest is a *ranking*, so what has to be tested is the order and the selection, not the
absolute numbers — which are weighted guesses the doc says to retune.

The property that matters most is that selection never empties a band. docs/05's flat 40% keep
rate assumes every band is oversupplied; measured at seed 42 the upper bands are filter-limited
instead, and a rate that deletes a thin band to enforce a ratio is worse than no rate at all.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pytest

from geoforge.config import INTEREST
from geoforge.scoring.features import Features
from geoforge.scoring.interest import elegance, interest, rank, select
from geoforge.scoring.score import BAND_ORDER

FEATURES = Features(
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
    n_circles=0,
    n_premises=3,
    construction_steps=4,
    goal_given_distance=0,
    unused_points=0,
)


@dataclass(frozen=True)
class Stub:
    """A candidate for ranking. `Scored` is a protocol precisely so this is possible."""

    id: str
    band: str
    score: float
    features: Features = FEATURES
    full_depth: int = 0


class TestElegance:
    def test_a_hard_proof_over_a_simple_figure_beats_the_reverse(self) -> None:
        """docs/05 §5.3's whole point: "a complicated figure with a shallow proof is noise"."""
        simple = dataclasses.replace(FEATURES, construction_steps=3)
        complex_ = dataclasses.replace(FEATURES, construction_steps=9)
        assert elegance(6.0, simple) > elegance(6.0, complex_)

    def test_it_uses_the_pruned_construction(self) -> None:
        """Scaffolding that was thrown away must not earn credit — the denominator is the
        figure the player sees."""
        assert elegance(6.0, FEATURES) == 6.0 / FEATURES.construction_steps

    def test_an_empty_construction_does_not_divide_by_zero(self) -> None:
        """Cannot happen from this pipeline. If it ever did, an infinity would sort straight to
        the top of every band, which is the worst possible way for a bug to present."""
        empty = dataclasses.replace(FEATURES, construction_steps=0)
        assert elegance(6.0, empty) == 6.0


class TestRanking:
    def test_more_elegant_ranks_higher(self) -> None:
        ranked = rank([Stub("a", "easy", 2.0), Stub("b", "easy", 8.0)])
        assert [c.id for c, _ in ranked] == ["b", "a"]

    def test_clutter_lowers_interest(self) -> None:
        clean = interest(Stub("a", "easy", 5.0), 0)
        cluttered = interest(Stub("a", "easy", 5.0), 3)
        assert cluttered.value < clean.value

    def test_ties_break_on_id_so_a_rebuild_orders_identically(self) -> None:
        """Without it two equally interesting puzzles swap places between runs and the bank
        stops being byte-reproducible (docs/02 invariant 2)."""
        stubs = [Stub("z", "easy", 5.0), Stub("a", "easy", 5.0), Stub("m", "easy", 5.0)]
        assert [c.id for c, _ in rank(stubs)] == ["a", "m", "z"]
        assert [c.id for c, _ in rank(list(reversed(stubs)))] == ["a", "m", "z"]

    def test_every_weighted_term_is_computed(self) -> None:
        """A weight for a term nobody measures is a silent no-op."""
        assert set(interest(Stub("a", "easy", 5.0), 0).terms) == set(INTEREST.weights)


class TestSelection:
    def test_it_keeps_the_configured_share_of_a_band(self) -> None:
        pool = [Stub(f"e{i:03d}", "easy", float(i)) for i in range(100)]
        kept = select(pool)
        assert len(kept) == int(100 * INTEREST.keep_rate["easy"])

    def test_it_keeps_the_most_interesting_ones(self) -> None:
        pool = [Stub(f"e{i:03d}", "easy", float(i)) for i in range(10)]
        kept = {c.id for c in select(pool)}
        assert "e009" in kept
        assert "e000" not in kept

    def test_it_never_empties_a_band(self) -> None:
        """A three-puzzle band at a 50% rate rounds to one, not zero. Deleting a band to
        enforce a ratio is the opposite of what the rate is for."""
        assert len(select([Stub("e0", "easy", 1.0)])) == 1
        assert len(select([Stub(f"e{i}", "easy", float(i)) for i in range(3)])) >= 1

    def test_bands_are_selected_independently(self) -> None:
        """Ranking across bands would let a deep hard puzzle crowd out every easy one, which
        turns the keep rate into a difficulty filter."""
        pool = [Stub(f"e{i:03d}", "easy", 1.0) for i in range(20)]
        pool += [Stub(f"h{i:03d}", "hard", 9.0) for i in range(20)]
        kept = select(pool)
        assert any(c.band == "easy" for c in kept)
        assert any(c.band == "hard" for c in kept)

    def test_a_full_keep_rate_keeps_everything(self) -> None:
        pool = [Stub(f"x{i:03d}", "expert", float(i)) for i in range(10)]
        assert len(select(pool)) == 10

    def test_selection_is_deterministic(self) -> None:
        pool = [Stub(f"e{i:03d}", "easy", float(i % 3)) for i in range(30)]
        assert [c.id for c in select(pool)] == [c.id for c in select(list(reversed(pool)))]

    @pytest.mark.parametrize("band", BAND_ORDER)
    def test_every_band_has_a_keep_rate(self, band: str) -> None:
        """A band missing from the table silently keeps everything, which is a policy nobody
        chose rather than a default anyone reviewed."""
        assert band in INTEREST.keep_rate
        assert 0.0 < INTEREST.keep_rate[band] <= 1.0
