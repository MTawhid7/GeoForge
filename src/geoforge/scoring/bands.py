"""**Provisional** depth-only difficulty banding (Phase 1 only).

This exists to satisfy one Phase 1 acceptance criterion — "100 validated puzzles across >= 2
bands" (`docs/09` P1) — and nothing else. The real scorer is Phase 2 (`docs/05` §5.1): a
multi-feature model over proof depth, rule variety, circle involvement, configuration
sensitivity and elegance.

**Replace this module; do not extend it.** Proof depth alone is a weak difficulty proxy: a deep
chain of one repeated idea is easier than a short argument needing an unusual insight. Adding
a second feature here would grow a scorer nobody designed, in the module documented as the
thing to throw away.
"""

from __future__ import annotations

from geoforge.config import BANDING

#: Easiest to hardest. The order is what makes "the highest band whose threshold is met" meaningful.
BAND_ORDER: tuple[str, ...] = ("easy", "medium", "hard", "expert")


def band_for_depth(depth: int) -> str:
    """The band a proof of this depth falls into.

    Below the easiest threshold still returns the easiest band: such puzzles were already rejected
    upstream by `GENERATION.min_proof_depth`, so anything reaching here is at least a puzzle.
    """
    chosen = BAND_ORDER[0]
    for band in BAND_ORDER:
        threshold = BANDING.depth_thresholds.get(band)
        if threshold is not None and depth >= threshold:
            chosen = band
    return chosen
