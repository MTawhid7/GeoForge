"""Puzzle JSON v2 — the authoritative code-level schema (docs/02).

These frozen dataclasses are the source of truth. The JSON Schema document and the TypeScript
types the frontend compiles against are *emitted* from them, so there is one definition of a
puzzle rather than three that drift.

`Puzzle.from_json` **is** the schema check. It parses strictly — a missing key, an unknown key,
an unknown major version or a value outside a declared grammar all raise `SchemaError` — which
is why no `jsonschema` dependency appears here. The emitted `.schema.json` is a contract for
anything outside this repo; enforcement inside it is this parser.

Two rules the parser exists to enforce, both previously unenforced anywhere:

* **The highlight grammar is normative** (docs/02). `highlights` may contain only `point:`,
  `seg:`, `angle:`, `circle:`, `arc:` and `region:` ids over display labels. A typo like
  `segment:A:B` used to travel all the way to a frontend that would silently render nothing.
* **A mark is a claim.** Every figure mark must be backed by a stated given or the goal. An
  unbacked mark tells the player something the puzzle never said, which is the leak the
  anti-leak layout pass exists to prevent — so the check lives here, where the figure is built,
  and not only there.

Point ids: engine names are lowercase (`a`, `a1`), display labels are uppercase (`A`, `A1`).
The two never mix in one field. `reference_figure` is the engine's, `figure` is the player's.
"""

from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Literal

from geoforge.config import SCHEMA
from geoforge.generator.translation.vertex_angles import label
from geoforge.solvers.types import Fact, FactKind

SCHEMA_VERSION = SCHEMA.version

#: Fields stripped from shipped bank shards (docs/02). Kept in the build archive.
BUILD_TIME_FIELDS = SCHEMA.stripped_fields


class SchemaError(ValueError):
    """A puzzle payload that is not a valid puzzle.

    Raised, never returned as a verdict: a malformed puzzle is a build defect, and the one
    thing that must not happen is a bank shipping a payload the frontend will fail to read.
    """


# --------------------------------------------------------------------------------------
# Grammars
# --------------------------------------------------------------------------------------

#: Display point label: an uppercase letter optionally followed by digits (`A`, `A1`).
_LABEL = r"[A-Z][0-9]*"

#: Normative highlight ids (docs/02). Nothing else may appear in `highlights`.
HIGHLIGHT_GRAMMAR = re.compile(
    rf"^(?:point:{_LABEL}"
    rf"|seg:{_LABEL}:{_LABEL}"
    rf"|angle:{_LABEL}:{_LABEL}:{_LABEL}"
    rf"|circle:{_LABEL}:{_LABEL}"
    rf"|arc:{_LABEL}:{_LABEL}:{_LABEL}"
    rf"|region:[A-Za-z0-9_]+)$"
)

#: The closed exact-value grammar (docs/02): integers, rationals `p/q`, and quadratic surd
#: terms `a*sqrt(b)`, summed. Deliberately closed — a value we cannot parse is a value we
#: cannot promise the frontend can render or compare.
#
# The sign is `[+-]?`, not `-?`. `_split_terms` keeps each term's sign, so every term of a sum
# after the first arrives with an explicit `+` — which the `-?` form rejected, making a
# multi-term value unparseable however well-formed it was. Latent until the area layer became
# the first quantity able to produce one (docs/10 A4).
_EXACT_TERM = re.compile(r"^[+-]?\d+(?:/\d+)?(?:\*sqrt\(\d+\))?$")


def validate_highlight(highlight: str) -> str:
    """Return `highlight` if it is a normative id, else raise."""
    if not HIGHLIGHT_GRAMMAR.match(highlight):
        raise SchemaError(
            f"{highlight!r} is not a normative highlight id (docs/02): expected one of "
            "point:/seg:/angle:/circle:/arc:/region: over uppercase display labels"
        )
    return highlight


@dataclass(frozen=True, slots=True, order=True)
class Exact:
    """A value in docs/02's closed grammar: a sum of `a/b*sqrt(c)` terms.

    **The type that replaced `Fraction` here** (docs/10 A4). `parse_exact` used to return a
    `Fraction` and reject every surd, with a docstring saying so and naming the exact layer that
    would eventually carry one. That layer exists: an area is `25/4*sqrt(3)`, and it is the
    whole reason the layer was built, since no engine predicate can hold a value that is not
    rational (docs/07 T18, T21).

    Deliberately not SymPy. This module is the boundary the bank validator and the frontend
    contract both stand on, and it must stay parseable from JSON alone with no CAS in the loop.
    Two coefficients and a radicand are all the grammar admits.
    """

    terms: tuple[tuple[Fraction, int], ...]
    """`(coefficient, radicand)` per term; radicand 1 means the term is rational."""

    def __float__(self) -> float:
        return sum(float(coeff) * math.sqrt(radicand) for coeff, radicand in self.terms)

    @property
    def rational(self) -> Fraction | None:
        """The value as a `Fraction`, or None when it is irrational.

        Callers that genuinely need a rational — angle arithmetic, the mutation helpers — ask
        for one and get `None` rather than a lossy approximation.
        """
        if any(radicand != 1 for _, radicand in self.terms):
            return None
        return sum((coeff for coeff, _ in self.terms), Fraction(0))

    @property
    def is_rational(self) -> bool:
        return self.rational is not None


def parse_exact(text: str) -> Exact:
    """Parse an `exact` string, raising on anything outside the closed grammar.

    The grammar is closed on purpose: a value we cannot parse is a value we cannot promise the
    frontend will render or compare correctly. Surds inside it are now *represented* rather than
    refused — see `Exact`.
    """
    terms: list[tuple[Fraction, int]] = []
    for term in _split_terms(text):
        if not _EXACT_TERM.match(term):
            raise SchemaError(f"{text!r} is outside the exact-value grammar (docs/02)")
        head, _, radical = term.partition("*sqrt(")
        radicand = int(radical.rstrip(")")) if radical else 1
        terms.append((Fraction(head), radicand))
    if not terms:
        raise SchemaError("empty exact value")
    return Exact(terms=tuple(terms))


def _split_terms(text: str) -> list[str]:
    """Split a sum into signed terms, keeping each term's sign."""
    if not text:
        raise SchemaError("empty exact value")
    terms = re.findall(r"[+-]?[^+-]+", text.replace(" ", ""))
    return [t for t in terms if t]


def display_label(engine_name: str) -> str:
    """Engine point name to player-facing label. `a1` becomes `A1` (docs/02)."""
    return label(engine_name)


def display_labels(engine_names: Sequence[str]) -> tuple[str, ...]:
    """Label a whole point set, refusing a collision.

    Two engine names mapping to one label would silently merge two points in every id the
    player sees — a figure with two `A`s, and highlights that resolve to whichever came first.
    """
    labels = tuple(display_label(n) for n in engine_names)
    if len(set(labels)) != len(labels):
        clash = sorted({x for x in labels if labels.count(x) > 1})
        raise SchemaError(f"engine point names collide on display labels {clash}")
    return labels


# --------------------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DisplayPoint:
    """A point in display coordinates, with its label offset (docs/06 §6.3 item 3)."""

    id: str
    x: float
    y: float
    label_dx: float = 0.0
    label_dy: float = 0.0


@dataclass(frozen=True, slots=True)
class DisplayCircle:
    """A circle in display coordinates.

    Carries `cx`/`cy`/`r` rather than docs/02's sketched `{center, through}`, for two reasons:
    a `cyclic` circle has no named centre at all, and making the frontend solve for a radius
    would put geometry in the renderer, which docs/02 invariant 1 forbids. Computing the centre
    numerically is verification of a circle the engine already proved, not derivation of one.
    """

    id: str
    cx: float
    cy: float
    r: float
    center_point: str | None = None
    """Display label of the centre when the figure names it, for highlighting."""
    through: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AngleArc:
    """A marked angle: a given's value, or the goal's question mark."""

    at: tuple[str, str, str]
    """(P, VERTEX, Q) in display labels."""
    label: str
    """`40°`, or `?` for the goal."""
    kind: Literal["given", "goal"] = "given"


@dataclass(frozen=True, slots=True)
class Marks:
    """What the figure asserts visually. Every entry must be backed by a given or the goal."""

    equal_segments: tuple[tuple[str, ...], ...] = ()
    """Congruence classes; each inner tuple is a group of `A:B` segment ids sharing a tick
    count. Grouped transitively so three equal segments get one tick style, not two."""
    parallel: tuple[tuple[str, ...], ...] = ()
    right_angles: tuple[str, ...] = ()
    """`angle:P:V:Q` ids drawn with a square."""
    angle_arcs: tuple[AngleArc, ...] = ()
    length_labels: tuple[tuple[str, str], ...] = ()
    """(segment id, label). Empty in v1 — `length` registers in P3 (docs/09)."""


@dataclass(frozen=True, slots=True)
class Figure:
    """The player-facing figure. Distinct from `reference_figure` — see docs/02."""

    points: tuple[DisplayPoint, ...]
    segments: tuple[tuple[str, str], ...] = ()
    circles: tuple[DisplayCircle, ...] = ()
    marks: Marks = field(default_factory=Marks)
    regions: tuple[()] = ()
    """Shaded regions for area puzzles — P5 (docs/09), always empty here."""


# --------------------------------------------------------------------------------------
# Statements
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Quantity:
    """A measurable thing the puzzle talks about (docs/04 §QTR)."""

    kind: str
    at: tuple[str, ...] = ()
    """Display labels naming it: (P, VERTEX, Q) for an angle."""


@dataclass(frozen=True, slots=True)
class ExactValue:
    exact: str
    """Canonical symbolic string in the closed grammar. The truth."""
    approx: float
    """float64, for input checking and rendering only — never for truth (docs/02)."""


@dataclass(frozen=True, slots=True)
class Given:
    """One stated hypothesis.

    A tagged union because most givens are *relations* (`AO = CO`, `AB ∥ CD`, `M is the
    midpoint of AB`) rather than the valued quantity statements docs/02's sketch showed. Both
    forms keep `fact`, the canonical engine-neutral id, which is what lets a shipped puzzle be
    re-derived and audited (docs/04 §V).
    """

    form: Literal["quantity", "relation"]
    fact: str
    display: str
    highlights: tuple[str, ...] = ()
    """Elements to light up when the player taps this given. Normative grammar."""
    quantity: Quantity | None = None
    value: ExactValue | None = None

    def __post_init__(self) -> None:
        has_value = self.quantity is not None and self.value is not None
        if (self.form == "quantity") != has_value:
            raise SchemaError(
                f"given {self.fact!r} is form={self.form!r} but "
                f"{'carries' if has_value else 'lacks'} a quantity and value"
            )


@dataclass(frozen=True, slots=True)
class GoalInput:
    """How the answer is collected (docs/02 answer policy, docs/07 T8).

    Four fields rather than docs/02's sketched `{mode, unit}`: `mode` is the widget and
    `exactness` is the class of accepted answer, and conflating them means P3's `length` type
    (decimal widget, surd exact form) cannot be expressed without a schema change.
    """

    mode: str
    exactness: str
    unit: str
    tolerance: float | None = None
    """None for exact classes. A per-puzzle band for decimal answers."""


@dataclass(frozen=True, slots=True)
class Goal:
    fact: str
    question: str
    quantity: Quantity
    answer: ExactValue
    display: str
    input: GoalInput


@dataclass(frozen=True, slots=True)
class Step:
    """One published solution step (docs/02)."""

    step: int
    rule: str
    """Template id. Public API — renaming is a schema change (CLAUDE.md)."""
    text: str
    derives: str
    """Canonical fact id: the trace handle linking this sentence to a proof node."""
    highlights: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Difficulty:
    band: str
    depth: int
    distinct_rules: int
    score: float | None = None
    """The docs/05 §5.1 weighted score. None until the scorer lands (M3)."""


# --------------------------------------------------------------------------------------
# Build-time blocks
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReferencePoint:
    id: str
    """Engine name, lowercase."""
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class ReferenceFigure:
    """The engine's diagram, in engine names, over which the goal was derived (docs/04 §V)."""

    points: tuple[ReferencePoint, ...]


# --------------------------------------------------------------------------------------
# Bank manifest
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Shard:
    """One band's puzzles, as a file the frontend can fetch on its own."""

    file: str
    band: str
    puzzles: int
    sha256: str
    """Of the shard's bytes as written. The frontend does not verify it — the point is that a
    bank served from a CDN can be audited after the fact without rebuilding it."""


@dataclass(frozen=True, slots=True)
class Manifest:
    """The bank's index: what is in it, what built it, and what it is still missing.

    Lives here rather than as a dict in `bank/build.py` for the same reason `Puzzle` does. The
    frontend reads it before anything else, so it is part of the data contract, and a contract
    with one definition cannot drift from the type the frontend compiles against.
    """

    schema_version: str
    generator_version: str
    generation_engine: str
    validator_engine: str
    """docs/02 invariant 3: a reader must be able to see the two were different engines."""
    seed: int
    puzzles: int
    by_band: Mapping[str, int]
    shards: tuple[Shard, ...]
    shippable: bool
    missing_for_shippable: tuple[str, ...]
    """Named, not implied. 'Not shippable' with no reason is a flag nobody can act on, and the
    frontend shows the list rather than deciding for itself what a preview bank is missing."""

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "generation_engine": self.generation_engine,
            "validator_engine": self.validator_engine,
            "seed": self.seed,
            "puzzles": self.puzzles,
            "by_band": dict(self.by_band),
            "shards": [
                {"file": s.file, "band": s.band, "puzzles": s.puzzles, "sha256": s.sha256}
                for s in self.shards
            ],
            "shippable": self.shippable,
            "missing_for_shippable": list(self.missing_for_shippable),
        }

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> Manifest:
        _reject_unknown(raw, set(_MANIFEST_KEYS), "manifest")
        _check_major(_require(raw, "schema_version", str, "manifest"))
        shards = _require(raw, "shards", list, "manifest")
        return cls(
            schema_version=raw["schema_version"],
            generator_version=_require(raw, "generator_version", str, "manifest"),
            generation_engine=_require(raw, "generation_engine", str, "manifest"),
            validator_engine=_require(raw, "validator_engine", str, "manifest"),
            seed=_require(raw, "seed", int, "manifest"),
            puzzles=_require(raw, "puzzles", int, "manifest"),
            by_band=dict(_require(raw, "by_band", dict, "manifest")),
            shards=tuple(_shard_from(s) for s in shards),
            shippable=_require(raw, "shippable", bool, "manifest"),
            missing_for_shippable=tuple(_require(raw, "missing_for_shippable", list, "manifest")),
        )


_MANIFEST_KEYS = tuple(f.name for f in dataclasses.fields(Manifest))


def _shard_from(raw: Any) -> Shard:
    if not isinstance(raw, Mapping):
        raise SchemaError(f"manifest.shards entry should be an object, got {type(raw).__name__}")
    _reject_unknown(raw, {"file", "band", "puzzles", "sha256"}, "shard")
    return Shard(
        file=_require(raw, "file", str, "shard"),
        band=_require(raw, "band", str, "shard"),
        puzzles=_require(raw, "puzzles", int, "shard"),
        sha256=_require(raw, "sha256", str, "shard"),
    )


# --------------------------------------------------------------------------------------
# Puzzle
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Puzzle:
    id: str
    quantity_type: str
    difficulty: Difficulty
    figure: Figure
    given: tuple[Given, ...]
    goal: Goal
    solution: tuple[Step, ...]
    schema_version: str = SCHEMA_VERSION
    configuration: tuple[str, ...] = ()
    reference_figure: ReferenceFigure | None = None
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _check_major(self.schema_version)
        for highlight in self.all_highlights():
            validate_highlight(highlight)
        _check_marks_are_backed(self)

    def all_highlights(self) -> tuple[str, ...]:
        return (
            *(h for g in self.given for h in g.highlights),
            *(h for s in self.solution for h in s.highlights),
            *self.figure.marks.right_angles,
        )

    def stripped(self) -> Puzzle:
        """The shipped form: build-time blocks removed (docs/02)."""
        return Puzzle(
            id=self.id,
            quantity_type=self.quantity_type,
            difficulty=self.difficulty,
            figure=self.figure,
            given=self.given,
            goal=self.goal,
            solution=self.solution,
            schema_version=self.schema_version,
        )

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "schema_version": self.schema_version,
            "quantity_type": self.quantity_type,
            "difficulty": _difficulty_json(self.difficulty),
            "figure": _figure_json(self.figure),
            "given": [_given_json(g) for g in self.given],
            "goal": _goal_json(self.goal),
            "solution": [_step_json(s) for s in self.solution],
        }
        if self.configuration:
            out["configuration"] = list(self.configuration)
        if self.reference_figure is not None:
            out["reference_figure"] = {
                "points": [{"id": p.id, "x": p.x, "y": p.y} for p in self.reference_figure.points]
            }
        if self.provenance is not None:
            out["provenance"] = dict(self.provenance)
        return out

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> Puzzle:
        """Parse strictly. Any deviation raises `SchemaError` — this is the schema check."""
        known = {
            "id",
            "schema_version",
            "quantity_type",
            "difficulty",
            "figure",
            "given",
            "goal",
            "solution",
            "configuration",
            "reference_figure",
            "provenance",
        }
        _reject_unknown(raw, known, "puzzle")
        version = _require(raw, "schema_version", str, "puzzle")
        _check_major(version)
        reference = raw.get("reference_figure")
        return cls(
            id=_require(raw, "id", str, "puzzle"),
            schema_version=version,
            quantity_type=_require(raw, "quantity_type", str, "puzzle"),
            difficulty=_difficulty_from(_require(raw, "difficulty", dict, "puzzle")),
            figure=_figure_from(_require(raw, "figure", dict, "puzzle")),
            given=tuple(_given_from(g) for g in _require(raw, "given", list, "puzzle")),
            goal=_goal_from(_require(raw, "goal", dict, "puzzle")),
            solution=tuple(_step_from(s) for s in _require(raw, "solution", list, "puzzle")),
            configuration=tuple(raw.get("configuration", ())),
            reference_figure=_reference_from(reference) if reference is not None else None,
            provenance=raw.get("provenance"),
        )


# --------------------------------------------------------------------------------------
# Marks are claims
# --------------------------------------------------------------------------------------


def _check_marks_are_backed(puzzle: Puzzle) -> None:
    """Every mark must be backed by a stated **given**; only the `?` arc may cite the goal.

    A mark the puzzle never stated is a fact the player is shown but not told. The goal is
    deliberately not a source of backing: a goal of 90° would otherwise license drawing a
    right-angle square on the very angle being asked for, which does not mislead — it simply
    prints the answer on the figure. So the goal backs exactly one mark, its own question mark.

    Checked structurally, on the ids, rather than trusted from whoever assembled the figure.
    """
    given_kinds = {_mark_backing(g.fact) for g in puzzle.given}
    marks = puzzle.figure.marks

    if marks.equal_segments and FactKind.CONGRUENT not in given_kinds:
        raise SchemaError(f"{puzzle.id}: equal-segment ticks with no cong among the givens")
    if marks.parallel and FactKind.PARALLEL not in given_kinds:
        raise SchemaError(f"{puzzle.id}: parallel marks with no para among the givens")
    if marks.right_angles and not (
        FactKind.PERPENDICULAR in given_kinds or FactKind.CONSTANT_ANGLE in given_kinds
    ):
        raise SchemaError(f"{puzzle.id}: right-angle marks with no perp or aconst among the givens")

    goal_at = _same_angle_key(puzzle.goal.quantity.at)
    for arc in marks.angle_arcs:
        if arc.kind != "goal" and _same_angle_key(arc.at) == goal_at is not None:
            raise SchemaError(
                f"{puzzle.id}: a given angle arc is drawn on the goal angle {arc.at}, "
                "which states the answer on the figure"
            )
    for right in marks.right_angles:
        if _same_angle_key(tuple(right.split(":")[1:])) == goal_at is not None:
            raise SchemaError(
                f"{puzzle.id}: a right-angle square is drawn on the goal angle, "
                "which states the answer on the figure"
            )

    n_given_arcs = sum(1 for a in marks.angle_arcs if a.kind == "given")
    n_valued = sum(
        1 for g in puzzle.given if g.fact.startswith(f"{FactKind.CONSTANT_ANGLE.value}:")
    )
    if n_given_arcs > n_valued:
        raise SchemaError(
            f"{puzzle.id}: {n_given_arcs} given angle arcs but only {n_valued} valued angle givens"
        )


def _same_angle_key(at: Sequence[str]) -> tuple[str, frozenset[str]] | None:
    """Identity of a vertex angle: ∠PVQ and ∠QVP are one angle, ∠PVQ and ∠VPQ are two.

    Comparing the three labels as a plain set would conflate the second pair — same points,
    different vertex, different angle — so the vertex is compared on its own.
    """
    if len(at) != 3:
        return None
    return at[1], frozenset({at[0], at[2]})


def _mark_backing(fact_id: str) -> FactKind | None:
    head = fact_id.split(":", 1)[0]
    try:
        return FactKind(head)
    except ValueError:
        return None


#: Which mark a stated fact kind may produce (docs/02, docs/06 §6.2).
#: Kinds absent from this table state nothing visual — `coll` is conveyed by the drawing
#: itself, and `cyclic` by the circle rather than by a mark.
MARK_FOR_KIND: Mapping[FactKind, str] = {
    FactKind.CONGRUENT: "equal_segments",
    FactKind.PARALLEL: "parallel",
    FactKind.PERPENDICULAR: "right_angles",
    FactKind.CONSTANT_ANGLE: "angle_arcs",
}


def is_right_angle(fact: Fact) -> bool:
    """A 90° `aconst` draws a square, not an arc labelled `90°`."""
    return fact.kind is FactKind.CONSTANT_ANGLE and fact.value == Fraction(1, 2)


# --------------------------------------------------------------------------------------
# JSON helpers
# --------------------------------------------------------------------------------------


def _check_major(version: str) -> None:
    major = version.split(".", 1)[0]
    if major != SCHEMA_VERSION.split(".", 1)[0]:
        raise SchemaError(
            f"schema_version {version!r}: this build reads major "
            f"{SCHEMA_VERSION.split('.', 1)[0]} only"
        )


def _reject_unknown(raw: Mapping[str, Any], known: set[str], where: str) -> None:
    unknown = sorted(set(raw) - known)
    if unknown:
        raise SchemaError(f"unknown {where} key(s): {unknown}")


def _require(raw: Mapping[str, Any], key: str, kind: type, where: str) -> Any:
    if key not in raw:
        raise SchemaError(f"{where} is missing required key {key!r}")
    value = raw[key]
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, kind):
        raise SchemaError(f"{where}.{key} should be {kind.__name__}, got {type(value).__name__}")
    return value


def _round(value: float) -> float:
    """Display coordinates are rounded at emit, so the JSON is the artifact, not a view of it."""
    return round(value, SCHEMA.coordinate_decimals)


def _approx(value: float) -> float:
    return round(value, SCHEMA.approx_decimals)


def _difficulty_json(d: Difficulty) -> dict[str, Any]:
    out: dict[str, Any] = {
        "band": d.band,
        "depth": d.depth,
        "distinct_rules": d.distinct_rules,
    }
    if d.score is not None:
        out["score"] = d.score
    return out


def _difficulty_from(raw: Mapping[str, Any]) -> Difficulty:
    _reject_unknown(raw, {"band", "depth", "distinct_rules", "score"}, "difficulty")
    return Difficulty(
        band=_require(raw, "band", str, "difficulty"),
        depth=_require(raw, "depth", int, "difficulty"),
        distinct_rules=_require(raw, "distinct_rules", int, "difficulty"),
        score=raw.get("score"),
    )


def _figure_json(f: Figure) -> dict[str, Any]:
    return {
        "points": [
            {
                "id": p.id,
                "x": _round(p.x),
                "y": _round(p.y),
                "label_dx": _round(p.label_dx),
                "label_dy": _round(p.label_dy),
            }
            for p in f.points
        ],
        "segments": [list(s) for s in f.segments],
        "circles": [
            {
                "id": c.id,
                "cx": _round(c.cx),
                "cy": _round(c.cy),
                "r": _round(c.r),
                "center_point": c.center_point,
                "through": list(c.through),
            }
            for c in f.circles
        ],
        "regions": [],
        "marks": {
            "equal_segments": [list(g) for g in f.marks.equal_segments],
            "parallel": [list(g) for g in f.marks.parallel],
            "right_angles": list(f.marks.right_angles),
            "angle_arcs": [
                {"at": list(a.at), "label": a.label, "kind": a.kind} for a in f.marks.angle_arcs
            ],
            "length_labels": [list(pair) for pair in f.marks.length_labels],
        },
    }


def _figure_from(raw: Mapping[str, Any]) -> Figure:
    _reject_unknown(raw, {"points", "segments", "circles", "regions", "marks"}, "figure")
    points = tuple(
        DisplayPoint(
            id=_require(p, "id", str, "figure.points"),
            x=_require(p, "x", float, "figure.points"),
            y=_require(p, "y", float, "figure.points"),
            label_dx=p.get("label_dx", 0.0),
            label_dy=p.get("label_dy", 0.0),
        )
        for p in _require(raw, "points", list, "figure")
    )
    circles = tuple(
        DisplayCircle(
            id=_require(c, "id", str, "figure.circles"),
            cx=_require(c, "cx", float, "figure.circles"),
            cy=_require(c, "cy", float, "figure.circles"),
            r=_require(c, "r", float, "figure.circles"),
            center_point=c.get("center_point"),
            through=tuple(c.get("through", ())),
        )
        for c in raw.get("circles", ())
    )
    return Figure(
        points=points,
        segments=tuple(_pair(s) for s in raw.get("segments", ())),
        circles=circles,
        marks=_marks_from(raw.get("marks", {})),
    )


def _pair(raw: Any) -> tuple[str, str]:
    """A two-element list of strings, refused if it is anything else."""
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        raise SchemaError(f"expected a pair, got {raw!r}")
    first, second = raw
    if not isinstance(first, str) or not isinstance(second, str):
        raise SchemaError(f"expected a pair of strings, got {raw!r}")
    return first, second


def _marks_from(raw: Mapping[str, Any]) -> Marks:
    _reject_unknown(
        raw,
        {"equal_segments", "parallel", "right_angles", "angle_arcs", "length_labels"},
        "figure.marks",
    )
    arcs = tuple(
        AngleArc(
            at=(a["at"][0], a["at"][1], a["at"][2]),
            label=_require(a, "label", str, "figure.marks.angle_arcs"),
            kind=a.get("kind", "given"),
        )
        for a in raw.get("angle_arcs", ())
    )
    return Marks(
        equal_segments=tuple(tuple(g) for g in raw.get("equal_segments", ())),
        parallel=tuple(tuple(g) for g in raw.get("parallel", ())),
        right_angles=tuple(raw.get("right_angles", ())),
        angle_arcs=arcs,
        length_labels=tuple(_pair(p) for p in raw.get("length_labels", ())),
    )


def _quantity_json(q: Quantity) -> dict[str, Any]:
    return {"kind": q.kind, "at": list(q.at)}


def _quantity_from(raw: Mapping[str, Any]) -> Quantity:
    _reject_unknown(raw, {"kind", "at"}, "quantity")
    return Quantity(kind=_require(raw, "kind", str, "quantity"), at=tuple(raw.get("at", ())))


def _value_json(v: ExactValue) -> dict[str, Any]:
    return {"exact": v.exact, "approx": _approx(v.approx)}


def _value_from(raw: Mapping[str, Any], where: str) -> ExactValue:
    _reject_unknown(raw, {"exact", "approx", "display"}, where)
    exact = _require(raw, "exact", str, where)
    parse_exact(exact)
    return ExactValue(exact=exact, approx=_require(raw, "approx", float, where))


def _given_json(g: Given) -> dict[str, Any]:
    out: dict[str, Any] = {
        "form": g.form,
        "fact": g.fact,
        "display": g.display,
        "highlights": list(g.highlights),
    }
    if g.quantity is not None:
        out["quantity"] = _quantity_json(g.quantity)
    if g.value is not None:
        out["value"] = _value_json(g.value)
    return out


def _given_from(raw: Mapping[str, Any]) -> Given:
    _reject_unknown(raw, {"form", "fact", "display", "highlights", "quantity", "value"}, "given")
    quantity = raw.get("quantity")
    value = raw.get("value")
    return Given(
        form=_require(raw, "form", str, "given"),
        fact=_require(raw, "fact", str, "given"),
        display=_require(raw, "display", str, "given"),
        highlights=tuple(raw.get("highlights", ())),
        quantity=_quantity_from(quantity) if quantity is not None else None,
        value=_value_from(value, "given.value") if value is not None else None,
    )


def _goal_json(g: Goal) -> dict[str, Any]:
    return {
        "fact": g.fact,
        "question": g.question,
        "quantity": _quantity_json(g.quantity),
        "answer": {**_value_json(g.answer), "display": g.display},
        "input": {
            "mode": g.input.mode,
            "exactness": g.input.exactness,
            "unit": g.input.unit,
            "tolerance": g.input.tolerance,
        },
    }


def _goal_from(raw: Mapping[str, Any]) -> Goal:
    _reject_unknown(raw, {"fact", "question", "quantity", "answer", "input"}, "goal")
    answer = _require(raw, "answer", dict, "goal")
    inp = _require(raw, "input", dict, "goal")
    _reject_unknown(inp, {"mode", "exactness", "unit", "tolerance"}, "goal.input")
    return Goal(
        fact=_require(raw, "fact", str, "goal"),
        question=_require(raw, "question", str, "goal"),
        quantity=_quantity_from(_require(raw, "quantity", dict, "goal")),
        answer=_value_from(answer, "goal.answer"),
        display=_require(answer, "display", str, "goal.answer"),
        input=GoalInput(
            mode=_require(inp, "mode", str, "goal.input"),
            exactness=_require(inp, "exactness", str, "goal.input"),
            unit=_require(inp, "unit", str, "goal.input"),
            tolerance=inp.get("tolerance"),
        ),
    )


def _step_json(s: Step) -> dict[str, Any]:
    return {
        "step": s.step,
        "rule": s.rule,
        "text": s.text,
        "derives": s.derives,
        "highlights": list(s.highlights),
    }


def _step_from(raw: Mapping[str, Any]) -> Step:
    _reject_unknown(raw, {"step", "rule", "text", "derives", "highlights"}, "solution step")
    return Step(
        step=_require(raw, "step", int, "solution step"),
        rule=_require(raw, "rule", str, "solution step"),
        text=_require(raw, "text", str, "solution step"),
        derives=_require(raw, "derives", str, "solution step"),
        highlights=tuple(raw.get("highlights", ())),
    )


def _reference_from(raw: Mapping[str, Any]) -> ReferenceFigure:
    _reject_unknown(raw, {"points"}, "reference_figure")
    return ReferenceFigure(
        points=tuple(
            ReferencePoint(
                id=_require(p, "id", str, "reference_figure.points"),
                x=_require(p, "x", float, "reference_figure.points"),
                y=_require(p, "y", float, "reference_figure.points"),
            )
            for p in _require(raw, "points", list, "reference_figure")
        )
    )


def circle_through(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> tuple[float, float, float] | None:
    """Centre and radius of the circle through three points, or None if they are collinear.

    Numeric, and deliberately so: the circle's *existence* was proved symbolically (a `cyclic`
    fact), and this only recovers where to draw it. Numerics verify and render; they never
    decide that a circle is there (docs/02 invariant 4).
    """
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    sa, sb, sc = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (sa * (by - cy) + sb * (cy - ay) + sc * (ay - by)) / d
    uy = (sa * (cx - bx) + sb * (ax - cx) + sc * (bx - ax)) / d
    return ux, uy, math.hypot(ax - ux, ay - uy)
