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


@dataclass(frozen=True)
class GenerationConfig:
    """Sampling and goal selection (docs/04 Stages 1, 2, 5)."""

    min_construction_steps: int = 3
    max_construction_steps: int = 9
    """DOC docs/04 Stage 1."""

    circle_step_weight: float = 2.0
    """GUESS, informed by PHASE0: circles carry most of the non-trivial difficulty in angle
    chasing, so the grammar is biased toward them. Retune against attrition data."""

    max_given_parameters: int = 3
    """DOC docs/04 Stage 2: how many free angle parameters get concrete values."""

    nice_angle_degrees: dict[str, tuple[int, ...]] = field(
        default_factory=lambda: {
            "easy": tuple(range(20, 90, 10)),
            "medium": tuple(range(15, 90, 5)),
            "hard": tuple(range(11, 90)),
            "expert": tuple(range(11, 90)),
        }
    )
    """DOC docs/04 Stage 2 'nice value' palette per band: easy uses multiples of 10, harder
    bands allow awkward integers. Moves into the quantity-type registry in M3 (docs/04 QTR)."""

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
class BandingConfig:
    """PROVISIONAL depth-only banding (Phase 1 only).

    The real multi-feature scorer is Phase 2 (docs/05 §5.1). This exists solely to satisfy the
    Phase 1 acceptance criterion of '>= 2 bands' and must be replaced, not extended.
    """

    depth_thresholds: dict[str, int] = field(
        default_factory=lambda: {"easy": 3, "medium": 5, "hard": 7, "expert": 9}
    )
    """GUESS: lower bound on minimal-proof depth for each band."""


SOLVER = SolverConfig()
TOLERANCE = ToleranceConfig()
DEGENERACY = DegeneracyConfig()
GENERATION = GenerationConfig()
EXTRACTION = ExtractionConfig()
MINIMIZATION = MinimizationConfig()
WELLPOSED = WellPosedConfig()
TRANSLATION = TranslationConfig()
BANDING = BandingConfig()
