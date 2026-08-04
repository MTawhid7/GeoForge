"""The docs/05 §5.1 difficulty features, measured over the minimal translated sub-DAG.

Scoring reads what the pipeline already produced and never re-runs deduction (docs/02). Every
feature here is a function of the sub-DAG, its translation and the pruned construction — three
objects `CandidatePuzzle` carries in memory precisely so this module needs no engine.

All features are **quantity-generic**: they read DAG structure and template metadata, never
quantity kinds, so enabling `length` in P3 does not require a second scorer (docs/05 §5.1).

Two features are recorded in both readings rather than one, because docs/05's wording admits
both and only data can choose:

* `width` is machine steps of the sub-DAG. docs/05 says "total rule applications", and
  difficulty should read proof structure rather than a presentation decision — idiom collapsing
  turns three machine steps into one sentence, and that is a writing choice, not an easier
  proof. `published_steps` is recorded alongside, so calibration can test the other reading
  without a code change.
* `rule_share_max` counts published **geometric** steps. The alternatives, and what each
  measures, are set out in `FilterConfig.max_rule_share` — where the numbers are.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from fractions import Fraction

from geoforge.config import SCORING
from geoforge.generator.construction import Construction
from geoforge.generator.traceback import Derivation
from geoforge.generator.translation import Translation
from geoforge.generator.translation.templates import is_geometric, tier_for
from geoforge.solvers.types import Fact, FactKind

#: Fact kinds that put a circle in the figure (docs/05 §5.2 filter 4).
CIRCLE_KINDS: frozenset[FactKind] = frozenset({FactKind.CYCLIC, FactKind.CIRCUMCENTER})


@dataclass(frozen=True, slots=True)
class Features:
    """One puzzle's measured features. Inputs to the score, the filters and interestingness."""

    # --- docs/05 §5.1 scored features ---
    depth: int
    """Longest premise-to-goal chain in the minimal sub-DAG. The primary signal."""
    width: int
    """Machine rule applications in the minimal sub-DAG."""
    distinct_rules: int
    """Conceptual variety over the same graph."""
    tier_max: int
    """Highest rule tier the published solution reaches (1 restatement - 4 circle theorems)."""
    tier_mix: int
    """How many distinct tiers it crosses. A proof that moves between families feels harder
    than one that stays in a single register at the same depth."""
    branch_join: int
    """Steps combining two or more *derived* facts. docs/05: "strongly felt as hard" — holding
    two independent sub-arguments in mind at once is the thing that makes a proof feel deep.
    Premises do not count: a step resting on two givens is one idea, not a join."""
    nice_penalty: float
    """Subtractive, in [0, 1]. See `_nice_penalty`."""

    # --- recorded for filters, interest and calibration ---
    published_steps: int
    """Sentences the player reads. The other reading of `width`."""
    geometric_steps: int
    """Published steps that are not the algebraic idiom. A solution with none of these is
    arithmetic wearing a figure."""
    distinct_templates: int
    rule_share_max: float
    """Largest share of the published geometric steps taken by one template, or 0 when there
    are too few steps for a share to mean anything."""
    n_points: int
    n_circles: int
    n_premises: int
    construction_steps: int
    """Steps in the *pruned* construction: the elegance denominator (docs/05 §5.3)."""
    goal_given_distance: int
    """Figure-graph hops from the goal's points to the nearest point a given mentions. 0 when a
    given touches the goal directly."""
    unused_points: int
    """Drawn points the minimal derivation does not need — `pruned.points - needed_points()`.

    **Recorded, deliberately unscored (M5).** It arrived as the replacement for the
    `requires_auxiliary` feature docs/05 §5.1a specified, which turned out to be identically zero
    (doc 07 T22). This one at least varies — 0 to 5, mean 1.58 over 163 puzzles at seed 42, with
    only 34% at zero — because `prune_figure` closes construction dependencies transitively, so a
    point needed to *build* a kept point survives into the figure with no premise naming it.

    It is not in `SCORING.weights`, and the reason is measured rather than cautious. Spearman
    against every difficulty signal on the same corpus:

        n_points +0.777 | depth -0.048 | width -0.110 | distinct_rules -0.140
        branch_join -0.147 | score -0.096

    So it is overwhelmingly a proxy for *figure size* and, if anything, runs the wrong way against
    difficulty: mean unused is 1.80 in easy and 2.11 in hard but 0.00 in expert (n=8 — thin, and
    the direction agrees with the rank correlations). Weighting it positively would score big
    rambling figures as hard, which is precisely the mistake doc 07 T19 records for proof depth.

    What it is genuinely evidence *for* is the sampler. A high count means Stage 1 built structure
    the puzzle then made no use of, so it belongs to the doc 07 L4 case that generation is the
    bottleneck, and it is reported as a build diagnostic rather than a difficulty term. Any future
    move to weight it must re-measure these correlations first."""

    @property
    def is_pure_algebra(self) -> bool:
        return self.geometric_steps == 0


def measure(derivation: Derivation, translation: Translation, pruned: Construction) -> Features:
    """All features for one candidate. Pure: no engine, no I/O, no randomness."""
    subdag = derivation.subdag
    published = tuple(step.rule for step in translation.steps)
    geometric = tuple(t for t in published if is_geometric(t))
    tiers = {tier_for(t) for t in published} or {1}

    return Features(
        depth=subdag.depth,
        width=subdag.width,
        distinct_rules=subdag.distinct_rules,
        tier_max=max(tiers),
        tier_mix=len(tiers),
        branch_join=_branch_joins(derivation),
        nice_penalty=_nice_penalty(derivation),
        published_steps=len(published),
        geometric_steps=len(geometric),
        distinct_templates=len(set(published)),
        rule_share_max=_rule_share(geometric),
        n_points=len(pruned.points),
        n_circles=sum(1 for f in derivation.premises if f.kind in CIRCLE_KINDS),
        n_premises=len(derivation.premises),
        construction_steps=len(pruned.steps),
        goal_given_distance=_goal_given_distance(derivation),
        unused_points=len(frozenset(pruned.points) - derivation.needed_points()),
    )


def _branch_joins(derivation: Derivation) -> int:
    subdag = derivation.subdag
    leaves = {f.fact_id for f in (*subdag.premises, *subdag.configuration, *subdag.trivial)}
    return sum(
        1 for step in subdag.steps if len({p for p in step.premises if p not in leaves}) >= 2
    )


def _rule_share(geometric: tuple[str, ...]) -> float:
    """Dominance of one template over the published geometric steps.

    Returns 0 below `min_steps_for_share`. A share over one or two steps is not evidence of
    monotony — 66 of 118 measured solutions have exactly one geometric step, and calling those
    "100% one rule" would reject more than half the corpus for a ratio with no denominator.
    """
    from geoforge.config import FILTERS

    if len(geometric) < FILTERS.min_steps_for_share:
        return 0.0
    counts = Counter(geometric)
    return max(counts.values()) / len(geometric)


def _degrees(fact: Fact) -> int | None:
    """A constant-angle fact's value in whole degrees, or None if it is not one."""
    if fact.kind is not FactKind.CONSTANT_ANGLE or fact.value is None:
        return None
    degrees = Fraction(fact.value) * 180
    return int(degrees) if degrees.denominator == 1 else None


def _nice_penalty(derivation: Derivation) -> float:
    """How much the puzzle gives away, in [0, 1] (docs/05 §5.1).

    **Two of the doc's three components ship.**

    1. *Answer telegraphed by a given* — the answer is literally one of the stated values. The
       player reads it off the list rather than deriving it.
    2. *Round values everywhere* — the share of stated angle values, plus the answer, drawn
       from the round palette. MEASURED at seed 42: 45 deg is the answer of 80 of 118 puzzles
       and 90 deg of 26, so this is the dominant shape of the corpus rather than an occasional
       blemish.

    *Symmetric freebies* does **not** ship. Deciding that a figure is symmetric and that its
    answer follows from the symmetry needs the graph canonicalization M4 builds for dedupe.
    Implementing a weaker guess here would put a number nobody can justify into the published
    difficulty. Recorded in docs/05 §5.1 rather than left as a silent gap.
    """
    goal_degrees = _degrees(derivation.goal)
    given_degrees = [d for d in (_degrees(f) for f in derivation.premises) if d is not None]

    telegraphed = 1.0 if goal_degrees is not None and goal_degrees in given_degrees else 0.0

    values = [*given_degrees, *([goal_degrees] if goal_degrees is not None else [])]
    if values:
        round_share = sum(1 for d in values if d in SCORING.round_answer_degrees) / len(values)
    else:
        round_share = 0.0

    # Telegraphing is the worse of the two, so it alone reaches the cap.
    return min(1.0, telegraphed + 0.5 * round_share)


def _goal_given_distance(derivation: Derivation) -> int:
    """Hops from the goal's points to the nearest point a stated given mentions.

    The graph is over points, with an edge between any two the *same* fact names — the figure
    as the premises describe it, not as it is drawn, since what matters is how far the argument
    has to travel. Unreachable counts as 0 rather than infinity: a goal in a component no given
    touches is not "very interesting", it is a puzzle that should not have been formed, and the
    well-posedness gate is what says so.
    """
    facts = (*derivation.premises, *derivation.configuration)
    adjacency: dict[str, set[str]] = {}
    for fact in facts:
        for a in fact.args:
            for b in fact.args:
                if a != b:
                    adjacency.setdefault(a, set()).add(b)

    given_points = {arg for fact in derivation.premises for arg in fact.args}
    goal_points = set(derivation.goal.args)
    if not given_points or goal_points & given_points:
        return 0

    queue = deque((point, 0) for point in goal_points)
    seen = set(goal_points)
    while queue:
        point, distance = queue.popleft()
        if point in given_points:
            return distance
        for neighbour in adjacency.get(point, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append((neighbour, distance + 1))
    return 0
