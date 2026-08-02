"""Stage 9 and the batch runner (docs/04).

Runs the whole pipeline over a seed-sharded range of constructions and emits candidate puzzles plus
an attrition report. Two properties matter more than throughput:

**Reproducibility.** The batch is a pure function of `(config, engine_version, master_seed, n)`
(docs/02 invariant 2). Each construction gets its seed from the master seed and its index, so shard
boundaries change nothing and a single puzzle can be re-run in isolation.

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
from dataclasses import dataclass, field
from importlib.metadata import version

import numpy as np

from geoforge.config import SOLVER
from geoforge.generator import wellposed
from geoforge.generator.construction import Construction
from geoforge.generator.degeneracy import check_figure
from geoforge.generator.extract import ExtractedGoal, extract_goals
from geoforge.generator.quantities import get as quantity_type
from geoforge.generator.sampler import sample_construction
from geoforge.generator.traceback import Derivation, derive, prune_figure
from geoforge.generator.translation import SolutionStep, Translation, translate
from geoforge.generator.translation.phrases import angle_of
from geoforge.generator.translation.vertex_angles import VertexAngle
from geoforge.scoring.bands import band_for_depth
from geoforge.solvers.interface import SolverBackend, get_backend
from geoforge.solvers.types import SolveOptions

#: Pipeline stage names, used as attrition keys. Ordered as the pipeline runs.
STAGES = ("sample", "realize", "degeneracy", "extract", "traceback", "translate", "wellposed")


@dataclass(frozen=True, slots=True)
class Discard:
    """One rejected candidate. `(stage, reason, seed)` per docs/04."""

    stage: str
    reason: str
    seed: int
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CandidatePuzzle:
    """Stage 9 output: everything needed to build, score and validate a puzzle."""

    id: str
    quantity_type: str
    construction: str
    """The *pruned* construction — the figure actually drawn."""
    premises: tuple[str, ...]
    configuration: tuple[str, ...]
    goal: str
    """Canonical fact id of the goal."""
    reference_points: tuple[tuple[str, float, float], ...]
    """The engine's coordinates for the *pruned* figure — the diagram the puzzle was derived
    over, and the input cross-engine validation needs (docs/04 §V).

    Restricted to the pruned construction's points on purpose. A validator handed the scaffolding
    the figure no longer shows could derive the goal through a point the player never sees, and
    report a pass the puzzle has not earned.

    Build-time data, not player-facing: the shipped `figure` with laid-out display coordinates is
    Phase 2's, and this is stripped from shipped banks alongside `provenance` (docs/02)."""
    question: str
    """Player-facing, e.g. "∠ACB"."""
    answer: str
    answer_unit: str
    solution: tuple[SolutionStep, ...]
    depth: int
    distinct_rules: int
    band: str
    seed: int
    provenance: dict[str, str | int]

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "quantity_type": self.quantity_type,
            "difficulty": {
                "band": self.band,
                "depth": self.depth,
                "distinct_rules": self.distinct_rules,
            },
            "given": list(self.premises),
            "configuration": list(self.configuration),
            "reference_figure": {
                "points": [{"id": n, "x": x, "y": y} for n, x, y in self.reference_points]
            },
            "goal": {
                "fact": self.goal,
                "question": self.question,
                "answer": {"exact": self.answer, "display": f"{self.answer}{self.answer_unit}"},
            },
            "solution": [
                {
                    "step": s.step,
                    "rule": s.rule,
                    "text": s.text,
                    "derives": s.derives,
                    "highlights": list(s.highlights),
                }
                for s in self.solution
            ],
            "provenance": dict(self.provenance),
        }


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
    constructions: int = 0
    wall_seconds: float = 0.0

    def by_stage(self) -> dict[str, int]:
        return dict(Counter(d.stage for d in self.discards))

    def by_reason(self) -> dict[str, int]:
        return dict(Counter(f"{d.stage}:{d.reason}" for d in self.discards))

    def by_band(self) -> dict[str, int]:
        return dict(Counter(p.band for p in self.puzzles))

    def summary(self) -> dict[str, object]:
        return {
            "constructions": self.constructions,
            "puzzles": len(self.puzzles),
            "soundness_failures": len(self.soundness_failures),
            "underdetermined": len(self.underdetermined),
            "wall_seconds": round(self.wall_seconds, 2),
            "by_band": self.by_band(),
            "attrition_by_stage": self.by_stage(),
            "attrition_by_reason": self.by_reason(),
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
) -> BatchReport:
    """Run the pipeline over `n` sampled constructions.

    `check_wellposed=False` skips Stage 8 only. It exists for the fast attrition sweeps that shape
    the sampler, never for producing shippable puzzles: without it nothing has verified that the
    answers are answers.
    """
    backend = backend or get_backend()
    report = BatchReport()
    rng = np.random.default_rng(seed)
    started = time.perf_counter()

    for index in range(n):
        construction, _ = sample_construction(rng)
        # Derived from the master seed, so a puzzle can be re-run alone and shard boundaries
        # cannot change what is generated.
        case_seed = seed * 1_000_000 + index
        report.constructions += 1
        _run_one(backend, construction, case_seed, report, check_wellposed=check_wellposed)

    report.wall_seconds = time.perf_counter() - started
    return report


def _run_one(
    backend: SolverBackend,
    construction: Construction,
    case_seed: int,
    report: BatchReport,
    *,
    check_wellposed: bool,
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
        extraction = extract_goals(backend, figure, opts)
    except Exception as exc:
        report.discards.append(Discard("extract", type(exc).__name__, case_seed, str(exc)[:200]))
        return

    for _, reason in extraction.rejected:
        report.discards.append(Discard("extract", str(reason), case_seed))
    if not extraction.goals:
        return

    coords = figure.coords()
    for goal_index, goal in enumerate(extraction.goals):
        derivation = derive(backend, figure.points, goal.result.proof_dag, goal.fact, opts)
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

        report.puzzles.append(
            _emit(construction, derivation, translation, goal, angle, coords, case_seed, goal_index)
        )


def _emit(
    construction: Construction,
    derivation: Derivation,
    translation: Translation,
    goal: ExtractedGoal,
    angle: VertexAngle,
    coords: dict[str, tuple[float, float]],
    case_seed: int,
    goal_index: int,
) -> CandidatePuzzle:
    """Stage 9: assemble the candidate puzzle.

    Pruning takes the union of what the derivation needs and what the *solution steps highlight* —
    a step may name a segment its premises only imply (docs/04 Stage 6).
    """
    pruning = prune_figure(
        construction, derivation.needed_points() | translation.highlighted_points()
    )
    pruned = pruning.construction(construction)
    kind = quantity_type(goal.quantity_type)
    depth = derivation.depth
    return CandidatePuzzle(
        # One construction can yield several goals, so the seed alone does not identify a puzzle.
        # The index is positional within the construction rather than a hash of the goal: string
        # hashing is randomized per process, and an id that moved between runs would break the
        # byte-identical-batch guarantee (docs/02 invariant 2). Final bank ids are Phase 2's.
        id=f"gf-{case_seed:012d}-{goal_index}",
        quantity_type=goal.quantity_type,
        construction=pruned.to_jgex(),
        premises=tuple(f.fact_id for f in derivation.premises),
        configuration=tuple(f.fact_id for f in derivation.configuration),
        goal=goal.fact.fact_id,
        reference_points=tuple(
            sorted((p, coords[p][0], coords[p][1]) for p in pruned.points if p in coords)
        ),
        question=angle.text,
        answer=kind.format_answer(goal.fact.value) if goal.fact.value is not None else "",
        answer_unit="°",
        solution=translation.steps,
        depth=depth,
        distinct_rules=goal.distinct_rules,
        band=band_for_depth(depth),
        seed=case_seed,
        provenance={
            "generator_version": generator_version(),
            "engine": f"{goal.result.stats.engine}-{goal.result.stats.engine_version}",
            "backend": SOLVER.backend,
            "seed": case_seed,
            "construction": construction.to_jgex(),
        },
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
        print(json.dumps(report.summary(), indent=2, sort_keys=True))
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

    # A soundness failure fails the run: docs/09 P1 requires zero across 1,000 constructions.
    # So does a cross-engine disagreement: two engines differing means one of them is wrong,
    # and we cannot tell which (docs/04 §V).
    return 1 if report.soundness_failures or disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())
