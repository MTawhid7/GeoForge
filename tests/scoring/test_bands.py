"""Provisional depth-only banding (Phase 1 only — `scoring/bands.py` is written to be replaced)."""

from __future__ import annotations

from geoforge.config import BANDING
from geoforge.scoring.bands import BAND_ORDER, band_for_depth


class TestBanding:
    def test_thresholds_map_to_their_band(self) -> None:
        for band, threshold in BANDING.depth_thresholds.items():
            assert band_for_depth(threshold) == band

    def test_deeper_is_never_easier(self) -> None:
        """Monotonicity is the one property a depth-based band must have."""
        ranks = [BAND_ORDER.index(band_for_depth(depth)) for depth in range(0, 20)]
        assert ranks == sorted(ranks)

    def test_shallow_proofs_still_get_a_band(self) -> None:
        """Below the easiest threshold a puzzle was already rejected upstream by
        `GENERATION.min_proof_depth`, so anything arriving here is at least a puzzle."""
        assert band_for_depth(0) == BAND_ORDER[0]

    def test_very_deep_proofs_land_in_the_hardest_band(self) -> None:
        assert band_for_depth(999) == BAND_ORDER[-1]

    def test_every_configured_band_is_in_the_order(self) -> None:
        assert set(BANDING.depth_thresholds) <= set(BAND_ORDER)

    def test_at_least_two_bands_are_reachable(self) -> None:
        """The Phase 1 acceptance criterion needs ≥ 2 bands to exist at all."""
        assert len({band_for_depth(d) for d in range(0, 20)}) >= 2
