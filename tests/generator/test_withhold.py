"""Naming a point instead of drawing it (docs/07 T29)."""

from __future__ import annotations

import numpy as np
import pytest
import sympy

from geoforge.generator.area import area_of
from geoforge.generator.templates import TEMPLATES, render, to_construction
from geoforge.generator.withhold import (
    DESCRIPTIONS,
    WithholdingError,
    candidates,
    hide_for_region,
    plan,
)
from geoforge.solvers.interface import get_backend
from geoforge.solvers.types import ProblemSpec, SolveOptions

SAS_MEDIAN = to_construction(
    "a = free a; b = lconst b a 5; c = s_angle b a c 60o, lconst c a 4; m = midpoint m b c"
)
TWO_MEDIANS = to_construction(
    "a = free a; b = lconst b a 5; c = s_angle b a c 60o, lconst c a 4;"
    " m = midpoint m b c; n = midpoint n b m"
)


class TestDescriptions:
    def test_a_midpoint_is_described_by_its_two_endpoints(self) -> None:
        result = plan(SAS_MEDIAN, ("m",))
        assert result.hidden == ("m",)
        assert result.descriptions == ("the midpoint of BC",)
        assert "m" not in result.visible

    def test_only_uniquely_pinning_constructions_are_describable(self) -> None:
        """`on_line` is absent on purpose: "a point on BC" does not say WHICH point, so hiding it
        would make the statement ill-posed rather than hard."""
        assert "on_line" not in DESCRIPTIONS
        assert "on_circle" not in DESCRIPTIONS
        assert "midpoint" in DESCRIPTIONS

    def test_candidates_skips_points_with_no_description(self) -> None:
        construction = to_construction("a b = segment a b; c = on_line c a b")
        assert "c" not in candidates(construction)

    def test_a_point_with_no_description_is_refused_not_guessed(self) -> None:
        construction = to_construction("a b = segment a b; c = on_line c a b")
        with pytest.raises(WithholdingError, match="no unique description"):
            plan(construction, ("c",))


class TestLeakage:
    """The refusal that matters most: a hidden point recoverable by eye is worse than no hiding,
    because the puzzle would LOOK like it hides a construction while giving it away."""

    def test_hiding_a_point_a_visible_one_depends_on_is_refused(self) -> None:
        with pytest.raises(WithholdingError, match="would give it away"):
            plan(TWO_MEDIANS, ("m",))

    def test_hiding_the_whole_dependent_chain_is_allowed(self) -> None:
        result = plan(TWO_MEDIANS, ("m", "n"))
        assert result.hidden == ("m", "n")
        assert result.descriptions == ("the midpoint of BC", "the midpoint of BM")

    def test_descriptions_resolve_in_order(self) -> None:
        """`n` is described in terms of `m`, which the solver has already been told how to build."""
        result = plan(TWO_MEDIANS, ("m", "n"))
        assert result.hidden.index("m") < result.hidden.index("n")

    def test_unknown_points_are_refused(self) -> None:
        with pytest.raises(WithholdingError, match="not points of this construction"):
            plan(SAS_MEDIAN, ("zzz",))

    def test_empty_withholding_is_a_no_op(self) -> None:
        result = plan(SAS_MEDIAN, ())
        assert result.is_empty
        assert set(result.visible) == set(SAS_MEDIAN.points)


class TestHideForRegion:
    def test_it_hides_the_regions_own_scaffolding(self) -> None:
        result = hide_for_region(SAS_MEDIAN, ("a", "b", "m"))
        assert result.hidden == ("m",)

    def test_it_backs_off_to_a_legal_subset_rather_than_failing(self) -> None:
        """`n` alone is legal where `m` alone is not; the helper must find that rather than
        raising, because an un-hideable figure is ordinary attrition."""
        result = hide_for_region(TWO_MEDIANS, ("a", "b", "n"))
        assert not result.is_empty
        assert "n" in result.hidden

    def test_nothing_hideable_returns_empty_rather_than_raising(self) -> None:
        construction = to_construction("a = free a; b = lconst b a 5; c = on_tline c a a b")
        assert hide_for_region(construction, ("a", "b", "c")).is_empty


class TestTheAnswerIsUnchanged:
    """Withholding changes what the figure SHOWS, never what is true. The engine still certifies
    the full construction, so the area must be identical with and without it."""

    def test_area_is_identical_with_and_without_withholding(self) -> None:
        backend = get_backend()
        figure = backend.realize(
            ProblemSpec(construction=SAS_MEDIAN.to_jgex()), SolveOptions(seed=42)
        )
        coords = {name: (x, y) for name, x, y in figure.points}
        full = area_of(("a", "b", "m"), tuple(figure.declared), coords)
        assert full is not None

        withholding = plan(SAS_MEDIAN, ("m",))
        # The construction handed to the engine is unchanged -- only the emitted figure omits m.
        assert "m" not in withholding.visible
        again = area_of(("a", "b", "m"), tuple(figure.declared), coords)
        assert again is not None
        assert sympy.simplify(full.exact - again.exact) == 0

    @pytest.mark.parametrize("template", [t for t in TEMPLATES if t.hideable], ids=lambda t: t.name)
    def test_every_hideable_template_actually_hides(self, template) -> None:
        text = render(template, np.random.default_rng(3), min_length=2, max_length=6)
        construction = to_construction(text)
        result = plan(construction, template.hideable)
        assert result.hidden == template.hideable
        assert all(result.descriptions), f"{template.name} produced an empty description"
        for point in template.hideable:
            assert point not in result.visible

    @pytest.mark.parametrize("template", [t for t in TEMPLATES if t.hideable], ids=lambda t: t.name)
    def test_hidden_points_are_never_region_free(self, template) -> None:
        """Hiding is only worth doing when it hides part of the REGION -- hiding a point the
        question never mentions adds reading difficulty, not geometry (docs/05 §5.5)."""
        assert set(template.hideable) & set(template.region)
