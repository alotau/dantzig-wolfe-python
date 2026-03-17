"""Worker-scalability benchmarks for the four_sea and eight_sea fixtures.

four_sea  — same problem decomposed into 4 subproblems (2 aircraft each).
eight_sea — same problem decomposed into 8 subproblems (1 aircraft each).

Both fixtures share the same master.cplex and must produce identical objective
values regardless of the number of workers used.

Run with output visible::

    pytest -s tests/benchmarks/test_four_sea_workers.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from benchmarks.models import BenchConfig, BenchMatrix, CellResult
from benchmarks.table import format_table
from dwsolver import Problem, SolveStatus, solve

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_FOUR_SEA  = _FIXTURES / "four_sea"
_EIGHT_SEA = _FIXTURES / "eight_sea"

# Both decompositions share the same master problem.
_MASTER = _FOUR_SEA / "master.cplex"

_KNOWN_OPTIMAL = 12.0  # expected objective for both fixtures

# ---------------------------------------------------------------------------
# Problem fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def four_sea_problem() -> Problem:
    """Load the four_sea CPLEX LP problem (4 subproblems) once for the module."""
    return Problem.from_lp(_MASTER, sorted(_FOUR_SEA.glob("subprob_*.cplex")))


@pytest.fixture(scope="module")
def eight_sea_problem() -> Problem:
    """Load the eight_sea CPLEX LP problem (8 subproblems) once for the module."""
    return Problem.from_lp(_MASTER, sorted(_EIGHT_SEA.glob("subprob_*.cplex")))


# ---------------------------------------------------------------------------
# Correctness test — both decompositions must agree on the optimal value
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_four_and_eight_sea_same_optimal(
    four_sea_problem: Problem,
    eight_sea_problem: Problem,
) -> None:
    """Workers 1–4 on four_sea and 1–8 on eight_sea all reach objective=12.0."""
    for label, problem, worker_counts in [
        ("four_sea",  four_sea_problem,  [1, 2, 3, 4]),
        ("eight_sea", eight_sea_problem, [1, 2, 3, 4, 5, 6, 7, 8]),
    ]:
        for w in worker_counts:
            result = solve(problem, workers=w)
            assert result.status == SolveStatus.OPTIMAL, (
                f"{label} workers={w}: expected OPTIMAL, got {result.status}"
            )
            assert result.objective == pytest.approx(_KNOWN_OPTIMAL), (
                f"{label} workers={w}: expected objective={_KNOWN_OPTIMAL}, "
                f"got {result.objective}"
            )


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------


def _run_timing(problem: Problem, worker_counts: list[int]) -> list[CellResult]:
    """Time solve() for each worker count and return CellResult list."""
    cells: list[CellResult] = []
    n_blocks = len(problem.blocks)
    for w in worker_counts:
        t_start = time.perf_counter()
        result = solve(problem, workers=w)
        elapsed = time.perf_counter() - t_start

        assert result.status == SolveStatus.OPTIMAL, (
            f"workers={w}: expected OPTIMAL, got {result.status}"
        )
        cells.append(
            CellResult(
                n_blocks=n_blocks,
                workers=w,
                elapsed=elapsed,
                status=result.status,
                iterations=result.iterations,
            )
        )
    return cells


def _print_timing_table(label: str, n_blocks: int, worker_counts: list[int],
                        cells: list[CellResult]) -> None:
    config = BenchConfig(
        subproblems=range(n_blocks, n_blocks + 1),
        worker_counts=worker_counts,
    )
    matrix = BenchMatrix(cells=[cells], config=config)
    table = format_table(matrix)
    table = table.replace("Subproblems", "Problem   ").replace(
        f"\n{n_blocks:>3}", f"\n{label}"
    )
    print("\n" + table, file=sys.stderr)


# ---------------------------------------------------------------------------
# four_sea benchmark — workers 1–4
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_four_sea_worker_scalability(four_sea_problem: Problem) -> None:
    """Solve four_sea with workers in [1, 2, 3, 4] and print timing table."""
    worker_counts = [1, 2, 3, 4]
    cells = _run_timing(four_sea_problem, worker_counts)
    _print_timing_table("four_sea", n_blocks=4, worker_counts=worker_counts, cells=cells)


# ---------------------------------------------------------------------------
# eight_sea benchmark — workers 1–8
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_eight_sea_worker_scalability(eight_sea_problem: Problem) -> None:
    """Solve eight_sea with workers in [1, 2, 3, 4, 5, 6, 7, 8] and print timing table."""
    worker_counts = [1, 2, 3, 4, 5, 6, 7, 8]
    cells = _run_timing(eight_sea_problem, worker_counts)
    _print_timing_table("eight_sea", n_blocks=8, worker_counts=worker_counts, cells=cells)
