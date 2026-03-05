"""Dantzig-Wolfe column-generation solver.

Full implementation in Phase 3 (T017–T018).
This stub satisfies the public API and mypy strict-mode imports.
"""

from __future__ import annotations

from dwsolver.models import (
    DEFAULT_TOLERANCE,
    DEFAULT_WORKERS,
    MAX_ITERATIONS,
    Problem,
    Result,
)


def solve(
    problem: Problem,
    workers: int | None = DEFAULT_WORKERS,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = MAX_ITERATIONS,
) -> Result:
    """Solve a block-angular LP using Dantzig-Wolfe decomposition.

    Args:
        problem: The block-angular LP to solve.
        workers: Number of parallel subproblem workers.
            ``None`` defaults to ``cpu_count() * 2``.
        tolerance: Convergence tolerance (relative reduced-cost gap).
        max_iterations: Maximum column-generation iterations.

    Returns:
        A :class:`Result` with status, objective, and variable values.
    """
    raise NotImplementedError("solve() implemented in T017")


__all__ = ["solve"]
