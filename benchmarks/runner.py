"""Benchmark timing loop: runs solve() across the full (subproblems, workers) grid."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

from benchmarks.generator import make_bench_problem
from benchmarks.models import BenchConfig, BenchMatrix, CellError, CellResult
from dwsolver import Problem, Result, SolveStatus, solve


def run_benchmark(config: BenchConfig) -> BenchMatrix:
    """Run the full timing grid and return the populated result matrix.

    Pre-generates all Problem instances (excluded from timing), then times
    solve(problem, workers=w) for every (n_blocks, workers) combination.
    Per-cell timeout is enforced via concurrent.futures.

    Args:
        config: Benchmark configuration.

    Returns:
        BenchMatrix with all cells populated.
    """
    subproblems = list(config.subproblems)
    worker_counts = config.worker_counts
    total_cells = len(subproblems) * len(worker_counts)
    cell_num = 0

    # Pre-generate all problems outside the timing loop
    print("Generating benchmark problems...", file=sys.stderr)
    problems: dict[int, Problem] = {n: make_bench_problem(n) for n in subproblems}

    all_cells: list[list[CellResult]] = []

    for n in subproblems:
        row: list[CellResult] = []
        prob = problems[n]
        for w in worker_counts:
            cell_num += 1
            elapsed, status, iterations = _time_cell(prob, w, config.repeats, config.timeout)
            cell = CellResult(
                n_blocks=n,
                workers=w,
                elapsed=elapsed,
                status=status,
                iterations=iterations,
            )
            row.append(cell)

            # Progress line to stderr
            elapsed_str = f"{elapsed:.3f}s" if elapsed is not None else "   N/A"
            status_str = status.value if isinstance(status, SolveStatus) else status.value
            print(
                f"[{cell_num:03d}/{total_cells:03d}] n_blocks={n:>2}, workers={w:>2}"
                f" → {elapsed_str:>8}  {status_str}",
                file=sys.stderr,
            )

        all_cells.append(row)

    return BenchMatrix(cells=all_cells, config=config)


def _timed_solve(problem: Problem, workers: int) -> tuple[float, Result]:
    """Run solve() on a worker thread and return (elapsed, result)."""
    t_start = time.perf_counter()
    result = solve(problem, workers=workers)
    elapsed = time.perf_counter() - t_start
    return elapsed, result


def _time_cell(
    problem: Problem,
    workers: int,
    repeats: int,
    timeout: float,
) -> tuple[float | None, SolveStatus | CellError, int | None]:
    """Time one (problem, workers) cell, honouring repeats and timeout.

    Returns:
        (best_elapsed, status, iterations) — best_elapsed is None for errors.
    """
    best_elapsed: float | None = None
    best_status: SolveStatus | CellError = CellError.ERROR
    best_iterations: int | None = None

    for _ in range(max(1, repeats)):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_timed_solve, problem, workers)
            try:
                elapsed, result = future.result(timeout=timeout)
                if best_elapsed is None or elapsed < best_elapsed:
                    best_elapsed = elapsed
                    best_status = result.status
                    best_iterations = result.iterations
            except TimeoutError:
                best_status = CellError.TIMEOUT
                break  # do not retry after a timeout
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[WARN] solve failed (n_blocks=?, workers={workers}): {exc}",
                    file=sys.stderr,
                )
                best_status = CellError.ERROR

    return best_elapsed, best_status, best_iterations
