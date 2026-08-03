"""Bank builder (docs/02, docs/09 P2).

Turns a generation run into a bank on disk: lay out each puzzle, validate every one against
the independent engine, strip the build-time blocks, and write per-band shards plus a manifest.

**A dev bank is not a shippable bank, and says so.** Scoring, dedupe, interestingness ranking
and anti-leak perturbation are later milestones; until they land the manifest carries
`shippable: false` and names what is missing. That is the same discipline as `--no-wellposed`
on the batch runner: a reduced build is fine to look at and must never be mistaken for the
real thing. `--strict` refuses to build at all while anything is missing, which is what CI
will use once the pipeline is complete.

The archive keeps everything the shards drop. `bank/validate.py` promises it can be pointed at
a bank file months later, and that promise needs a file that still has `reference_figure` in it.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from geoforge import schema
from geoforge.bank import validate as cross
from geoforge.bank.layout import lay_out
from geoforge.config import BANK, SOLVER, VALIDATION
from geoforge.generator.batch import generator_version, run
from geoforge.generator.emit import assemble
from geoforge.generator.translation.phrases import angle_of
from geoforge.scoring.bands import BAND_ORDER
from geoforge.solvers.interface import SolverBackend, get_backend

#: What a shippable bank still needs (docs/09 P2). Named rather than implied, so the manifest
#: says *why* it is not shippable instead of just that it is not.
MISSING_FOR_SHIPPABLE: tuple[str, ...] = (
    "difficulty_scoring",
    "hard_filters",
    "isomorphism_dedupe",
    "interestingness_ranking",
    "anti_leak_layout",
)


@dataclass
class BuildReport:
    puzzles: list[schema.Puzzle] = field(default_factory=list)
    layout_failures: list[str] = field(default_factory=list)
    validation_failures: list[str] = field(default_factory=list)
    generation: dict[str, Any] = field(default_factory=dict)
    layout_considered: int = 0
    layout_admissible: int = 0
    wall_seconds: float = 0.0

    def by_band(self) -> dict[str, int]:
        counts = {band: 0 for band in BAND_ORDER}
        for puzzle in self.puzzles:
            counts[puzzle.difficulty.band] = counts.get(puzzle.difficulty.band, 0) + 1
        return {band: n for band, n in counts.items() if n}

    def summary(self) -> dict[str, Any]:
        return {
            "puzzles": len(self.puzzles),
            "by_band": self.by_band(),
            "layout_failures": len(self.layout_failures),
            "validation_failures": len(self.validation_failures),
            "layout_admissible_per_puzzle": (
                round(self.layout_admissible / len(self.puzzles), 1) if self.puzzles else 0.0
            ),
            "generation": self.generation,
        }


def build(
    n: int,
    seed: int,
    out_dir: Path,
    *,
    backend: SolverBackend | None = None,
    strict: bool = False,
) -> BuildReport:
    """Generate, lay out, validate, and write a bank."""
    backend = backend or get_backend()
    started = time.perf_counter()
    report = BuildReport()

    batch = run(n, seed, backend)
    report.generation = dict(batch.summary())

    for candidate in batch.puzzles:
        laid = _laid_out(backend, candidate)
        if laid is None:
            report.layout_failures.append(candidate.id)
            continue
        report.layout_considered += laid[1].considered
        report.layout_admissible += laid[1].admissible
        report.puzzles.append(laid[0])

    # Validation runs over the *unstripped* payloads: the second engine needs the reference
    # figure, and a bank validated after stripping would be validating a different artifact
    # from the one that was checked (docs/04 §V).
    payloads = [p.to_json() for p in report.puzzles]
    validations = cross.validate_all(payloads)
    report.validation_failures = [
        f"{v.puzzle_id} [{v.outcome}] {v.detail}" for v in validations if not v.ok
    ]

    report.wall_seconds = time.perf_counter() - started
    if not report.validation_failures:
        _write(report, out_dir, seed=seed, strict=strict)
    return report


def _laid_out(backend: SolverBackend, candidate: Any) -> tuple[schema.Puzzle, Any] | None:
    """Re-assemble one candidate over its chosen display coordinates."""
    goal_angle = angle_of(candidate.derivation.goal, _reference(candidate))
    if goal_angle is None or goal_angle.degrees is None:  # pragma: no cover - gated at Stage 7
        return None

    result = lay_out(
        backend,
        candidate.pruned,
        candidate.derivation,
        candidate.translation,
        goal_angle,
        _reference(candidate),
        candidate.puzzle.figure.segments,
        candidate.seed,
    )
    if not result.ok:
        return None

    puzzle = assemble(
        puzzle_id=candidate.id,
        quantity_type=candidate.quantity_type,
        pruned=candidate.pruned,
        derivation=candidate.derivation,
        translation=candidate.translation,
        goal_angle=goal_angle,
        reference_coords=_reference(candidate),
        difficulty=candidate.puzzle.difficulty,
        display_coords=result.coords,
        label_offsets=result.labels,
        provenance=candidate.puzzle.provenance,
    )
    return puzzle, result


def _reference(candidate: Any) -> dict[str, tuple[float, float]]:
    return {name: (x, y) for name, x, y in candidate.reference_points}


def _write(report: BuildReport, out_dir: Path, *, seed: int, strict: bool) -> None:
    if strict and MISSING_FOR_SHIPPABLE:
        raise RuntimeError(
            "--strict refuses a bank that is not shippable; still missing: "
            f"{', '.join(MISSING_FOR_SHIPPABLE)}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    shards: list[schema.Shard] = []
    for band in BAND_ORDER:
        in_band = [p for p in report.puzzles if p.difficulty.band == band]
        for index in range(0, len(in_band), BANK.shard_size):
            chunk = in_band[index : index + BANK.shard_size]
            name = f"{band}-{index // BANK.shard_size:03d}.json"
            payload = json.dumps([p.stripped().to_json() for p in chunk], indent=2, sort_keys=True)
            (out_dir / name).write_text(payload)
            shards.append(
                schema.Shard(
                    file=name,
                    band=band,
                    puzzles=len(chunk),
                    sha256=hashlib.sha256(payload.encode()).hexdigest(),
                )
            )

    manifest = schema.Manifest(
        schema_version=schema.SCHEMA_VERSION,
        generator_version=generator_version(),
        generation_engine=SOLVER.backend,
        validator_engine=VALIDATION.backend,
        seed=seed,
        puzzles=len(report.puzzles),
        by_band=report.by_band(),
        shards=tuple(shards),
        # Loud rather than implied: everything downstream should treat this bank as a preview.
        shippable=not MISSING_FOR_SHIPPABLE,
        missing_for_shippable=MISSING_FOR_SHIPPABLE,
    ).to_json()
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    archive_dir = out_dir.parent / BANK.archive_dirname
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"seed-{seed}.json.gz"
    with gzip.open(archive, "wt") as handle:
        json.dump(
            {"manifest": manifest, "puzzles": [p.to_json() for p in report.puzzles]},
            handle,
            indent=2,
            sort_keys=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a puzzle bank (docs/09 P2).")
    parser.add_argument("--n", type=int, default=BANK.default_constructions)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=BANK.output_dir)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="refuse to build while the bank is not shippable",
    )
    args = parser.parse_args(argv)

    report = build(args.n, args.seed, Path(args.out), strict=args.strict)
    print(json.dumps(report.summary(), indent=2, sort_keys=True))

    for failure in report.validation_failures:
        print(f"VALIDATION FAILURE {failure}", file=sys.stderr)
    if MISSING_FOR_SHIPPABLE and not args.strict:
        print(
            "\nNOT SHIPPABLE — still missing: " + ", ".join(MISSING_FOR_SHIPPABLE),
            file=sys.stderr,
        )
    # Any invalid puzzle fails the build: two engines differing means one is wrong and we
    # cannot tell which (docs/04 §V, docs/09 P2 AC).
    return 1 if report.validation_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
