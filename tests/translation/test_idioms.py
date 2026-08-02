"""Idiom collapsing (docs/03 §3.5 item 2b).

Engine-free: hand-built DAGs put the exact idiom shapes in front of the collapser, which is the
only way to assert both that it fires on scaffolding and that it leaves real reasoning alone.
"""

from __future__ import annotations

from fractions import Fraction

from geoforge.generator.translation.idioms import (
    find_collapses,
    is_degenerate_pair,
    is_scaffolding,
    is_self_similarity,
)
from geoforge.solvers.types import Fact, FactKind, Justification, JustificationKind, ProofStep

AR = Justification(kind=JustificationKind.AR_DEDUCTION, ar_reason="Ratio Chasing")
SAS = Justification(
    kind=JustificationKind.RULE_APPLICATION,
    rule_id="r63",
    rule_name="SAS Similarity of triangles (Reverse)",
)
PROPS = Justification(
    kind=JustificationKind.RULE_APPLICATION,
    rule_id="r53",
    rule_name="Properties of similar triangles (Reverse)",
)


class TestDetection:
    def test_triangle_similar_to_itself(self) -> None:
        fact = Fact(kind=FactKind.SIMTRI_REFLECT, args=("a", "c", "o", "c", "a", "o"))
        assert is_self_similarity(fact)

    def test_genuine_similarity_is_not_an_idiom(self) -> None:
        fact = Fact(kind=FactKind.SIMTRI_REFLECT, args=("a", "b", "c", "d", "e", "f"))
        assert not is_self_similarity(fact)
        assert not is_scaffolding(fact)

    def test_reciprocal_ratio(self) -> None:
        """AO:CO = CO:AO says only that the ratio is 1."""
        assert is_degenerate_pair(
            Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "o", "c", "o", "c", "o", "a", "o"))
        )

    def test_unit_ratio(self) -> None:
        """AJ:AJ = HJ:IJ is HJ = IJ dressed up as a ratio."""
        assert is_degenerate_pair(
            Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "j", "a", "j", "h", "j", "i", "j"))
        )

    def test_self_restatement(self) -> None:
        assert is_degenerate_pair(
            Fact(kind=FactKind.EQUAL_ANGLES, args=("a", "o", "c", "o", "a", "o", "c", "o"))
        )

    def test_ordinary_equal_ratios_survive(self) -> None:
        assert not is_degenerate_pair(
            Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "b", "c", "d", "e", "f", "g", "h"))
        )


# --------------------------------------------------------------------------------------
# The isosceles-via-self-similarity idiom, exactly as the engine emits it
# --------------------------------------------------------------------------------------

CONG = Fact(kind=FactKind.CONGRUENT, args=("a", "o", "c", "o"))
RECIPROCAL = Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "o", "c", "o", "c", "o", "a", "o"))
SELF_SIMILAR = Fact(kind=FactKind.SIMTRI_REFLECT, args=("a", "c", "o", "c", "a", "o"))
SAMECLOCK = Fact(kind=FactKind.SAME_CLOCK, args=("a", "c", "o", "a", "c", "o"))
BASE_ANGLES = Fact(kind=FactKind.EQUAL_ANGLES, args=("a", "c", "a", "o", "c", "o", "a", "c"))

FACTS = {f.fact_id: f for f in (CONG, RECIPROCAL, SELF_SIMILAR, SAMECLOCK, BASE_ANGLES)}

STEPS = (
    ProofStep(conclusion=RECIPROCAL.fact_id, premises=(CONG.fact_id,), justification=AR),
    ProofStep(
        conclusion=SELF_SIMILAR.fact_id,
        premises=(RECIPROCAL.fact_id, SAMECLOCK.fact_id),
        justification=SAS,
    ),
    ProofStep(
        conclusion=BASE_ANGLES.fact_id,
        premises=(SELF_SIMILAR.fact_id, SAMECLOCK.fact_id),
        justification=PROPS,
    ),
)


class TestSelfSimilarityCollapse:
    def test_three_steps_become_one(self) -> None:
        collapses = find_collapses(STEPS, FACTS)
        anchored = {c.anchor: c for c in collapses}
        assert BASE_ANGLES.fact_id in anchored
        collapse = anchored[BASE_ANGLES.fact_id]
        assert RECIPROCAL.fact_id in collapse.absorbed
        assert SELF_SIMILAR.fact_id in collapse.absorbed

    def test_the_collapsed_step_cites_the_equal_sides(self) -> None:
        """The idiom's real input is OA = OC — that is the sentence a human writes."""
        collapse = next(c for c in find_collapses(STEPS, FACTS) if c.anchor == BASE_ANGLES.fact_id)
        assert CONG in collapse.premises

    def test_configuration_facts_are_not_cited(self) -> None:
        collapse = next(c for c in find_collapses(STEPS, FACTS) if c.anchor == BASE_ANGLES.fact_id)
        assert all(not f.is_configuration for f in collapse.premises)

    def test_a_ratio_conclusion_keeps_the_similarity_template(self) -> None:
        """`r53` reads *several* consequences out of one similarity — three angle equalities and
        two ratio equalities. Only the angle ones are the isosceles theorem; applying that
        template to a ratio produces "the base angles are equal: AC : AD = AD : CD".
        """
        ratio = Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "c", "a", "d", "a", "d", "c", "d"))
        facts = {**FACTS, ratio.fact_id: ratio}
        steps = (
            *STEPS,
            ProofStep(
                conclusion=ratio.fact_id,
                premises=(SELF_SIMILAR.fact_id, SAMECLOCK.fact_id),
                justification=PROPS,
            ),
        )
        collapse = next(c for c in find_collapses(steps, facts) if c.anchor == ratio.fact_id)
        assert collapse.template_id is None

    def test_the_template_becomes_the_isosceles_theorem(self) -> None:
        """Reading equal angles out of a triangle-similar-to-itself *is* the isosceles theorem,
        which the engine has its own rule for (r13). The collapse rewrites the long route into
        the short route's template rather than inventing one."""
        collapse = next(c for c in find_collapses(STEPS, FACTS) if c.anchor == BASE_ANGLES.fact_id)
        assert collapse.template_id == "isosceles_base_angles"


class TestSharedSideCollapse:
    """The unit-ratio idiom: two triangles sharing a side."""

    def test_similarity_keeps_its_own_template(self) -> None:
        cong = Fact(kind=FactKind.CONGRUENT, args=("i", "j", "h", "j"))
        unit = Fact(kind=FactKind.EQUAL_RATIOS, args=("a", "j", "a", "j", "h", "j", "i", "j"))
        angles = Fact(kind=FactKind.EQUAL_ANGLES, args=("j", "a", "j", "h", "j", "i", "j", "a"))
        similar = Fact(kind=FactKind.SIMTRI_REFLECT, args=("a", "h", "j", "a", "i", "j"))
        facts = {f.fact_id: f for f in (cong, unit, angles, similar)}
        steps = (
            ProofStep(conclusion=unit.fact_id, premises=(cong.fact_id,), justification=AR),
            ProofStep(
                conclusion=similar.fact_id,
                premises=(unit.fact_id, angles.fact_id),
                justification=SAS,
            ),
        )
        collapse = next(c for c in find_collapses(steps, facts) if c.anchor == similar.fact_id)
        assert collapse.template_id is None, "a shared-side similarity is still a similarity"
        assert cong in collapse.premises
        assert angles in collapse.premises, "non-scaffolding premises must survive untouched"


class TestNoFalsePositives:
    def test_a_proof_without_idioms_is_left_alone(self) -> None:
        premise = Fact(kind=FactKind.CONGRUENT, args=("a", "b", "c", "d"))
        goal = Fact(kind=FactKind.CONSTANT_ANGLE, args=("a", "b", "a", "c"), value=Fraction(1, 3))
        facts = {f.fact_id: f for f in (premise, goal)}
        steps = (
            ProofStep(conclusion=goal.fact_id, premises=(premise.fact_id,), justification=PROPS),
        )
        assert find_collapses(steps, facts) == ()

    def test_undervied_scaffolding_absorbs_nothing(self) -> None:
        """Scaffolding that is a premise rather than a conclusion has no derivation behind it,
        so there is no step to suppress — marking one absorbed would delete a step that never
        existed."""
        facts = {f.fact_id: f for f in (SELF_SIMILAR, SAMECLOCK, BASE_ANGLES)}
        steps = (
            ProofStep(
                conclusion=BASE_ANGLES.fact_id,
                premises=(SELF_SIMILAR.fact_id, SAMECLOCK.fact_id),
                justification=PROPS,
            ),
        )
        collapse = next(c for c in find_collapses(steps, facts))
        assert collapse.absorbed == frozenset()
