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
    tier: int
    """Conceptual weight, 1-4 (docs/05 §5.1 `tier_max`/`tier_mix`). Assigned here rather than
    read off the engine, because the engine has no notion of which of its rules feels hard —
    docs/05 says tiers are ours. 1 restatement · 2 elementary triangle/angle · 3 similarity and
    congruence · 4 circle theorems."""


#: engine rule id → template. Rule names in comments are the engine's own descriptions.
TEMPLATES: dict[str, Template] = {
    # --- triangles -------------------------------------------------------------------
    "r13": Template("isosceles_base_angles", "angle", 2),  # Isosceles triangle equal angles
    "r14": Template("equal_base_angles_isosceles", "angle", 2),  # Equal base angles imply isosceles
    "r52": Template("similar_triangles_properties", "angle", 3),  # Properties of similar (Direct)
    "r53": Template("similar_triangles_properties", "angle", 3),  # Properties of similar (Reverse)
    "r34": Template("aa_similarity", "angle", 3),  # AA Similarity (Direct)
    "r35": Template("aa_similarity", "angle", 3),  # AA Similarity (Reverse)
    "r60": Template("sss_similarity", "angle", 3),  # SSS Similarity (Direct)
    "r61": Template("sss_similarity", "angle", 3),  # SSS Similarity (Reverse)
    "r62": Template("sas_similarity", "angle", 3),  # SAS Similarity (Direct)
    "r63": Template("sas_similarity", "angle", 3),  # SAS Similarity (Reverse)
    # Properties of congruent triangles, Direct then Reverse.
    "r77": Template("congruent_triangles_properties", "angle", 3),
    "r78": Template("congruent_triangles_properties", "angle", 3),
    "r11": Template("angle_bisector", "angle", 3),  # Bisector theorem I
    # --- added in M5 from the discard log, which is what it is for ---
    # --- circles ---------------------------------------------------------------------
    "r03": Template("angles_in_same_arc", "angle", 4),  # Arc determines internal angles
    "r04": Template("equal_angles_imply_cyclic", "angle", 4),  # Congruent angles are in a cyclic
    "r72": Template("circle_radii_equal", "angle", 4),  # Disassembling a circle
    "r19": Template("thales_semicircle", "angle", 4),  # Hypotenuse is diameter
    # --- segments --------------------------------------------------------------------
    "r51": Template("midpoint_halves", "angle", 1),  # Midpoint splits in two
    "r54": Template("midpoint_definition", "angle", 1),  # Definition of midpoint
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


#: Templates the engine reaches through a *pair* of rules, one per triangle orientation
#: ("Direct" and "Reverse"). The two rules differ only in the orientation of the matched
#: triangles, so they say the same sentence — but covering one and not the other means every
#: puzzle whose figure happens to be traversed the other way is discarded as untranslatable,
#: with nothing but a discard-log line to say why. Pinned by `TestDirectAndReversePairs`.
PAIRED_TEMPLATES: frozenset[str] = frozenset(
    {
        "similar_triangles_properties",
        "congruent_triangles_properties",
        "aa_similarity",
        "sss_similarity",
        "sas_similarity",
    }
)


#: Templates the *algebraic* path produces, with their tiers. These have no engine rule id —
#: `translate` names an AR step `restate` or `combine` by its premise count — so they cannot
#: live in `TEMPLATES`, and a tier table keyed only on `TEMPLATES` would silently score them
#: as tier 0. Measured over 1,200 constructions at seed 42: `combine` appears in **118 of 118**
#: formed puzzles, so this is not an edge case, it is most of every solution.
AR_TEMPLATES: dict[str, int] = {"restate": 1, "combine": 2}

#: Template ids that are algebra rather than geometry. Kept explicit because docs/05 §5.2's
#: monotony filter has to exclude them: a rule present in every single puzzle measures how
#: often the engine did arithmetic, not whether the solution is repetitive.
ALGEBRAIC: frozenset[str] = frozenset(AR_TEMPLATES)


def template_for(rule_id: str | None) -> Template | None:
    return TEMPLATES.get(rule_id) if rule_id else None


def tier_for(template_id: str) -> int:
    """Conceptual tier of a published step's template (docs/05 §5.1).

    Raises rather than defaulting: a template with no tier would score as the easiest thing in
    the table, so the puzzle using it would be quietly under-banded. `TestEveryTemplateHasATier`
    makes adding one without a tier fail a test run instead.
    """
    for template in TEMPLATES.values():
        if template.template_id == template_id:
            return template.tier
    if template_id in AR_TEMPLATES:
        return AR_TEMPLATES[template_id]
    raise KeyError(f"template {template_id!r} has no tier (docs/05 §5.1)")


def is_geometric(template_id: str) -> bool:
    return template_id not in ALGEBRAIC


def is_suppressed(rule_id: str | None) -> bool:
    return bool(rule_id) and rule_id in SUPPRESSED
