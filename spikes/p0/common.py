"""Shared helpers for the Phase 0 spikes.

Throwaway spike code: Phase 1 rewrites this against the Solver Abstraction Layer (docs/03).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from newclid.api import GeometricSolverBuilder, PythonDefault
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.problem import predicate_to_construction
from newclid.proof_data import ProofData, proof_data_from_state

import newclid_patches

APPLIED_PATCHES = newclid_patches.apply_all()

SPIKE_DIR = Path(__file__).resolve().parent
PROBLEMS_FILE = SPIKE_DIR / "problems" / "spike_problems.txt"
OUT_DIR = SPIKE_DIR / "out"


def load_problems(path: Path = PROBLEMS_FILE) -> list[tuple[str, str]]:
    """Parse the two-line dataset format: name line, then JGEX formulation line."""
    lines = [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if len(lines) % 2 != 0:
        raise ValueError(f"{path} has an odd number of content lines ({len(lines)})")
    return list(zip(lines[::2], lines[1::2]))


@dataclass
class SolveOutcome:
    name: str
    problem: str
    backend: str
    solved: bool
    error: str | None = None
    t_build: float = 0.0
    t_solver_build: float = 0.0
    t_run: float = 0.0
    steps: int | None = None
    proof_length: int | None = None
    proof_rules_length: int | None = None
    goals_total: int = 0
    goals_proved: int = 0
    n_points: int | None = None
    proof_data: ProofData | None = field(default=None, repr=False)
    proof_text: str | None = field(default=None, repr=False)

    @property
    def t_total(self) -> float:
        return self.t_build + self.t_solver_build + self.t_run

    def row(self) -> dict[str, Any]:
        """Flat, JSON-safe summary (no heavy proof payloads)."""
        return {
            "name": self.name,
            "backend": self.backend,
            "solved": self.solved,
            "error": self.error,
            "t_build": round(self.t_build, 4),
            "t_solver_build": round(self.t_solver_build, 4),
            "t_run": round(self.t_run, 4),
            "t_total": round(self.t_total, 4),
            "steps": self.steps,
            "proof_length": self.proof_length,
            "proof_rules_length": self.proof_rules_length,
            "goals_proved": self.goals_proved,
            "goals_total": self.goals_total,
            "n_points": self.n_points,
        }


def solve_one(
    name: str,
    problem_txt: str,
    *,
    seed: int = 42,
    backend: str = "python",
    collect_proof: bool = False,
) -> SolveOutcome:
    """Solve one JGEX problem, timing each stage separately.

    backend="python" forces the pure-Python DDARN path. This matters: once py-yuclid is
    installed, newclid's auto-default switches to the C++ backend, which does NOT support
    `acompute` goals (Newclid's own test suite marks acompute_test as expected-to-fail there).
    """
    out = SolveOutcome(name=name, problem=problem_txt, backend=backend, solved=False)
    try:
        rng = np.random.default_rng(seed)
        t0 = time.perf_counter()
        setup = JGEXProblemBuilder(rng=rng).with_problem_from_txt(problem_txt).build()
        t1 = time.perf_counter()

        if backend == "python":
            builder = GeometricSolverBuilder(rng=rng, api_default=PythonDefault())
        elif backend == "yuclid":
            builder = GeometricSolverBuilder(rng=rng)  # auto-picks HEDefault when installed
        else:
            raise ValueError(f"unknown backend {backend!r}")
        solver = builder.build(setup)
        t2 = time.perf_counter()

        solved = solver.run()
        t3 = time.perf_counter()

        out.solved = solved
        out.t_build, out.t_solver_build, out.t_run = t1 - t0, t2 - t1, t3 - t2
        out.n_points = len(setup.points)
        if solver.run_infos is not None:
            out.steps = solver.run_infos.steps
            per_goal = solver.run_infos.success_per_goal
            out.goals_total = len(per_goal)
            out.goals_proved = sum(1 for v in per_goal.values() if v)

        if collect_proof:
            goals_constructions = [
                predicate_to_construction(g) for g in solver.proof_state.goals
            ]
            pd = proof_data_from_state(
                goals_constructions=goals_constructions, proof_state=solver.proof_state
            )
            out.proof_data = pd
            out.proof_length = pd.proof_length
            out.proof_rules_length = pd.proof_rules_length
            out.proof_text = solver.proof()
    except Exception as exc:  # spike code: record failures as data, never crash the sweep
        out.error = f"{type(exc).__name__}: {exc}"
    return out


def iter_problems(only: str | None = None) -> Iterator[tuple[str, str]]:
    for name, txt in load_problems():
        if only and only not in name:
            continue
        yield name, txt
