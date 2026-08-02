"""Cross-engine bank validation (docs/04 §V, docs/02 invariant 3).

Two things need proving, and the second is the one people forget: that the validator **accepts
real puzzles**, and that it **rejects corrupted ones**. A validator with no teeth passes
everything and certifies nothing, so every failure mode gets its own mutation.

The puzzles here come from a real pipeline run rather than from hand-written fixtures. A
hand-written puzzle would test the validator against my idea of what the generator emits;
these test it against what the generator actually emits.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from geoforge.bank.validate import (
    Validation,
    ValidationOutcome,
    corrupt_answer,
    corrupt_published_answer,
    drop_premise,
    main,
    summary,
    validate,
    validate_all,
)
from geoforge.generator.batch import BatchReport, run
from geoforge.solvers.interface import ValidatorBackend, get_backend, get_validator

BATCH_N = 60
SEED = 42


@pytest.fixture(scope="module")
def report() -> BatchReport:
    return run(BATCH_N, SEED)


@pytest.fixture(scope="module")
def puzzles(report: BatchReport) -> list[dict[str, Any]]:
    emitted = [p.to_json() for p in report.puzzles]
    assert emitted, "the pipeline must reach Stage 9 for validation to have anything to check"
    return emitted


@pytest.fixture(scope="module")
def validator() -> ValidatorBackend:
    return get_validator()


class TestValidatorAcceptsRealPuzzles:
    def test_every_emitted_puzzle_validates(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """docs/04 §V: an independent engine re-derives every accepted puzzle."""
        failures = [v for v in validate_all(puzzles, validator) if not v.ok]
        assert failures == [], [f"{v.puzzle_id} [{v.outcome}] {v.detail}" for v in failures]

    def test_the_verdict_names_the_engine_that_gave_it(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        verdict = validate(puzzles[0], validator)
        assert verdict.engine.startswith("ag2ddar-")

    def test_configuration_facts_are_reported_as_carried_not_asserted(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """DDAR has no `sameclock`; the configuration rides in the exported coordinates. What
        matters is that the log says so, rather than the facts vanishing without trace."""
        verdicts = [validate(p, validator) for p in puzzles]
        assert any(v.configuration_carried for v in verdicts)
        for verdict, puzzle in zip(verdicts, puzzles, strict=True):
            assert list(verdict.configuration_carried) == puzzle["configuration"]


class TestMutations:
    """docs/04 §V: 'a validator that never fails is untested'."""

    def test_a_corrupted_answer_is_rejected(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """The goal fact and the published answer are shifted together, so the puzzle stays
        internally consistent and only the geometry can catch it. This is the mutation that
        tests the *cross-engine* check."""
        for puzzle in puzzles:
            verdict = validate(corrupt_answer(puzzle), validator)
            assert verdict.outcome is ValidationOutcome.NUMERIC_MISMATCH, verdict

    def test_a_corrupted_answer_survives_the_numeric_check_still_fails_symbolically(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """The numeric re-check runs first and catches the mutation, so on its own it would
        hide whether the second engine is doing anything. Bypass it and check the engine
        directly: DDAR must refuse to derive the corrupted value."""
        from fractions import Fraction

        from geoforge.solvers.types import Fact, PremiseSpec, fact_from_id

        for puzzle in puzzles:
            goal = fact_from_id(puzzle["goal"]["fact"])
            assert goal.value is not None
            wrong = Fact(goal.kind, goal.args, goal.value + Fraction(1, 180))
            spec = PremiseSpec(
                points=tuple(
                    sorted((p["id"], p["x"], p["y"]) for p in puzzle["reference_figure"]["points"])
                ),
                premises=tuple(fact_from_id(f) for f in puzzle["given"]),
                goals=(wrong,),
            )
            proved = validator.solve_facts(spec).proof_dag.proved_goals
            assert wrong.fact_id not in proved, puzzle["id"]

    def test_a_lying_published_answer_is_rejected(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """Here the geometry is untouched and the JSON lies. The engine would pass it happily,
        which is why validation also ties the published answer to the derived fact."""
        for puzzle in puzzles:
            verdict = validate(corrupt_published_answer(puzzle), validator)
            assert verdict.outcome is ValidationOutcome.ANSWER_MISMATCH, verdict

    def test_dropping_a_premise_makes_the_goal_underivable(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """Stage 6 minimization claims no given is redundant. This is that claim re-checked by
        a second engine: remove any one and the answer must stop following."""
        checked = 0
        for puzzle in puzzles:
            for index in range(len(puzzle["given"])):
                verdict = validate(drop_premise(puzzle, index), validator)
                assert verdict.outcome is ValidationOutcome.NOT_DERIVABLE, (
                    f"{puzzle['id']} still derives its answer without {puzzle['given'][index]}"
                )
                checked += 1
        assert checked, "no premises were dropped, so nothing was tested"

    def test_a_malformed_puzzle_is_rejected_not_crashed_on(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        broken = json.loads(json.dumps(puzzles[0]))
        del broken["reference_figure"]
        assert validate(broken, validator).outcome is ValidationOutcome.MALFORMED

    def test_a_configuration_fact_smuggled_into_the_givens_is_rejected(
        self, puzzles: list[dict[str, Any]], validator: ValidatorBackend
    ) -> None:
        """DDAR cannot state one. Treating it as a pass would certify a puzzle whose stated
        hypotheses were never checked."""
        smuggled = json.loads(json.dumps(puzzles[0]))
        smuggled["given"].append("sameclock:a:b:c:a:b:c")
        assert validate(smuggled, validator).outcome is ValidationOutcome.UNSUPPORTED


class TestIndependence:
    def test_validating_with_the_generation_engine_is_refused(
        self, puzzles: list[dict[str, Any]]
    ) -> None:
        """CLAUDE.md and docs/02 invariant 3. The failure this guards against is silent: a bank
        'validated' by its own generator passes everything and proves nothing."""
        with pytest.raises(ValueError, match="invariant 3"):
            validate(puzzles[0], get_backend())  # type: ignore[arg-type]


class TestSummaryAndCli:
    def test_summary_counts_outcomes(self, puzzles: list[dict[str, Any]]) -> None:
        verdicts = [
            Validation("a", ValidationOutcome.VALIDATED, "e"),
            Validation("b", ValidationOutcome.NOT_DERIVABLE, "e"),
        ]
        assert summary(verdicts)["validated"] == 1
        assert summary(verdicts)["failed"] == 1

    def test_cli_validates_a_batch_file_and_exits_zero(
        self, puzzles: list[dict[str, Any]], tmp_path: Any
    ) -> None:
        path = tmp_path / "bank.json"
        path.write_text(json.dumps({"summary": {}, "puzzles": puzzles}))
        assert main([str(path), "--mutation-test"]) == 0

    def test_cli_exits_nonzero_when_a_puzzle_fails(
        self, puzzles: list[dict[str, Any]], tmp_path: Any
    ) -> None:
        """A validation failure must fail the build, not print a warning."""
        path = tmp_path / "bank.json"
        path.write_text(json.dumps({"summary": {}, "puzzles": [corrupt_answer(puzzles[0])]}))
        assert main([str(path)]) == 1
