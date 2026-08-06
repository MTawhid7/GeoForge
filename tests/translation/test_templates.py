"""The rule whitelist and the string table (docs/03 §3.5 item 1, docs/02 localization).

Mostly consistency checks between two tables that must not drift apart. They are cheap and they
catch the failure that would otherwise reach a player: a template id with no sentence behind it,
which raises at bank-build time rather than at review time.
"""

from __future__ import annotations

import pytest

from geoforge.generator.translation.strings import EN
from geoforge.generator.translation.templates import (
    ALGEBRAIC,
    AR_TEMPLATES,
    PAIRED_TEMPLATES,
    SUPPRESSED,
    TEMPLATES,
    is_geometric,
    template_for,
    tier_for,
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
    def test_every_template_declares_a_registered_quantity_family(self) -> None:
        """docs/04 §QTR: enabling a quantity type requires its template family to exist."""
        from geoforge.generator.quantities import registry

        families = {t.template_family for t in registry().values()}
        assert families == {"angle", "area"}
        for template in TEMPLATES.values():
            assert template.quantity_family in families, (
                f"{template.template_id!r} declares family {template.quantity_family!r}, "
                "which no registered quantity type claims"
            )

    def test_every_registered_family_has_at_least_one_template(self) -> None:
        """The other direction, and the one that actually bites: a type registered without a
        template family reaches Stage 7 and is discarded as `unknown_rule` on every puzzle it
        produces — attrition that looks like a hard corpus rather than a missing table."""
        covered = {t.quantity_family for t in TEMPLATES.values()}
        from geoforge.generator.quantities import registry

        for quantity_type in registry().values():
            assert quantity_type.template_family in covered, (
                f"quantity type {quantity_type.name!r} has no templates"
            )


class TestAreaRoutes:
    """The area layer names its own steps, so the whitelist is keyed by route (docs/10 A4).

    No engine rule fires for an area — there is no area predicate — so `area.proof_dag` supplies
    the `rule_id` itself. These entries are what let a layer-verified quantity clear the
    readability gate that every angle puzzle already has to clear.
    """

    ROUTES = (
        "area_right_triangle",
        "area_heron",
        "area_sas",
        "area_median_split",
        "area_cevian_split",
    )

    def test_every_route_the_layer_can_emit_has_a_template(self) -> None:
        """Keyed off the layer's own table, not a copy, so a sixth route cannot be added
        without either a template or a failing test."""
        from geoforge.generator.area import _ROUTE_NAMES

        assert set(_ROUTE_NAMES) == set(self.ROUTES)
        for route in _ROUTE_NAMES:
            template = template_for(route)
            assert template is not None, f"route {route!r} would be discarded as unknown_rule"
            assert template.quantity_family == "area"

    def test_the_ratio_rules_outrank_the_direct_formulas(self) -> None:
        """The tier ordering is a claim about difficulty, so it is asserted rather than left to
        the table's reading order. Applying half-a-b-sin-C is routine; seeing that a median
        halves an area — with no length available at all — is the step that carries these
        puzzles (docs/10 §10.10c)."""
        assert tier_for("area_median_split") > tier_for("area_sas")
        assert tier_for("area_cevian_split") > tier_for("area_heron")

    def test_the_route_name_is_the_public_step_rule(self) -> None:
        """`solution[].rule` is public API (CLAUDE.md). Template id and whitelist key are the
        same string on purpose: an alias would give one step two public names."""
        for route in self.ROUTES:
            template = template_for(route)
            assert template is not None and template.template_id == route


class TestEveryTemplateHasATier:
    """docs/05 §5.1 scores `tier_max` and `tier_mix`, and tiers are assigned in our whitelist.

    A template with no tier would score as the easiest thing in the table, so its puzzle would
    be quietly under-banded — the failure is invisible in output and only shows up as a band
    distribution nobody can explain. Modelled on `test_every_template_has_a_string`, which
    exists for the same reason one layer up.
    """

    def test_every_published_template_id_has_a_tier(self) -> None:
        for template_id in EN:
            assert tier_for(template_id) in range(1, 5), template_id

    def test_the_ar_templates_are_covered_although_they_have_no_rule_id(self) -> None:
        """`combine` and `restate` are named by premise count, not by an engine rule, so a tier
        table keyed only on TEMPLATES would miss them — and `combine` appears in every single
        puzzle the pipeline makes."""
        assert set(AR_TEMPLATES) <= set(EN)
        for template_id in AR_TEMPLATES:
            assert tier_for(template_id) in range(1, 5)

    def test_an_unknown_template_raises_rather_than_defaulting(self) -> None:
        with pytest.raises(KeyError, match="no tier"):
            tier_for("not_a_template")

    def test_tiers_are_ordered_the_way_docs_05_describes(self) -> None:
        """1 restatement · 2 elementary triangle/angle · 3 similarity and congruence ·
        4 circle theorems. Spot-checked at each end so a wholesale re-tiering has to be
        deliberate."""
        assert tier_for("midpoint_definition") == 1
        assert tier_for("isosceles_base_angles") == 2
        assert tier_for("aa_similarity") == 3
        assert tier_for("thales_semicircle") == 4

    def test_algebra_is_not_geometry(self) -> None:
        """The distinction docs/05 §5.2's monotony filter turns on."""
        assert not is_geometric("combine")
        assert not is_geometric("restate")
        assert is_geometric("isosceles_base_angles")
        assert set(AR_TEMPLATES) == ALGEBRAIC
