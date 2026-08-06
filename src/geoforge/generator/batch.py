"""Stage 9 and the batch runner (docs/04).

Runs the whole pipeline over a seed-sharded range of constructions and emits candidate puzzles plus
an attrition report. Two properties matter more than throughput:

**Reproducibility.** The batch is a pure function of `(config, engine_version, master_seed, n)`
(docs/02 invariant 2). Construction *i* is a function of `(master_seed, i)` alone — both the clause
sampling and the engine seed — so shard boundaries change nothing and a single puzzle can be re-run
in isolation. That property is what makes the parallel bank build possible, and it is not free: a
single `Generator` advanced across the loop would make construction *i* depend on every draw before
it, which reads as deterministic in one process and silently produces a different corpus the moment
the range is split. Pinned by `test_batch.py::TestShardability`.

**Every discard is accounted for.** Each one records `(stage, reason, seed)`. The per-stage and
per-band attrition report is the primary regression signal: when a sampler, engine or translator
change shifts the numbers, the report says where. A stage that silently drops a candidate would
make the whole report a guess.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.metadata import version

import numpy as np

from geoforge import schema
from geoforge.config import GENERATION, SOLVER
from geoforge.generator import wellposed
from geoforge.generator.construction import Construction
from geoforge.generator.degeneracy import check_figure
from geoforge.generator.emit import assemble
from geoforge.generator.extract import ExtractedGoal, extract_goals
from geoforge.generator.sampler import draw, profile_for
from geoforge.generator.traceback import Derivation, derive, prune_figure
from geoforge.generator.translation import (
    Translation,
    translate,
    unspeakable_givens,
)
from geoforge.generator.translation.phrases import angle_of
from geoforge.generator.translation.vertex_angles import VertexAngle
from geoforge.schema import SchemaError
from geoforge.scoring import filters
from geoforge.scoring.features import Features, measure
from geoforge.scoring.filters import UnusedGivenBug
from geoforge.scoring.score import Score, score
from geoforge.solvers.interface import SolverBackend, get_backend
from geoforge.solvers.types import Fact, SolveOptions

#: Pipeline stage names, used as attrition keys. Ordered as the pipeline runs.
STAGES = (
    "sample",
    "realize",
    "degeneracy",
    "extract",
    "traceback",
    "translate",
    "wellposed",
    "score",
    "emit",
)


@dataclass(frozen=True, slots=True)
class Discard:
    """One rejected candidate. `(stage, reason, seed)` per docs/04."""

    stage: str
    reason: str
    seed: int
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CandidatePuzzle:
    """Stage 9 output: the shippable puzzle, plus the pipeline objects scoring will need.

    The artifact is `puzzle`, a schema-v2 `Puzzle`. The rest are the generator objects docs/05
    scores over — carried in memory and never serialized, so nothing leaks into the JSON: the
    only thing `to_json` can emit is what the schema defines.
    """

    puzzle: schema.Puzzle
    derivation: Derivation
    translation: Translation
    pruned: Construction
    """The pruned construction — the figure actually drawn. Scoring's elegance denominator."""
    seed: int
    features: Features
    """The docs/05 §5.1 measurements. In memory only; `difficulty.score` is what ships."""
    scored: Score
    full_depth: int = 0
    """Depth of the *whole* solve before minimization. Interestingness reads it: a much longer
    alternate derivation existing in the full DAG means the published short path is an insight
    (docs/05 §5.3)."""

    def to_json(self) -> dict[str, object]:
        return self.puzzle.to_json()

    # Convenience accessors over the artifact, so callers do not reach through two layers.
    @property
    def id(self) -> str:
        return self.puzzle.id

    @property
    def quantity_type(self) -> str:
        return self.puzzle.quantity_type

    @property
    def band(self) -> str:
        return self.puzzle.difficulty.band

    @property
    def depth(self) -> int:
        return self.puzzle.difficulty.depth

    @property
    def distinct_rules(self) -> int:
        return self.puzzle.difficulty.distinct_rules

    @property
    def score(self) -> float:
        return self.scored.value

    @property
    def premises(self) -> tuple[str, ...]:
        return tuple(g.fact for g in self.puzzle.given)

    @property
    def configuration(self) -> tuple[str, ...]:
        return self.puzzle.configuration

    @property
    def goal(self) -> str:
        return self.puzzle.goal.fact

    @property
    def question(self) -> str:
        return self.puzzle.goal.question

    @property
    def answer(self) -> str:
        return self.puzzle.goal.answer.exact

    @property
    def solution(self) -> tuple[schema.Step, ...]:
        return self.puzzle.solution

    @property
    def construction(self) -> str:
        return self.pruned.to_jgex()

    @property
    def provenance(self) -> Mapping[str, object]:
        return self.puzzle.provenance or {}

    @property
    def reference_points(self) -> tuple[tuple[str, float, float], ...]:
        reference = self.puzzle.reference_figure
        return tuple((p.id, p.x, p.y) for p in reference.points) if reference else ()


@dataclass
class BatchReport:
    """What a run produced, and where everything else went."""

    puzzles: list[CandidatePuzzle] = field(default_factory=list)
    discards: list[Discard] = field(default_factory=list)
    soundness_failures: list[str] = field(default_factory=list)
    """The engine contradicting its own diagram. Serialized reproduction cases; docs/09 P1 requires
    zero of these in the acceptance run, and a run that finds one exits non-zero."""
    underdetermined: list[str] = field(default_factory=list)
    """Puzzles whose stated facts do not pin the answer. Ordinary attrition — the well-posedness
    gate catching exactly what it exists to catch (docs/07 T13) — but kept for analysis, because a
    rising rate means the sampler is producing figures whose configuration we cannot express."""
    bugs: list[str] = field(default_factory=list)
    """docs/05 §5.2 filter 5 hits: a stated given the minimal solution never uses. Not attrition
    — minimization and the sub-DAG disagreeing about what the proof needs means one of them is
    wrong. A run that collects one exits non-zero."""
    constructions: int = 0
    sampled_bands: dict[str, int] = field(default_factory=dict)
    """How the Stage-1 profile budget was actually spent (docs/04 Stage 1). Distinct from
    `by_band`, which reports the band each *surviving* puzzle scored into — comparing the two is
    how you see which profile is paying for itself."""
    sampled_origins: dict[str, int] = field(default_factory=dict)
    """`seeded` vs `grown` construction counts (docs/07 T24). The same comparison one level up:
    seeding was adopted on a 60-skeleton probe, and this is what keeps the claim under
    measurement on every build rather than in the commit message that introduced it."""
    puzzle_origins: dict[str, int] = field(default_factory=dict)
    """The other half of that comparison — which source the *surviving* puzzles came from. A
    source can be sampled often and yield nothing, which is precisely the failure mode the
    grown sampler had and the reason this pair of counters exists rather than one."""
    wall_seconds: float = 0.0

    def by_stage(self) -> dict[str, int]:
        return dict(Counter(d.stage for d in self.discards))

    def by_reason(self) -> dict[str, int]:
        return dict(Counter(f"{d.stage}:{d.reason}" for d in self.discards))

    def by_band(self) -> dict[str, int]:
        return dict(Counter(p.band for p in self.puzzles))

    def summary(self) -> dict[str, object]:
        """The reproducible half of the report — everything a rerun must reproduce exactly.

        Wall time is deliberately absent. It belongs in `timing()`, printed rather than
        written, because an artifact carrying it cannot be compared with `diff`: two identical
        builds would differ on a field that says nothing about what they produced. Keeping it
        out is what lets a bank build be verified by comparing files (docs/02 invariant 2).
        """
        return {
            "constructions": self.constructions,
            "puzzles": len(self.puzzles),
            "soundness_failures": len(self.soundness_failures),
            "unused_given_bugs": len(self.bugs),
            "underdetermined": len(self.underdetermined),
            "sampled_bands": dict(sorted(self.sampled_bands.items())),
            "sampled_origins": dict(sorted(self.sampled_origins.items())),
            "puzzle_origins": dict(sorted(self.puzzle_origins.items())),
            "by_band": self.by_band(),
            "attrition_by_stage": self.by_stage(),
            "attrition_by_reason": self.by_reason(),
        }

    def timing(self) -> dict[str, object]:
        """Throughput, which no rerun is expected to reproduce."""
        rate = self.constructions / self.wall_seconds if self.wall_seconds else 0.0
        return {
            "wall_seconds": round(self.wall_seconds, 2),
            "constructions_per_second": round(rate, 1),
        }


def generator_version() -> str:
    try:
        return version("geoforge")
    except Exception:  # not installed as a distribution (editable checkout, CI sandbox)
        return "0.0.0+unknown"


def run(
    n: int,
    seed: int = 42,
    backend: SolverBackend | None = None,
    *,
    check_wellposed: bool = True,
    reject_sight_readable: bool = True,
) -> BatchReport:
    """Run the pipeline over `n` sampled constructions.

    `check_wellposed=False` skips Stage 8 only. It exists for the fast attrition sweeps that shape
    the sampler, never for producing shippable puzzles: without it nothing has verified that the
    answers are answers.

    `reject_sight_readable=False` keeps goals answering a multiple of 30 or 45 degrees
    (docs/07 T5). Same contract as above — a lever for tests and sweeps, never for shipping.
    It exists because the policy costs an order of magnitude of yield (measured at seed 42:
    8.25% to 0.43%), so a test fixture that wants *a corpus of candidate puzzles* to exercise
    machinery on would otherwise need thousands of constructions and still cover its shapes by
    luck. The rejection itself is asserted directly instead, where it can be seen to fire.
    """
    backend = backend or get_backend()
    report = BatchReport()
    started = time.perf_counter()

    for index in range(n):
        rng = construction_rng(seed, index)
        band = band_for_index(rng)
        construction, stats = draw(rng, band=band)
        case_seed = case_seed_for(seed, index)
        report.constructions += 1
        report.sampled_bands[band] = report.sampled_bands.get(band, 0) + 1
        origin = "seeded" if stats.origin != "grown" else "grown"
        report.sampled_origins[origin] = report.sampled_origins.get(origin, 0) + 1
        _run_one(
            backend,
            construction,
            case_seed,
            report,
            band=band,
            origin=origin,
            check_wellposed=check_wellposed,
            reject_sight_readable=reject_sight_readable,
        )

    report.wall_seconds = time.perf_counter() - started
    return report


def band_for_index(rng: np.random.Generator) -> str:
    """Which Stage-1 profile this construction is sampled on (docs/04 Stage 1).

    Drawn from the construction's own stream, so the band stays a pure function of
    `(seed, index)` and sharding still changes nothing (docs/04 "Determinism and parallelism").

    This is the *input* profile, not the band the puzzle ends up in — that comes from the score
    (docs/05 §5.1). Until Phase 3 M4 no band was passed at all, so every construction in every
    band was sampled on the easy profile.
    """
    bands = sorted(GENERATION.band_mix)
    weights = np.array([GENERATION.band_mix[b] for b in bands], dtype=float)
    return bands[int(rng.choice(len(bands), p=weights / weights.sum()))]


def construction_rng(seed: int, index: int) -> np.random.Generator:
    """The sampler stream for construction `index` of the batch at `seed`.

    Seeded per index rather than advanced across the loop, so that construction *i* does not
    depend on the constructions before it. NumPy mixes the pair through `SeedSequence`, so
    neighbouring indices are uncorrelated despite differing by one.
    """
    return np.random.default_rng([seed, index])


def case_seed_for(seed: int, index: int) -> int:
    """The engine seed for construction `index`. Also the id a discard is reproduced from."""
    return seed * 1_000_000 + index


def _run_one(
    backend: SolverBackend,
    construction: Construction,
    case_seed: int,
    report: BatchReport,
    *,
    band: str = "easy",
    origin: str = "grown",
    check_wellposed: bool,
    reject_sight_readable: bool = True,
) -> None:
    opts = SolveOptions(seed=case_seed)

    figure = backend.realize(construction.to_spec(), opts)
    verdict = check_figure(figure)
    if not verdict.ok:
        report.discards.append(
            Discard("degeneracy", str(verdict.reason), case_seed, verdict.detail)
        )
        return

    try:
        extraction = extract_goals(
            backend,
            figure,
            opts,
            max_goals=profile_for(band).max_goals,
            reject_sight_readable=reject_sight_readable,
        )
    except Exception as exc:
        report.discards.append(Discard("extract", type(exc).__name__, case_seed, str(exc)[:200]))
        return

    for _, reason in extraction.rejected:
        report.discards.append(Discard("extract", str(reason), case_seed))
    if not extraction.goals:
        return

    coords = figure.coords()
    for goal_index, goal in enumerate(extraction.goals):
        derivation = derive(backend, figure.points, goal.proof_dag, goal.fact, opts)
        if derivation is None:
            report.discards.append(
                Discard("traceback", "no_derivation", case_seed, goal.fact.fact_id)
            )
            continue

        translation = translate(derivation.subdag, coords)
        if not translation.ok:
            for failure in translation.failures or ():
                report.discards.append(
                    Discard("translate", str(failure.reason), case_seed, failure.detail)
                )
            if not translation.failures:
                report.discards.append(Discard("translate", "no_steps", case_seed))
            continue

        angle = angle_of(goal.fact, coords)
        if angle is None or angle.degrees is None:
            report.discards.append(Discard("translate", "goal_unreadable", case_seed))
            continue

        # The givens are gated here rather than inside `translate`, which only sees steps, and
        # ahead of Stage 8, which costs 64 resamples. A puzzle stating a fact we cannot phrase
        # is unshippable no matter how well-posed it turns out to be.
        mute = unspeakable_givens(derivation.premises, coords)
        if mute:
            for failure in mute:
                report.discards.append(
                    Discard("translate", str(failure.reason), case_seed, failure.detail)
                )
            continue

        if check_wellposed:
            wp = wellposed.check(
                backend, construction, derivation, translation, angle, coords, case_seed
            )
            if not wp.ok:
                report.discards.append(Discard("wellposed", str(wp.reason), case_seed, wp.detail))
                if wp.reproduction:
                    target = (
                        report.soundness_failures
                        if wp.is_soundness_failure
                        else report.underdetermined
                    )
                    target.append(wp.reproduction)
                continue

        # Pruning happens before scoring rather than inside assembly: the pruned construction is
        # the figure the player sees, so it is what docs/05's figure-complexity filter and the
        # elegance denominator must both be measured over.
        pruned = _prune(construction, derivation, translation)
        features = measure(derivation, translation, pruned)

        # docs/05 §5.2 filter 5. A bug report, not a discard: the run records it and exits
        # non-zero rather than losing it in an attrition line.
        try:
            filters.assert_every_given_is_used(derivation)
        except UnusedGivenBug as bug:
            report.bugs.append(str(bug))
            continue

        filtered = filters.check(features)
        if not filtered.ok:
            for rejection in filtered.rejections:
                report.discards.append(
                    Discard("score", str(rejection), case_seed, goal.fact.fact_id)
                )
            continue

        # Assembly is a gate, not just a formatter: the schema refuses a figure whose marks
        # assert something the givens do not, including the case where a mark states the
        # answer outright. Those are attrition with a named reason rather than a crash — but
        # they are *counted*, so a rising `emit:` line means a real assembly bug rather than
        # a quietly swallowed one.
        try:
            report.puzzles.append(
                _emit(
                    derivation,
                    translation,
                    goal,
                    angle,
                    coords,
                    figure.declared,
                    case_seed,
                    goal_index,
                    construction,
                    pruned,
                    features,
                    score(features),
                )
            )
            report.puzzle_origins[origin] = report.puzzle_origins.get(origin, 0) + 1
        except SchemaError as exc:
            report.discards.append(Discard("emit", _emit_reason(exc), case_seed, str(exc)[:200]))


#: Assembly refusals, keyed for the attrition report. An unrecognised one is reported as
#: `schema_error` rather than bucketed into a neighbour, so it cannot hide in a familiar row.
_EMIT_REASONS: tuple[tuple[str, str], ...] = (
    ("states the answer on the figure", "figure_states_the_answer"),
    ("no player-facing phrasing", "given_unspeakable"),
    ("collide on display labels", "label_collision"),
    ("with no cong among", "unbacked_mark"),
    ("with no para among", "unbacked_mark"),
    ("with no perp or aconst among", "unbacked_mark"),
)


def _emit_reason(exc: SchemaError) -> str:
    message = str(exc)
    for needle, reason in _EMIT_REASONS:
        if needle in message:
            return reason
    return "schema_error"


def _prune(
    construction: Construction, derivation: Derivation, translation: Translation
) -> Construction:
    """The figure actually drawn.

    Takes the union of what the derivation needs and what the *solution steps highlight* — a
    step may name a segment its premises only imply (docs/04 Stage 6).
    """
    pruning = prune_figure(
        construction, derivation.needed_points() | translation.highlighted_points()
    )
    return pruning.construction(construction)


def _emit(
    derivation: Derivation,
    translation: Translation,
    goal: ExtractedGoal,
    angle: VertexAngle,
    coords: dict[str, tuple[float, float]],
    declared: tuple[Fact, ...],
    case_seed: int,
    goal_index: int,
    construction: Construction,
    pruned: Construction,
    features: Features,
    scored: Score,
) -> CandidatePuzzle:
    """Stage 9: assemble the candidate puzzle."""
    drawn = set(pruned.points)
    depth = derivation.depth
    puzzle = assemble(
        # One construction can yield several goals, so the seed alone does not identify a puzzle.
        # The index is positional within the construction rather than a hash of the goal: string
        # hashing is randomized per process, and an id that moved between runs would break the
        # byte-identical-batch guarantee (docs/02 invariant 2). Final bank ids are Phase 2's.
        puzzle_id=f"gf-{case_seed:012d}-{goal_index}",
        quantity_type=goal.quantity_type,
        pruned=pruned,
        derivation=derivation,
        translation=translation,
        goal_angle=angle,
        reference_coords={p: xy for p, xy in coords.items() if p in drawn},
        difficulty=schema.Difficulty(
            band=scored.band,
            depth=depth,
            # Both difficulty features must read the same graph: the minimal derivation. Taking
            # `goal.distinct_rules` here would publish a count over the *whole* solve beside a
            # depth over the sub-DAG, so a puzzle would advertise conceptual variety its own
            # solution never shows (docs/05 §5.1).
            distinct_rules=derivation.distinct_rules,
            score=scored.value,
        ),
        declared=declared,
        provenance={
            "generator_version": generator_version(),
            # A layer-verified quantity has no engine solve of its own (docs/10 A3). Its
            # *premises* still came from one, so the field records which engine certified them
            # and says plainly that the value did not — a bank entry must never imply an engine
            # vouched for arithmetic it cannot express.
            "engine": (
                f"{goal.result.stats.engine}-{goal.result.stats.engine_version}"
                if goal.result is not None
                else f"{SOLVER.backend}+{goal.quantity_type}-layer"
            ),
            "backend": SOLVER.backend,
            "seed": case_seed,
            "construction": construction.to_jgex(),
        },
    )
    return CandidatePuzzle(
        puzzle=puzzle,
        derivation=derivation,
        translation=translation,
        pruned=pruned,
        seed=case_seed,
        features=features,
        scored=scored,
        full_depth=goal.depth,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the GeoForge generation pipeline.")
    parser.add_argument("--n", type=int, default=200, help="constructions to sample")
    parser.add_argument("--seed", type=int, default=42, help="master seed")
    parser.add_argument("--out", type=str, default=None, help="write puzzles as JSON here")
    parser.add_argument("--report", action="store_true", help="print the attrition report")
    parser.add_argument(
        "--no-wellposed",
        action="store_true",
        help="skip Stage 8 (attrition sweeps only; output is not shippable)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="cross-validate every emitted puzzle on the second engine; disagreement fails the run",
    )
    args = parser.parse_args(argv)

    report = run(args.n, args.seed, check_wellposed=not args.no_wellposed)

    disagreements: list[str] = []
    if args.validate:
        from geoforge.bank import validate as cross

        validations = cross.validate_all([p.to_json() for p in report.puzzles])
        print(json.dumps(cross.summary(validations), indent=2, sort_keys=True))
        disagreements = [f"{v.puzzle_id} [{v.outcome}] {v.detail}" for v in validations if not v.ok]

    if args.report:
        print(json.dumps({**report.summary(), **report.timing()}, indent=2, sort_keys=True))
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(
                {
                    "summary": report.summary(),
                    "puzzles": [p.to_json() for p in report.puzzles],
                },
                handle,
                indent=2,
                sort_keys=True,
            )
        print(f"wrote {len(report.puzzles)} puzzles to {args.out}")

    for case in report.soundness_failures:
        print("SOUNDNESS FAILURE", file=sys.stderr)
        print(case, file=sys.stderr)
    for case in disagreements:
        print(f"CROSS-ENGINE DISAGREEMENT {case}", file=sys.stderr)
    for bug in report.bugs:
        print(f"UNUSED GIVEN {bug}", file=sys.stderr)

    # A soundness failure fails the run: docs/09 P1 requires zero across 1,000 constructions.
    # So does a cross-engine disagreement: two engines differing means one of them is wrong,
    # and we cannot tell which (docs/04 §V). So does an unused given: docs/05 §5.2 filter 5
    # calls it a bug report, and a bug report nobody is forced to read is a log line.
    return 1 if report.soundness_failures or disagreements or report.bugs else 0


if __name__ == "__main__":
    raise SystemExit(main())
