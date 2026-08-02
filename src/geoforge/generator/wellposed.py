"""Stage 8: the well-posedness gate (docs/04) — the critical correctness gate.

A puzzle is well-posed when its stated premises **plus its configuration facts** determine the
answer. Everything upstream can be right and the puzzle still be broken: the engine proves the goal
holds of *this* figure, but a player is entitled to any figure matching the statement, and if the
answer moves between those the puzzle has no answer.

The check is empirical, and deliberately so — a symbolic uniqueness proof is a much harder problem
than the one we set out to solve. Resample the construction with fresh free parameters, keep only
samples whose configuration matches the reference, and require the answer to be the same in all of
them.

Three distinctions the gate depends on:

* **A configuration flip is not ill-posedness.** Reflecting a point to the far side of a line
  gives a legitimately different figure, in which the answer may legitimately differ. Those
  samples are discarded, not counted against the puzzle. Failing to make this distinction
  would reject nearly every good puzzle.
* **Underdetermination is this gate working, not a bug** (amended in M5; docs/07 T13). `docs/04`
  Stage 8 originally read a deviation among configuration-matching samples as an upstream soundness
  bug. M5 measured that the recorded configuration facts do *not* pin the figure completely — the
  engine records what its rules needed, not a full description — so a proved value can depend on the
  reference diagram in ways nothing we state captures. Those puzzles have no answer and are
  discarded. The one verdict that does indict the engine is `ENGINE_CONTRADICTS_DIAGRAM`.
* **The check is on the published sentences, not on angle values** (`docs/04` Stage 8 item 2b).
  Steps are re-rendered from each resampled figure and the text must come out identical. Freezing
  each stated angle's value would be wrong: a step says "∠CAO = ∠OCA", and as C runs round its
  circle both angles change while the sentence stays true. Only what a sentence claims must hold.

Residual limit, accepted and recorded (docs/07 T3): resampling explores the *construction's*
parameterization of the premise manifold, not the whole manifold. Cross-engine validation (M6)
is the compensating control.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from geoforge.config import TRANSLATION, WELLPOSED
from geoforge.generator.construction import Construction
from geoforge.generator.traceback import Derivation
from geoforge.generator.translation import Translation, translate
from geoforge.generator.translation.vertex_angles import VertexAngle, measure
from geoforge.solvers.interface import SolverBackend
from geoforge.solvers.types import Fact, SolveOptions


class WellPosedReason(StrEnum):
    """Why a puzzle failed the gate."""

    TOO_FEW_SAMPLES = "too_few_samples"
    """Not enough configuration-matching resamples to conclude anything. Attrition: the gate
    declined to certify, which is not the same as finding a problem."""
    GOAL_UNDERDETERMINED = "goal_underdetermined"
    """The answer moved between two figures that both satisfy everything the puzzle states.
    The puzzle has no answer, so it is discarded — **this is the gate working**, not a bug."""
    STEP_UNDERDETERMINED = "step_underdetermined"
    """A solution step's vertex angle moved. The sentence is true of the shipped figure and false
    of another one the statement allows."""
    UNMEASURABLE = "unmeasurable"
    """The goal has no vertex-angle reading, so there is nothing to compare."""
    ENGINE_CONTRADICTS_DIAGRAM = "engine_contradicts_diagram"
    """**The one genuine soundness failure.** The engine symbolically proved a fact that is
    numerically false in the very diagram it proved it about. Nothing downstream can compensate
    for that, so it fails the build (docs/04 Stage 4's numeric guard, applied here too)."""


@dataclass(frozen=True, slots=True)
class WellPosedVerdict:
    ok: bool
    samples_accepted: int
    samples_rejected: int
    """Resamples discarded for having a different configuration. Expected, not a problem."""
    reason: WellPosedReason | None = None
    detail: str = ""
    reproduction: str | None = None
    """Serialized case for a soundness failure. docs/08 §8.1: a correctness failure is filed,
    never silently skipped."""

    @property
    def is_soundness_failure(self) -> bool:
        """Whether this verdict means a *bug*, as opposed to the gate doing its job.

        The 1,000-construction acceptance run (docs/09 P1) counts these and must see zero.

        Underdetermination is deliberately **not** counted here. `docs/04` Stage 8 originally read
        a deviation among configuration-matching samples as an upstream soundness bug, on the
        assumption that the recorded configuration facts pin the figure completely. M5 measured
        that they do not: the engine's numerical checks record what its *rules* needed, not a full
        description of the configuration, and an angle-chased `aconst` can depend on the reference
        diagram in ways no recorded fact captures. Discarding those puzzles is the entire point of
        this gate. Calling each one a build-failing bug would cry wolf and hide the real signal.
        Recorded as docs/07 T13.
        """
        return self.reason is WellPosedReason.ENGINE_CONTRADICTS_DIAGRAM

    @property
    def is_underdetermined(self) -> bool:
        """The statement does not pin the answer. Ordinary attrition, but worth counting: a rising
        rate means the sampler is producing figures whose configuration we cannot express."""
        return self.reason in (
            WellPosedReason.GOAL_UNDERDETERMINED,
            WellPosedReason.STEP_UNDERDETERMINED,
        )


def check(
    backend: SolverBackend,
    construction: Construction,
    derivation: Derivation,
    translation: Translation,
    goal_angle: VertexAngle,
    reference_coords: dict[str, tuple[float, float]],
    seed: int,
) -> WellPosedVerdict:
    """Resample the construction and require the published answer to be invariant.

    `goal_angle` is the vertex angle actually published as the question, carrying the exact answer
    the reference diagram gave.
    """
    configuration = derivation.configuration

    # The engine's symbolic claim must hold of the diagram it made the claim about. This is the
    # only failure here that indicts the engine rather than the puzzle, and nothing downstream
    # could compensate for it (docs/02 invariant 4).
    try:
        if not all(backend.check_facts(_as_points(reference_coords), (derivation.goal,))):
            return WellPosedVerdict(
                ok=False,
                samples_accepted=0,
                samples_rejected=0,
                reason=WellPosedReason.ENGINE_CONTRADICTS_DIAGRAM,
                detail=f"{derivation.goal.fact_id} is false in the reference figure",
                reproduction=_reproduction(
                    construction, derivation, goal_angle, 0.0, 0.0, seed, seed
                ),
            )
    except Exception as exc:
        return WellPosedVerdict(
            ok=False,
            samples_accepted=0,
            samples_rejected=0,
            reason=WellPosedReason.UNMEASURABLE,
            detail=f"goal not numerically checkable: {type(exc).__name__}",
        )

    if goal_angle.degrees is None:
        return WellPosedVerdict(
            ok=False,
            samples_accepted=0,
            samples_rejected=0,
            reason=WellPosedReason.UNMEASURABLE,
            detail="goal has no vertex-angle value",
        )

    # What must hold of every admissible figure is **the sentences we publish**, so the check is
    # to re-render them from the resampled figure and require the same text.
    #
    # This replaces the obvious-looking alternative of freezing each stated angle's value or its
    # direct/supplement reading, both of which are wrong. A step says "∠CAO = ∠OCA"; as C runs
    # round its circle both of those angles change and both readings flip *together*, and the
    # sentence stays true throughout. Only what a sentence actually claims has to be stable, and
    # re-rendering is precisely the test of that.
    reference_text = _rendered(translation)

    # The published answer must be what the reference figure actually shows. If these disagree,
    # every later comparison is against the wrong number, and no amount of resampling notices.
    measured_goal = measure(reference_coords, goal_angle.p, goal_angle.vertex, goal_angle.q)
    published = float(goal_angle.degrees)
    if (
        measured_goal is None
        or abs(measured_goal - published) > TRANSLATION.angle_render_tolerance_degrees
    ):
        return WellPosedVerdict(
            ok=False,
            samples_accepted=0,
            samples_rejected=0,
            reason=WellPosedReason.UNMEASURABLE,
            detail=f"published answer {goal_angle.degrees}° is not what the reference figure shows",
        )

    accepted = 0
    rejected = 0

    for attempt in range(WELLPOSED.max_resample_attempts):
        if accepted >= WELLPOSED.n_samples:
            break
        # A distinct seed per attempt, offset well clear of the generation seed so a resample
        # never silently reproduces the reference figure and "confirms" it against itself.
        sample_seed = seed + 1_000_003 + attempt
        figure = backend.realize(construction.to_spec(), SolveOptions(seed=sample_seed))
        if not figure.ok:
            rejected += 1
            continue

        coords = figure.coords()
        if not _same_configuration(backend, figure.points, configuration):
            rejected += 1
            continue

        # The answer itself must not move.
        observed_goal = measure(coords, goal_angle.p, goal_angle.vertex, goal_angle.q)
        if observed_goal is None:
            rejected += 1
            continue
        if abs(observed_goal - measured_goal) > WELLPOSED.relative_tolerance * 180.0:
            return _underdetermined(
                WellPosedReason.GOAL_UNDERDETERMINED,
                accepted,
                rejected,
                f"{goal_angle.text}: {measured_goal:.6f}° here, {observed_goal:.6f}° in a figure "
                "satisfying everything the puzzle states",
                construction,
                derivation,
                goal_angle,
                measured_goal,
                observed_goal,
                seed,
                sample_seed,
            )

        # Every published sentence must say the same thing about this figure too.
        sample_text = _rendered(translate(derivation.subdag, coords))
        if sample_text != reference_text:
            return _underdetermined(
                WellPosedReason.STEP_UNDERDETERMINED,
                accepted,
                rejected,
                _first_difference(reference_text, sample_text),
                construction,
                derivation,
                goal_angle,
                measured_goal,
                observed_goal,
                seed,
                sample_seed,
            )
        accepted += 1

    if accepted < WELLPOSED.n_samples:
        return WellPosedVerdict(
            ok=False,
            samples_accepted=accepted,
            samples_rejected=rejected,
            reason=WellPosedReason.TOO_FEW_SAMPLES,
            detail=f"{accepted} of {WELLPOSED.n_samples} required samples",
        )
    return WellPosedVerdict(ok=True, samples_accepted=accepted, samples_rejected=rejected)


def _rendered(translation: Translation) -> tuple[str, ...]:
    """The published sentences, in order. An untranslatable resample yields a shorter tuple,
    which is itself a difference — a figure whose solution cannot even be written is not one the
    puzzle should be claiming to cover."""
    return tuple(step.text for step in translation.steps)


def _first_difference(reference: tuple[str, ...], sample: tuple[str, ...]) -> str:
    for index, (expected, observed) in enumerate(zip(reference, sample, strict=False)):
        if expected != observed:
            return f"step {index + 1}: {expected!r} becomes {observed!r}"
    return f"solution length {len(reference)} becomes {len(sample)}"


def _underdetermined(
    reason: WellPosedReason,
    accepted: int,
    rejected: int,
    detail: str,
    construction: Construction,
    derivation: Derivation,
    angle: VertexAngle,
    expected: float,
    observed: float,
    seed: int,
    sample_seed: int,
) -> WellPosedVerdict:
    return WellPosedVerdict(
        ok=False,
        samples_accepted=accepted,
        samples_rejected=rejected,
        reason=reason,
        detail=detail,
        reproduction=_reproduction(
            construction, derivation, angle, expected, observed, seed, sample_seed
        ),
    )


def _as_points(coords: dict[str, tuple[float, float]]) -> tuple[tuple[str, float, float], ...]:
    return tuple(sorted((name, x, y) for name, (x, y) in coords.items()))


def _same_configuration(
    backend: SolverBackend,
    points: tuple[tuple[str, float, float], ...],
    configuration: tuple[Fact, ...],
) -> bool:
    """Whether a resampled figure sits in the same configuration as the reference."""
    if not configuration:
        return True
    try:
        return all(backend.check_facts(points, configuration))
    except Exception:
        # An unevaluable configuration fact must not pass as "matching": that would admit
        # flipped figures and turn a legitimate discard into a spurious soundness failure.
        return False


def _stated_angles(translation: Translation, goal_angle: VertexAngle) -> tuple[VertexAngle, ...]:
    """Every vertex angle the published puzzle asserts: the goal, plus each step's angles.

    Step angles are recovered from the normative `angle:<P>:<VERTEX>:<P>` highlights (docs/02),
    which is exactly the set of angles a step puts in front of the player.
    """
    # Values are stripped: the gate compares measurement against measurement, and a value would
    # make the goal a different dict key from the same angle named by a step's highlight.
    angles: dict[VertexAngle, None] = {
        VertexAngle(p=goal_angle.p, vertex=goal_angle.vertex, q=goal_angle.q): None
    }
    for step in translation.steps:
        for highlight in step.highlights:
            parts = highlight.split(":")
            if parts[0] != "angle" or len(parts) != 4:
                continue
            p, vertex, q = (part.lower() for part in parts[1:])
            angles[VertexAngle(p=p, vertex=vertex, q=q)] = None
    return tuple(angles)


def _reproduction(
    construction: Construction,
    derivation: Derivation,
    angle: VertexAngle,
    expected: float,
    observed: float,
    seed: int,
    sample_seed: int,
) -> str:
    """Everything needed to reproduce a soundness failure from a clean checkout."""
    return json.dumps(
        {
            "kind": "wellposedness_soundness_failure",
            "construction": construction.to_jgex(),
            "generation_seed": seed,
            "resample_seed": sample_seed,
            "angle": angle.text,
            "expected_degrees": expected,
            "observed_degrees": observed,
            "goal": derivation.goal.fact_id,
            "premises": [f.fact_id for f in derivation.premises],
            "configuration": [f.fact_id for f in derivation.configuration],
        },
        indent=2,
        sort_keys=True,
    )
