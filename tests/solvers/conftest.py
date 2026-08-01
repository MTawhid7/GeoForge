"""Shared fixtures for the SAL contract suite."""

from __future__ import annotations

import pytest

from geoforge.solvers import ProblemSpec, get_backend
from geoforge.solvers.interface import SolverBackend
from tests.solvers.corpus import CORPUS


@pytest.fixture(scope="session")
def backend() -> SolverBackend:
    return get_backend()


@pytest.fixture(params=sorted(CORPUS), ids=sorted(CORPUS))
def corpus_case(request: pytest.FixtureRequest) -> tuple[str, ProblemSpec]:
    name = str(request.param)
    return name, CORPUS[name]
