"""Stage 7: minimal sub-DAG → `solution[]` steps, behind the readability gate.

docs/04 Stage 7, docs/03 §3.5.

The gate is the point of this module. A puzzle ships **only if every step of its minimal derivation
translates**; anything else is discarded and logged by cause. That converts the pivot's biggest risk
— machine proofs being unreadable — into attrition, never into shipped ugliness (docs/01).

Order matters as much as wording. The engine's steps arrive in canonical fact order, which is
arbitrary to a reader, so they are re-sorted into a topological order that ends at the goal: every
step is stated after the steps it rests on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoforge.config import TRANSLATION
from geoforge.generator.traceback import SubDAG
from geoforge.generator.translation import idioms, phrases, templates
from geoforge.generator.translation.strings import EN
from geoforge.generator.translation.vertex_angles import Coords
from geoforge.solvers.types import Fact, FactId, JustificationKind, ProofStep


class FailureReason(StrEnum):
    """Why a step could not be translated. The discard log is keyed on these (docs/03 §3.5)."""

    UNKNOWN_RULE = "unknown_rule"
    """The rule is not in the whitelist. Extending `templates.TEMPLATES` fixes it — this is the
    priority queue for doing so."""
    AR_CHAIN_TOO_LONG = "ar_chain_too_long"
    """An algebraic step combines more premises than `max_ar_chain`. No amount of wording makes a
    14-premise linear combination readable."""
    UNSPEAKABLE_CONCLUSION = "unspeakable_conclusion"
    """The step's conclusion has no human phrasing — most often an angle between two lines that do
    not meet at a named point, which has no ∠ABC spelling."""
    NO_PREMISES_TO_CITE = "no_premises_to_cite"
    """Every premise was unspeakable, leaving a sentence with nothing to stand on."""


@dataclass(frozen=True, slots=True)
class SolutionStep:
    """One player-facing step, matching the `solution[]` schema of docs/02."""

    step: int
    rule: str
    """Template id. Public API (CLAUDE.md)."""
    text: str
    derives: FactId
    highlights: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Failure:
    reason: FailureReason
    detail: str
    """Rule id or fact id, whichever identifies the offender for the discard log."""


@dataclass(frozen=True, slots=True)
class Translation:
    steps: tuple[SolutionStep, ...]
    failures: tuple[Failure, ...]
    suppressed: int
    """Steps deliberately not shown (engine bookkeeping). Not failures."""

    @property
    def ok(self) -> bool:
        """Whether the puzzle may ship (docs/03 §3.5 item 3)."""
        if TRANSLATION.require_full_translation and self.failures:
            return False
        return bool(self.steps)

    def highlighted_points(self) -> frozenset[str]:
        """Points any step highlights, for Stage 6 figure pruning: a step may name a segment its
        premises only imply (docs/04 Stage 6)."""
        out: set[str] = set()
        for step in self.steps:
            for highlight in step.highlights:
                out.update(part.lower() for part in highlight.split(":")[1:])
        return frozenset(out)


def translate(subdag: SubDAG, coords: Coords) -> Translation:
    """Translate a minimal derivation into solution steps."""
    facts = {fact.fact_id: fact for fact in subdag.facts}
    collapses = idioms.find_collapses(subdag.steps, facts)
    absorbed = frozenset().union(*(c.absorbed for c in collapses)) if collapses else frozenset()
    rewrites = {c.anchor: c for c in collapses}

    steps: list[SolutionStep] = []
    failures: list[Failure] = []
    suppressed = 0

    for step in _in_reading_order(subdag):
        if step.conclusion in absorbed:
            continue
        if templates.is_suppressed(step.justification.rule_id):
            suppressed += 1
            continue

        rendered = _render(step, facts, coords, rewrites.get(step.conclusion))
        if isinstance(rendered, Failure):
            failures.append(rendered)
            continue
        steps.append(
            SolutionStep(
                step=len(steps) + 1,
                rule=rendered.rule,
                text=rendered.text,
                derives=rendered.derives,
                highlights=rendered.highlights,
            )
        )

    return Translation(steps=tuple(steps), failures=tuple(failures), suppressed=suppressed)


def _render(
    step: ProofStep,
    facts: dict[FactId, Fact],
    coords: Coords,
    collapse: idioms.Collapse | None,
) -> SolutionStep | Failure:
    """Render one step, or say why it cannot be."""
    conclusion = facts.get(step.conclusion)
    if conclusion is None:
        return Failure(FailureReason.UNSPEAKABLE_CONCLUSION, step.conclusion)
    conclusion_phrase = phrases.describe(conclusion, coords)
    if conclusion_phrase is None:
        return Failure(FailureReason.UNSPEAKABLE_CONCLUSION, step.conclusion)

    if collapse is not None and collapse.template_id is not None:
        # The idiom changed which theorem is being applied (self-similarity → isosceles).
        template_id = collapse.template_id
    else:
        template = _template_for(step)
        if isinstance(template, Failure):
            return template
        template_id = template

    premise_facts: tuple[Fact, ...] = (
        collapse.premises
        if collapse is not None
        else tuple(f for f in (facts.get(p) for p in step.premises) if f is not None)
    )

    premise_phrases = [
        phrase
        for phrase in (phrases.describe(fact, coords) for fact in premise_facts)
        if phrase is not None
    ]
    if not premise_phrases:
        return Failure(FailureReason.NO_PREMISES_TO_CITE, step.conclusion)

    text = EN[template_id].format(
        premises=_join(tuple(p.text for p in premise_phrases)),
        conclusion=conclusion_phrase.text,
    )
    highlights = tuple(
        dict.fromkeys(
            (
                *(h for phrase in premise_phrases for h in phrase.highlights),
                *conclusion_phrase.highlights,
            )
        )
    )
    return SolutionStep(
        step=0, rule=template_id, text=text, derives=step.conclusion, highlights=highlights
    )


def _template_for(step: ProofStep) -> str | Failure:
    """Which template narrates this step: a whitelisted rule, or an in-budget AR chain."""
    justification = step.justification
    if justification.kind is JustificationKind.AR_DEDUCTION:
        if len(step.premises) > TRANSLATION.max_ar_chain:
            return Failure(
                FailureReason.AR_CHAIN_TOO_LONG,
                f"{len(step.premises)} premises > {TRANSLATION.max_ar_chain}",
            )
        return "restate" if len(step.premises) == 1 else "combine"

    template = templates.template_for(justification.rule_id)
    if template is None:
        return Failure(
            FailureReason.UNKNOWN_RULE,
            f"{justification.rule_id} {justification.rule_name}",
        )
    return template.template_id


def _join(parts: tuple[str, ...]) -> str:
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _in_reading_order(subdag: SubDAG) -> tuple[ProofStep, ...]:
    """Topological order, ending at the goal.

    A reader needs every step's premises established before the step appears. The engine's own
    ordering is by canonical fact id, which is stable but meaningless as prose. Ties break on the
    conclusion's id so the ordering stays reproducible (docs/02 invariant 2).
    """
    by_conclusion = {step.conclusion: step for step in subdag.steps}
    ordered: list[ProofStep] = []
    seen: set[FactId] = set()

    def visit(fid: FactId, path: frozenset[FactId]) -> None:
        if fid in seen or fid in path:
            return
        step = by_conclusion.get(fid)
        if step is None:
            return
        seen.add(fid)
        for premise in sorted(step.premises):
            visit(premise, path | {fid})
        ordered.append(step)

    visit(subdag.goal, frozenset())
    # Anything the goal does not reach is not part of the solution, but emit it deterministically
    # rather than dropping it silently.
    for step in sorted(subdag.steps, key=lambda s: s.conclusion):
        visit(step.conclusion, frozenset())
    return tuple(ordered)
