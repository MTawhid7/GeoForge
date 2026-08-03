"""The generated JSON Schema and TypeScript, and the drift check that keeps them honest.

The test that carries the weight is `TestGeneratedTypesMatchTheJson`. The emitters walk
`dataclasses.fields()`, but the artifact is produced by `to_json`, which renames and
synthesises keys — so the two can disagree while both look fine on their own, and the symptom
would be a frontend compiling against a field the pipeline never writes. Comparing the emitted
interfaces against *real* emitted payloads is the only check that sees that.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from geoforge import schema, schema_emit
from geoforge.generator.batch import BatchReport, run

BATCH_N = 60
SEED = 42


@pytest.fixture(scope="module")
def report() -> BatchReport:
    return run(BATCH_N, SEED)


@pytest.fixture(scope="module")
def payloads(report: BatchReport) -> list[dict[str, Any]]:
    emitted = [p.to_json() for p in report.puzzles]
    assert emitted
    return emitted


def _interface_fields(text: str, name: str) -> set[str]:
    """Field names declared by one emitted TypeScript interface.

    Line-based rather than brace-based: a rendered type may itself contain braces (`Goal.answer`
    is `ExactValue & { display: string }`), and splitting on the first `}` silently truncates
    the interface — which reads as a missing field rather than as a broken parser.
    """
    body = text.split(f"export interface {name} {{", 1)[1]
    fields = set()
    for line in body.splitlines():
        if line.startswith("}"):
            break
        stripped = line.strip()
        if stripped:
            fields.add(stripped.split(":", 1)[0].rstrip("?"))
    return fields


class TestDeterminism:
    def test_two_renders_are_identical(self) -> None:
        """The drift check is a byte comparison, so the emitter must not vary run to run."""
        assert schema_emit.emit_ts() == schema_emit.emit_ts()
        assert schema_emit.json_schema_text() == schema_emit.json_schema_text()

    def test_committed_artifacts_are_current(self) -> None:
        """What CI runs. A stale artifact fails the build rather than shipping a lie."""
        assert schema_emit.check() == []

    def test_the_check_actually_detects_drift(self, tmp_path: Any, monkeypatch: Any) -> None:
        """A drift check that cannot fail is not a check."""
        stale = tmp_path / "puzzle.ts"
        stale.write_text("export interface Puzzle { nope: string }\n")
        monkeypatch.setattr(schema_emit, "TS_PATH", stale)
        problems = schema_emit.check()
        assert problems
        assert "is stale" in problems[0]

    def test_a_missing_artifact_is_drift_not_a_crash(self, tmp_path: Any, monkeypatch: Any) -> None:
        monkeypatch.setattr(schema_emit, "TS_PATH", tmp_path / "absent.ts")
        assert schema_emit.check()


class TestGeneratedTypesMatchTheJson:
    """Every key the pipeline emits is declared, and every declared key is emitted."""

    def test_puzzle_keys_are_declared(self, payloads: list[dict[str, Any]]) -> None:
        declared = _interface_fields(schema_emit.emit_ts(), "Puzzle")
        for raw in payloads:
            undeclared = set(raw) - declared
            assert not undeclared, f"{raw['id']} emits {sorted(undeclared)}, absent from Puzzle"

    def test_nested_keys_are_declared(self, payloads: list[dict[str, Any]]) -> None:
        text = schema_emit.emit_ts()
        for raw in payloads:
            for interface, payload in (
                ("Figure", raw["figure"]),
                ("Marks", raw["figure"]["marks"]),
                ("Goal", raw["goal"]),
                ("GoalInput", raw["goal"]["input"]),
                ("Difficulty", raw["difficulty"]),
            ):
                undeclared = set(payload) - _interface_fields(text, interface)
                assert not undeclared, f"{interface} is missing {sorted(undeclared)}"

    def test_given_keys_are_declared(self, payloads: list[dict[str, Any]]) -> None:
        declared = _interface_fields(schema_emit.emit_ts(), "Given")
        for raw in payloads:
            for given in raw["given"]:
                assert set(given) <= declared, sorted(set(given) - declared)

    def test_step_keys_are_declared(self, payloads: list[dict[str, Any]]) -> None:
        declared = _interface_fields(schema_emit.emit_ts(), "Step")
        for raw in payloads:
            for step in raw["solution"]:
                assert set(step) <= declared

    def test_required_puzzle_keys_are_always_emitted(self, payloads: list[dict[str, Any]]) -> None:
        """A field the emitter marks required must actually be present, or the frontend's
        non-optional type is a lie about data it will sometimes not receive."""
        document = schema_emit.json_schema()
        required = set(document["$defs"]["Puzzle"]["required"])
        for raw in payloads:
            missing = required - set(raw)
            assert not missing, f"{raw['id']} lacks required {sorted(missing)}"

    def test_the_answer_override_reflects_the_real_shape(
        self, payloads: list[dict[str, Any]]
    ) -> None:
        """`Goal.answer` is an ExactValue plus a `display` that `to_json` synthesises, which no
        dataclass field describes. If that override drifted, the frontend would lose `display`."""
        for raw in payloads:
            assert set(raw["goal"]["answer"]) == {"exact", "approx", "display"}
        assert "ExactValue & { display: string }" in schema_emit.emit_ts()


class TestJsonSchemaDocument:
    def test_it_is_valid_json_and_names_its_version(self) -> None:
        document = json.loads(schema_emit.json_schema_text())
        assert document["$schema"].startswith("https://json-schema.org/")
        assert schema.SCHEMA_VERSION in document["$id"]

    def test_every_ref_resolves(self) -> None:
        document = schema_emit.json_schema()
        defs = set(document["$defs"])

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str):
                    assert ref.removeprefix("#/$defs/") in defs, ref
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(document)

    def test_objects_are_closed(self) -> None:
        """`additionalProperties: false` mirrors the parser, which rejects unknown keys. A doc
        that allowed extras would describe a laxer format than the code accepts."""
        for name, definition in schema_emit.json_schema()["$defs"].items():
            assert definition["additionalProperties"] is False, name


class TestTypeRendering:
    def test_fixed_arity_tuples_keep_their_arity(self) -> None:
        """`at` is (P, VERTEX, Q). Rendered as `string[]` the frontend could index a fourth."""
        assert schema_emit.ts_type(tuple[str, str, str]) == "[string, string, string]"
        document = schema_emit.json_schema()["$defs"]["AngleArc"]["properties"]["at"]
        assert document["minItems"] == document["maxItems"] == 3

    def test_variadic_tuples_render_as_arrays(self) -> None:
        assert schema_emit.ts_type(tuple[str, ...]) == "string[]"

    def test_optional_renders_as_a_null_union(self) -> None:
        assert schema_emit.ts_type(str | None) == "string | null"

    def test_literals_become_string_unions(self) -> None:
        import typing

        hints = typing.get_type_hints(schema.Given)
        assert schema_emit.ts_type(hints["form"]) == '"quantity" | "relation"'

    def test_an_untaught_type_raises_rather_than_guessing(self) -> None:
        """Silently rendering an unknown annotation as `unknown` would let a real type reach the
        frontend as an opaque blob, which is worse than a build failure at emit time."""
        with pytest.raises(TypeError, match="has not been taught"):
            schema_emit.ts_type(complex)
        with pytest.raises(TypeError, match="has not been taught"):
            schema_emit.json_type(complex)
