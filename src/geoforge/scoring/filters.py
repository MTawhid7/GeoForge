"""The docs/05 §5.2 hard rejection filters. Any hit discards the puzzle.

Six of the seven live here. Filter 6 (answer-policy exactness) belongs to the quantity-type
registry and already runs at Stage 5, and filter 7 (isomorphism duplicate) is a batch-level
question rather than a per-puzzle one — it lands with `bank/dedupe.py` in M4.

**Filter 5 raises.** docs/05 says an unused given "must be impossible after Stage-6
minimization; a hit is a bug report, not a silent discard". A returned verdict would be counted
as attrition and vanish into a report line, which is the same as not noticing. An exception is
the only form of "bug report" that survives a refactor of the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoforge.config import FILTERS
from geoforge.generator.traceback import Derivation
from geoforge.scoring.features import Features


class UnusedGivenBug(RuntimeError):
    """A stated given the minimal solution never uses (docs/05 §5.2 filter 5).

    Not a rejection: Stage 6 minimizes premises against the engine, so an unused given means
    minimization and the sub-DAG disagree about what the proof needs, and one of them is wrong.
    Shipping the puzzle would hand the player a red herring; discarding it quietly would leave
    the defect in place.
    """


class Rejection(StrEnum):
    """Why a puzzle was filtered out. Counted in the attrition report (docs/04)."""

    TOO_SHALLOW = "too_shallow"
    """docs/05 §5.2 filter 1: depth or rule variety below the floor, over the minimal sub-DAG."""
    READ_OFF_THE_PICTURE = "read_off_the_picture"
    """docs/05 §5.2 filter 2: no geometric step at all — the answer follows from the givens by
    arithmetic alone."""
    MONOTONOUS = "monotonous"
    """docs/05 §5.2 filter 3: one template dominates the published geometric steps."""
    FIGURE_TOO_SIMPLE = "figure_too_simple"
    FIGURE_TOO_COMPLEX = "figure_too_complex"
    TOO_MANY_CIRCLES = "too_many_circles"
    """docs/05 §5.2 filter 4, split three ways: "figure complexity out of range" as one reason
    would make the attrition report unable to say which end it was."""


@dataclass(frozen=True, slots=True)
class FilterResult:
    rejections: tuple[Rejection, ...]

    @property
    def ok(self) -> bool:
        return not self.rejections


def check(features: Features) -> FilterResult:
    """Run every per-puzzle hard filter. Empty result means the puzzle survives."""
    hits: list[Rejection] = []

    if features.depth < FILTERS.min_depth or features.distinct_rules < FILTERS.min_distinct_rules:
        hits.append(Rejection.TOO_SHALLOW)

    if features.geometric_steps < FILTERS.min_geometric_steps:
        hits.append(Rejection.READ_OFF_THE_PICTURE)

    if features.rule_share_max > FILTERS.max_rule_share:
        hits.append(Rejection.MONOTONOUS)

    if features.n_points < FILTERS.min_points:
        hits.append(Rejection.FIGURE_TOO_SIMPLE)
    elif features.n_points > FILTERS.max_points:
        hits.append(Rejection.FIGURE_TOO_COMPLEX)

    if features.n_circles > FILTERS.max_circles:
        hits.append(Rejection.TOO_MANY_CIRCLES)

    return FilterResult(rejections=tuple(hits))


def unused_givens(derivation: Derivation) -> tuple[str, ...]:
    """Stated givens the minimal sub-DAG never rests on.

    "Used" means exactly "is a leaf of the derivation". Deliberately not widened to include
    facts a published sentence happens to mention: a premise that is a *conclusion* of some step
    is a premise the puzzle did not need to state, which is the very thing this filter is
    looking for, and counting it as used would hide it.
    """
    used = {fact.fact_id for fact in derivation.subdag.premises}
    return tuple(sorted(f.fact_id for f in derivation.premises if f.fact_id not in used))


def assert_every_given_is_used(derivation: Derivation) -> None:
    """docs/05 §5.2 filter 5. Raises `UnusedGivenBug`; returns nothing on success."""
    unused = unused_givens(derivation)
    if unused:
        raise UnusedGivenBug(
            f"{derivation.goal.fact_id}: stated givens no minimal solution uses: "
            f"{list(unused)} (docs/05 §5.2 filter 5)"
        )
