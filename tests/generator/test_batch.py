"""The batch runner and Stage 9 emit (docs/04), plus the Phase 1 acceptance criteria.

The full-scale acceptance runs (1,000 constructions; 100 puzzles across ≥ 2 bands) take minutes and
live in `make bench-batch`, not here. What these tests pin are the properties those runs depend on:
reproducibility, complete attrition accounting, and that nothing reaches output without passing
every gate.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

from geoforge.generator.batch import STAGES, BatchReport, main, run
from geoforge.scoring.bands import BAND_ORDER
from tests.translation.test_phrases import HIGHLIGHT_GRAMMAR

#: Small enough to keep the suite fast, large enough that the pipeline reaches Stage 9.
BATCH_N = 60
SEED = 42


@pytest.fixture(scope="module")
def report() -> BatchReport:
    return run(BATCH_N, SEED)


class TestReproducibility:
    """docs/09 P1 AC 1: a fixed seed gives a byte-identical batch."""

    def test_two_runs_agree(self, report: BatchReport) -> None:
        again = run(BATCH_N, SEED)
        assert [p.to_json() for p in report.puzzles] == [p.to_json() for p in again.puzzles]

    def test_attrition_is_identical(self, report: BatchReport) -> None:
        """The attrition report is the primary regression signal, so it has to be stable enough
        to diff (docs/04)."""
        again = run(BATCH_N, SEED)
        assert report.by_reason() == again.by_reason()

    def test_batch_survives_a_different_hash_seed(self) -> None:
        """The determinism test that matters, and the one that would have caught BUG-4.

        Two runs inside one process share that process's string-hash seed, so they agree even when
        engine canonicalization leaks `set` ordering into results. Subprocesses do not.
        """
        script = (
            "import json;from geoforge.generator.batch import run;"
            f"print(json.dumps([p.to_json() for p in run({BATCH_N // 3}, {SEED}).puzzles],"
            " sort_keys=True))"
        )
        outputs = []
        for hash_seed in ("0", "31337"):
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": hash_seed},
                check=True,
            )
            outputs.append(proc.stdout)
        assert outputs[0] == outputs[1]

    def test_a_different_seed_gives_different_output(self) -> None:
        """Reproducibility must not be the trivial kind where the seed does nothing."""
        other = run(BATCH_N, SEED + 1)
        assert [p.id for p in other.puzzles] != [p.id for p in run(BATCH_N, SEED).puzzles]


class TestAttritionAccounting:
    def test_every_discard_names_a_real_stage(self, report: BatchReport) -> None:
        for discard in report.discards:
            assert discard.stage in STAGES, discard

    def test_every_discard_carries_its_seed(self, report: BatchReport) -> None:
        """docs/04: `(stage, reason, seed)`. Without the seed a discard cannot be reproduced."""
        for discard in report.discards:
            assert discard.seed > 0

    def test_report_counts_constructions_it_actually_ran(self, report: BatchReport) -> None:
        assert report.constructions == BATCH_N

    def test_summary_is_json_serializable(self, report: BatchReport) -> None:
        """It gets written to disk and diffed between builds."""
        assert json.loads(json.dumps(report.summary()))


class TestEmittedPuzzles:
    """docs/09 P1 AC 3: everything shipped has passed every gate."""

    def test_a_batch_produces_puzzles(self, report: BatchReport) -> None:
        assert report.puzzles, "the pipeline must reach Stage 9 on a batch this size"

    def test_no_soundness_failures(self, report: BatchReport) -> None:
        """docs/09 P1 AC 4, at test scale. The full 1,000-construction run is `make bench-batch`."""
        assert report.soundness_failures == []

    def test_every_puzzle_has_a_solution(self, report: BatchReport) -> None:
        for puzzle in report.puzzles:
            assert puzzle.solution, f"{puzzle.id} shipped with no solution"
            assert [s.step for s in puzzle.solution] == list(range(1, len(puzzle.solution) + 1))

    def test_every_puzzle_has_an_answer_and_a_question(self, report: BatchReport) -> None:
        for puzzle in report.puzzles:
            assert puzzle.answer
            assert puzzle.question.startswith("∠")

    def test_every_puzzle_has_stated_givens(self, report: BatchReport) -> None:
        """A puzzle with no givens is either trivial or lost its premises somewhere."""
        for puzzle in report.puzzles:
            assert puzzle.premises

    def test_bands_are_known(self, report: BatchReport) -> None:
        for puzzle in report.puzzles:
            assert puzzle.band in BAND_ORDER

    def test_depth_meets_the_configured_floor(self, report: BatchReport) -> None:
        from geoforge.config import GENERATION

        for puzzle in report.puzzles:
            assert puzzle.depth >= GENERATION.min_proof_depth

    def test_highlights_follow_the_normative_grammar(self, report: BatchReport) -> None:
        for puzzle in report.puzzles:
            for step in puzzle.solution:
                for highlight in step.highlights:
                    assert HIGHLIGHT_GRAMMAR.match(highlight), highlight

    def test_rule_ids_are_template_ids(self, report: BatchReport) -> None:
        """`solution[].rule` is public API and must never leak an engine rule id."""
        for puzzle in report.puzzles:
            for step in puzzle.solution:
                assert not re.match(r"^r\d+$", step.rule)

    def test_provenance_identifies_the_engine_and_seed(self, report: BatchReport) -> None:
        """docs/02 invariant 2: an artifact is reproducible from its provenance."""
        for puzzle in report.puzzles:
            assert puzzle.provenance["seed"] == puzzle.seed
            assert "newclid" in str(puzzle.provenance["engine"])
            assert puzzle.provenance["construction"]

    def test_ids_are_unique(self, report: BatchReport) -> None:
        ids = [p.id for p in report.puzzles]
        assert len(ids) == len(set(ids))

    def test_pruned_construction_is_not_longer_than_the_original(self, report: BatchReport) -> None:
        for puzzle in report.puzzles:
            drawn = puzzle.construction.count(";")
            sampled = str(puzzle.provenance["construction"]).count(";")
            assert drawn <= sampled


class TestCli:
    def test_run_writes_puzzles_and_exits_zero(self, tmp_path: object) -> None:
        out = f"{tmp_path}/puzzles.json"
        assert main(["--n", "20", "--seed", "42", "--out", out]) == 0
        with open(out) as handle:
            payload = json.load(handle)
        assert "summary" in payload
        assert isinstance(payload["puzzles"], list)

    def test_no_wellposed_flag_skips_the_gate(self) -> None:
        """The flag exists for attrition sweeps. It must be off by default: without Stage 8
        nothing has checked that the answers are answers."""
        gated = run(30, SEED)
        ungated = run(30, SEED, check_wellposed=False)
        assert len(ungated.puzzles) >= len(gated.puzzles)
