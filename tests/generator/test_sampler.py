"""Stage 1-2 sampler (docs/04)."""

from __future__ import annotations

import numpy as np
import pytest

from geoforge.config import GENERATION
from geoforge.generator.sampler import sample_construction
from geoforge.solvers.catalog import catalog, extensions, seeds


class TestCatalog:
    def test_catalog_is_populated(self) -> None:
        assert len(catalog()) > 50

    def test_seeds_need_no_input_points(self) -> None:
        assert seeds()
        assert all(d.arity == 0 for d in seeds())

    def test_extensions_need_input_points(self) -> None:
        assert extensions()
        assert all(d.arity > 0 for d in extensions())

    def test_every_entry_can_be_rendered(self) -> None:
        """Every argument must be classifiable as input, output, or numeric parameter —
        otherwise the sampler would emit malformed JGEX."""
        for definition in catalog().values():
            classified = (
                set(definition.input_points)
                | set(definition.output_points)
                | set(definition.numeric_params)
            )
            assert set(definition.arg_order) <= classified, definition.name

    def test_circle_primitives_are_flagged(self) -> None:
        by_name = catalog()
        assert by_name["on_circum"].introduces_circle
        assert by_name["circle"].introduces_circle
        assert not by_name["on_line"].introduces_circle


class TestSampling:
    def test_is_deterministic_for_a_seed(self) -> None:
        a, _ = sample_construction(np.random.default_rng(7))
        b, _ = sample_construction(np.random.default_rng(7))
        assert a.to_jgex() == b.to_jgex()

    def test_different_seeds_differ(self) -> None:
        a, _ = sample_construction(np.random.default_rng(1))
        b, _ = sample_construction(np.random.default_rng(2))
        assert a.to_jgex() != b.to_jgex()

    def test_respects_step_bounds(self) -> None:
        rng = np.random.default_rng(3)
        for _ in range(20):
            construction, _ = sample_construction(rng)
            assert 1 <= len(construction.steps) <= GENERATION.max_construction_steps

    def test_explicit_step_count_is_honoured(self) -> None:
        construction, stats = sample_construction(np.random.default_rng(5), n_steps=4)
        assert len(construction.steps) == 4
        assert stats.steps_committed == 4

    def test_never_samples_excluded_constructions(self) -> None:
        """Problem-specific fixtures (test_r20, e5128, ...) are not general primitives."""
        rng = np.random.default_rng(11)
        for _ in range(60):
            construction, _ = sample_construction(rng)
            for step in construction.steps:
                assert step.construction not in GENERATION.excluded_constructions

    def test_only_references_already_introduced_points(self) -> None:
        """A clause may not mention a point before it exists (docs/03 §3.4)."""
        rng = np.random.default_rng(13)
        for _ in range(60):
            construction, _ = sample_construction(rng)
            known: set[str] = set()
            for step in construction.steps:
                for arg in step.args:
                    is_value = any(ch.isdigit() for ch in arg)
                    if is_value or arg in step.outputs:
                        continue
                    assert arg in known, f"{arg} used before introduction in {step.to_jgex()}"
                known.update(step.outputs)

    def test_point_names_are_unique(self) -> None:
        rng = np.random.default_rng(17)
        for _ in range(40):
            construction, _ = sample_construction(rng)
            names = [p for step in construction.steps for p in step.outputs]
            assert len(names) == len(set(names))

    def test_circle_bias_is_effective(self) -> None:
        """Phase 0 found circles carry the difficulty, so the grammar up-weights them."""
        rng = np.random.default_rng(19)
        with_circle = sum(1 for _ in range(80) if sample_construction(rng)[0].introduces_circle)
        assert with_circle > 40, f"only {with_circle}/80 constructions involved a circle"

    @pytest.mark.parametrize("band", ["easy", "medium", "hard"])
    def test_numeric_givens_come_from_the_band_palette(self, band: str) -> None:
        """Stage 2: angle givens are drawn from the band's nice-value palette."""
        rng = np.random.default_rng(23)
        allowed = {f"{v}o" for v in GENERATION.nice_angle_degrees[band]}
        seen_any = False
        for _ in range(60):
            construction, _ = sample_construction(rng, band=band)
            for step in construction.steps:
                if step.construction in ("s_angle", "aconst"):
                    angles = [a for a in step.args if a.endswith("o")]
                    for angle in angles:
                        seen_any = True
                        assert angle in allowed, f"{angle} outside the {band} palette"
        assert seen_any, "expected at least one angle given across 60 samples"
