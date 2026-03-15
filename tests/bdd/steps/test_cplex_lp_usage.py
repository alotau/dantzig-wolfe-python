"""pytest-bdd step implementations for cplex_lp_usage.feature — T005.

Wires the Gherkin scenarios in
``specs/001-gherkin-bdd-specs/features/cplex_lp_usage.feature``
to the CLI entry point via Click's ``CliRunner``.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pytest_bdd import given, parsers, scenarios, then, when

from dwsolver import DWSolverInputError, Problem, solve
from dwsolver.cli import main

# Link all scenarios in the feature file to this module.
scenarios("cplex_lp_usage.feature")

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
_FOUR_SEA_DIR = _FIXTURES_DIR / "four_sea"

# ---------------------------------------------------------------------------
# Minimal CPLEX LP strings reused by library API BDD steps
# ---------------------------------------------------------------------------

_BDD_MASTER_2BLOCK = """\
Minimize
 obj: x1 + 2 x2 + 3 y1 + 4 y2
Subject To
 c1: x1 + y1 <= 10
 c2: x2 + y2 = 5
End
"""

_BDD_SUB_BLOCK0 = """\
Minimize
 obj1: x1 + 2 x2
Subject To
 lc1: x1 - x2 >= 0
Bounds
 0 <= x1 <= 5
 0 <= x2 <= 5
End
"""

_BDD_SUB_BLOCK1 = """\
Minimize
 obj2: 3 y1 + 4 y2
Subject To
 lc2: y1 + y2 <= 4
Bounds
 0 <= y1 <= 3
 0 <= y2 <= 3
End
"""

_BDD_MASTER_EMPTY_SUBJECT_TO = """\
Minimize
 obj: x1
Subject To
End
"""

_BDD_SUB_VALID = """\
Minimize
Subject To
Bounds
 0 <= x1 <= 5
End
"""

_BDD_SUB_EMPTY_BOUNDS = """\
Minimize
Subject To
Bounds
End
"""

_BDD_MASTER_DUP = """\
Minimize
 obj: x1
Subject To
 c1: x1 <= 10
End
"""

_BDD_SUB_DUP = """\
Minimize
Subject To
 c1: x1 >= 0
Bounds
 0 <= x1 <= 5
End
"""

_BDD_MASTER_PHANTOM = """\
Minimize
 obj: phantom_var
Subject To
 c1: phantom_var <= 10
End
"""

_BDD_SUB_KNOWN = """\
Minimize
Subject To
 c1: x1 >= 0
Bounds
 0 <= x1 <= 5
End
"""


# ---------------------------------------------------------------------------
# Shared context fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_ctx() -> dict[str, Any]:
    """Mutable dict shared across BDD steps within a single scenario."""
    return {}


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Invocation helper
# ---------------------------------------------------------------------------


def _invoke(
    runner: CliRunner,
    command_str: str,
    tmp_path: Path,
    shared_ctx: dict[str, Any],
) -> None:
    """Parse *command_str*, resolve file paths, and invoke the CLI.

    Stores the invocation result in ``shared_ctx["result"]`` and the
    expected default output path in ``shared_ctx["output_path"]``.

    LP fixture files under ``four_sea/`` are served from the real fixture
    directory so they are not copied to ``tmp_path`` (they are read-only).
    JSON problem files are copied to ``tmp_path`` so the default solution
    file lands in a temporary location.
    """
    parts = command_str.split()
    if parts and parts[0] == "dwsolver":
        parts = parts[1:]

    args: list[str] = []
    first_positional: Path | None = None
    output_path: Path | None = None

    i = 0
    while i < len(parts):
        part = parts[i]

        if part in ("--output", "-o") and i + 1 < len(parts):
            raw_out = parts[i + 1]
            out_p = Path(raw_out) if Path(raw_out).is_absolute() else tmp_path / raw_out
            args += [part, str(out_p)]
            output_path = out_p
            i += 2

        elif part in ("--workers", "-w", "--tolerance", "-t", "--format") and i + 1 < len(parts):
            args += [part, parts[i + 1]]
            i += 2

        elif not part.startswith("-"):
            # Positional file argument.
            # four_sea fixture files are referenced by relative path like
            # "four_sea/master.cplex".  Try the fixtures directory first.
            src = _FIXTURES_DIR / part
            if src.exists():
                if str(part).startswith("four_sea/"):
                    # Serve directly from fixtures directory — no copy needed.
                    resolved = src
                else:
                    # JSON files: copy to tmp_path so solution file lands there.
                    dst = tmp_path / Path(part).name
                    if not dst.exists():
                        shutil.copy(str(src), str(dst))
                    resolved = dst
            else:
                resolved = tmp_path / Path(part).name

            if first_positional is None:
                first_positional = resolved
            args.append(str(resolved))
            i += 1

        else:
            args.append(part)
            i += 1

    # Determine default output path (used when --output was not given).
    if output_path is None and first_positional is not None:
        stem = first_positional.stem
        output_path = first_positional.parent / f"{stem}.solution.json"

    invocation_result = runner.invoke(main, args)
    shared_ctx["result"] = invocation_result
    shared_ctx["output_path"] = output_path


def _load_solution(shared_ctx: dict[str, Any]) -> dict[str, Any]:
    out_p: Path | None = shared_ctx.get("output_path")
    assert out_p is not None, "output_path not set in shared_ctx"
    assert out_p.exists(), f"Solution file not found: {out_p}"
    return json.loads(out_p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the dwsolver command is available on the PATH")
def given_command_available() -> None:
    """Verified implicitly: tests import dwsolver.cli.main directly."""


# ---------------------------------------------------------------------------
# Given — setup
# ---------------------------------------------------------------------------


@given("the four_sea CPLEX LP fixtures are available")
def given_four_sea_fixtures(shared_ctx: dict[str, Any]) -> None:
    """Confirm that the four_sea fixture directory exists."""
    assert _FOUR_SEA_DIR.exists(), (
        f"four_sea fixtures not found at {_FOUR_SEA_DIR}; run: T001 download step"
    )
    shared_ctx["four_sea_available"] = True


@given(parsers.parse('a valid block-angular LP input file "{filename}"'))
def given_valid_file(filename: str, shared_ctx: dict[str, Any]) -> None:
    shared_ctx["input_filename"] = filename


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('I run "{command}"'))
def when_run(
    command: str,
    shared_ctx: dict[str, Any],
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    _invoke(cli_runner, command, tmp_path, shared_ctx)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("the exit code is {code:d}"))
def then_exit_code(code: int, shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx["result"]
    assert result.exit_code == code, (
        f"Expected exit code {code}, got {result.exit_code}.\n"
        f"Output: {result.output!r}\n"
        f"Exception: {result.exception!r}"
    )


@then("the exit code is non-zero")
def then_exit_nonzero(shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx["result"]
    assert result.exit_code != 0, f"Expected non-zero exit code, got 0.\nOutput: {result.output!r}"


@then(parsers.parse('a solution file "{filename}" is created'))
def then_solution_file_created(filename: str, shared_ctx: dict[str, Any], tmp_path: Path) -> None:
    # Check output_path first; fall back to tmp_path / filename.
    out_p: Path | None = shared_ctx.get("output_path")
    if out_p is None or out_p.name != filename:
        out_p = tmp_path / filename
    assert out_p.exists(), f"Solution file {filename!r} not found at {out_p}"
    shared_ctx["output_path"] = out_p


@then(parsers.parse('the solution file contains status "{status}"'))
def then_solution_status(status: str, shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    assert data.get("status") == status


@then(parsers.parse("the solution file objective is approximately {value:g}"))
def then_solution_objective_approx(value: float, shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    obj = data.get("objective")
    assert obj is not None, "Solution file has no 'objective' field"
    assert abs(obj - value) < 1e-3, f"Expected objective ≈ {value}, got {obj}"


@then("an error message is written to stderr")
def then_error_on_stderr(shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx["result"]
    # Support both configurations:
    # - mix_stderr=True: stderr is merged into result.output
    # - mix_stderr=False: stderr is available as result.stderr
    stderr_text = getattr(result, "stderr", "")
    assert result.output or stderr_text or result.exception, (
        "Expected error output on stderr but got none.\n"
        f"stdout: {result.output!r}\n"
        f"stderr: {stderr_text!r}\n"
        f"exception: {result.exception!r}"
    )
    # Non-zero exit confirms an error was raised.
    assert result.exit_code != 0, (
        f"Expected non-zero exit code for error scenario, got {result.exit_code}"
    )


# ---------------------------------------------------------------------------
# US2 — Library API: When steps
# ---------------------------------------------------------------------------


def _capture_lp(shared_ctx: dict[str, Any], fn: object) -> None:
    """Run *fn*, storing result or exception under ``lp_problem``/``lp_exception``."""
    exc: Exception | None = None
    problem: Problem | None = None
    try:
        problem = fn()  # type: ignore[operator]
    except DWSolverInputError as e:
        exc = e
    shared_ctx["lp_problem"] = problem
    shared_ctx["lp_exception"] = exc


@when("I call Problem.from_lp with the four_sea master and subproblem files")
def when_from_lp_four_sea(shared_ctx: dict[str, Any]) -> None:
    _capture_lp(
        shared_ctx,
        lambda: Problem.from_lp(
            _FOUR_SEA_DIR / "master.cplex",
            [
                _FOUR_SEA_DIR / "subprob_1.cplex",
                _FOUR_SEA_DIR / "subprob_2.cplex",
                _FOUR_SEA_DIR / "subprob_3.cplex",
                _FOUR_SEA_DIR / "subprob_4.cplex",
            ],
        ),
    )


@when("I call Problem.from_lp_text with a simple two-block LP")
def when_from_lp_text_simple(shared_ctx: dict[str, Any]) -> None:
    _capture_lp(
        shared_ctx,
        lambda: Problem.from_lp_text(_BDD_MASTER_2BLOCK, [_BDD_SUB_BLOCK0, _BDD_SUB_BLOCK1]),
    )


@when("I solve the loaded LP problem")
def when_solve_loaded_lp(shared_ctx: dict[str, Any]) -> None:
    problem: Problem | None = shared_ctx.get("lp_problem")
    assert problem is not None, (
        f"No LP problem loaded (exception: {shared_ctx.get('lp_exception')!r})"
    )
    shared_ctx["lp_result"] = solve(problem)


@when("I solve the four_sea problem via from_lp and via from_file")
def when_solve_four_sea_both_formats(shared_ctx: dict[str, Any]) -> None:
    four_sea_json = _FIXTURES_DIR / "ref_four_sea.json"
    if not four_sea_json.exists():
        pytest.skip("ref_four_sea.json fixture not available")
    lp_problem = Problem.from_lp(
        _FOUR_SEA_DIR / "master.cplex",
        [
            _FOUR_SEA_DIR / "subprob_1.cplex",
            _FOUR_SEA_DIR / "subprob_2.cplex",
            _FOUR_SEA_DIR / "subprob_3.cplex",
            _FOUR_SEA_DIR / "subprob_4.cplex",
        ],
    )
    json_problem = Problem.from_file(four_sea_json)
    shared_ctx["lp_obj"] = solve(lp_problem).objective
    shared_ctx["json_obj"] = solve(json_problem).objective


@when("I call Problem.from_lp with a nonexistent master path")
def when_from_lp_nonexistent(shared_ctx: dict[str, Any], tmp_path: Path) -> None:
    exc: Exception | None = None
    try:
        Problem.from_lp(tmp_path / "ghost.cplex", [tmp_path / "ghost_sub.cplex"])
    except DWSolverInputError as e:
        exc = e
    shared_ctx["lp_exception"] = exc


# ---------------------------------------------------------------------------
# US3 — Additional error handling: When steps
# ---------------------------------------------------------------------------


@when("I call Problem.from_lp_text with a master that has an empty Subject To")
def when_from_lp_text_empty_subject_to(shared_ctx: dict[str, Any]) -> None:
    exc: Exception | None = None
    try:
        Problem.from_lp_text(_BDD_MASTER_EMPTY_SUBJECT_TO, [_BDD_SUB_VALID])
    except DWSolverInputError as e:
        exc = e
    shared_ctx["lp_exception"] = exc


@when("I call Problem.from_lp_text with a subproblem that has an empty Bounds section")
def when_from_lp_text_empty_bounds(shared_ctx: dict[str, Any]) -> None:
    exc: Exception | None = None
    try:
        Problem.from_lp_text(_BDD_MASTER_2BLOCK, [_BDD_SUB_EMPTY_BOUNDS])
    except DWSolverInputError as e:
        exc = e
    shared_ctx["lp_exception"] = exc


@when("I call Problem.from_lp_text with two subproblems that share a variable name")
def when_from_lp_text_dup_var(shared_ctx: dict[str, Any]) -> None:
    exc: Exception | None = None
    try:
        Problem.from_lp_text(_BDD_MASTER_DUP, [_BDD_SUB_DUP, _BDD_SUB_DUP])
    except DWSolverInputError as e:
        exc = e
    shared_ctx["lp_exception"] = exc


@when("I call Problem.from_lp_text with a master referencing an undeclared variable")
def when_from_lp_text_phantom(shared_ctx: dict[str, Any]) -> None:
    exc: Exception | None = None
    try:
        Problem.from_lp_text(_BDD_MASTER_PHANTOM, [_BDD_SUB_KNOWN])
    except DWSolverInputError as e:
        exc = e
    shared_ctx["lp_exception"] = exc


# ---------------------------------------------------------------------------
# US2 + US3 — Library API: Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("a Problem object with {n:d} blocks is returned"))
def then_problem_with_n_blocks(n: int, shared_ctx: dict[str, Any]) -> None:
    problem = shared_ctx.get("lp_problem")
    assert problem is not None, (
        f"Expected a Problem but got None (exception: {shared_ctx.get('lp_exception')!r})"
    )
    assert isinstance(problem, Problem)
    assert len(problem.blocks) == n, f"Expected {n} blocks, got {len(problem.blocks)}"


@then(parsers.parse('the Problem block {n:d} has id "{expected_id}"'))
def then_block_has_id(n: int, expected_id: str, shared_ctx: dict[str, Any]) -> None:
    problem: Problem = shared_ctx["lp_problem"]
    actual = problem.blocks[n].block_id
    assert actual == expected_id, f"Expected block {n} id={expected_id!r}, got {actual!r}"


@then(parsers.parse('the LP solve status is "{status}"'))
def then_lp_solve_status(status: str, shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx.get("lp_result")
    assert result is not None, "No LP solve result in context"
    assert result.status == status, f"Expected status={status!r}, got {result.status!r}"


@then(parsers.parse("the LP solve objective is approximately {value:g}"))
def then_lp_solve_objective(value: float, shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx.get("lp_result")
    assert result is not None, "No LP solve result in context"
    obj = result.objective
    assert obj is not None, "Result has no objective value"
    assert abs(obj - value) < 1e-3, f"Expected objective ≈ {value}, got {obj}"


@then("the two solve objectives agree within 1e-6")
def then_objectives_agree(shared_ctx: dict[str, Any]) -> None:
    lp_obj = shared_ctx.get("lp_obj")
    json_obj = shared_ctx.get("json_obj")
    assert lp_obj is not None and json_obj is not None
    assert math.isclose(lp_obj, json_obj, abs_tol=1e-6), (
        f"Objectives differ: LP={lp_obj}, JSON={json_obj}"
    )


@then("a DWSolverInputError is raised from the LP loader")
def then_lp_loader_error(shared_ctx: dict[str, Any]) -> None:
    exc = shared_ctx.get("lp_exception")
    assert exc is not None, "Expected DWSolverInputError to be raised but no exception was caught"
    assert isinstance(exc, DWSolverInputError), (
        f"Expected DWSolverInputError, got {type(exc).__name__}: {exc}"
    )
