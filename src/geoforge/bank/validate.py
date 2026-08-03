"""Cross-engine bank validation (docs/04 §V, docs/02 invariant 3).

Every puzzle is re-derived from scratch by an engine that shares no lineage with the one that
generated it. A soundness bug in one is then unlikely to be mirrored in the other. Any
disagreement blocks the build — there is no "warn and ship".

**The input is the emitted JSON, not the generator's objects.** That is deliberate. A validator
handed the generator's in-memory state re-checks the *run*; this one re-checks the *artifact*,
which is what actually ships, and it can be pointed at a bank file months later with nothing
else in scope.

What each puzzle is checked for, and by whom:

| Check | Independent of the generation engine? |
|---|---|
| Goal derivable from the stated givens over the reference diagram | **Yes** — AG2 DDAR |
| Goal true in its own reference diagram, at bank tolerance | Yes — direct measurement |
| Published answer agrees with the goal fact's exact value | No — a self-consistency check |
| Every premise and the goal expressible to the validator | Yes |

**Configuration facts are carried by the coordinates, not asserted.** DDAR has no `sameclock`
or `sameside`, and it does not need them: it is handed the reference diagram itself, so the
figure's configuration is pinned by construction rather than by predicates. What this does
*not* re-check is the well-posedness argument — whether some *other* diagram satisfying the
same premises would give a different answer. That is Stage 8's job on the generation side and
stays there; cross-validation certifies the answer over the reference diagram. Recorded as a
limitation in docs/07.

A validator that never fails is untested (docs/04 §V), so the mutation helpers at the bottom
are part of this module rather than of the test file: they are how the build proves its
validator still has teeth.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Any

from geoforge.config import SOLVER, VALIDATION
from geoforge.generator.quantities import directed_line_angle
from geoforge.generator.quantities import get as quantity_type
from geoforge.solvers.ag2_backend import UnsupportedByValidator
from geoforge.solvers.interface import ValidatorBackend, get_validator
from geoforge.solvers.newclid_backend import ENGINE_NAME as GENERATION_ENGINE
from geoforge.solvers.types import (
    CONFIGURATION_KINDS,
    Fact,
    FactKind,
    PremiseSpec,
    SolveOptions,
    fact_from_id,
)


class ValidationOutcome(StrEnum):
    """Why a puzzle passed or failed. Every value but `VALIDATED` blocks the bank build."""

    VALIDATED = "validated"
    NOT_DERIVABLE = "not_derivable"
    """The validator could not derive the goal from the stated givens. Either the puzzle is
    wrong, or its givens are not enough to reach the answer — both are ship-blocking."""
    ANSWER_MISMATCH = "answer_mismatch"
    """The published answer disagrees with the goal fact the solution actually derives."""
    NUMERIC_MISMATCH = "numeric_mismatch"
    """The goal is false in the puzzle's own reference diagram."""
    UNSUPPORTED = "unsupported"
    """A premise or goal the validator cannot state. Not a pass: an unchecked puzzle and a
    valid puzzle are different things, and only one of them may ship."""
    MALFORMED = "malformed"
    ENGINE_ERROR = "engine_error"


@dataclass(frozen=True, slots=True)
class Validation:
    """The verdict on one puzzle."""

    puzzle_id: str
    outcome: ValidationOutcome
    engine: str
    detail: str = ""
    configuration_carried: tuple[str, ...] = ()
    """Configuration facts held by the exported coordinates rather than asserted as premises.
    Recorded, not dropped: a reader of the validation log must be able to see exactly what the
    second engine was and was not told."""
    wall_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.outcome is ValidationOutcome.VALIDATED


def validate(puzzle: Mapping[str, Any], validator: ValidatorBackend | None = None) -> Validation:
    """Re-derive one emitted puzzle with the independent engine."""
    validator = validator or get_validator()
    _refuse_generation_engine(validator)
    puzzle_id = str(puzzle.get("id", "<no id>"))
    started = time.perf_counter()

    def verdict(
        outcome: ValidationOutcome, detail: str = "", carried: tuple[str, ...] = ()
    ) -> Validation:
        return Validation(
            puzzle_id=puzzle_id,
            outcome=outcome,
            engine=f"{validator.name}-{validator.engine_version[:7]}",
            detail=detail,
            configuration_carried=carried,
            wall_seconds=time.perf_counter() - started,
        )

    try:
        points = _points_of(puzzle)
        # Schema v2 states givens as objects. `fact` is the canonical id and the only field
        # the validator reads: `display` is prose and could say anything without changing what
        # the puzzle claims, so re-deriving from it would validate the wording, not the maths.
        premises = tuple(fact_from_id(g["fact"]) for g in puzzle["given"])
        configuration = tuple(fact_from_id(f) for f in puzzle.get("configuration", ()))
        goal = fact_from_id(puzzle["goal"]["fact"])
        answer = str(puzzle["goal"]["answer"]["exact"])
        kind = quantity_type(str(puzzle["quantity_type"]))
    except (KeyError, TypeError, ValueError) as exc:
        return verdict(ValidationOutcome.MALFORMED, f"{type(exc).__name__}: {exc}")

    carried = tuple(f.fact_id for f in configuration if f.kind in CONFIGURATION_KINDS)
    if len(carried) != len(configuration):
        stated = [f.fact_id for f in configuration if f.kind not in CONFIGURATION_KINDS]
        return verdict(
            ValidationOutcome.MALFORMED,
            f"`configuration` holds non-configuration facts: {stated}",
        )

    # Answer consistency first: it needs no engine, and a mismatch here means the JSON is
    # internally inconsistent regardless of what any engine says about the geometry.
    if goal.value is None:
        return verdict(ValidationOutcome.MALFORMED, f"goal {goal.fact_id} carries no value")
    expected = kind.format_answer(goal.value)
    if expected != answer:
        return verdict(
            ValidationOutcome.ANSWER_MISMATCH,
            f"published {answer!r} but goal fact {goal.fact_id} is {expected!r}",
            carried,
        )

    numeric = _numeric_check(goal, points)
    if numeric is None:
        return verdict(
            ValidationOutcome.UNSUPPORTED,
            f"no numeric re-check is registered for goal kind {goal.kind.value!r}",
            carried,
        )
    residual, tolerance = numeric
    if residual > tolerance:
        return verdict(
            ValidationOutcome.NUMERIC_MISMATCH,
            f"{goal.fact_id} is off by {residual:.3e} deg in its own reference diagram "
            f"(tolerance {tolerance:.0e})",
            carried,
        )

    spec = PremiseSpec(points=points, premises=premises, goals=(goal,))
    try:
        opts = SolveOptions(max_wall_seconds=VALIDATION.max_wall_seconds)
        result = validator.solve_facts(spec, opts)
    except UnsupportedByValidator as exc:
        return verdict(ValidationOutcome.UNSUPPORTED, str(exc), carried)
    except Exception as exc:  # an engine crash is a build failure, never a pass
        return verdict(ValidationOutcome.ENGINE_ERROR, f"{type(exc).__name__}: {exc}", carried)

    if result.stats.hit_cap:
        # A run that blew past its budget is not evidence either way, and treating it as a pass
        # is how an unchecked puzzle reaches a bank (docs/08 §8.1 no-silent-failure).
        return verdict(
            ValidationOutcome.ENGINE_ERROR,
            f"{validator.name} took {result.stats.wall_seconds:.1f}s, over the "
            f"{VALIDATION.max_wall_seconds:.0f}s cap",
            carried,
        )

    if goal.fact_id not in result.proof_dag.proved_goals:
        return verdict(
            ValidationOutcome.NOT_DERIVABLE,
            f"{validator.name} could not derive {goal.fact_id} "
            f"from {[f.fact_id for f in premises]}",
            carried,
        )
    return verdict(ValidationOutcome.VALIDATED, carried=carried)


def validate_all(
    puzzles: Sequence[Mapping[str, Any]], validator: ValidatorBackend | None = None
) -> tuple[Validation, ...]:
    validator = validator or get_validator()
    return tuple(validate(p, validator) for p in puzzles)


def summary(validations: Sequence[Validation]) -> dict[str, object]:
    return {
        "puzzles": len(validations),
        "validated": sum(1 for v in validations if v.ok),
        "failed": sum(1 for v in validations if not v.ok),
        "by_outcome": dict(Counter(str(v.outcome) for v in validations)),
        "engine": validations[0].engine if validations else "",
        "wall_seconds": round(sum(v.wall_seconds for v in validations), 2),
    }


# --------------------------------------------------------------------------------------
# Mutation testing — docs/04 §V: "a validator that never fails is untested"
# --------------------------------------------------------------------------------------


def corrupt_answer(puzzle: Mapping[str, Any], offset_degrees: int | None = None) -> dict[str, Any]:
    """Shift the goal's *exact value* and its published answer by `offset_degrees`.

    The whole puzzle stays self-consistent, so nothing but the second engine's geometry can
    catch it. This is the mutation that tests the cross-engine check itself.
    """
    offset = VALIDATION.mutation_offset_degrees if offset_degrees is None else offset_degrees
    mutant: dict[str, Any] = json.loads(json.dumps(puzzle))
    goal = fact_from_id(mutant["goal"]["fact"])
    if goal.value is None:
        raise ValueError(f"{goal.fact_id} carries no value to corrupt")
    shifted = Fact(kind=goal.kind, args=goal.args, value=goal.value + Fraction(offset, 180))
    mutant["goal"]["fact"] = str(shifted.fact_id)
    kind = quantity_type(str(mutant["quantity_type"]))
    assert shifted.value is not None
    mutant["goal"]["answer"]["exact"] = kind.format_answer(shifted.value)
    mutant["goal"]["answer"]["display"] = f"{mutant['goal']['answer']['exact']}°"
    # `approx` too, or the mutant is not the self-consistent puzzle this claims to produce —
    # a validator could then catch it on an inconsistency instead of on the geometry, and the
    # test would pass while checking something weaker than it says.
    mutant["goal"]["answer"]["approx"] = float(shifted.value * 180)
    return mutant


def corrupt_published_answer(
    puzzle: Mapping[str, Any], offset_degrees: int | None = None
) -> dict[str, Any]:
    """Shift only the player-facing answer, leaving the goal fact alone.

    A different failure mode from `corrupt_answer`: here the geometry is untouched and the
    *JSON* lies. The cross-engine check would happily pass it, which is why validation also
    ties the published answer back to the fact the solution derives.
    """
    offset = VALIDATION.mutation_offset_degrees if offset_degrees is None else offset_degrees
    mutant: dict[str, Any] = json.loads(json.dumps(puzzle))
    mutant["goal"]["answer"]["exact"] = str(int(mutant["goal"]["answer"]["exact"]) + offset)
    return mutant


def drop_premise(puzzle: Mapping[str, Any], index: int) -> dict[str, Any]:
    """Remove one stated given. A puzzle whose premises are minimal must stop being derivable."""
    mutant: dict[str, Any] = json.loads(json.dumps(puzzle))
    del mutant["given"][index]
    return mutant


# --------------------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------------------


def _refuse_generation_engine(validator: ValidatorBackend) -> None:
    """Bank validation must not run on the engine that generated the bank (CLAUDE.md).

    Checked at the point of use rather than trusted to config, because the failure is silent:
    a bank "validated" by its own generator would pass everything and prove nothing.
    """
    if validator.name in (GENERATION_ENGINE, SOLVER.backend):
        raise ValueError(
            f"{validator.name!r} generated this bank; validating with it would only re-confirm "
            "its own bugs (docs/02 invariant 3)."
        )


def _points_of(puzzle: Mapping[str, Any]) -> tuple[tuple[str, float, float], ...]:
    raw = puzzle["reference_figure"]["points"]
    return tuple(sorted((str(p["id"]), float(p["x"]), float(p["y"])) for p in raw))


def _numeric_check(
    goal: Fact, points: tuple[tuple[str, float, float], ...]
) -> tuple[float, float] | None:
    """Measure the goal on the reference diagram. Returns `(residual_degrees, tolerance)`.

    `None` means no measurement is registered for this kind — which validation treats as
    UNSUPPORTED rather than as a pass. Numerics VERIFY here, they derive nothing
    (docs/02 invariant 4): the value being checked was proved symbolically upstream.
    """
    if goal.kind is not FactKind.CONSTANT_ANGLE or goal.value is None:
        return None
    coords = {name: (x, y) for name, x, y in points}
    if any(p not in coords for p in goal.args):
        return None
    a, b, c, d = goal.args
    measured = directed_line_angle(coords[a], coords[b], coords[c], coords[d])
    stated = float(goal.degrees()) % 180.0
    residual = min(abs(measured - stated), 180.0 - abs(measured - stated))
    return residual, VALIDATION.numeric_tolerance_degrees


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-engine validation of an emitted puzzle file (docs/04 §V)."
    )
    parser.add_argument("path", help="JSON written by geoforge.generator.batch --out")
    parser.add_argument(
        "--mutation-test", action="store_true", help="also prove the validator bites"
    )
    args = parser.parse_args(argv)

    with open(args.path) as handle:
        puzzles = json.load(handle)["puzzles"]

    validator = get_validator()
    validations = validate_all(puzzles, validator)
    print(json.dumps(summary(validations), indent=2, sort_keys=True))
    for v in validations:
        if not v.ok:
            print(f"FAILED {v.puzzle_id} [{v.outcome}] {v.detail}", file=sys.stderr)

    failed = sum(1 for v in validations if not v.ok)
    if args.mutation_test and puzzles:
        failed += _mutation_battery(puzzles, validator)
    return 1 if failed else 0


def _mutation_battery(puzzles: Sequence[Mapping[str, Any]], validator: ValidatorBackend) -> int:
    """All three mutations, not just the first — and every premise, not a sample.

    Each targets a distinct failure the others cannot see: a self-consistent wrong answer tests
    the *geometry* check, a lying published answer tests that the answer is tied back to the
    derived fact, and a dropped premise tests minimality. Running only one leaves the other two
    guarantees asserted by nothing. Returns the number of mutations that got through, which is
    the number of ways this validator has been shown to have no teeth.
    """
    escaped = 0
    for name, mutants in (
        ("corrupted answers", [corrupt_answer(p) for p in puzzles]),
        ("lying published answers", [corrupt_published_answer(p) for p in puzzles]),
        (
            "dropped premises",
            [drop_premise(p, i) for p in puzzles for i in range(len(p["given"]))],
        ),
    ):
        caught = sum(1 for m in mutants if not validate(m, validator).ok)
        print(f"mutation test: {caught}/{len(mutants)} {name} rejected")
        if caught != len(mutants):
            escaped += 1
    return escaped


if __name__ == "__main__":
    raise SystemExit(main())
