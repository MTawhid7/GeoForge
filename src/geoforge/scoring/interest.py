"""Interestingness: a soft ranking within a band (docs/05 §5.3).

Never a rejection on its own. It orders a band and the bank build keeps the top slice, which is
the main volume-versus-quality knob (docs/05 §5.3, docs/01's <= 5% trivial/ugly floor).

**Per-band keep rates, not docs/05's flat 40%.** The flat rate assumes every band is
oversupplied. Measured at seed 42 over 1,200 constructions the upper bands are *filter*-limited,
not interest-limited — expert is empty and hard holds 17 of 105 — so discarding 60% of them
would shrink the bands docs/07 T10 already flags as thin. Easy is where the surplus is, and
that is where the rate bites. docs/05 §5.3 records the deviation.

**Elegance is the primary signal** (docs/05 §5.3, adopted from TongGeometry as an idea; no GPL
code is read or copied — CLAUDE.md). A hard proof over a simple figure is the signature of a
good puzzle; a complicated figure with a shallow proof is noise.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from geoforge.config import INTEREST
from geoforge.scoring.features import Features
from geoforge.solvers.types import FactKind


class Scored(Protocol):
    """What ranking needs from a candidate. A protocol so `scoring` never imports the
    generator's batch module, which imports `scoring` — and so tests can rank a stub."""

    @property
    def id(self) -> str: ...
    @property
    def band(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def features(self) -> Features: ...
    @property
    def full_depth(self) -> int: ...


@dataclass(frozen=True, slots=True)
class Interest:
    value: float
    elegance: float
    terms: dict[str, float]


def elegance(score: float, features: Features) -> float:
    """Proof difficulty ÷ construction complexity (docs/05 §5.3).

    The denominator is the *pruned* construction's step count — the figure the player actually
    sees. Using the unpruned one would reward a puzzle for scaffolding that was thrown away.
    Never zero: a construction with no steps cannot have produced a puzzle, but dividing by it
    would turn a pipeline bug into an infinity that silently sorts to the top.
    """
    return score / max(features.construction_steps, 1)


def clutter(features: Features, collinear_facts: int) -> float:
    """docs/05 §5.3's negative term: visual clutter.

    Collinear premises are the measurable part — three points on a line the player must keep
    straight. Point count alone is not clutter; a five-point figure with no incidences reads
    more easily than a four-point one with two.
    """
    return collinear_facts + max(0, features.n_points - FIGURE_COMFORT) * 0.5


#: GUESS: points beyond this start to cost readability rather than add interest. Measured range
#: is 3-8 with a median of 5, so this only bites at the top of the observed distribution.
FIGURE_COMFORT = 6


def interest(candidate: Scored, collinear_facts: int) -> Interest:
    """Rank one candidate. Higher is more interesting."""
    features = candidate.features
    terms = {
        "elegance": elegance(candidate.score, features),
        # docs/05 §5.3: "a much longer alternate derivation exists in the full DAG (the short
        # path is an *insight*)". Only the gain counts. The reverse — a minimal proof that came
        # out *deeper* than the engine's first attempt — is the ordinary case on this corpus
        # (14 of 105 at seed 42) and is not evidence of anything.
        "insight": float(max(0, candidate.full_depth - features.depth)),
        "goal_given_distance": float(features.goal_given_distance),
        "tier_mix": float(features.tier_mix),
        "clutter": clutter(features, collinear_facts),
    }
    value = sum(INTEREST.weights.get(name, 0.0) * term for name, term in terms.items())
    return Interest(
        value=round(value, 4),
        elegance=round(terms["elegance"], 4),
        terms={k: round(v, 4) for k, v in terms.items()},
    )


def collinear_count(premises: Sequence[object]) -> int:
    """`coll` premises, for the clutter term. Takes facts; typed loosely so a stub can rank."""
    return sum(1 for f in premises if getattr(f, "kind", None) is FactKind.COLLINEAR)


def rank(
    candidates: Sequence[Scored], collinear: dict[str, int] | None = None
) -> list[tuple[Scored, Interest]]:
    """Every candidate with its interest, most interesting first.

    Ties break on puzzle id, so a rebuild orders identically (docs/02 invariant 2). Without it
    two puzzles with the same elegance would swap places between runs and the bank would not be
    byte-reproducible.
    """
    collinear = collinear or {}
    scored = [(c, interest(c, collinear.get(c.id, 0))) for c in candidates]
    return sorted(scored, key=lambda pair: (-pair[1].value, pair[0].id))


def select(candidates: Sequence[Scored], collinear: dict[str, int] | None = None) -> list[Scored]:
    """Keep the top slice of each band, per `INTEREST.keep_rate`.

    A band with a keep rate below 1 always keeps at least one puzzle: rounding a three-puzzle
    band down to zero would delete the band to enforce a ratio, which is the opposite of what
    the rate is for.
    """
    by_band: dict[str, list[tuple[Scored, Interest]]] = defaultdict(list)
    for candidate, value in rank(candidates, collinear):
        by_band[candidate.band].append((candidate, value))

    kept: list[Scored] = []
    for band, ranked in by_band.items():
        rate = INTEREST.keep_rate.get(band, 1.0)
        keep = len(ranked) if rate >= 1.0 else max(1, int(len(ranked) * rate))
        kept.extend(candidate for candidate, _ in ranked[:keep])
    return sorted(kept, key=lambda c: c.id)
