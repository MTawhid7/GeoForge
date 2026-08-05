"""The human configuration library (docs/04 Stage 1, docs/07 T24).

These datasets live in the reference clones, which are optional developer checkouts. Every test
here skips rather than fails when they are absent — a contributor without the clones must still
get a green suite, and `sampler.draw` falls back to clause growth for the same reason.

What is worth testing about third-party data is the *boundary*: that we parse their syntax into
ours without loss, that we never carry their goal across, and that the ordering a seeded batch
indexes into is stable. The data itself is not ours to assert on.
"""

from __future__ import annotations

import pytest

from geoforge.generator import corpora
from geoforge.generator.corpora import Provenance

pytestmark = pytest.mark.skipif(not corpora.available(), reason="reference clones not checked out")


@pytest.fixture(scope="module")
def library() -> tuple[corpora.Configuration, ...]:
    configurations = corpora.load()
    assert configurations, "available() said yes but load() returned nothing"
    return configurations


class TestParsing:
    def test_every_configuration_parses_into_our_construction_type(
        self, library: tuple[corpora.Configuration, ...]
    ) -> None:
        """A skeleton that does not parse is a skeleton Stage 1 cannot use. Measured at 0 of 635
        when this landed; a regression here means their syntax drifted from ours and the fallback
        would quietly shrink the library rather than fail."""
        unparseable = [c.name for c in library if not c.to_construction().steps]
        assert not unparseable, f"{len(unparseable)} unparseable: {unparseable[:5]}"

    def test_their_goal_is_never_carried_across(
        self, library: tuple[corpora.Configuration, ...]
    ) -> None:
        """Their goals are `perp`/`cyclic` statements to prove; ours are values to find. Letting
        one through would put a goal we never verified into a construction."""
        for configuration in library:
            assert "?" not in configuration.construction, configuration.name

    def test_points_match_the_parsed_construction(
        self, library: tuple[corpora.Configuration, ...]
    ) -> None:
        for configuration in library[:120]:
            assert configuration.points == configuration.to_construction().points

    def test_round_trip_through_jgex_loses_no_predicate(
        self, library: tuple[corpora.Configuration, ...]
    ) -> None:
        """Stage 1 emits `to_jgex()` to the engine, so a lossy parse produces a *different
        figure* rather than an error — the realize rate would stay at 100% and the geometry
        would silently be wrong.

        This caught exactly that: the first parser kept only the first predicate of a clause, so
        `d = on_line d o h, on_line d a b` became `d = on_line d o h` and left `d` free to slide
        along a line. Comparing predicate counts is what a clause-count check would have missed.
        """
        for configuration in library[:150]:
            construction = configuration.to_construction()
            original = configuration.construction
            assert construction.to_jgex().count(",") == original.count(","), configuration.name
            assert construction.to_jgex().count("=") == original.count("=")


class TestOrdering:
    def test_load_is_deterministic(self) -> None:
        """A seeded batch indexes into this list, so its order is part of the reproducibility
        contract (docs/02 invariant 2)."""
        assert [c.name for c in corpora.load()] == [c.name for c in corpora.load()]

    def test_ordering_does_not_depend_on_the_requested_set(self) -> None:
        both = [c.name for c in corpora.load(("imo", "jgex_ag_231"))]
        reversed_request = [c.name for c in corpora.load(("jgex_ag_231", "imo"))]
        assert both == reversed_request, "load() must sort its datasets, not follow the argument"


class TestProvenance:
    def test_both_labels_are_populated(self) -> None:
        """The ground-truth split (docs/05 §5.1c) needs both sides to exist."""
        assert corpora.by_provenance(Provenance.OLYMPIAD)
        assert corpora.by_provenance(Provenance.TEXTBOOK)

    def test_the_split_partitions_the_library(
        self, library: tuple[corpora.Configuration, ...]
    ) -> None:
        olympiad = corpora.by_provenance(Provenance.OLYMPIAD)
        textbook = corpora.by_provenance(Provenance.TEXTBOOK)
        assert len(olympiad) + len(textbook) == len(library)


class TestMissingClones:
    def test_absent_datasets_degrade_to_empty(self, tmp_path: object) -> None:
        """Not an error: a build without the clones must still produce puzzles by growth."""
        assert corpora.load(root=tmp_path) == ()  # type: ignore[arg-type]
        assert not corpora.available(root=tmp_path)  # type: ignore[arg-type]


class TestSeededSampling:
    """`GENERATION.corpus_share` is 0.0, so `draw` never takes the seeded branch on a default
    build (docs/07 T24: seeding is gated on M7). These exercise it directly — an off-by-default
    path with no test is a path that rots until the day someone turns it on.
    """

    def test_decorate_appends_givens_without_disturbing_the_skeleton(self) -> None:
        import numpy as np

        from geoforge.generator.sampler import decorate

        configuration = corpora.load(("jgex_ag_231",))[0]
        base = configuration.to_construction()
        decorated, stats = decorate(np.random.default_rng(0), configuration, "hard")

        assert decorated.steps[: len(base.steps)] == base.steps, "the skeleton was modified"
        added = decorated.steps[len(base.steps) :]
        assert added, "no given was added, so the figure stays metric-free and yields nothing"
        assert all(step.construction == "s_angle" for step in added)
        assert stats.origin == configuration.name

    def test_decoration_is_a_function_of_the_rng(self) -> None:
        """Stage 1 must stay reproducible from `(seed, index)` (docs/02 invariant 2)."""
        import numpy as np

        from geoforge.generator.sampler import decorate

        configuration = corpora.load(("jgex_ag_231",))[0]
        first, _ = decorate(np.random.default_rng(7), configuration, "hard")
        second, _ = decorate(np.random.default_rng(7), configuration, "hard")
        assert first.to_jgex() == second.to_jgex()

    def test_draw_uses_the_library_when_the_share_is_one(self) -> None:
        import numpy as np

        import geoforge.config as config
        from geoforge.generator.sampler import draw

        original = config.GENERATION.corpus_share
        object.__setattr__(config.GENERATION, "corpus_share", 1.0)
        try:
            _, stats = draw(np.random.default_rng(3), band="hard")
            assert stats.origin != "grown"
        finally:
            object.__setattr__(config.GENERATION, "corpus_share", original)

    def test_draw_grows_when_the_share_is_zero(self) -> None:
        """The shipping default, and the reason a build without the clones still works."""
        import numpy as np

        from geoforge.generator.sampler import draw

        _, stats = draw(np.random.default_rng(3), band="hard")
        assert stats.origin == "grown"
