"""Command-line interface for dwsolver.

Full implementation in Phase 3 (T019).
This stub satisfies the public API and mypy strict-mode imports.
"""

from __future__ import annotations

import click


@click.command()
@click.argument("problem_file", type=click.Path(exists=False))
@click.option("--output", "-o", default=None, help="Output path (default: <input>.solution.json)")
@click.option("--workers", "-w", default=None, type=int, help="Parallel subproblem workers")
@click.option(
    "--tolerance",
    "-t",
    default=1e-6,
    type=float,
    show_default=True,
    help="Convergence tolerance",
)
def main(
    problem_file: str,
    output: str | None,
    workers: int | None,
    tolerance: float,
) -> None:
    """Solve a block-angular LP using Dantzig-Wolfe decomposition.

    PROBLEM_FILE is the path to a dwsolver JSON input file.
    The solution is written to PROBLEM_FILE.solution.json by default.
    """
    raise NotImplementedError("CLI implemented in T019")
