"""Area construction templates (docs/10 step A1b)."""

from __future__ import annotations

import numpy as np
import pytest
import sympy

from geoforge.generator.area import area_of
from geoforge.generator.templates import (
    TEMPLATE_ANGLES,
    TEMPLATES,
    AreaTemplate,
    draw_area,
    render,
    to_construction,
)
from geoforge.solvers.interface import get_backend
from geoforge.solvers.types import ProblemSpec, SolveOptions


class TestLibrary:
    def test_every_template_parses_and_pins_its_region(self) -> None:
        rng = np.random.default_rng(0)
        for template in TEMPLATES:
            text = render(template, rng, min_length=2, max_length=6)
            assert "{" not in text, f"{template.name} left a placeholder: {text}"
            construction = to_construction(text)
            assert construction.steps, template.name
            assert set(template.region) <= set(construction.points), (
                f"{template.name} asks about {template.region} but only builds "
                f"{construction.points}"
            )

    def test_no_template_states_a_right_angle(self) -> None:
        """90 degrees makes the SAS area rational and is its own supplement, which is how two
        separate defects hid themselves (ONBOARDING gotcha 6)."""
        assert 90 not in TEMPLATE_ANGLES

    def test_templates_have_distinct_names(self) -> None:
        assert len({t.name for t in TEMPLATES}) == len(TEMPLATES)

    def test_at_least_one_multi_step_template(self) -> None:
        """A one-step template is an arithmetic exercise, not a puzzle (docs/10 §10.10b)."""
        assert any(t.steps_to_solve >= 2 for t in TEMPLATES)

    def test_multi_predicate_clauses_survive_parsing(self) -> None:
        """Dropping a clause's tail leaves the point underdetermined, which realizes to a
        DIFFERENT figure rather than to an error (docs/07 T24)."""
        construction = to_construction(
            "a = free a; b = lconst b a 2; c = lconst c a 2, lconst c b 2"
        )
        last = construction.steps[-1]
        assert last.extra, "the second predicate of the final clause was dropped"


class TestDraw:
    def test_draw_is_deterministic_for_a_seed(self) -> None:
        first = draw_area(np.random.default_rng(7))
        second = draw_area(np.random.default_rng(7))
        assert first[2] == second[2]
        assert first[1].name == second[1].name

    def test_draw_can_be_restricted_to_named_templates(self) -> None:
        for _ in range(5):
            _, template, _ = draw_area(np.random.default_rng(3), names=("equilateral",))
            assert template.name == "equilateral"

    def test_unknown_template_selection_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no templates"):
            draw_area(np.random.default_rng(0), names=("does-not-exist",))


class TestAgainstTheEngine:
    """Every template must realize and must yield a computable area."""

    @pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.name)
    def test_template_realizes_and_yields_an_area(self, template: AreaTemplate) -> None:
        backend = get_backend()
        rng = np.random.default_rng(11)
        text = render(template, rng, min_length=2, max_length=6)
        construction = to_construction(text)
        figure = backend.realize(
            ProblemSpec(construction=construction.to_jgex()), SolveOptions(seed=42)
        )
        coords = {name: (x, y) for name, x, y in figure.points}
        result = area_of(template.region, tuple(figure.declared), coords)
        assert result is not None, f"{template.name} pinned no computable area: {text}"
        assert result.approx > 0

    @pytest.mark.parametrize(
        "template", [t for t in TEMPLATES if t.irrational], ids=lambda t: t.name
    )
    def test_templates_marked_irrational_really_are(self, template: AreaTemplate) -> None:
        """The `irrational` column is a measurement, so it has to keep being true."""
        backend = get_backend()
        rng = np.random.default_rng(5)
        seen_irrational = False
        for _ in range(6):
            text = render(template, rng, min_length=2, max_length=6)
            figure = backend.realize(
                ProblemSpec(construction=to_construction(text).to_jgex()), SolveOptions(seed=42)
            )
            coords = {name: (x, y) for name, x, y in figure.points}
            result = area_of(template.region, tuple(figure.declared), coords)
            if result is not None and result.is_irrational:
                seen_irrational = True
                break
        assert seen_irrational, f"{template.name} never produced an irrational area"


class TestWellPosedness:
    """The gate that decides whether any of this ships (docs/10 §10.8).

    A template claims to PIN its region. If that is true the area must be the same number in
    every figure the construction realizes to -- a different seed gives a different diagram, and
    an area that moves with it was never determined by the givens.
    """

    @pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.name)
    def test_area_is_invariant_across_resampled_figures(self, template: AreaTemplate) -> None:
        backend = get_backend()
        text = render(template, np.random.default_rng(13), min_length=2, max_length=6)
        construction = to_construction(text)

        values: list[sympy.Expr] = []
        for seed in (1, 7, 99, 12345):
            figure = backend.realize(
                ProblemSpec(construction=construction.to_jgex()), SolveOptions(seed=seed)
            )
            coords = {name: (x, y) for name, x, y in figure.points}
            # area_of verifies against each diagram and raises on disagreement, so reaching the
            # append at all already means the exact value matched that figure's shoelace area.
            result = area_of(template.region, tuple(figure.declared), coords)
            if result is not None:
                values.append(result.exact)

        assert len(values) >= 2, f"{template.name} realized too rarely to judge: {text}"
        for other in values[1:]:
            assert sympy.simplify(values[0] - other) == 0, (
                f"{template.name} is NOT well-posed: {text} gave {values}"
            )
