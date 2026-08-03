"""Scoring is reproducible across processes (docs/02 invariant 2).

Run in **subprocesses with different `PYTHONHASHSEED`**, not in-process. Python randomizes
string hashing per process, so any scoring path that iterated a set of fact ids or template
names would be stable within one run and silently different between two — the class of bug
ONBOARDING §6.4d records as costing two milestones, and the reason M4's dedupe is forbidden
from using `hash()` at all.

An in-process repeat test cannot see this. That is the whole point of paying for a subprocess.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

SCRIPT = """
import json
from geoforge.generator.batch import run
from geoforge.scoring import interest
from geoforge.scoring.report import distribution

report = run({n}, {seed})
collinear = {{c.id: interest.collinear_count(c.derivation.premises) for c in report.puzzles}}
print(json.dumps({{
    "scores": [[c.id, c.score, c.band] for c in report.puzzles],
    "features": [
        [c.id, c.features.depth, c.features.width, c.features.distinct_rules,
         c.features.tier_max, c.features.tier_mix, c.features.branch_join,
         c.features.nice_penalty, c.features.rule_share_max]
        for c in report.puzzles
    ],
    "ranking": [c.id for c, _ in interest.rank(report.puzzles, collinear)],
    "selected": [c.id for c in interest.select(report.puzzles, collinear)],
    "rejections": {{k: v for k, v in report.by_reason().items() if k.startswith("score:")}},
    "constant_features": distribution(report.puzzles)["constant_features"],
}}, sort_keys=True))
"""

N = 200
SEED = 42


def _run(hash_seed: str) -> dict[str, object]:
    environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT.format(n=N, seed=SEED)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    return json.loads(result.stdout)  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def two_runs() -> tuple[dict[str, object], dict[str, object]]:
    return _run("0"), _run("99991")


def test_the_run_produced_something_to_compare(
    two_runs: tuple[dict[str, object], dict[str, object]],
) -> None:
    """The near-miss: two empty runs agree perfectly and prove nothing."""
    first, _ = two_runs
    assert first["scores"], "no puzzles scored, so every comparison below is vacuous"


def test_scores_and_bands_agree_across_hash_seeds(
    two_runs: tuple[dict[str, object], dict[str, object]],
) -> None:
    first, second = two_runs
    assert first["scores"] == second["scores"]


def test_features_agree_across_hash_seeds(
    two_runs: tuple[dict[str, object], dict[str, object]],
) -> None:
    first, second = two_runs
    assert first["features"] == second["features"]


def test_the_interest_ranking_agrees_across_hash_seeds(
    two_runs: tuple[dict[str, object], dict[str, object]],
) -> None:
    """The order, not just the set. Ranking ties break on puzzle id for exactly this reason —
    a bank whose selection depends on iteration order is not byte-reproducible."""
    first, second = two_runs
    assert first["ranking"] == second["ranking"]
    assert first["selected"] == second["selected"]


def test_filter_rejections_agree_across_hash_seeds(
    two_runs: tuple[dict[str, object], dict[str, object]],
) -> None:
    first, second = two_runs
    assert first["rejections"] == second["rejections"]
