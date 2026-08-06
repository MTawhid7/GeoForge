"""Display layout: the premise-preservation invariant, admissibility, and label placement.

The test that matters most is `TestPremisesSurviveTheLayout`: every drawn figure must satisfy
every stated premise, checked by the engine over the *display* coordinates. That is docs/06
§6.3's "never perturb declared facts" stated as something a machine can fail, and it is the
test that would catch any future drift toward moving points directly.

`TestAdmissibilityCanReject` exists because on real output every candidate is admissible, so
the gate would otherwise be asserted by nothing. Its branches are exercised directly instead.
One of them documents a correction: a mirrored figure must be *accepted*, because reflection is
an isometry and everything a puzzle publishes is undirected.
"""

from __future__ import annotations

import math

import pytest

from geoforge.bank.layout import _admissible, _candidates, lay_out, place_labels
from geoforge.config import LAYOUT
from geoforge.generator import quantities
from geoforge.generator.batch import BatchReport, CandidatePuzzle, run
from geoforge.generator.emit import frame
from geoforge.solvers.interface import SolverBackend, get_backend
from geoforge.solvers.types import fact_from_id

BATCH_N = 60
SEED = 42


@pytest.fixture(scope="module")
def backend() -> SolverBackend:
    return get_backend()


@pytest.fixture(scope="module")
def report() -> BatchReport:
    # `reject_sight_readable=False`: this corpus exists to exercise machinery, and the
    # product answer policy (docs/07 T5) costs an order of magnitude of yield.
    return run(BATCH_N, SEED, reject_sight_readable=False)


@pytest.fixture(scope="module")
def candidates(report: BatchReport) -> list[CandidatePuzzle]:
    assert report.puzzles
    return report.puzzles


def _reference(candidate: CandidatePuzzle) -> dict[str, tuple[float, float]]:
    return {name: (x, y) for name, x, y in candidate.reference_points}


def _laid(backend: SolverBackend, candidate: CandidatePuzzle):  # type: ignore[no-untyped-def]
    claim = quantities.get(candidate.quantity_type).claim_of(
        candidate.derivation.goal, _reference(candidate)
    )
    assert claim is not None
    return lay_out(
        backend,
        candidate.pruned,
        candidate.derivation,
        candidate.translation,
        claim,
        _reference(candidate),
        candidate.puzzle.figure.segments,
        candidate.seed,
    )


class TestPremisesSurviveTheLayout:
    """docs/06 §6.3 and docs/07 T5: the drawn figure is metrically consistent with every given."""

    def test_every_premise_holds_in_the_display_figure(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates:
            result = _laid(backend, candidate)
            assert result.ok, candidate.id
            drawn = frame(result.coords)
            points = tuple(sorted((n, xy[0], xy[1]) for n, xy in drawn.items()))
            premises = tuple(fact_from_id(g.fact) for g in candidate.puzzle.given)
            assert all(backend.check_facts(points, premises)), (
                f"{candidate.id}: the figure the player sees does not satisfy its own givens"
            )

    def test_the_layout_never_loses_a_puzzle(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """The reference figure is always a candidate, so a puzzle that was drawable at Stage 9
        stays drawable. A layout that can fail a good puzzle is a yield bug wearing a feature."""
        for candidate in candidates:
            assert _laid(backend, candidate).ok, candidate.id

    def test_framing_keeps_the_figure_in_the_viewbox(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates:
            drawn = frame(_laid(backend, candidate).coords)
            for x, y in drawn.values():
                assert 0 <= x <= LAYOUT.viewbox_width
                assert 0 <= y <= LAYOUT.viewbox_height


class TestAdmissibilityCanReject:
    """A gate that never fires is untested — and on real output this one never fires.

    Measured: no candidate is ever refused, across every instantiation in a seed-42 batch and
    400 further resamples of one construction. That is not a broken check, it is two facts
    about the current pipeline: Newclid's `realize` makes the same discrete topological choices
    for a fixed construction, and everything the puzzle publishes is undirected. So each branch
    is exercised directly here instead of being left asserted by nothing.
    """

    def test_a_mirrored_figure_is_accepted(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """The case that corrected the design. A reflection is an isometry: it preserves every
        distance and every *undirected* angle, and undirected is all a puzzle publishes. So a
        mirrored drawing is a correct drawing and must be accepted — rejecting it would discard
        half the candidate space to protect against nothing."""
        for candidate in candidates:
            reference = _reference(candidate)
            claim = quantities.get(candidate.quantity_type).claim_of(
                candidate.derivation.goal, reference
            )
            assert claim is not None
            mirrored = {name: (-x, y) for name, (x, y) in reference.items()}
            assert _admissible(
                backend, mirrored, candidate.derivation, candidate.translation, claim
            ), candidate.id

    def test_a_figure_where_the_goal_moved_is_refused(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """Drag one arm of the goal angle. The drawing now shows an angle other than the one
        the puzzle answers, which is the failure this gate exists for."""
        refused = 0
        for candidate in candidates:
            reference = _reference(candidate)
            claim = quantities.get(candidate.quantity_type).claim_of(
                candidate.derivation.goal, reference
            )
            assert claim is not None
            vertex = reference[claim.angle.vertex]
            moved = dict(reference)
            arm = reference[claim.angle.p]
            # Rotate P 30 degrees about the vertex: distances to the vertex are untouched, so
            # only the angle itself changes.
            dx, dy = arm[0] - vertex[0], arm[1] - vertex[1]
            cos, sin = math.cos(math.radians(30)), math.sin(math.radians(30))
            moved[claim.angle.p] = (
                vertex[0] + dx * cos - dy * sin,
                vertex[1] + dx * sin + dy * cos,
            )
            if not _admissible(backend, moved, candidate.derivation, candidate.translation, claim):
                refused += 1
        assert refused == len(candidates), "moving the goal angle was not refused"

    def test_a_figure_that_breaks_a_configuration_fact_is_refused(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """Collapse two points a recorded configuration fact distinguishes.

        The pair has to come from a configuration fact. Collapsing an arbitrary pair often
        breaks nothing the puzzle recorded, because the configuration facts on this corpus are
        thin — some `sameclock` entries are tautologies of the form `sameclock x y z x y z`,
        which constrain nothing at all (docs/07 T13).

        **Widened in Phase 3 M4 from `diff` specifically.** It used to select `FactKind.DIFFERENT`
        by name, and the M4 sampler no longer produces any: the corpus now records `sameclock`
        almost exclusively, so the test silently had nothing to check and said so. Any
        configuration fact naming two distinct points will do — collapsing them degenerates the
        triangle the fact is about, which is what admissibility must refuse.

        **Widened again in Phase 3 M6.** It used to collapse `pairs[0]` and require *that* pair
        to be refused, which held only while every puzzle's first configuration fact happened to
        be load-bearing. Seeded figures (docs/07 T24) carry many more configuration facts, some
        of them genuinely slack, so the first pair is no longer a fair representative — and a
        test that fails because the corpus got richer is testing the corpus, not the gate. The
        property that actually has to hold is that a recorded configuration fact constrains
        *something*: for each puzzle, at least one collapse it records must be refused.
        """
        checked = 0
        for candidate in candidates:
            pairs = [
                (f.args[i], f.args[j])
                for f in candidate.derivation.configuration
                for i in range(len(f.args))
                for j in range(i + 1, len(f.args))
                if f.args[i] != f.args[j]
            ]
            if not pairs:
                continue
            reference = _reference(candidate)
            claim = quantities.get(candidate.quantity_type).claim_of(
                candidate.derivation.goal, reference
            )
            assert claim is not None

            refused = False
            for first, second in pairs:
                collapsed = dict(reference)
                collapsed[second] = reference[first]
                if not _admissible(
                    backend, collapsed, candidate.derivation, candidate.translation, claim
                ):
                    refused = True
                    break
            assert refused, (
                f"{candidate.id}: no collapse of any pair its configuration facts name was "
                f"refused, so those facts constrain nothing"
            )
            checked += 1
        assert checked, "no puzzle carried a usable configuration fact, so nothing was tested"

    def test_the_reference_figure_itself_is_admissible(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """The near-miss: without this the reflection test could pass by refusing everything."""
        for candidate in candidates:
            reference = _reference(candidate)
            claim = quantities.get(candidate.quantity_type).claim_of(
                candidate.derivation.goal, reference
            )
            assert claim is not None
            assert _admissible(
                backend, reference, candidate.derivation, candidate.translation, claim
            ), candidate.id

    def test_candidates_are_genuinely_different_figures(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """Choosing among instantiations only helps if they differ. If `realize` returned the
        same shape at every seed, the whole layout would be an expensive identity function."""
        candidate = candidates[0]
        drawn = tuple(candidate.pruned.points)
        figures = _candidates(
            backend, candidate.pruned, _reference(candidate), drawn, candidate.seed
        )
        assert len(figures) > 1

        shapes = set()
        for figure in figures:
            names = sorted(figure)
            base = math.dist(figure[names[0]], figure[names[1]]) or 1.0
            shapes.add(
                tuple(round(math.dist(figure[names[0]], figure[n]) / base, 6) for n in names[2:])
            )
        assert len(shapes) > 1, "every instantiation had the same shape"


class TestDeterminism:
    def test_the_same_puzzle_lays_out_identically(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates[:3]:
            first, second = _laid(backend, candidate), _laid(backend, candidate)
            assert first.coords == second.coords
            assert first.labels == second.labels


class TestLabels:
    def test_every_point_gets_an_offset(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        for candidate in candidates:
            result = _laid(backend, candidate)
            assert set(result.labels) == set(candidate.pruned.points)

    def test_offsets_are_on_the_configured_circle(
        self, backend: SolverBackend, candidates: list[CandidatePuzzle]
    ) -> None:
        """Labels sit at a fixed radius, so no label is left on top of its own point."""
        for candidate in candidates:
            for dx, dy in _laid(backend, candidate).labels.values():
                assert math.hypot(dx, dy) == pytest.approx(LAYOUT.label_radius, rel=0.02)

    def test_two_points_do_not_take_the_same_label_spot(self) -> None:
        """Two points a hair apart must not send their labels to the same place."""
        coords = {"a": (0.0, 0.0), "b": (0.05, 0.0), "c": (1.0, 0.0)}
        labels = place_labels(coords, [("A", "C")])
        assert labels["a"] != labels["b"]

    def test_placement_is_a_function_of_the_geometry(self) -> None:
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.5, 0.9)}
        segments = [("A", "B"), ("B", "C"), ("A", "C")]
        assert place_labels(coords, segments) == place_labels(coords, segments)
