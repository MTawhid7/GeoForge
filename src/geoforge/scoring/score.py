"""The difficulty score and its bands (docs/05 §5.1).

Score = weighted sum of the §5.1 features, normalized to 0-10, minus `nice_penalty`.

**Each feature is normalized over a useful range, not over its arithmetic range.** The shippable
corpus occupies a narrow slice of every feature — depth is 3 to 7, never 0 to 10 — so dividing
by the arithmetic range would compress every real puzzle into the bottom of the scale and make
the doc's band cuts unreachable. `lo` is the value at which a puzzle is barely a puzzle, which
is the corresponding hard filter's own floor wherever one exists: clearing a bar you were
required to clear earns nothing.

The weights are not the contract; the feature structure is (docs/05 preamble). Retuning them
requires citing a spot-check batch, which is what `scoring.report` exists to produce.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoforge.config import BANDING, SCORING
from geoforge.scoring.features import Features

#: Easiest to hardest. The order is what makes "the highest band whose cut is met" meaningful.
BAND_ORDER: tuple[str, ...] = ("easy", "medium", "hard", "expert")


@dataclass(frozen=True, slots=True)
class Score:
    """A scored puzzle: the number, its band, and what produced them."""

    value: float
    band: str
    contributions: dict[str, float]
    """Per-feature points, before the penalty. Carried so a surprising band can be explained
    without re-deriving it — the calibration protocol needs to say *why*, not just *what*."""
    penalty: float


def normalized(name: str, value: float) -> float:
    """One feature mapped into [0, 1] over its configured useful range."""
    lo, hi = SCORING.ranges[name]
    if hi <= lo:  # pragma: no cover - a misconfigured range is a config bug, not a data case
        raise ValueError(f"scoring range for {name!r} is empty: ({lo}, {hi})")
    return min(1.0, max(0.0, (value - lo) / (hi - lo)))


def score(features: Features) -> Score:
    """The docs/05 §5.1 score for one puzzle."""
    values = {
        "depth": float(features.depth),
        "distinct_rules": float(features.distinct_rules),
        "branch_join": float(features.branch_join),
        "tier_max": float(features.tier_max),
        "tier_mix": float(features.tier_mix),
        "width": float(features.width),
    }
    contributions = {
        name: weight * normalized(name, values[name]) * SCORING.scale
        for name, weight in SCORING.weights.items()
    }
    penalty = features.nice_penalty * SCORING.nice_penalty_weight * SCORING.scale
    value = min(SCORING.scale, max(0.0, sum(contributions.values()) - penalty))
    return Score(
        value=round(value, 3),
        band=band_for(value),
        contributions={k: round(v, 3) for k, v in contributions.items()},
        penalty=round(penalty, 3),
    )


def band_for(value: float) -> str:
    """The band a score falls into. Total over [0, scale]: every score has a band.

    A value below the easiest cut still returns the easiest band rather than raising. Bands
    partition the scale, and a puzzle that scored 0 is an easy puzzle, not an error — the hard
    filters, not the banding, are what decide whether it ships.
    """
    chosen = BAND_ORDER[0]
    for band in BAND_ORDER:
        cut = BANDING.cuts.get(band)
        if cut is not None and value >= cut:
            chosen = band
    return chosen
