"""Command-line interface for dwsolver — T019.

Entry point: ``dwsolver [OPTIONS] PROBLEM_FILE``

Exit codes:
    0  — solver ran successfully (optimal, infeasible, unbounded, or iteration limit)
    1  — tool failure (bad input file, I/O error, etc.)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from dwsolver.models import DEFAULT_TOLERANCE, DWSolverInputError, Problem
from dwsolver.solver import solve


@click.command()
@click.argument("problem_file", type=click.Path(exists=False))
@click.option("--output", "-o", default=None, help="Output path (default: <input>.solution.json)")
@click.option("--workers", "-w", default=None, type=int, help="Parallel subproblem workers")
@click.option(
    "--tolerance",
    "-t",
    default=DEFAULT_TOLERANCE,
    type=float,
    show_default=True,
    help="DW convergence tolerance",
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
    try:
        problem = Problem.from_file(problem_file)
    except DWSolverInputError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    result = solve(problem, workers=workers, tolerance=tolerance)

    # Default output: strip the input extension, append .solution.json
    # e.g. "problem.json" → "problem.solution.json"
    if output is None:
        stem = Path(problem_file).stem
        out_path = str(Path(problem_file).parent / f"{stem}.solution.json")
    else:
        out_path = output
    try:
        Path(out_path).write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
    except OSError as exc:
        click.echo(f"Cannot write output: {exc}", err=True)
        sys.exit(1)
