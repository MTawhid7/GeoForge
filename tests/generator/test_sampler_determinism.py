"""M2 acceptance: a fixed seed reproduces a whole batch byte for byte (docs/09 P1).

Determinism is a correctness property here, not a nicety: docs/02 invariant 2 requires every
artifact to be reproducible from (generator_version, engine_version, seed), and the batch
attrition report is the primary regression signal for sampler changes (docs/04).
"""

from __future__ import annotations

import collections
import json

from geoforge.generator.batch import construction_rng
from geoforge.generator.degeneracy import check_figure
from geoforge.generator.sampler import sample_construction
from geoforge.solvers import ProblemSpec, SolveOptions, get_backend

BATCH_SIZE = 200
SEED = 42


def _sample_batch(seed: int, n: int) -> list[str]:
    """Seeded exactly as `batch.run` seeds it — per index, not off one advancing stream."""
    return [sample_construction(construction_rng(seed, i))[0].to_jgex() for i in range(n)]


class TestBatchDeterminism:
    def test_two_hundred_constructions_are_byte_identical(self) -> None:
        first = _sample_batch(SEED, BATCH_SIZE)
        second = _sample_batch(SEED, BATCH_SIZE)
        assert json.dumps(first) == json.dumps(second)

    def test_batch_is_varied(self) -> None:
        """Determinism must not come from emitting the same construction repeatedly."""
        batch = _sample_batch(SEED, BATCH_SIZE)
        assert len(set(batch)) > BATCH_SIZE * 0.9

    def test_every_construction_is_well_formed(self) -> None:
        for jgex in _sample_batch(SEED, BATCH_SIZE):
            assert " = " in jgex
            for clause in jgex.split("; "):
                lhs, _, rhs = clause.partition(" = ")
                assert lhs.strip() and rhs.strip()


class TestPipelineStageAttrition:
    """Stage 1 -> 3 on a fixed seed, reporting attrition per reason.

    Sized well below the full batch to keep the suite fast; the 1,000-construction soundness
    run is M5's acceptance criterion.
    """

    def test_stage_attrition_is_reproducible_and_nonzero(self) -> None:
        def run() -> collections.Counter[str]:
            backend = get_backend()
            counts: collections.Counter[str] = collections.Counter()
            for i in range(25):
                construction, _ = sample_construction(construction_rng(SEED, i))
                figure = backend.realize(construction.to_spec(), SolveOptions(seed=1000 + i))
                verdict = check_figure(figure)
                counts[str(verdict.reason) if verdict.reason else "accepted"] += 1
            return counts

        first, second = run(), run()
        assert first == second, "attrition must be reproducible for a fixed seed"
        assert sum(first.values()) == 25
        assert first["accepted"] > 0, "Stage 3 must not reject everything"

    def test_realize_reports_failures_instead_of_raising(self) -> None:
        """An unrealizable construction is attrition, not an exception. The generator needs a
        verdict it can count and log with the seed, not a traceback (docs/08 §8.1)."""
        # A point cannot be both the midpoint of AB and lie off the line through A and B.
        impossible = ProblemSpec(
            construction="a b = segment a b; m = midpoint m a b; c = on_tline c m a b; "
            "d = intersection_ll d a b c m"
        )
        figure = get_backend().realize(impossible, SolveOptions(seed=1))
        assert not figure.ok
        assert figure.error is not None
