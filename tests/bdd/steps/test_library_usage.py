"""pytest-bdd step implementations for library_usage.feature.

Covers T029–T036:
  T029 — Optimal solve scenarios (status, objective, variable_values)
  T030 — Stateless calls (two independent Problem objects → independent Results)
  T031 — Infeasible / unbounded via library
  T032 — workers and tolerance parameters
  T033 — Problem.from_file() via library
  T034 — DWSolverInputError raised for invalid input; importable from top-level
  T035 — Iteration limit returns best feasible solution (partial result)
  T036 — Additional DWSolverInputError trigger paths (in unit tests; here: import check)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from dwsolver import DWSolverInputError, Problem, Result, SolveStatus, solve
from dwsolver.models import (
    Block,
    BlockConstraints,
    Bounds,
    LinkingColumns,
    Master,
)

# Link ALL scenarios in this feature file to this module.
scenarios("library_usage.feature")

# ---------------------------------------------------------------------------
# Path to shared fixtures directory
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers — build Problem objects programmatically
# ---------------------------------------------------------------------------


def _two_block_problem() -> Problem:
    """Two-block, 1-linking-constraint LP.  Known optimal: obj=-9, x1=0, x2=3."""
    return Problem(
        master=Master(constraint_names=["Con1"], rhs=[3.0], senses=["="]),
        blocks=[
            Block(
                block_id="block_0",
                variable_names=["x1"],
                objective=[-2.0],
                bounds=[Bounds(lower=0.0, upper=2.0)],
                constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
                linking_columns=LinkingColumns(rows=[0], cols=[0], values=[1.0]),
            ),
            Block(
                block_id="block_1",
                variable_names=["x2"],
                objective=[-3.0],
                bounds=[Bounds(lower=0.0, upper=3.0)],
                constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
                linking_columns=LinkingColumns(rows=[0], cols=[0], values=[1.0]),
            ),
        ],
    )


def _infeasible_problem() -> Problem:
    """Infeasible: master requires x1+x2=10, but bounds cap sum at 8."""
    return Problem.from_file(_FIXTURES_DIR / "infeasible_problem.json")


def _unbounded_problem() -> Problem:
    """Unbounded block-angular LP."""
    return Problem.from_file(_FIXTURES_DIR / "unbounded_problem.json")


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_ctx() -> dict[str, Any]:
    """Mutable dict passed between BDD steps within one scenario."""
    return {}


# ---------------------------------------------------------------------------
# Given — problem setup
# ---------------------------------------------------------------------------


@given("a Problem object with a valid two-block block-angular structure")
def given_valid_two_block(shared_ctx: dict[str, Any]) -> None:
    shared_ctx["problem"] = _two_block_problem()


@given('a Problem object "problem_a" and a different Problem object "problem_b"')
def given_two_problems(shared_ctx: dict[str, Any]) -> None:
    # problem_a: original two-block LP (min -2x1 - 3x2)
    shared_ctx["problem_a"] = _two_block_problem()
    # problem_b: same topology but different objective (min -x1 - x2)
    shared_ctx["problem_b"] = Problem(
        master=Master(constraint_names=["Con1"], rhs=[3.0], senses=["="]),
        blocks=[
            Block(
                block_id="block_0",
                variable_names=["x1"],
                objective=[-1.0],
                bounds=[Bounds(lower=0.0, upper=2.0)],
                constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
                linking_columns=LinkingColumns(rows=[0], cols=[0], values=[1.0]),
            ),
            Block(
                block_id="block_1",
                variable_names=["x2"],
                objective=[-1.0],
                bounds=[Bounds(lower=0.0, upper=3.0)],
                constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
                linking_columns=LinkingColumns(rows=[0], cols=[0], values=[1.0]),
            ),
        ],
    )


@given("a Problem object describing an infeasible LP")
def given_infeasible_problem(shared_ctx: dict[str, Any]) -> None:
    shared_ctx["problem"] = _infeasible_problem()


@given("a Problem object describing an unbounded LP")
def given_unbounded_problem(shared_ctx: dict[str, Any]) -> None:
    shared_ctx["problem"] = _unbounded_problem()


@given("a Problem object and a Solver configured with a very low iteration limit")
def given_problem_with_low_iter_limit(shared_ctx: dict[str, Any]) -> None:
    # Use the Lasdon problem (4 variables, 2 linking constraints) which requires
    # multiple column-generation iterations and won't converge with max_iterations=1.
    shared_ctx["problem"] = Problem.from_file(_FIXTURES_DIR / "ref_book_lasdon.json")
    shared_ctx["max_iterations"] = 1  # fires ITERATION_LIMIT before convergence


@given("a Problem object that is missing a required structural field")
def given_invalid_problem(shared_ctx: dict[str, Any], tmp_path: Path) -> None:
    """Store a factory that raises DWSolverInputError when we try to load it."""
    bad_file = tmp_path / "missing_fields.json"
    bad_file.write_text(
        json.dumps({"schema_version": "1.0"}),  # missing master and blocks
        encoding="utf-8",
    )
    shared_ctx["invalid_file"] = bad_file
    shared_ctx["problem"] = None


@given(parsers.parse('a valid block-angular LP input file "{filename}"'))
def given_valid_file_for_library(filename: str, shared_ctx: dict[str, Any]) -> None:
    shared_ctx["input_file"] = _FIXTURES_DIR / filename


# ---------------------------------------------------------------------------
# When — solver invocations
# ---------------------------------------------------------------------------


@when("I call solver.solve(problem)")
def when_call_solve(shared_ctx: dict[str, Any]) -> None:
    exc: Exception | None = None
    result: Result | None = None

    if shared_ctx.get("invalid_file") is not None:
        # The "invalid input" scenario: error comes from from_file()
        try:
            Problem.from_file(shared_ctx["invalid_file"])
        except DWSolverInputError as e:
            exc = e
        except Exception as e:
            exc = e
    else:
        problem: Problem = shared_ctx["problem"]
        max_iter: int = shared_ctx.get("max_iterations", 1000)
        try:
            result = solve(problem, max_iterations=max_iter)
        except Exception as e:
            exc = e

    shared_ctx["result"] = result
    shared_ctx["exception"] = exc


@when("I call solver.solve(problem_a) and then solver.solve(problem_b)")
def when_call_solve_two_problems(shared_ctx: dict[str, Any]) -> None:
    shared_ctx["result_a"] = solve(shared_ctx["problem_a"])
    shared_ctx["result_b"] = solve(shared_ctx["problem_b"])


@when("I call solver.solve(problem) and the limit is reached before convergence")
def when_call_solve_with_limit(shared_ctx: dict[str, Any]) -> None:
    max_iter: int = shared_ctx.get("max_iterations", 1)
    result = solve(shared_ctx["problem"], max_iterations=max_iter)
    shared_ctx["result"] = result
    shared_ctx["exception"] = None


_WORKERS_STEP = "I call solver.solve(problem, workers={workers:d}) and record the objective value"


@when(parsers.parse(_WORKERS_STEP))
def when_solve_workers_record(workers: int, shared_ctx: dict[str, Any]) -> None:
    result = solve(shared_ctx["problem"], workers=workers)
    shared_ctx.setdefault("objective_values", []).append(result.objective)


@when(parsers.parse("I call solver.solve(problem, tolerance={tol:g})"))
def when_solve_tolerance(tol: float, shared_ctx: dict[str, Any]) -> None:
    result = solve(shared_ctx["problem"], tolerance=tol)
    shared_ctx["result"] = result
    shared_ctx["exception"] = None


@when(parsers.parse('I import "{symbol}" from "{module}"'))
def when_import_symbol(symbol: str, module: str, shared_ctx: dict[str, Any]) -> None:
    exc: Exception | None = None
    try:
        imported_module = __import__(module, fromlist=[symbol])
        shared_ctx["imported"] = getattr(imported_module, symbol)
    except (ImportError, AttributeError) as e:
        exc = e
    shared_ctx["exception"] = exc


@when(parsers.parse('I call Problem.from_file("{filename}")'))
def when_call_from_file(filename: str, shared_ctx: dict[str, Any]) -> None:
    src = _FIXTURES_DIR / filename
    problem = Problem.from_file(src)
    shared_ctx["problem"] = problem
    shared_ctx["result"] = None


# ---------------------------------------------------------------------------
# Then — result assertions
# ---------------------------------------------------------------------------


@then(parsers.parse('the result status is "{status}"'))
def then_result_status(status: str, shared_ctx: dict[str, Any]) -> None:
    result: Result | None = shared_ctx.get("result")
    assert result is not None, (
        f"Expected a result but got None (exception={shared_ctx.get('exception')!r})"
    )
    assert result.status == status, f"Expected status={status!r}, got {result.status!r}"


@then("the result contains an objective value")
def then_result_has_objective(shared_ctx: dict[str, Any]) -> None:
    result: Result | None = shared_ctx.get("result")
    assert result is not None
    assert result.objective is not None, "Expected non-null objective in result"
    assert math.isfinite(result.objective), f"Expected finite objective, got {result.objective}"


@then("the result contains an objective value for the incumbent solution")
def then_result_has_incumbent_objective(shared_ctx: dict[str, Any]) -> None:
    # Same assertion as 'the result contains an objective value' but phrased for partial results.
    result: Result | None = shared_ctx.get("result")
    assert result is not None
    assert result.objective is not None, (
        "Expected non-null objective value for incumbent solution (iteration_limit result)"
    )
    assert math.isfinite(result.objective), f"Expected finite objective, got {result.objective}"


@then("result.variable_values is a non-empty mapping of variable names to numeric values")
def then_variable_values_non_empty(shared_ctx: dict[str, Any]) -> None:
    result: Result | None = shared_ctx.get("result")
    assert result is not None
    assert isinstance(result.variable_values, dict), "variable_values must be a dict"
    assert len(result.variable_values) > 0, "variable_values must be non-empty for optimal result"
    for name, val in result.variable_values.items():
        assert isinstance(name, str), f"key must be str, got {type(name)}"
        assert isinstance(val, (int, float)), f"value must be numeric, got {type(val)}"


@then("each call returns an independent Result with no shared state")
def then_results_independent(shared_ctx: dict[str, Any]) -> None:
    r_a: Result = shared_ctx["result_a"]
    r_b: Result = shared_ctx["result_b"]
    assert isinstance(r_a, Result)
    assert isinstance(r_b, Result)
    # Results are separate objects
    assert r_a is not r_b
    # variable_values dicts are separate objects
    assert r_a.variable_values is not r_b.variable_values
    # Both should be optimal for these simple problems
    assert r_a.status == SolveStatus.OPTIMAL
    assert r_b.status == SolveStatus.OPTIMAL


@then("both objective values are equal")
def then_lib_objectives_equal(shared_ctx: dict[str, Any]) -> None:
    objs = shared_ctx.get("objective_values", [])
    assert len(objs) == 2, f"Expected 2 recorded objective values, got {objs!r}"
    assert objs[0] is not None and objs[1] is not None
    assert math.isclose(objs[0], objs[1], abs_tol=1e-6), (
        f"Objective values differ: {objs[0]} vs {objs[1]}"
    )


@then("result.variable_values is empty")
def then_variable_values_empty(shared_ctx: dict[str, Any]) -> None:
    result: Result | None = shared_ctx.get("result")
    assert result is not None
    assert result.variable_values == {}, (
        f"Expected empty variable_values, got {result.variable_values!r}"
    )


@then(parsers.parse("result.tolerance is {tol:g}"))
def then_result_tolerance(tol: float, shared_ctx: dict[str, Any]) -> None:
    result: Result | None = shared_ctx.get("result")
    assert result is not None
    assert math.isclose(result.tolerance, tol, rel_tol=1e-9), (
        f"Expected tolerance={tol}, got {result.tolerance}"
    )


@then("the result contains a non-empty diagnostic message")
def then_result_diagnostic(shared_ctx: dict[str, Any]) -> None:
    result: Result | None = shared_ctx.get("result")
    assert result is not None
    info = result.solver_info
    assert isinstance(info, dict) and info.get("message"), (
        f"Expected non-empty solver_info.message, got {info!r}"
    )


# ---------------------------------------------------------------------------
# Then — error / exception assertions
# ---------------------------------------------------------------------------


@then("a DWSolverInputError is raised")
def then_dwsolver_error_raised(shared_ctx: dict[str, Any]) -> None:
    exc = shared_ctx.get("exception")
    assert exc is not None, "Expected DWSolverInputError to be raised, but no exception was stored"
    assert isinstance(exc, DWSolverInputError), (
        f"Expected DWSolverInputError, got {type(exc).__name__}: {exc}"
    )


@then("the exception message identifies the missing or invalid field")
def then_exception_message_informative(shared_ctx: dict[str, Any]) -> None:
    exc = shared_ctx.get("exception")
    assert exc is not None
    msg = str(exc)
    assert len(msg) > 10, f"Exception message too short to be informative: {msg!r}"


@then("the import succeeds without error")
def then_import_succeeds(shared_ctx: dict[str, Any]) -> None:
    exc = shared_ctx.get("exception")
    assert exc is None, f"Import raised an exception: {exc!r}"
    assert shared_ctx.get("imported") is not None, "Imported symbol is None"


# ---------------------------------------------------------------------------
# Then — from_file() assertions
# ---------------------------------------------------------------------------


@then("a Problem object is returned with the correct number of blocks")
def then_problem_has_blocks(shared_ctx: dict[str, Any]) -> None:
    problem: Problem | None = shared_ctx.get("problem")
    assert problem is not None, "Expected a Problem object to be loaded"
    assert isinstance(problem, Problem)
    # simple_two_block.json has exactly 2 blocks
    assert len(problem.blocks) == 2, f"Expected 2 blocks, got {len(problem.blocks)}"


@then("I can pass it directly to solver.solve(problem)")
def then_can_solve_loaded_problem(shared_ctx: dict[str, Any]) -> None:
    problem: Problem | None = shared_ctx.get("problem")
    assert problem is not None
    result = solve(problem)
    assert result.status == SolveStatus.OPTIMAL
    shared_ctx["result"] = result
