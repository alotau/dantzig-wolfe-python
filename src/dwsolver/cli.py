"""Command-line interface for dwsolver — T011/T020.

Entry point: ``dwsolver [OPTIONS] FILES...``

Accepts either a single JSON problem file or a master + subproblem CPLEX LP
file set.  Format is auto-detected from the first file's extension unless
``--format`` overrides it.

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

_LP_EXTENSIONS = frozenset({".lp", ".cplex"})


def _detect_format(files: tuple[str, ...], fmt: str | None) -> str:
    """Return ``"json"`` or ``"lp"`` based on ``--format`` or file extension.

    Raises ``DWSolverInputError`` for unknown extensions or invalid argument
    combinations (e.g. single LP file without ``--format json``).
    """
    if fmt == "json":
        return "json"
    if fmt == "lp":
        return "lp"

    # Auto-detect from first file's extension.
    first_ext = Path(files[0]).suffix.lower()
    if first_ext == ".json":
        return "json"
    if first_ext in _LP_EXTENSIONS:
        if len(files) == 1:
            raise DWSolverInputError(
                f"Single CPLEX LP file provided ({files[0]!r}). "
                "LP format requires a master file and at least one subproblem file. "
                "To load a JSON problem, use --format json."
            )
        return "lp"

    raise DWSolverInputError(
        f"Cannot determine input format from extension {first_ext!r}. "
        "Use --format json or --format lp."
    )


@click.command()
@click.argument("files", nargs=-1, required=True)
@click.option(
    "--format",
    "fmt",
    default=None,
    type=click.Choice(["json", "lp"]),
    help="Override input format detection (json or lp).",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output path (default: <first file stem>.solution.json)",
)
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
    files: tuple[str, ...],
    fmt: str | None,
    output: str | None,
    workers: int | None,
    tolerance: float,
) -> None:
    """Solve a block-angular LP using Dantzig-Wolfe decomposition.

    FILES is one JSON problem file, or a master CPLEX LP file followed by one
    or more subproblem CPLEX LP files.  Format is auto-detected from the first
    file's extension (.json → JSON, .lp/.cplex → CPLEX LP).

    The solution is written to <first-file-stem>.solution.json by default.
    """
    try:
        detected = _detect_format(files, fmt)
        if detected == "json":
            problem = Problem.from_file(files[0])
        else:
            problem = Problem.from_lp(files[0], list(files[1:]))
    except DWSolverInputError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    result = solve(problem, workers=workers, tolerance=tolerance)

    first = Path(files[0])
    out_path = str(first.parent / f"{first.stem}.solution.json") if output is None else output
    try:
        Path(out_path).write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
    except OSError as exc:
        click.echo(f"Cannot write output: {exc}", err=True)
        sys.exit(1)
