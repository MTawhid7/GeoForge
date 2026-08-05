"""Threshold constants, grouped by concern. See config/__init__.py for the hard rule.

Provenance tags:
  PHASE0  measured in spikes/p0/REPORT.md
  DOC     specified in docs/NN
  GUESS   informed starting value, expected to be retuned against data
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SolverConfig:
    """Engine invocation limits (docs/03 §3.3)."""

    backend: str = "yuclid"
    """PHASE0: Yuclid is primary — 23-26x faster, and the pure-Python rule matcher cannot
    apply rules containing numeric constants (BUG-2). 'python' is debug-only."""

    max_facts: int = 20_000
    """DOC docs/03: resource cap; constructions hitting it are discarded and logged."""

    max_wall_seconds: float = 5.0
    """DOC docs/03. PHASE0 context: the slowest spike problem took 0.4 s on Yuclid."""


@dataclass(frozen=True)
class ToleranceConfig:
    """The single source of truth for numeric comparison (docs/04 'Tolerance policy')."""

    absolute: float = 1e-7
    """DOC docs/04: absolute tolerance on normalized quantities (radians, unit-scale coords).
    Never compare floats for equality; never let a numeric check pass a fact no symbolic
    derivation produced."""

    max_denominator: int = 1_000_000
    """PHASE0: matches newclid.tools.get_quotient, which raises past this. Doubles as the
    'nice value' filter — an angle that is not a rational multiple of pi is not a puzzle."""


@dataclass(frozen=True)
class DegeneracyConfig:
    """Stage-3 cheap numeric pre-checks, run before the engine call (docs/04)."""

    min_point_separation: float = 1e-2
    """DOC docs/04 (unit-scale figure)."""

    min_triangle_area: float = 1e-3
    """DOC docs/04: also the accidental-collinearity test."""

    min_angle_degrees: float = 1.0
    """DOC docs/04: reject angles within this of 0 deg or 180 deg."""


@dataclass(frozen=True, slots=True)
class BandProfile:
    """How Stage 1 samples for one band (docs/04 Stage 1).

    Added Phase 3 M4. `sample_construction` has always taken a `band`, and the batch runner has
    never passed one, so every construction in every band was drawn on the easy profile. One
    profile per band is the fix; `GenerationConfig.band_mix` decides how the budget is split.
    """

    min_steps: int
    max_steps: int
    circle_weight: float
    """Relative pick weight for primitives that put a **drawable** circle into the figure —
    `circle` and `on_circum`, the only two the renderer will draw (`solvers/catalog.py`).
    There are 2 of them against 60 other usable extensions, so the pick probability per step is
    `2w / (60 + 2w)`: w=2 gives 6%, w=10 gives 25%, w=20 gives 40%. The old global value of 2.0
    was spread across 37 mis-flagged primitives and bought nothing."""
    angle_weight: float
    """Relative pick weight for primitives that state an angle value (`s_angle`, `aconst`).
    MEASURED Phase 3 M4: at weight 1.0 only 2 of 22 surviving puzzles stated an angle at all, so
    the per-band angle palette governed 9% of the corpus and the rest answered 45 degrees because
    the figure contained a square. A puzzle asking for an angle should usually be given one."""
    require_angle_given: bool
    """Force an early step to state an angle value.

    A figure that states no angle can only have its angles determined by its own symmetry, and
    a symmetric figure's angles are the multiples of 30 and 45 that
    `GenerationConfig.rejected_answer_degrees` throws away. MEASURED at seed 42: with the
    rejection on and this off, 600 constructions yielded **one** puzzle.

    Weighting alone does not achieve it — at `angle_weight` 6-12, 91% of surviving puzzles still
    stated no angle, because a weighted draw that misses simply never comes back to it."""
    max_goals: int
    """Goal candidates kept per construction (docs/04 Stage 5)."""
    max_givens: int
    """How many angle givens `sampler.decorate` appends to a seeded human configuration
    (docs/04 Stage 1b, docs/07 T24).

    Distinct from `require_angle_given`, which forces *one* given into a grown construction. A
    seeded skeleton is far richer — 7 to 17 points against our 3 to 9 — so one given often leaves
    most of it undetermined and Stage 5 finds nothing. More givens pin more of the figure and
    raise yield; too many make the answer a restatement of a given, which Stage 5's
    `already_given` check then discards. Capped again inside `decorate` at half the skeleton's
    point count, so a small skeleton is never over-constrained.

    MEASURED 2026-08-05, seed 42, n=40 expert-band figures per row (docs/07 T26). Sweeping this
    value trades goal yield against the auxiliary-construction rate:

    | givens | goals | aux | aux rate | structural saturation |
    |---|---|---|---|---|
    | 1 | 24 | 2 | 8.3% | 84.1% |
    | 2 | 28 | 2 | 7.1% | 84.0% |
    | 3 | 39 | 2 | 5.1% | 83.2% |
    | 4 | 41 | 2 | 4.9% | 82.6% |

    Read this carefully before "tuning for aux": the **absolute aux count is invariant at 2**.
    Extra givens do not destroy aux puzzles, they add easy ones, so the rate falls by dilution.
    Lowering this value raises the ratio and lowers the yield, and produces no more aux puzzles
    per unit compute — which is the only quantity that matters once M8 filters for aux anyway.
    Saturation barely moves because it is a property of the *skeleton*, not of the decoration."""
    region_weight: float = 1.0
    """Relative pick weight for primitives that bound a closed polygonal region
    (`ConstructionDef.bounds_region`) — the regions an area puzzle can ask about (docs/10 §10.7).

    MEASURED 2026-08-05, seed 42, 300 grown expert constructions: the region primitives appear
    **10-20 times each** against `circle` at 283 and `on_circum` at 272, so at weight 1.0 a
    6-step figure almost never contains one. The 635 seeded configurations are worse for this
    specific purpose — triangle- and circle-rich but with `r_trapezoid` and `eqdia_quadrangle`
    appearing **zero** times, `pentagon` and `rectangle` once each.

    Default 1.0 keeps every existing band byte-identical; only the `area` profile raises it. This
    is deliberate — `circle_weight` was once a global 2.0 spread across 37 mis-flagged primitives
    and it bought nothing while looking like it worked (docs/09 P3 M4), so a new weight ships off
    everywhere it has not been measured."""
    length_weight: float = 1.0
    """Relative pick weight for primitives that state a length value (`lconst`, `l2const`).

    Area is dimensional and needs a pinned scale where angle forbids one (docs/07 T7). This is
    the grown-construction counterpart of `max_length_givens`, which does the same job for seeded
    skeletons. Same reasoning as `region_weight` for the 1.0 default."""
    require_length_given: bool = False
    """Force one step that states a length into a *grown* construction (docs/10 §10.6).

    The scale counterpart of `require_angle_given`, and forced for the same measured reason: a
    weighted draw that misses never comes back. MEASURED 2026-08-05 at `length_weight` 10.0,
    only **78 of 200** area-profile constructions pinned a scale without this. An area puzzle over
    an unpinned figure has no determined answer, so this is a correctness requirement for the
    area profile rather than a yield tweak.

    Default False: no difficulty band pins a scale, and none should start."""
    max_length_givens: int = 0
    """How many `lconst` givens `sampler.decorate` appends to a seeded skeleton (docs/10 §10.6).

    **Default 0 — no existing band pins a scale, and angle puzzles must not start.** A stated
    length is a premise Stage 6 must keep, and pinning two independent lengths over-determines a
    figure, so this should stay at 0 or 1 until measured otherwise."""


@dataclass(frozen=True)
class GenerationConfig:
    """Sampling and goal selection (docs/04 Stages 1, 2, 5)."""

    band_profiles: dict[str, BandProfile] = field(
        default_factory=lambda: {
            "easy": BandProfile(
                min_steps=3,
                max_steps=5,
                circle_weight=3.0,
                angle_weight=6.0,
                require_angle_given=True,
                max_goals=3,
                max_givens=1,
            ),
            "medium": BandProfile(
                min_steps=4,
                max_steps=7,
                circle_weight=8.0,
                angle_weight=8.0,
                require_angle_given=True,
                max_goals=3,
                max_givens=2,
            ),
            "hard": BandProfile(
                min_steps=5,
                max_steps=9,
                circle_weight=14.0,
                angle_weight=10.0,
                require_angle_given=True,
                max_goals=3,
                max_givens=2,
            ),
            "expert": BandProfile(
                min_steps=6,
                max_steps=9,
                circle_weight=20.0,
                angle_weight=12.0,
                require_angle_given=True,
                max_goals=3,
                max_givens=3,
            ),
            # A sampling profile, not a difficulty band -- `Band` is `str` and `profile_for`
            # falls back to easy for anything unknown, so this is inert until the area pipeline
            # asks for it by name (docs/10 step A1).
            "area": BandProfile(
                min_steps=4,
                max_steps=8,
                circle_weight=8.0,
                angle_weight=8.0,
                require_angle_given=True,
                max_goals=3,
                max_givens=1,
                region_weight=12.0,
                length_weight=10.0,
                require_length_given=True,
                max_length_givens=1,
            ),
        }
    )
    """DOC docs/04 Stage 1. MEASURED at seed 42 — see the M4 attrition note in docs/09.

    The four difficulty bands are measured. **The `area` profile's weights are NOT** — they are
    starting values chosen to be re-measured by docs/10 step A1, and they are recorded as guesses
    on purpose so nobody later reads them as evidence. The reasoning behind each: `region_weight`
    dominates because regions are the *target* of an area question and are otherwise drawn 10-20
    times per 300 constructions; `length_weight` and `max_length_givens=1` pin the scale a
    dimensional quantity needs; `circle_weight` is 8 rather than expert's 20 because at 20 the
    two circle primitives took 555 of ~1000 sampled steps and would crowd out the regions;
    `angle_weight` stays up because ½·a·b·sin C needs a stated angle."""

    band_mix: dict[str, float] = field(
        default_factory=lambda: {"easy": 0.15, "medium": 0.25, "hard": 0.35, "expert": 0.25}
    )
    """Share of constructions sampled on each profile. Weighted away from easy on purpose: the
    profile is an *input*, not the band a puzzle ends up in, and easy was oversupplied 23:6 over
    hard while expert was empty. Must be non-empty; values are normalized, so they need not
    sum to 1."""

    max_seed_points: int = 12
    """Largest human configuration Stage 1b will use (docs/04 Stage 1b, docs/07 T24).

    MEASURED: the library runs to 31 points and engine closure cost is superlinear in the point
    count, so the long tail dominates throughput. Uncapped seeding at `corpus_share` 0.5 took
    batch throughput from 29.9 to 2.7 constructions/s — an 11x regression that also made the test
    suite unusable. 12 keeps 514 of 635 configurations (81%) and drops the tail that pays least
    per second. Not a difficulty judgement: a 20-point figure is not too hard, it is too slow, and
    if throughput stops binding this should rise."""

    corpus_share: float = 0.0
    """Share of constructions seeded from the human configuration library rather than grown
    (docs/04 Stage 1, docs/07 T24).

    **Default 0.0 — seeding is built, tested and OFF, pending M7.** MEASURED at seed 42, n=3000,
    `corpus_share` 0.5, before `max_seed_points` existed:

    | source | constructions | puzzles | yield |
    |---|---|---|---|
    | grown  | 1530 | 86 | 5.6% |
    | seeded | 1470 | 10 | 0.7% |

    Seeded skeletons yield **6x better at goal extraction** (33% against 5.4%) and **8x worse
    end to end**, and cost 11x throughput (29.9 -> 2.7 constructions/s). The goals are found and
    then die downstream, concentrated in `translate:unknown_rule`,
    `translate:unspeakable_conclusion` and `translate:ar_chain_too_long` — richer configurations
    are proved by theorems the 19-rule whitelist cannot pronounce. That whitelist is exactly what
    M7's LLM renderer retires (docs/07 T17), so seeding is gated on M7 rather than broken.

    **This attribution is a hypothesis consistent with the aggregate attrition, not a measured
    per-source split** — the run that would have separated the two was interrupted. Re-measure it
    before turning this up, and re-measure throughput too: `max_seed_points` landed after the
    numbers above and drops the 19% tail that cost the most.

    A share and not a switch, because the two sources fail in opposite ways: the library is finite
    so a bank built only from it repeats skeletons, while clause growth is unbounded but small and
    symmetric. `BatchReport.sampled_origins` and `.puzzle_origins` keep both halves visible."""

    @property
    def min_construction_steps(self) -> int:
        return min(p.min_steps for p in self.band_profiles.values())

    @property
    def max_construction_steps(self) -> int:
        """DOC docs/04 Stage 1. Derived from the profiles so there is one source of truth."""
        return max(p.max_steps for p in self.band_profiles.values())

    max_given_parameters: int = 3
    """DOC docs/04 Stage 2: how many free angle parameters get concrete values."""

    nice_angle_degrees: dict[str, tuple[int, ...]] = field(
        default_factory=lambda: {
            "easy": tuple(range(20, 90, 10)),
            "medium": tuple(range(15, 90, 5)),
            "hard": tuple(d for d in range(12, 89, 2) if d % 10),
            "expert": tuple(d for d in range(12, 89, 2) if d % 10),
        }
    )
    """DOC docs/04 Stage 2 'nice value' palette per band.

    **Upper bands made non-round in Phase 3 M4** (docs/07 T18): `aconst` holds a `Fraction` of
    pi, so 74 degrees costs exactly what 90 does, and the round palette was our config rather
    than an engine limit. Two constraints shape the harder palette:
    - *multiples of 10 are excluded*, because they are what produced an answer distribution of
      71x45 degrees and 15x90 out of 98;
    - *values stay even*, because bisecting an odd angle leaves a half-degree and the angle
      `answer_policy` is whole degrees, so odd givens mostly cost yield rather than buying
      variety."""

    excluded_constructions: frozenset[str] = field(
        default_factory=lambda: frozenset({"test_r20", "test_r25", "e5128", "2l1c", "3peq", "free"})
    )
    """Problem-specific fixtures and bare points rather than general primitives; sampling them
    produces figures that are either degenerate or tied to one published problem."""

    max_clause_attempts: int = 40
    """GUESS: how many times to retry picking a usable primitive before giving up on a step."""

    max_goals_per_construction: int = 3
    """DOC docs/04 Stage 5."""

    min_proof_depth: int = 3
    min_distinct_rules: int = 2
    """DOC docs/05 §5.2 filters 1: below these a puzzle is trivial. Shared with scoring —
    one source, per docs/04 Stage 5."""

    rejected_answer_degrees: frozenset[int] = field(default_factory=lambda: frozenset({45, 90}))
    """Whole-degree answers rejected outright at Stage 5, however good the proof behind them.

    45 and 90 are not merely *common*, they are **recognised rather than measured**. Nobody
    estimates a right angle off a figure; they see one. 45 is the same — it is a square's
    diagonal. Since figures are drawn to scale and stay that way (docs/07 T5, docs/06 §6.3), a
    puzzle answering either has no content left whatever its derivation looks like.

    A **rejection, not a ranking penalty**. MEASURED at seed 42: ranking by proof depth was
    actively concentrating these — 45 degrees was 13 of 47 verified candidates (28%) but 11 of
    24 after ranking (46%), because the engine's longest mechanical chains live in exactly the
    symmetric figures whose angles are round (docs/07 T19). Demoting them in the sort only helps
    when the same construction also offers something better, and most offer nothing else.

    **Why not every multiple of 30, which was tried.** Measured over 3,000 constructions:

    | rejected | puzzles | yield | distinct answers | modal share |
    |---|---|---|---|---|
    | nothing | 163 | 5.43% | 10 | 71.8% |
    | {45, 90} | 25 | 0.83% | 9 | 36.0% |
    | multiples of 30 and 45 | 13 | 0.43% | 7 | 30.8% |

    {45, 90} does almost all the work. Extending to every multiple of 30 removes 12 more
    puzzles, buys 5 percentage points of modal share, and halves the yield again. The residual
    concentration is 30 degrees at 9 occurrences, which is what docs/05 §5.2 filter 8's
    per-band entropy cap is for — a cap limits a value's *share* rather than banning the number,
    so a genuinely hard puzzle answering 60 degrees survives while a bank full of them does not.
    Banning the value outright cannot make that distinction.

    Cost, measured and intended: this deletes 139 of 163 puzzles (docs/09 P3 M4 — the bank
    shrinking sharply is the pass condition). Volume is P4's problem.

    Shared with scoring the same way `min_proof_depth` is — one source, per docs/04 Stage 5. A
    non-integer number of degrees is never rejected: `Fact.value` is a `Fraction` of pi
    (docs/07 T18), so those are genuinely awkward angles and the best answers we produce.
    """


@dataclass(frozen=True)
class ExtractionConfig:
    """Stage-5 quantity extraction: numeric proposes, symbolic verifies (docs/03 §3.3a)."""

    angle_snap_tolerance_degrees: float = 1e-6
    """PHASE1 (measured, not guessed): on realized figures the residual between a genuinely
    exact angle and its integer-degree value is <= 1e-13, while the median residual of an
    arbitrary angle is ~1e-2. Anywhere in that eight-order gap works; 1e-6 leaves seven orders
    of margin against accumulated construction error without admitting junk.

    This replaces `newclid.tools.get_quotient` as the nice-value filter. get_quotient's
    tolerance is *relative*, so its effective window widens with the denominator and it will
    snap almost any value given denominators up to 1e6 — Phase 0 saw it return 17/19 for a
    generic tangent-chord angle. Harmless for soundness (symbolic verification rejected it)
    but it wastes an engine call per junk candidate."""

    min_goal_degrees: int = 1
    max_goal_degrees: int = 179
    """A goal of 0 or 180 degrees is a degenerate figure, not a puzzle."""

    max_candidates_per_construction: int = 24
    """GUESS: cap on proposals put forward for symbolic verification, per construction. Each
    costs one engine call; the snap filter usually leaves far fewer."""

    exclude_given_goals: bool = True
    """DOC docs/04 Stage 5: a goal that is literally one of the construction's stated givens is
    not a puzzle. Kept as a switch so the attrition report can measure how many are lost."""


@dataclass(frozen=True)
class MinimizationConfig:
    """Stage-6 traceback and premise minimization (docs/04)."""

    minimize_premises: bool = True
    max_premise_drop_attempts: int = 32
    """GUESS: one engine call per attempt; a construction with more stated premises than this
    is out of scope for Phase 1 anyway (max 9 steps)."""


@dataclass(frozen=True)
class WellPosedConfig:
    """Stage-8 well-posedness gate (docs/04)."""

    n_samples: int = 64
    """DOC docs/04: resampled instantiations per candidate puzzle."""

    relative_tolerance: float = 1e-6
    """DOC docs/04: max deviation of the goal value across configuration-matching samples."""

    max_resample_attempts: int = 200
    """GUESS: samples whose configuration facts differ from the reference are discarded, so
    the sampler needs headroom to collect n_samples matching ones."""


@dataclass(frozen=True)
class TranslationConfig:
    """Trace -> readable solution steps (docs/03 §3.5)."""

    max_ar_chain: int = 5
    """PHASE0 (this value is measured, not guessed): the fraction of puzzles whose every step
    translates was 46% at 3, 55% at 4, 82% at 5, 91% at 7. The gate needs >= 80%, and
    newclid's AR appendix supplies the coefficients needed to narrate a 5-premise step."""

    angle_render_tolerance_degrees: float = 1e-3
    """PHASE1 M5: tolerance for deciding whether a proved directed angle renders as the vertex
    angle or its supplement. Deliberately looser than
    `EXTRACTION.angle_snap_tolerance_degrees` — that one is a *filter* deciding whether a value
    is nice enough to be an answer, and must be tight; this one only picks between two readings
    that differ by |180 - 2d|, so anything far below that gap works, and near d = 90 the two
    readings coincide and the choice cannot go wrong.

    Measured: the reference figure realizes to ~1e-13, but resampled figures land as far as
    ~1e-6 off. Reusing the extraction tolerance here made the well-posedness gate reject a
    correct Thales solution on the 51st resample."""

    require_full_translation: bool = True
    """DOC docs/03 §3.5: a puzzle ships only if EVERY step of its minimal derivation
    translates. Untranslatable puzzles are discarded, never shipped ugly."""


@dataclass(frozen=True)
class ValidationConfig:
    """Bank-build cross-engine validation (docs/04 §V, docs/02 invariant 3)."""

    backend: str = "ag2ddar"
    """The validator engine. Must never equal `SolverConfig.backend`'s engine — validation on
    the generating engine would only re-confirm its own bugs. `bank/validate.py` enforces it."""

    max_wall_seconds: float = 30.0
    """PHASE1 M6 (measured): DDAR closed a generated puzzle in 35 ms mean, 82 ms max over the
    53 puzzles of a 400-construction batch. The cap is three orders above that, so it fires
    only on a genuine blow-up — pure-Python DDAR searches similar triangles in O(n^3)."""

    numeric_tolerance_degrees: float = 1e-6
    """PHASE1: the bank-tolerance numeric re-check of docs/04 §V — does the published answer
    hold in the puzzle's own reference diagram? Measured: an exact angle realizes to within
    1e-13 of its integer-degree value on a reference figure (this is the reference diagram, not
    a resampled one, so no extra slack is warranted). Separate from
    `TRANSLATION.angle_render_tolerance_degrees`, which answers a different question and is
    deliberately looser."""

    mutation_offset_degrees: int = 1
    """The corruption a mutation test applies to a published answer. One degree is the
    smallest that is still a wrong answer under the integer-degree answer policy, so it is the
    strictest version of "the validator must reject a corrupted answer" (docs/04 §V)."""


@dataclass(frozen=True)
class ScoringConfig:
    """The docs/05 §5.1 difficulty model.

    Every feature is normalized over a *useful range* rather than over [0, cap]: the shippable
    corpus occupies a narrow slice of each feature's arithmetic range (depth is 3-7, never 0-10),
    and dividing by the arithmetic range would squash every real puzzle into the bottom fifth of
    the scale. `lo` is the value at which a puzzle is barely a puzzle — usually the hard filter's
    own floor — and `hi` is where more stops meaning harder.

    MEASURED over 1,200 constructions at seed 42 (118 puzzles): depth 3-7 (median 4), width
    3-14 (median 4), distinct_rules 3-8 (median 4), branch joins 0-5 (median 0, 64 of 118 have
    none). The weights are GUESSes; the ranges are not.
    """

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "depth": 0.30,
            "distinct_rules": 0.18,
            "branch_join": 0.18,
            "tier_max": 0.14,
            "tier_mix": 0.10,
            "width": 0.10,
        }
    )
    """GUESS. They sum to 1, so the weighted sum is in [0, 1] before scaling — which is what
    makes `nice_penalty` expressible as a fraction of the whole scale rather than as a magic
    number of points. docs/05 says depth is primary and the weights are not the stable contract;
    the feature structure is. Retune against a spot check, citing the batch."""

    ranges: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "depth": (3.0, 10.0),
            "distinct_rules": (2.0, 8.0),
            "branch_join": (0.0, 4.0),
            "tier_max": (1.0, 4.0),
            "tier_mix": (1.0, 4.0),
            "width": (3.0, 14.0),
        }
    )
    """(lo, hi) per feature. `lo` matches the corresponding hard filter where one exists, so a
    puzzle that only just survives filtering scores near zero on that feature rather than
    collecting points for clearing a bar it was required to clear."""

    nice_penalty_weight: float = 0.15
    """GUESS: the most a puzzle can lose for being telegraphed — 1.5 points of 10. Subtractive
    per docs/05 §5.1; enough to move a puzzle down a band, not enough to erase a deep proof."""

    scale: float = 10.0
    """docs/05 §5.1: the score is reported 0-10."""

    round_answer_degrees: frozenset[int] = field(
        default_factory=lambda: frozenset({30, 45, 60, 90, 120, 135, 150})
    )
    """MEASURED: 45 deg is the answer of 80 of 118 puzzles and 90 deg of 26 — together 90% of
    the corpus. docs/05's "90/60 everywhere" is real and much stronger than the doc implies,
    which is why `nice_penalty` charges for it rather than treating it as flavour."""


@dataclass(frozen=True)
class BandingConfig:
    """Score-to-band cuts (docs/05 §5.1)."""

    cuts: dict[str, float] = field(
        default_factory=lambda: {"easy": 0.0, "medium": 3.0, "hard": 5.5, "expert": 7.5}
    )
    """DOC docs/05 §5.1: easy [0,3) medium [3,5.5) hard [5.5,7.5) expert [7.5,10]. Lower bound
    per band; the bands must tile [0, scale] with no gap, which `TestBandsTile` asserts."""


@dataclass(frozen=True)
class FilterConfig:
    """docs/05 §5.2 hard rejection filters. Any hit discards the puzzle."""

    min_depth: int = 3
    min_distinct_rules: int = 2
    """DOC docs/05 §5.2 filter 1, over the *minimal sub-DAG*. The same numbers run at Stage 5
    over the whole solve as a cheap pre-filter; the two are not ordered (docs/05 §5.2)."""

    min_geometric_steps: int = 1
    """docs/05 §5.2 filter 2, in the form the corpus actually produces. A solution made only of
    algebraic combination steps is the "read it off the picture" puzzle the doc describes:
    MEASURED, all 4 such puzzles in 118 are a single `combine` sentence at depth 3."""

    max_rule_share: float = 0.6
    min_steps_for_share: int = 3
    """docs/05 §5.2 filter 3, "one rule > 60% of applications". Two calibrations, both MEASURED
    over the same 118 puzzles, because the doc's wording admits three readings and they differ
    by two orders of magnitude:

      * over machine steps of the sub-DAG, the observed maximum share is 0.50 — the filter
        **never fires**, at any threshold the doc could have meant;
      * over published steps counting the algebraic idiom, it rejects 11 (9.3%) — but `combine`
        appears in 118 of 118 puzzles, so that number measures how often the engine did
        arithmetic;
      * over published *geometric* steps, which is what a reader experiences as repetition, it
        rejects 8 (6.8%) at 0.6, 2 at 0.7 and 0 at 0.75.

    So: geometric published steps, threshold 0.6. `min_steps_for_share` exists because a share
    over one or two steps is not evidence of anything — 66 of 118 solutions have exactly one
    geometric step, and rejecting them for "100% one rule" would delete more than half the
    corpus for a ratio with no denominator."""

    min_points: int = 4
    max_points: int = 12
    max_circles: int = 2
    """DOC docs/05 §5.2 filter 4 (v1 readability). MEASURED: points run 3-8, so only the lower
    bound binds and it rejects 1 of 118."""


@dataclass(frozen=True)
class InterestConfig:
    """docs/05 §5.3 interestingness. Soft: ranks within a band, never rejects on its own."""

    keep_rate: dict[str, float] = field(
        default_factory=lambda: {"easy": 0.5, "medium": 0.8, "hard": 0.9, "expert": 1.0}
    )
    """Per band, deviating from docs/05's flat 40% — recorded in the doc, not applied silently.
    The flat rate assumes every band is oversupplied. MEASURED at seed 42 the upper bands are
    filter-limited, not interest-limited, so discarding 60% of expert output would shrink the
    band the roadmap already flags as thin (docs/07 T10) to nothing. Easy is where the surplus
    actually is."""

    elegance_floor: float = 0.0
    """The elegance ratio is a ranking signal, not a gate (docs/05 §5.3: "soft score"). Kept as
    a config value so the decision to leave it open is visible rather than absent."""

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "elegance": 1.0,
            "insight": 0.3,
            "goal_given_distance": 0.3,
            "tier_mix": 0.2,
            "clutter": -0.3,
        }
    )
    """GUESS. docs/05 §5.3 names elegance as the primary signal and the rest as adjustments,
    which is what these magnitudes say.

    Two of them are MEASURED to be constant on current output and therefore contribute nothing
    to the *ranking*, which is all interest is used for: `goal_given_distance` is 0 for all 105
    puzzles (with 4-8 points every premise touches the goal's points, so there is nowhere for
    the argument to travel), and `insight` is 0 for all but 2. They are kept rather than deleted
    because both discriminate on larger figures and both are docs/05 §5.3 terms; the zero is
    recorded here so nobody reads their presence as evidence they are doing something."""


@dataclass(frozen=True)
class SchemaConfig:
    """Puzzle JSON v2 (docs/02). Changing any of these is a schema change."""

    version: str = "2.0"
    """`major.minor`. The frontend refuses an unknown major; a minor bump is additive.
    A string rather than docs/02's sketched integer, because the doc's own rules speak of
    both kinds of bump and an integer can only express one of them."""

    coordinate_decimals: int = 2
    """PHASE2: display coordinates are rounded at emit, so the JSON *is* the artifact rather
    than a view of a longer float. Two decimals over a 1000-unit viewbox is 0.01 units —
    a hundredth of a pixel at full width, far below anything a renderer or an eye resolves.
    It is also the determinism knob: rounding here means two builds agreeing to 1e-9 in
    float space agree byte for byte in JSON."""

    approx_decimals: int = 6
    """PHASE2: `approx` is for input checking and rendering only (docs/02), never for truth.
    Six decimals is well inside the integer-degree answer policy and keeps the field stable
    against last-bit float noise between runs."""

    stripped_fields: tuple[str, ...] = (
        "reference_figure",
        "provenance",
        "configuration",
    )
    """Build-time blocks removed from shipped shards, kept in the build archive (docs/02)."""


@dataclass(frozen=True)
class LayoutConfig:
    """Display figure geometry (docs/06 §6.3).

    The anti-leak thresholds are specified by the doc; the framing values are ours. Nothing
    here moves a point relative to another — every transform the layout applies is a
    similarity, because any other kind breaks a premise (docs/07 T5).
    """

    viewbox_width: float = 1000.0
    viewbox_height: float = 750.0
    """4:3, the aspect docs/06 §6.3 asks the layout to aim for. Fixed rather than per-figure so
    every shard renders in one coordinate system and the frontend never rescales differently
    between puzzles."""

    margin_fraction: float = 0.08
    """GUESS: keeps point labels off the viewbox edge at 360 px width."""

    instantiation_samples: int = 24
    """GUESS: how many fresh instantiations to consider besides the reference figure. Each
    costs one `realize` (a few ms). The reference is always a candidate, so the layout can
    only improve on what Stage 9 would have drawn."""

    seed_offset: int = 7_000_003
    """Keeps layout candidates clear of WELLPOSED's resample seeds (1_000_003), so a drawing is
    never silently the same figure Stage 8 used to confirm the puzzle."""

    rotation_grid_degrees: float = 2.0
    """GUESS: the pose is chosen by scanning this grid over 180 deg. A grid rather than a local
    optimizer because the objective is periodic; 2 deg is well below what an eye reads as tilt."""

    goal_render_tolerance_degrees: float = 1e-3
    """Matches TRANSLATION.angle_render_tolerance_degrees, and for the same reason: a candidate
    drawing is accepted only if the goal still measures what the puzzle publishes."""

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "separation": 1.0,
            "feature_angle": 1.0,
            "clearance": 0.6,
            "aspect": 0.3,
        }
    )
    """GUESS (docs/06 §6.3 item 1): separation and feature angle are what make a figure
    readable, clearance stands in for label-collision risk, and aspect is a mild preference
    rather than a constraint. Retune against the spot check, not by intuition."""

    label_radius: float = 30.0
    """Label offset in viewbox units, measured to the glyph's centre.

    Calibrated against the renderer rather than guessed: `web/src/render/style.ts` draws point
    labels at 34 units and point dots at radius 9, so an offset of 30 leaves roughly half a
    glyph of clear space between the dot and the text. At the narrowest supported width — 360
    px for a 1000-unit viewbox — that is a 12 px label sitting 11 px off its point.

    It is the *magnitude* only; which of the 16 directions each label takes is chosen by
    `place_labels` and shipped in the JSON, because docs/06 §6.3 puts label placement offline
    and leaves the frontend nothing to do but draw at the stated offset."""

    label_directions: int = 16
    """GUESS: compass directions a label may take. Discrete because the choice is coupled only
    through label-label collisions, which a few relaxation passes settle."""

    label_relaxation_passes: int = 4
    """GUESS: greedy placement is order-dependent, so the first point chooses without knowing
    about the last; a few passes let early choices react to late ones."""


@dataclass(frozen=True)
class BankConfig:
    """Bank build and packaging (docs/02, docs/06 §6.5)."""

    shard_size: int = 200
    """GUESS: per-band lazy-loaded shards (docs/06 §6.5). Small enough that the first puzzle
    is interactive before the rest of a band has downloaded."""

    output_dir: str = "banks/v2"
    archive_dirname: str = "_archive"
    """The archive keeps the unstripped payloads, so `bank/validate.py` can be pointed at a
    build months later — which is what its docstring promises and what stripped shards cannot
    support."""

    default_constructions: int = 2_000
    """GUESS: a starting budget for `make bank`. Target-driven generation with per-band floors
    replaces this once the scorer redistributes the bands (docs/09 P2)."""


@dataclass(frozen=True)
class AreaConfig:
    """The area layer (docs/10). Arithmetic on engine-certified quantities, never derivation."""

    verification_tolerance: float = 1e-7
    """How far an exactly-computed area may sit from the shoelace area of the reference diagram
    before the computation is treated as WRONG (docs/10 §10.8).

    This is a soundness check, not a snapping tolerance: it never rounds a value into
    acceptability, it only decides whether an already-exact result agrees with the diagram. A
    disagreement is a bug in the layer or a mis-certified premise, so the layer raises rather
    than discards — the opposite of `EXTRACTION.angle_snap_tolerance_degrees`, which filters
    candidates.

    1e-7 sits between realized-figure construction error (~1e-13 residual on exact quantities,
    the same measurement behind the angle snap tolerance) and the ~1e-2 scale of a genuinely
    different value. Tighter risks false alarms from accumulated float error in Heron on large
    figures; looser would admit a wrong decomposition."""

    max_decomposition_depth: int = 3
    """How far `area._decompose` may recurse through certified midpoint splits (docs/10 §10.5).

    Each level is one area-ratio step in the solution, so this is a difficulty knob as much as a
    termination bound: depth 1 is "a median halves the triangle", depth 2 reaches the medial
    triangle at a quarter. A bound is required regardless, because a cyclic set of midpoint facts
    would otherwise recurse forever.

    3 is a starting value, not a measurement — beyond that the solution's chain of ratio steps
    gets long enough that the puzzle is arithmetic rather than insight, which is the thin-layer
    constraint in docs/10 §10.3."""

    max_region_vertices: int = 6
    """Largest polygon the layer will fan-decompose. Beyond this the figure is too busy for the
    region to be legible in the statement, which is a docs/06 concern rather than a mathematical
    one — the arithmetic scales fine."""


SOLVER = SolverConfig()
TOLERANCE = ToleranceConfig()
AREA = AreaConfig()
DEGENERACY = DegeneracyConfig()
GENERATION = GenerationConfig()
EXTRACTION = ExtractionConfig()
MINIMIZATION = MinimizationConfig()
WELLPOSED = WellPosedConfig()
TRANSLATION = TranslationConfig()
VALIDATION = ValidationConfig()
SCORING = ScoringConfig()
BANDING = BandingConfig()
FILTERS = FilterConfig()
INTEREST = InterestConfig()
SCHEMA = SchemaConfig()
LAYOUT = LayoutConfig()
BANK = BankConfig()
