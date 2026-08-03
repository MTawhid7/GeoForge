"""The docs/05 §5.1 calibration protocol, as something you can run.

    "every bank build → stratified 50-puzzle spot check, owner records perceived band; weight
    changes must cite a spot-check batch"

A protocol that exists only in prose is a protocol nobody follows. `spot_check` produces the
sample and the per-feature evidence behind each band, so a weight change can cite a batch
instead of an intuition — and `distribution` prints what the whole batch looks like, which is
what says whether a cut is doing anything at all.

Stratified, not random: bands differ in size by an order of magnitude here (73 easy against 0
expert at seed 42), so a uniform sample of 50 would be 35 easy puzzles and tell you nothing
about the cuts that matter.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

import numpy as np

from geoforge.config import BANDING, SCORING
from geoforge.scoring.interest import Scored, interest
from geoforge.scoring.score import BAND_ORDER


def spot_check(candidates: Sequence[Scored], n: int = 50, seed: int = 42) -> list[dict[str, Any]]:
    """A stratified sample, with the evidence behind each puzzle's band.

    Proportional to band size but with a floor, so a thin band is still represented: the whole
    point of the exercise is to check the cuts, and the expert cut cannot be checked against
    zero expert puzzles.
    """
    rng = np.random.default_rng(seed)
    by_band: dict[str, list[Scored]] = defaultdict(list)
    for candidate in candidates:
        by_band[candidate.band].append(candidate)

    present = [b for b in BAND_ORDER if by_band[b]]
    if not present:
        return []
    floor = max(1, n // (2 * len(present)))

    sample: list[Scored] = []
    for band in present:
        pool = sorted(by_band[band], key=lambda c: c.id)
        want = min(len(pool), max(floor, round(n * len(pool) / len(candidates))))
        picks = rng.choice(len(pool), size=want, replace=False)
        sample.extend(pool[int(i)] for i in sorted(picks))

    return [_row(c) for c in sorted(sample, key=lambda c: (BAND_ORDER.index(c.band), c.id))]


def _row(candidate: Scored) -> dict[str, Any]:
    features = candidate.features
    return {
        "id": candidate.id,
        "band": candidate.band,
        "score": candidate.score,
        "perceived_band": "",  # the owner fills this in; the protocol is a human judgement
        "depth": features.depth,
        "width": features.width,
        "published_steps": features.published_steps,
        "distinct_rules": features.distinct_rules,
        "tier_max": features.tier_max,
        "tier_mix": features.tier_mix,
        "branch_join": features.branch_join,
        "nice_penalty": round(features.nice_penalty, 3),
        "elegance": interest(candidate, 0).elegance,
    }


def distribution(candidates: Sequence[Scored]) -> dict[str, Any]:
    """What the batch looks like, per band and per feature.

    Reported alongside the sample because a spot check answers "is this puzzle in the right
    band" and cannot answer "is this cut ever reached" — the question a band with no puzzles in
    it raises.
    """
    scores = sorted(c.score for c in candidates)
    if not scores:
        return {"puzzles": 0}

    def percentile(fraction: float) -> float:
        return round(scores[min(len(scores) - 1, int(fraction * len(scores)))], 3)

    return {
        "puzzles": len(scores),
        "by_band": {b: n for b, n in sorted(Counter(c.band for c in candidates).items())},
        "empty_bands": [b for b in BAND_ORDER if not any(c.band == b for c in candidates)],
        "score": {
            "min": round(scores[0], 3),
            "p25": percentile(0.25),
            "median": percentile(0.5),
            "p75": percentile(0.75),
            "max": round(scores[-1], 3),
        },
        "cuts": dict(BANDING.cuts),
        "headroom_to_next_cut": _headroom(scores[-1]),
        "features": {
            name: _feature_stats(candidates, name)
            for name in ("depth", "width", "distinct_rules", "branch_join", "tier_max", "tier_mix")
        },
        "constant_features": _constant_features(candidates),
    }


def _headroom(best: float) -> dict[str, float]:
    """How far the best puzzle is from each cut it did not reach.

    An empty band is either "the sampler cannot make them" or "the cut is one point away", and
    those call for opposite responses (docs/07 T10: never lower a cut to fake a band).
    """
    return {band: round(cut - best, 3) for band, cut in sorted(BANDING.cuts.items()) if cut > best}


def _feature_stats(candidates: Sequence[Scored], name: str) -> dict[str, Any]:
    values = sorted(float(getattr(c.features, name)) for c in candidates)
    lo, hi = SCORING.ranges[name]
    return {
        "min": values[0],
        "median": values[len(values) // 2],
        "max": values[-1],
        "range": [lo, hi],
        "saturated": sum(1 for v in values if v >= hi),
    }


def _constant_features(candidates: Sequence[Scored]) -> list[str]:
    """Features taking one value across the whole batch.

    A constant feature contributes a fixed offset and no discrimination, so it is worth naming
    rather than leaving for someone to discover while wondering why a weight did nothing.
    """
    names = (
        "depth",
        "width",
        "distinct_rules",
        "branch_join",
        "tier_max",
        "tier_mix",
        "nice_penalty",
        "goal_given_distance",
        "rule_share_max",
    )
    return [name for name in names if len({getattr(c.features, name) for c in candidates}) == 1]


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    from geoforge.generator.batch import run

    parser = argparse.ArgumentParser(description="docs/05 §5.1 calibration spot check.")
    parser.add_argument("--n", type=int, default=400, help="constructions to sample")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample", type=int, default=50, help="puzzles in the spot check")
    args = parser.parse_args(argv)

    report = run(args.n, args.seed)
    print(
        json.dumps(
            {
                "distribution": distribution(report.puzzles),
                "spot_check": spot_check(report.puzzles, args.sample, args.seed),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
