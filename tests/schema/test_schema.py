"""Puzzle JSON v2: the grammars, the strict parser, and the marks-are-claims invariant.

The round-trip tests run over a real pipeline batch, because a hand-written puzzle would only
test the schema against my idea of what the generator emits. The rejection tests are
hand-built, because the generator does not produce malformed puzzles on demand — and a parser
whose refusals are never exercised is a parser that has only been tested on the happy path.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from geoforge import schema
from geoforge.generator.batch import BatchReport, run
from geoforge.schema import Puzzle, SchemaError

BATCH_N = 60
SEED = 42


@pytest.fixture(scope="module")
def report() -> BatchReport:
    return run(BATCH_N, SEED)


@pytest.fixture(scope="module")
def payloads(report: BatchReport) -> list[dict[str, Any]]:
    emitted = [p.to_json() for p in report.puzzles]
    assert emitted, "the pipeline must reach Stage 9 for the schema to have anything to check"
    return emitted


class TestRoundTrip:
    def test_every_emitted_puzzle_parses(self, payloads: list[dict[str, Any]]) -> None:
        for raw in payloads:
            assert Puzzle.from_json(raw).id == raw["id"]

    def test_parse_then_emit_is_a_fixed_point(self, payloads: list[dict[str, Any]]) -> None:
        """If a round trip changed anything, the JSON would not be the artifact — some field
        would only be correct as long as nobody read it back."""
        for raw in payloads:
            assert Puzzle.from_json(raw).to_json() == raw

    def test_json_is_serializable_and_stable(self, payloads: list[dict[str, Any]]) -> None:
        for raw in payloads:
            assert json.loads(json.dumps(raw, sort_keys=True)) == raw

    def test_stripped_form_drops_exactly_the_build_time_blocks(
        self, payloads: list[dict[str, Any]]
    ) -> None:
        shipped = Puzzle.from_json(payloads[0]).stripped().to_json()
        for key in schema.BUILD_TIME_FIELDS:
            assert key not in shipped, f"{key} must not reach a shipped shard (docs/02)"
        assert shipped["figure"] and shipped["given"] and shipped["solution"]

    def test_stripped_form_still_parses(self, payloads: list[dict[str, Any]]) -> None:
        """A shipped shard has to be readable by the same parser the frontend types come from."""
        shipped = Puzzle.from_json(payloads[0]).stripped().to_json()
        assert Puzzle.from_json(shipped).reference_figure is None


class TestRejections:
    """One negative per refusal path. Each must fail for its own stated reason."""

    def test_unknown_top_level_key(self, payloads: list[dict[str, Any]]) -> None:
        raw = json.loads(json.dumps(payloads[0]))
        raw["difficultly"] = {}
        with pytest.raises(SchemaError, match="unknown puzzle key"):
            Puzzle.from_json(raw)

    def test_missing_required_key(self, payloads: list[dict[str, Any]]) -> None:
        raw = json.loads(json.dumps(payloads[0]))
        del raw["goal"]
        with pytest.raises(SchemaError, match="missing required key 'goal'"):
            Puzzle.from_json(raw)

    def test_unknown_major_version(self, payloads: list[dict[str, Any]]) -> None:
        raw = json.loads(json.dumps(payloads[0]))
        raw["schema_version"] = "3.0"
        with pytest.raises(SchemaError, match="major"):
            Puzzle.from_json(raw)

    def test_a_minor_bump_is_accepted(self, payloads: list[dict[str, Any]]) -> None:
        """Additive changes bump the minor and must stay readable (docs/02)."""
        raw = json.loads(json.dumps(payloads[0]))
        raw["schema_version"] = "2.7"
        assert Puzzle.from_json(raw).schema_version == "2.7"

    def test_a_highlight_outside_the_grammar(self, payloads: list[dict[str, Any]]) -> None:
        raw = json.loads(json.dumps(payloads[0]))
        raw["given"][0]["highlights"] = ["segment:A:B"]
        with pytest.raises(SchemaError, match="normative highlight id"):
            Puzzle.from_json(raw)

    def test_a_lowercase_highlight_is_refused(self, payloads: list[dict[str, Any]]) -> None:
        """Engine names must never reach a player-facing id; `seg:a:b` is the shape of that bug."""
        raw = json.loads(json.dumps(payloads[0]))
        raw["given"][0]["highlights"] = ["seg:a:b"]
        with pytest.raises(SchemaError, match="normative highlight id"):
            Puzzle.from_json(raw)

    def test_an_exact_value_outside_the_grammar(self, payloads: list[dict[str, Any]]) -> None:
        raw = json.loads(json.dumps(payloads[0]))
        raw["goal"]["answer"]["exact"] = "cbrt(2)"
        with pytest.raises(SchemaError, match="exact-value grammar"):
            Puzzle.from_json(raw)

    def test_a_surd_is_refused_until_the_exact_layer_exists(self) -> None:
        """Syntactically inside the grammar, semantically unrepresentable in v1. Refusing beats
        returning a float and calling it exact."""
        with pytest.raises(SchemaError, match="surd"):
            schema.parse_exact("3*sqrt(2)")

    def test_a_given_that_claims_a_form_it_does_not_carry(
        self, payloads: list[dict[str, Any]]
    ) -> None:
        raw = json.loads(json.dumps(payloads[0]))
        raw["given"][0]["form"] = "quantity"
        with pytest.raises(SchemaError, match="form='quantity'"):
            Puzzle.from_json(raw)

    def test_colliding_display_labels(self) -> None:
        """Two engine points labelled the same would merge in every id the player sees."""
        with pytest.raises(SchemaError, match="collide on display labels"):
            schema.display_labels(["a", "A"])

    def test_labels_that_do_not_collide_are_fine(self) -> None:
        assert schema.display_labels(["a", "a1", "b"]) == ("A", "A1", "B")


class TestExactGrammar:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("40", 40), ("-30", -30), ("1/2", 0.5), ("90", 90), ("7/3", 7 / 3)],
    )
    def test_accepted(self, text: str, expected: float) -> None:
        assert float(schema.parse_exact(text)) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["", "40deg", "4.5", "1//2", "pi", "40 + x"])
    def test_refused(self, text: str) -> None:
        with pytest.raises(SchemaError):
            schema.parse_exact(text)


class TestMarksAreClaims:
    """A mark is a claim, so it must be backed by a given — and never by the goal.

    These are hand-built because the pipeline does not emit unbacked marks; that is the point.
    Without them the invariant would be asserted by a check nothing has ever made fail.
    """

    def _puzzle(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "test-1",
            "schema_version": "2.0",
            "quantity_type": "angle",
            "difficulty": {"band": "easy", "depth": 3, "distinct_rules": 2},
            "figure": {
                "points": [
                    {"id": "A", "x": 0.0, "y": 0.0},
                    {"id": "B", "x": 10.0, "y": 0.0},
                    {"id": "C", "x": 0.0, "y": 10.0},
                ],
                "segments": [["A", "B"], ["A", "C"]],
                "circles": [],
                "regions": [],
                "marks": {
                    "equal_segments": [],
                    "parallel": [],
                    "right_angles": [],
                    "angle_arcs": [{"at": ["B", "A", "C"], "label": "?", "kind": "goal"}],
                    "length_labels": [],
                },
            },
            "given": [
                {
                    "form": "relation",
                    "fact": "coll:a:b:c",
                    "display": "A, B and C are collinear",
                    "highlights": ["point:A"],
                }
            ],
            "goal": {
                "fact": "aconst:a:b:a:c=1/2",
                "question": "∠BAC",
                "quantity": {"kind": "angle", "at": ["B", "A", "C"]},
                "answer": {"exact": "90", "approx": 90.0, "display": "90°"},
                "input": {"mode": "keypad", "exactness": "integer", "unit": "deg"},
            },
            "solution": [],
        }
        base["figure"]["marks"].update(overrides.pop("marks", {}))
        base.update(overrides)
        return base

    def test_the_baseline_is_valid(self) -> None:
        """Otherwise every test below could pass for the wrong reason."""
        assert Puzzle.from_json(self._puzzle()).id == "test-1"

    def test_ticks_with_no_congruent_given(self) -> None:
        raw = self._puzzle(marks={"equal_segments": [["A:B", "A:C"]]})
        with pytest.raises(SchemaError, match="no cong among the givens"):
            Puzzle.from_json(raw)

    def test_parallel_marks_with_no_parallel_given(self) -> None:
        raw = self._puzzle(marks={"parallel": [["A:B", "A:C"]]})
        with pytest.raises(SchemaError, match="no para among the givens"):
            Puzzle.from_json(raw)

    def test_right_angle_mark_with_no_perpendicular_given(self) -> None:
        raw = self._puzzle(marks={"right_angles": ["angle:B:C:A"]})
        with pytest.raises(SchemaError, match="no perp or aconst among the givens"):
            Puzzle.from_json(raw)

    def test_a_right_angle_square_on_the_goal_angle_states_the_answer(self) -> None:
        """The goal is 90°, so marking it would print the answer on the figure. This is why the
        goal backs no mark but its own question mark."""
        raw = self._puzzle(marks={"right_angles": ["angle:B:A:C"]})
        raw["given"].append(
            {
                "form": "relation",
                "fact": "perp:a:b:a:c",
                "display": "AB ⊥ AC",
                "highlights": ["seg:A:B", "seg:A:C"],
            }
        )
        with pytest.raises(SchemaError, match="states the answer on the figure"):
            Puzzle.from_json(raw)

    def test_a_right_angle_square_elsewhere_is_fine(self) -> None:
        """The near-miss that keeps the check above from passing by rejecting every square.
        Same points, different vertex — ∠BCA is not ∠BAC."""
        raw = self._puzzle(marks={"right_angles": ["angle:B:C:A"]})
        raw["given"].append(
            {
                "form": "relation",
                "fact": "perp:c:b:c:a",
                "display": "CB ⊥ CA",
                "highlights": ["seg:B:C", "seg:A:C"],
            }
        )
        assert Puzzle.from_json(raw).figure.marks.right_angles == ("angle:B:C:A",)

    def test_a_given_arc_on_the_goal_angle_states_the_answer(self) -> None:
        raw = self._puzzle(
            marks={
                "angle_arcs": [
                    {"at": ["B", "A", "C"], "label": "90°", "kind": "given"},
                    {"at": ["B", "A", "C"], "label": "?", "kind": "goal"},
                ]
            }
        )
        raw["given"].append(
            {
                "form": "quantity",
                "fact": "aconst:a:b:a:c=1/2",
                "display": "∠BAC = 90°",
                "highlights": ["angle:B:A:C"],
                "quantity": {"kind": "angle", "at": ["B", "A", "C"]},
                "value": {"exact": "90", "approx": 90.0},
            }
        )
        with pytest.raises(SchemaError, match="states the answer on the figure"):
            Puzzle.from_json(raw)

    def test_more_given_arcs_than_valued_givens(self) -> None:
        raw = self._puzzle(
            marks={
                "angle_arcs": [
                    {"at": ["A", "B", "C"], "label": "40°", "kind": "given"},
                    {"at": ["B", "A", "C"], "label": "?", "kind": "goal"},
                ]
            }
        )
        with pytest.raises(SchemaError, match="given angle arcs but only 0 valued"):
            Puzzle.from_json(raw)


class TestEmittedFigures:
    """Properties of the figures the pipeline actually produces."""

    def test_every_point_id_is_a_display_label(self, payloads: list[dict[str, Any]]) -> None:
        for raw in payloads:
            for point in raw["figure"]["points"]:
                assert point["id"][0].isupper(), point["id"]

    def test_reference_points_stay_in_engine_names(self, payloads: list[dict[str, Any]]) -> None:
        """The two coordinate systems must not bleed into one another (docs/02)."""
        for raw in payloads:
            for point in raw["reference_figure"]["points"]:
                assert point["id"][0].islower(), point["id"]

    def test_segments_reference_existing_points(self, payloads: list[dict[str, Any]]) -> None:
        for raw in payloads:
            known = {p["id"] for p in raw["figure"]["points"]}
            for a, b in raw["figure"]["segments"]:
                assert {a, b} <= known, (
                    f"{raw['id']} draws a segment to a point it has no place for"
                )

    def test_marks_reference_existing_points(self, payloads: list[dict[str, Any]]) -> None:
        for raw in payloads:
            known = {p["id"] for p in raw["figure"]["points"]}
            for arc in raw["figure"]["marks"]["angle_arcs"]:
                assert set(arc["at"]) <= known

    def test_every_puzzle_marks_its_goal_and_marks_it_once(
        self, payloads: list[dict[str, Any]]
    ) -> None:
        """Without the `?` the player is not told which angle is being asked for."""
        for raw in payloads:
            goal_arcs = [a for a in raw["figure"]["marks"]["angle_arcs"] if a["kind"] == "goal"]
            assert len(goal_arcs) == 1, raw["id"]
            assert goal_arcs[0]["label"] == "?"
            assert goal_arcs[0]["at"] == raw["goal"]["quantity"]["at"]

    def test_display_coordinates_sit_inside_the_viewbox(
        self, payloads: list[dict[str, Any]]
    ) -> None:
        from geoforge.config import LAYOUT

        for raw in payloads:
            for point in raw["figure"]["points"]:
                assert 0 <= point["x"] <= LAYOUT.viewbox_width, raw["id"]
                assert 0 <= point["y"] <= LAYOUT.viewbox_height, raw["id"]

    def test_framing_preserves_shape(self, payloads: list[dict[str, Any]]) -> None:
        """Framing is a similarity transform, so every ratio of distances survives it. Anything
        else would break a premise (docs/06 §6.3, docs/07 T5)."""
        import math

        for raw in payloads:
            reference = {p["id"]: (p["x"], p["y"]) for p in raw["reference_figure"]["points"]}
            display = {p["id"].lower(): (p["x"], p["y"]) for p in raw["figure"]["points"]}
            names = sorted(set(reference) & set(display))
            if len(names) < 3:
                continue
            base_ref = math.dist(reference[names[0]], reference[names[1]])
            base_dis = math.dist(display[names[0]], display[names[1]])
            if base_ref == 0:
                continue
            for other in names[2:]:
                ratio_ref = math.dist(reference[names[0]], reference[other]) / base_ref
                ratio_dis = math.dist(display[names[0]], display[other]) / base_dis
                assert ratio_dis == pytest.approx(ratio_ref, rel=1e-3), raw["id"]
