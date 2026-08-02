"""The rule whitelist: engine rule id → readable template (docs/03 §3.5 item 1).

A rule is translatable only if it is listed here. Anything else makes its puzzle untranslatable and
therefore discarded, with the offending rule logged — **the discard log is the priority queue for
extending this table** (docs/03 §3.5 item 3). Coverage grows deliberately; it is never widened by a
generic catch-all, because a rule nobody has read is a rule nobody can vouch for the prose of.

Sizing, measured rather than guessed. Phase 0 saw 13 distinct rules fire across its corpus; over 300
sampled constructions in M4, 12 rules account for **every** rule step of every formed puzzle. The
table covers both sets, so rule-step coverage starts at 100% on current output and the gate's real
work is the AR budget.

Three rules are **suppressed** rather than translated. They are engine bookkeeping whose prose would
confuse rather than help — see `SUPPRESSED`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Template:
    """How one engine rule becomes a sentence."""

    template_id: str
    """Public API: appears in puzzle JSON as `solution[].rule` (CLAUDE.md). Renaming = schema
    change."""
    quantity_family: str
    """Which quantity type's template family this belongs to (docs/04 §QTR). Enabling a new
    quantity type requires its family to exist here."""


#: engine rule id → template. Rule names in comments are the engine's own descriptions.
TEMPLATES: dict[str, Template] = {
    # --- triangles -------------------------------------------------------------------
    "r13": Template("isosceles_base_angles", "angle"),  # Isosceles triangle equal angles
    "r14": Template("equal_base_angles_isosceles", "angle"),  # Equal base angles imply isosceles
    "r52": Template("similar_triangles_properties", "angle"),  # Properties of similar (Direct)
    "r53": Template("similar_triangles_properties", "angle"),  # Properties of similar (Reverse)
    "r34": Template("aa_similarity", "angle"),  # AA Similarity (Direct)
    "r35": Template("aa_similarity", "angle"),  # AA Similarity (Reverse)
    "r60": Template("sss_similarity", "angle"),  # SSS Similarity (Direct)
    "r61": Template("sss_similarity", "angle"),  # SSS Similarity (Reverse)
    "r62": Template("sas_similarity", "angle"),  # SAS Similarity (Direct)
    "r63": Template("sas_similarity", "angle"),  # SAS Similarity (Reverse)
    # --- circles ---------------------------------------------------------------------
    "r03": Template("angles_in_same_arc", "angle"),  # Arc determines internal angles
    "r04": Template("equal_angles_imply_cyclic", "angle"),  # Congruent angles are in a cyclic
    "r72": Template("circle_radii_equal", "angle"),  # Disassembling a circle
    # --- segments --------------------------------------------------------------------
    "r51": Template("midpoint_halves", "angle"),  # Midpoint splits in two
}

#: Rules whose steps are correct but must not appear in player text.
#:
#: These are not failures — a suppressed step is dropped from the solution and its conclusion is
#: simply used by later steps. Suppression is deliberate and narrow; the default for an unknown
#: rule is to fail the gate, not to hide the step.
SUPPRESSED: dict[str, str] = {
    "r82": (
        "'Parallel from collinear' reports two segments of one straight line as parallel. True "
        "for the engine's line algebra, and reads as an error to a player looking at three "
        "collinear points."
    ),
    "r56": (
        "'Properties of midpoint (coll)' concludes that a midpoint lies on its own segment. "
        "Restating the definition is not a solution step."
    ),
}


def template_for(rule_id: str | None) -> Template | None:
    return TEMPLATES.get(rule_id) if rule_id else None


def is_suppressed(rule_id: str | None) -> bool:
    return bool(rule_id) and rule_id in SUPPRESSED
