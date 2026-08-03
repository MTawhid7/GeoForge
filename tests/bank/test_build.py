"""The bank builder: shards, manifest, archive, and the gates that fail a build.

Two properties the build exists to guarantee. Shipped shards must not carry build-time data —
`reference_figure` and `provenance` are how a puzzle is audited, not how it is played. And an
invalid puzzle must fail the build rather than reach a shard, because a bank that ships one
broken puzzle is worse than a bank that does not ship.

The honesty tests matter as much: while scoring, dedupe and anti-leak are missing, the manifest
must say so in a form a downstream tool can read, and `--strict` must refuse outright.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from geoforge import schema
from geoforge.bank.build import MISSING_FOR_SHIPPABLE, build, main
from geoforge.config import BANK

BUILD_N = 60
SEED = 42


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Any, Path]:
    out = tmp_path_factory.mktemp("bank") / "v2"
    report = build(BUILD_N, SEED, out)
    assert report.puzzles, "the build must produce puzzles for these tests to mean anything"
    return report, out


@pytest.fixture(scope="module")
def manifest(built: tuple[Any, Path]) -> dict[str, Any]:
    return json.loads((built[1] / "manifest.json").read_text())


class TestShards:
    def test_a_shard_exists_for_every_band_with_puzzles(
        self, built: tuple[Any, Path], manifest: dict[str, Any]
    ) -> None:
        report, out = built
        assert set(manifest["by_band"]) == set(report.by_band())
        for shard in manifest["shards"]:
            assert (out / shard["file"]).exists()

    def test_shard_counts_sum_to_the_bank(self, manifest: dict[str, Any]) -> None:
        assert sum(s["puzzles"] for s in manifest["shards"]) == manifest["puzzles"]

    def test_every_shard_hash_matches_its_file(
        self, built: tuple[Any, Path], manifest: dict[str, Any]
    ) -> None:
        import hashlib

        _, out = built
        for shard in manifest["shards"]:
            payload = (out / shard["file"]).read_text()
            assert hashlib.sha256(payload.encode()).hexdigest() == shard["sha256"]

    def test_no_shard_exceeds_the_configured_size(self, manifest: dict[str, Any]) -> None:
        for shard in manifest["shards"]:
            assert shard["puzzles"] <= BANK.shard_size


class TestStripping:
    def test_shipped_puzzles_carry_no_build_time_data(self, built: tuple[Any, Path]) -> None:
        """docs/02: `reference_figure` and `provenance` are build-time only. Shipping them
        would hand every player the exact coordinates the answer was derived over."""
        _, out = built
        for shard in out.glob("*-*.json"):
            for puzzle in json.loads(shard.read_text()):
                for key in schema.BUILD_TIME_FIELDS:
                    assert key not in puzzle, f"{puzzle['id']} ships {key}"

    def test_shipped_puzzles_still_parse(self, built: tuple[Any, Path]) -> None:
        """A shard has to be readable by the parser the frontend types are generated from."""
        _, out = built
        for shard in out.glob("*-*.json"):
            for puzzle in json.loads(shard.read_text()):
                assert schema.Puzzle.from_json(puzzle).figure.points

    def test_shipped_puzzles_keep_everything_a_player_needs(self, built: tuple[Any, Path]) -> None:
        _, out = built
        for shard in out.glob("*-*.json"):
            for raw in json.loads(shard.read_text()):
                puzzle = schema.Puzzle.from_json(raw)
                assert puzzle.figure.points and puzzle.given and puzzle.solution
                assert puzzle.goal.answer.exact
                assert any(a.kind == "goal" for a in puzzle.figure.marks.angle_arcs)


class TestArchive:
    def test_the_archive_keeps_what_the_shards_drop(self, built: tuple[Any, Path]) -> None:
        """`bank/validate.py` promises it can be pointed at a build months later. That needs a
        file that still has the reference figure in it."""
        _, out = built
        archive = out.parent / BANK.archive_dirname / f"seed-{SEED}.json.gz"
        assert archive.exists()
        with gzip.open(archive, "rt") as handle:
            payload = json.load(handle)
        assert payload["puzzles"]
        for puzzle in payload["puzzles"]:
            assert puzzle["reference_figure"]["points"]
            assert puzzle["provenance"]

    def test_the_archive_still_validates(self, built: tuple[Any, Path]) -> None:
        from geoforge.bank.validate import validate_all

        _, out = built
        with gzip.open(out.parent / BANK.archive_dirname / f"seed-{SEED}.json.gz", "rt") as handle:
            payload = json.load(handle)
        failures = [v for v in validate_all(payload["puzzles"]) if not v.ok]
        assert failures == [], [f"{v.puzzle_id} {v.detail}" for v in failures]


class TestHonestyAboutWhatIsMissing:
    def test_the_manifest_says_it_is_not_shippable(self, manifest: dict[str, Any]) -> None:
        assert manifest["shippable"] is False

    def test_the_manifest_names_what_is_missing(self, manifest: dict[str, Any]) -> None:
        """'Not shippable' with no reason is a flag nobody can act on."""
        assert set(manifest["missing_for_shippable"]) == set(MISSING_FOR_SHIPPABLE)

    def test_the_manifest_names_both_engines(self, manifest: dict[str, Any]) -> None:
        """docs/02 invariant 3: a reader must be able to see they were different."""
        assert manifest["generation_engine"] != manifest["validator_engine"]

    def test_strict_refuses_an_incomplete_bank(self, tmp_path: Path) -> None:
        """What CI will use once the pipeline is complete. Until then it must refuse."""
        with pytest.raises(RuntimeError, match="not shippable"):
            build(20, SEED, tmp_path / "v2", strict=True)


class TestValidationGate:
    def test_an_invalid_puzzle_fails_the_build(
        self, built: tuple[Any, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The gate docs/09 P2 turns on: any non-validated verdict must stop the build, and
        must stop it *before* anything is written."""
        from geoforge.bank import build as build_module
        from geoforge.bank.validate import Validation, ValidationOutcome

        def all_broken(payloads: Any, validator: Any = None) -> tuple[Validation, ...]:
            return tuple(
                Validation(str(p["id"]), ValidationOutcome.NOT_DERIVABLE, "stub", "injected")
                for p in payloads
            )

        monkeypatch.setattr(build_module.cross, "validate_all", all_broken)
        out = tmp_path / "v2"
        report = build(BUILD_N, SEED, out)
        assert report.validation_failures
        assert not out.exists(), "a failing build must not leave shards behind"

    def test_the_cli_exits_non_zero_on_a_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from geoforge.bank import build as build_module
        from geoforge.bank.validate import Validation, ValidationOutcome

        monkeypatch.setattr(
            build_module.cross,
            "validate_all",
            lambda payloads, validator=None: tuple(
                Validation(str(p["id"]), ValidationOutcome.ANSWER_MISMATCH, "stub", "injected")
                for p in payloads
            ),
        )
        assert main(["--n", "40", "--seed", "42", "--out", str(tmp_path / "v2")]) == 1

    def test_the_cli_exits_zero_on_a_clean_build(self, tmp_path: Path) -> None:
        """The near-miss: without it the test above could pass on a build that always fails."""
        assert main(["--n", "40", "--seed", "42", "--out", str(tmp_path / "v2")]) == 0


class TestDeterminism:
    def test_two_builds_agree(self, tmp_path: Path) -> None:
        first = build(40, SEED, tmp_path / "a")
        second = build(40, SEED, tmp_path / "b")
        assert [p.to_json() for p in first.puzzles] == [p.to_json() for p in second.puzzles]
        assert (tmp_path / "a" / "manifest.json").read_text() == (
            tmp_path / "b" / "manifest.json"
        ).read_text()
