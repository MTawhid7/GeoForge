"""The rule whitelist and the string table (docs/03 §3.5 item 1, docs/02 localization).

Mostly consistency checks between two tables that must not drift apart. They are cheap and they
catch the failure that would otherwise reach a player: a template id with no sentence behind it,
which raises at bank-build time rather than at review time.
"""

from __future__ import annotations

from geoforge.generator.translation.strings import EN
from geoforge.generator.translation.templates import (
    PAIRED_TEMPLATES,
    SUPPRESSED,
    TEMPLATES,
    template_for,
)


class TestTablesAgree:
    def test_every_template_has_a_string(self) -> None:
        for rule_id, template in TEMPLATES.items():
            assert template.template_id in EN, (
                f"rule {rule_id} maps to template {template.template_id!r}, which has no text"
            )

    def test_ar_templates_exist(self) -> None:
        """Algebraic steps are narrated by these two, not by a rule id."""
        assert "combine" in EN
        assert "restate" in EN

    def test_every_string_uses_only_known_placeholders(self) -> None:
        for template_id, text in EN.items():
            rendered = text.format(premises="P", conclusion="C")
            assert "{" not in rendered, f"{template_id} left a placeholder unfilled"

    def test_no_rule_is_both_translated_and_suppressed(self) -> None:
        assert not set(TEMPLATES) & set(SUPPRESSED)

    def test_suppression_is_justified_in_writing(self) -> None:
        """Hiding a correct step from the player needs a reason on record, not a bare set."""
        for rule_id, reason in SUPPRESSED.items():
            assert len(reason) > 40, f"{rule_id} is suppressed without an explanation"


class TestDirectAndReversePairs:
    """Both orientations of a paired theorem must be whitelisted, or half its puzzles die.

    r78 ("Properties of congruent triangles (Reverse)") was missing while r77 (Direct) was
    present, and the only symptom was two `unknown_rule` discards after the Phase 2 sampler
    change moved the corpus. This test states the invariant so the next missing half fails a
    test run instead of waiting for a corpus that happens to traverse a triangle the other way.
    """

    def test_paired_templates_have_both_orientations(self) -> None:
        for template_id in PAIRED_TEMPLATES:
            rules = sorted(r for r, t in TEMPLATES.items() if t.template_id == template_id)
            assert len(rules) == 2, (
                f"{template_id} is reached by {rules}; a paired theorem needs its Direct and "
                "Reverse rules both whitelisted"
            )

    def test_pair_list_names_only_real_templates(self) -> None:
        known = {t.template_id for t in TEMPLATES.values()}
        assert known >= PAIRED_TEMPLATES


class TestLookup:
    def test_known_rule_resolves(self) -> None:
        template = template_for("r13")
        assert template is not None
        assert template.template_id == "isosceles_base_angles"

    def test_unknown_rule_returns_none(self) -> None:
        """Which fails the gate. There is deliberately no catch-all: a rule nobody has read is a
        rule nobody can vouch for the prose of."""
        assert template_for("r99") is None
        assert template_for(None) is None


class TestQuantityFamilies:
    def test_every_template_declares_its_quantity_family(self) -> None:
        """docs/04 §QTR: enabling a quantity type requires its template family to exist."""
        for template in TEMPLATES.values():
            assert template.quantity_family == "angle", (
                "Phase 1 registers the angle family only; a new family arrives with its type"
            )
