"""Idiom collapsing (docs/03 §3.5 item 2b) — required, not an optimization.

Engine proofs contain fixed multi-step idioms that a human writes as one step. Translating them
step-for-step produces text that is correct and unreadable, so **translation is compression**: Phase
0's 10-step machine proof of Thales is a 6-step human solution here.

Both idioms we have measured share one shape: the engine manufactures a **degenerate intermediate**
— a statement that is trivially true and says nothing — purely to fit the shape of a general rule.

*Isosceles via self-similarity* (15 of 95 steps in the Phase 0 corpus, and the top two rules by
frequency over generated puzzles):

    AR (Ratio Chasing)  OA = OC                    ⟹  OA:OC = OC:OA
    r63 SAS Similarity (Reverse)                   ⟹  △OAC ≅ △OCA   (the triangle with itself)
    r53 Properties of similar triangles (Reverse)  ⟹  ∠OAC = ∠OCA

Three steps, one of which asserts a triangle is similar to itself reversed, to say: *OA = OC, so the
base angles are equal.* The engine already has a rule for exactly that — `r13 Isosceles triangle
equal angles` — and uses it when it happens to find that route first. So the collapse is not an
invention: it rewrites the long route into the short route's own template.

*Unit-ratio restatement*, for two triangles sharing a side:

    AR (Ratio Chasing)  HJ = IJ                    ⟹  AJ:AJ = HJ:IJ
    r63 SAS Similarity                             ⟹  △AHJ ≅ △AIJ

`AJ:AJ` is 1. The first step dresses a plain equality up as a ratio nobody would write, so the
similarity step should simply cite the equality.

The general treatment: a **scaffolding** fact is one no human would state. Any step consuming one
absorbs the derivation behind it and cites that derivation's real inputs instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoforge.solvers.types import Fact, FactId, FactKind, ProofStep

_SIMILARITY_KINDS = frozenset(
    {
        FactKind.SIMTRI_CLOCK,
        FactKind.SIMTRI_REFLECT,
        FactKind.CONTRI_CLOCK,
        FactKind.CONTRI_REFLECT,
    }
)


def is_self_similarity(fact: Fact) -> bool:
    """`simtrir a c o c a o` — a triangle declared similar to itself, reordered.

    Machine-correct and meaningless to a reader: it is how the engine derives that a triangle with
    two equal sides has two equal angles.
    """
    if fact.kind not in _SIMILARITY_KINDS or len(fact.args) != 6:
        return False
    return sorted(fact.args[:3]) == sorted(fact.args[3:])


def is_degenerate_pair(fact: Fact) -> bool:
    """An equality that carries no information beyond a plain equality of two things.

    Three shapes, all of which the engine produces and no human writes:

    * `eqratio a j a j h j i j` — "AJ:AJ = HJ:IJ", i.e. HJ = IJ dressed up as a ratio.
    * `eqratio a o c o c o a o` — "AO:CO = CO:AO", a ratio equal to its own reciprocal, which
      says only that the ratio is 1, i.e. AO = CO.
    * `eqangle a o c o a o c o` — a statement restating itself.
    """
    if fact.kind not in (FactKind.EQUAL_RATIOS, FactKind.EQUAL_ANGLES) or len(fact.args) != 8:
        return False
    left, right = fact.args[:4], fact.args[4:]
    reciprocal = left[2:] + left[:2]
    return left == right or right == reciprocal or left[:2] == left[2:] or right[:2] == right[2:]


def is_scaffolding(fact: Fact) -> bool:
    """Whether a fact exists only to satisfy the shape of a rule."""
    return is_self_similarity(fact) or is_degenerate_pair(fact)


@dataclass(frozen=True, slots=True)
class Collapse:
    """One idiom occurrence: an anchor step rewritten, and the steps it swallows."""

    anchor: FactId
    """The conclusion of the step that survives, rewritten."""
    premises: tuple[Fact, ...]
    """The premises the rewritten step should cite — the idiom's real inputs."""
    absorbed: frozenset[FactId]
    """Conclusions of steps that must not be emitted at all."""
    template_id: str | None = None
    """Override for the anchor's template; None keeps the rule's own. Only the self-similarity
    idiom overrides, because only it changes *which theorem* is being applied."""


def find_collapses(steps: tuple[ProofStep, ...], facts: dict[FactId, Fact]) -> tuple[Collapse, ...]:
    """Find every idiom occurrence in a derivation."""
    by_conclusion = {step.conclusion: step for step in steps}
    scaffolding = {fid for fid, fact in facts.items() if is_scaffolding(fact)}
    if not scaffolding:
        return ()

    collapses: list[Collapse] = []
    for step in steps:
        consumed = [p for p in step.premises if p in scaffolding]
        if not consumed:
            continue

        absorbed: set[FactId] = set()
        roots: list[Fact] = []
        for premise in consumed:
            _absorb(premise, by_conclusion, scaffolding, facts, absorbed, roots)

        # Premises of the anchor that were not scaffolding stay as they were — minus the
        # configuration facts, which are never cited in a sentence (see `_absorb`).
        kept = [
            facts[p]
            for p in step.premises
            if p not in scaffolding and p in facts and not facts[p].is_configuration
        ]
        # Reading *equal angles* back out of a triangle-similar-to-itself is the isosceles
        # theorem, so the anchor's template changes. Two things must both hold:
        #   - the idiom really was the self-similarity one (a shared-side similarity is still a
        #     similarity; only its premises get tidied), and
        #   - this step concludes an angle. `r53` also emits *ratio* consequences of the same
        #     similarity, and "the base angles are equal: AC : AD = AD : CD" is nonsense.
        conclusion = facts.get(step.conclusion)
        collapsed_self_similarity = any(
            fid in facts and is_self_similarity(facts[fid]) for fid in absorbed
        )
        concludes_an_angle = conclusion is not None and conclusion.kind in (
            FactKind.EQUAL_ANGLES,
            FactKind.CONSTANT_ANGLE,
        )
        collapses.append(
            Collapse(
                anchor=step.conclusion,
                premises=tuple(sorted(set(roots) | set(kept))),
                absorbed=frozenset(absorbed),
                template_id=(
                    "isosceles_base_angles"
                    if collapsed_self_similarity and concludes_an_angle
                    else None
                ),
            )
        )
    return tuple(collapses)


def _absorb(
    fid: FactId,
    by_conclusion: dict[FactId, ProofStep],
    scaffolding: set[FactId],
    facts: dict[FactId, Fact],
    absorbed: set[FactId],
    roots: list[Fact],
) -> None:
    """Absorb the sub-derivation behind a scaffolding fact, collecting its real premises.

    Everything between the anchor and the honest facts is machinery for a claim no human makes.
    What comes out is the `cong` (or other stated) facts the idiom actually rests on, which is what
    the rewritten step cites.
    """
    if fid in absorbed:
        return
    step = by_conclusion.get(fid)
    if step is None:
        # Scaffolding nobody derived: it is a premise of the puzzle, and an unspeakable one.
        # Dropping it from the text is right, but it must not be marked absorbed — no step
        # produced it, so there is nothing to suppress.
        return
    absorbed.add(fid)
    for premise in step.premises:
        fact = facts.get(premise)
        if fact is None:
            continue
        if premise in scaffolding:
            _absorb(premise, by_conclusion, scaffolding, facts, absorbed, roots)
        elif fact.is_configuration:
            continue  # holds the configuration fixed; not something to say out loud
        else:
            roots.append(fact)
