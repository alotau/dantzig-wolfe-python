"""pytest-bdd step implementations for cli_usage.feature — T021.

Note on "dwsolver solve FILE" vs flat CLI
-----------------------------------------
The Gherkin feature was written before the CLI contract was finalised.
The contract (contracts/cli_api.md) specifies a flat command:

    dwsolver [OPTIONS] PROBLEM_FILE

not a subcommand.  The helper ``_invoke`` strips the ``"solve"`` token
from the command string so every "When I run ..." step works correctly
against the flat CLI entry point.

Thread safety
-------------
Each test invocation uses Click's ``CliRunner`` in isolation.
``mix_stderr=False`` gives separate access to stdout and stderr.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pytest_bdd import given, parsers, scenarios, then, when

from dwsolver.cli import main

# Link all scenarios in this feature file to this module.
scenarios("cli_usage.feature")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


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
    """Parse *command_str*, resolve paths, and invoke the CLI entry point.

    Stores the result in ``shared_ctx["result"]`` and the path of the
    default output file (if ``--output`` was not given) in
    ``shared_ctx["output_path"]``.
    """
    parts = command_str.split()

    # Strip the "dwsolver" stem
    if parts and parts[0] == "dwsolver":
        parts = parts[1:]

    # Strip the "solve" stub token (not a real subcommand in the flat API)
    if parts and parts[0] == "solve":
        parts = parts[1:]

    args: list[str] = []
    problem_path: Path | None = None
    output_path: Path | None = None

    i = 0
    while i < len(parts):
        part = parts[i]

        if part in ("--output", "-o") and i + 1 < len(parts):
            raw_out = parts[i + 1]
            # Preserve absolute paths (e.g. /nonexistent_dir/out.json) so
            # the unwritable-output scenario can test error behaviour.
            out_p = Path(raw_out) if Path(raw_out).is_absolute() else tmp_path / raw_out
            args += [part, str(out_p)]
            output_path = out_p
            i += 2

        elif part in ("--workers", "-w", "--tolerance", "-t") and i + 1 < len(parts):
            args += [part, parts[i + 1]]
            i += 2

        elif part in ("--verbose", "-v"):
            args.append(part)
            i += 1

        elif not part.startswith("-"):
            # Positional: problem file.  Try to resolve against the fixtures
            # directory; if the fixture exists, copy it to *tmp_path* so the
            # default solution file is also written there (not into the repo).
            src = _FIXTURES_DIR / part
            if src.exists():
                dst = tmp_path / part
                if not dst.exists():
                    shutil.copy(str(src), str(dst))
                problem_path = dst
            else:
                # Non-existent file (e.g. "nonexistent_file.json") — pass the
                # path inside *tmp_path* so it's guaranteed not to exist.
                problem_path = tmp_path / part
            args.append(str(problem_path))
            i += 1

        else:
            args.append(part)
            i += 1

    # Record the expected default output path (used when --output not given)
    if output_path is None and problem_path is not None:
        # CLI uses stem + ".solution.json", e.g. problem.json → problem.solution.json
        stem = problem_path.stem
        output_path = problem_path.parent / f"{stem}.solution.json"

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
    """Verified implicitly: the test imports dwsolver.cli.main directly."""


# ---------------------------------------------------------------------------
# Given — problem file setup
# ---------------------------------------------------------------------------


@given(parsers.parse('a valid block-angular LP input file "{filename}"'))
def given_valid_file(filename: str, shared_ctx: dict[str, Any]) -> None:
    shared_ctx["input_filename"] = filename


@given(parsers.parse('a "{status}" LP input file "{filename}"'))
def given_status_file(status: str, filename: str, shared_ctx: dict[str, Any]) -> None:
    shared_ctx["input_filename"] = filename


@given(parsers.parse('a malformed input file "{filename}" that is not a valid problem schema'))
def given_malformed_file(filename: str, tmp_path: Path, shared_ctx: dict[str, Any]) -> None:
    """Write a syntactically valid JSON file that fails schema validation."""
    bad = tmp_path / filename
    bad.write_text(json.dumps({"this": "is not a valid problem"}), encoding="utf-8")
    shared_ctx["input_filename"] = filename
    shared_ctx["_malformed_path"] = bad  # already placed in tmp_path


# ---------------------------------------------------------------------------
# When — CLI invocations
# ---------------------------------------------------------------------------


@when(parsers.parse('I run "{command}"'))
def when_run(
    command: str,
    shared_ctx: dict[str, Any],
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    _invoke(cli_runner, command, tmp_path, shared_ctx)


@when(parsers.parse('I run "{command}" and record the objective value'))
def when_run_and_record(
    command: str,
    shared_ctx: dict[str, Any],
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    _invoke(cli_runner, command, tmp_path, shared_ctx)
    data = _load_solution(shared_ctx)
    shared_ctx.setdefault("objective_values", []).append(data.get("objective"))


# ---------------------------------------------------------------------------
# Then — exit code assertions
# ---------------------------------------------------------------------------


@then("the exit code is 0")
def then_exit_zero(shared_ctx: dict[str, Any]) -> None:
    assert shared_ctx["result"].exit_code == 0, (
        f"Expected exit 0, got {shared_ctx['result'].exit_code}\n"
        f"stdout: {shared_ctx['result'].output}\n"
        f"stderr: {getattr(shared_ctx['result'], 'stderr_bytes', b'').decode(errors='replace')}"
    )


@then("the exit code is non-zero")
def then_exit_nonzero(shared_ctx: dict[str, Any]) -> None:
    assert shared_ctx["result"].exit_code != 0, (
        f"Expected non-zero exit, got 0\nstdout: {shared_ctx['result'].output}"
    )


# ---------------------------------------------------------------------------
# Then — output file assertions
# ---------------------------------------------------------------------------


@then(parsers.parse('a solution file "{filename}" is created'))
def then_solution_file_created(
    filename: str,
    shared_ctx: dict[str, Any],
    tmp_path: Path,
) -> None:
    # The solution file lives next to the copied input in tmp_path.
    solution_path = tmp_path / filename
    # If the output was explicitly set via --output it is already tracked.
    # Fall back to discovering it from tmp_path when the name matches a known pattern.
    if not solution_path.exists():
        # Maybe it was written next to the input file copy
        candidate = shared_ctx.get("output_path")
        if candidate and Path(candidate).name == filename:
            solution_path = Path(candidate)
    assert solution_path.exists(), (
        f"Solution file '{filename}' not found in {tmp_path}\n"
        f"Files present: {list(tmp_path.iterdir())}"
    )
    # Update tracked path for subsequent Then steps
    shared_ctx["output_path"] = solution_path


@then(parsers.parse('the solution file contains status "{status}"'))
def then_solution_status(status: str, shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    assert data.get("status") == status, f"Expected status={status!r}, got {data.get('status')!r}"


@then("the solution file contains the optimal objective value")
def then_solution_objective(shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    assert data.get("objective") is not None, "Expected non-null objective value"
    # For simple_two_block.json the known optimal is –9.0 ± small tolerance
    assert abs(data["objective"] - (-9.0)) < 1e-3, (
        f"Expected objective ≈ -9.0, got {data['objective']}"
    )


@then("the solution file contains a non-empty mapping of variable names to values")
def then_solution_var_mapping(shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    var_values = data.get("variable_values", {})
    assert isinstance(var_values, dict) and len(var_values) > 0, (
        f"Expected non-empty variable_values, got: {var_values!r}"
    )


@then("the solution file contains a non-empty diagnostic message")
def then_solution_diagnostic(shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    info = data.get("solver_info", {})
    assert isinstance(info, dict) and info.get("message"), (
        f"Expected non-empty solver_info.message, got: {info!r}"
    )


@then("the solution file does not contain variable assignments")
def then_no_variable_assignments(shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    var_values = data.get("variable_values", {})
    assert len(var_values) == 0, (
        f"Expected empty variable_values for infeasible/unbounded, got: {var_values!r}"
    )


@then(parsers.parse("the solution file records the tolerance value {tol:g}"))
def then_tolerance_recorded(tol: float, shared_ctx: dict[str, Any]) -> None:
    data = _load_solution(shared_ctx)
    recorded = data.get("tolerance")
    assert recorded is not None, "Expected 'tolerance' key in solution file"
    assert abs(float(recorded) - tol) < 1e-12, f"Expected tolerance={tol}, got {recorded}"


# ---------------------------------------------------------------------------
# Then — stderr / error assertions
# ---------------------------------------------------------------------------


@then("an error message is written to stderr")
def then_stderr_has_message(shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx["result"]
    stderr = result.stderr or ""
    assert stderr.strip(), "Expected non-empty error output on stderr"


@then("an error message is written to stderr mentioning the missing file")
def then_stderr_mentions_missing(shared_ctx: dict[str, Any]) -> None:
    result = shared_ctx["result"]
    stderr = result.stderr or ""
    assert stderr.strip(), "Expected non-empty error output mentioning missing file on stderr"


@then("no solution file is created")
def then_no_solution_file(shared_ctx: dict[str, Any], tmp_path: Path) -> None:
    # Check that no .solution.json files appear in tmp_path
    solution_files = list(tmp_path.glob("*.solution.json"))
    assert len(solution_files) == 0, f"Expected no solution files but found: {solution_files}"


# ---------------------------------------------------------------------------
# Then — multi-invocation comparisons
# ---------------------------------------------------------------------------


@then("both objective values are equal")
def then_both_objectives_equal(shared_ctx: dict[str, Any]) -> None:
    objs = shared_ctx.get("objective_values", [])
    assert len(objs) == 2, f"Expected 2 recorded objective values, got: {objs!r}"
    assert abs(objs[0] - objs[1]) < 1e-6, f"Objective values differ: {objs[0]} vs {objs[1]}"


@then("solver diagnostic lines are written to the output")
def then_verbose_diagnostics(shared_ctx: dict[str, Any]) -> None:
    """Verbose mode emits per-iteration DW diagnostic lines to stderr.

    With ``mix_stderr=False`` we must read diagnostics from ``result.stderr``.
    """
    result = shared_ctx["result"]
    stderr = result.stderr or ""
    assert "DW" in stderr, f"Expected DW diagnostic lines in CLI stderr output, got: {stderr!r}"
