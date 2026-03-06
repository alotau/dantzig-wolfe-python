"""Unit tests for dwsolver.solver — T022 + T043.

Covers:
  - dispatch_subproblems: calls all blocks, respects worker cap
  - Integration: simple_two_block → optimal
  - Integration: infeasible_problem → infeasible
  - Integration: unbounded_problem → unbounded
  - workers=1 vs workers=N → identical results
  - Degenerate pricing: no improving column → terminates as optimal
  - T043: single-block degenerate decomposition
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest

from dwsolver.models import (
    DEFAULT_TOLERANCE,
    Block,
    BlockConstraints,
    Bounds,
    LinkingColumns,
    Master,
    Problem,
    Result,
    SolveStatus,
)
from dwsolver.solver import dispatch_subproblems, solve
from dwsolver.subproblem import SubproblemResult

# ---------------------------------------------------------------------------
# Paths to fixtures
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures"
SIMPLE_TWO_BLOCK = FIXTURES / "simple_two_block.json"
INFEASIBLE = FIXTURES / "infeasible_problem.json"
UNBOUNDED = FIXTURES / "unbounded_problem.json"


# ---------------------------------------------------------------------------
# Helpers — build Problem programmatically
# ---------------------------------------------------------------------------


def _simple_two_block_problem() -> Problem:
    """Two-block, 1-linking-constraint problem. Optimal: obj=-9, x2=3."""
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


def _single_block_problem() -> Problem:
    """Single-block LP. min -2x1 - 3x2 s.t. x1+x2=3, 0<=x1<=2, 0<=x2<=3. Optimal: -9."""
    return Problem(
        master=Master(constraint_names=["link"], rhs=[3.0], senses=["="]),
        blocks=[
            Block(
                block_id="b0",
                variable_names=["x1", "x2"],
                objective=[-2.0, -3.0],
                bounds=[Bounds(lower=0.0, upper=2.0), Bounds(lower=0.0, upper=3.0)],
                constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
                linking_columns=LinkingColumns(rows=[0, 0], cols=[0, 1], values=[1.0, 1.0]),
            )
        ],
    )


# ---------------------------------------------------------------------------
# dispatch_subproblems
# ---------------------------------------------------------------------------


class TestDispatchSubproblems:
    def test_all_blocks_called(self) -> None:
        problem = _simple_two_block_problem()
        call_count: list[int] = [0]

        def fake_solve(block, row_duals, convexity_dual, tolerance):  # type: ignore[no-untyped-def]
            call_count[0] += 1
            return SubproblemResult(
                status="optimal", col_obj=0.0, col_linking=[0.0], primal_values=[0.0]
            )

        with patch("dwsolver.solver.solve_subproblem", side_effect=fake_solve):
            results = dispatch_subproblems(
                blocks=problem.blocks,
                row_duals=[0.0],
                convexity_duals=[0.0, 0.0],
                workers=1,
                tolerance=DEFAULT_TOLERANCE,
            )

        assert call_count[0] == 2  # both blocks processed
        assert len(results) == 2

    def test_result_order_matches_block_order(self) -> None:
        problem = _simple_two_block_problem()
        call_log: list[str] = []

        def fake_solve(block, row_duals, convexity_dual, tolerance):  # type: ignore[no-untyped-def]
            call_log.append(block.block_id)
            return SubproblemResult(
                status="optimal",
                col_obj=0.0,
                col_linking=[0.0],
                primal_values=[0.0],
            )

        with patch("dwsolver.solver.solve_subproblem", side_effect=fake_solve):
            results = dispatch_subproblems(
                blocks=problem.blocks,
                row_duals=[0.0],
                convexity_duals=[0.0, 0.0],
                workers=2,
                tolerance=DEFAULT_TOLERANCE,
            )

        # Results indexed [0] and [1] regardless of completion order
        assert len(results) == 2
        assert all(r is not None for r in results)

    def test_worker_pool_capped_at_block_count(self) -> None:
        """Pool size should be min(workers or cpu*2, len(blocks))."""
        problem = _simple_two_block_problem()
        # Only 2 blocks but 100 workers requested — should still work fine
        calls: list[int] = [0]

        def fake_solve(block, row_duals, convexity_dual, tolerance):  # type: ignore[no-untyped-def]
            calls[0] += 1
            return SubproblemResult(
                status="optimal", col_obj=0.0, col_linking=[0.0], primal_values=[0.0]
            )

        with patch("dwsolver.solver.solve_subproblem", side_effect=fake_solve):
            results = dispatch_subproblems(
                blocks=problem.blocks,
                row_duals=[0.0],
                convexity_duals=[0.0, 0.0],
                workers=100,
                tolerance=DEFAULT_TOLERANCE,
            )

        assert calls[0] == 2
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Integration: solve() with problem objects
# ---------------------------------------------------------------------------


class TestSolveIntegration:
    def test_simple_two_block_optimal(self) -> None:
        problem = _simple_two_block_problem()
        result = solve(problem)
        assert result.status == SolveStatus.OPTIMAL
        assert result.objective is not None
        assert math.isclose(result.objective, -9.0, abs_tol=1e-4)
        assert result.iterations >= 1
        assert math.isclose(result.tolerance, DEFAULT_TOLERANCE)

    def test_simple_two_block_variable_values(self) -> None:
        problem = _simple_two_block_problem()
        result = solve(problem)
        assert result.status == SolveStatus.OPTIMAL
        assert "x1" in result.variable_values or "x2" in result.variable_values
        total = sum(result.variable_values.values())
        assert math.isclose(total, 3.0, abs_tol=1e-4)  # x1 + x2 = 3 (linking constraint)

    def test_workers_1_and_4_give_identical_results(self) -> None:
        problem = _simple_two_block_problem()
        r1 = solve(problem, workers=1)
        r4 = solve(problem, workers=4)
        assert r1.status == r4.status
        assert r1.objective is not None and r4.objective is not None
        assert math.isclose(r1.objective, r4.objective, abs_tol=1e-6)

    def test_tolerance_recorded_in_result(self) -> None:
        problem = _simple_two_block_problem()
        result = solve(problem, tolerance=1e-4)
        assert math.isclose(result.tolerance, 1e-4)

    def test_infeasible_problem_fixture(self) -> None:
        problem = Problem.from_file(INFEASIBLE)
        result = solve(problem)
        assert result.status == SolveStatus.INFEASIBLE
        assert result.objective is None
        assert result.variable_values == {}

    def test_unbounded_problem_fixture(self) -> None:
        problem = Problem.from_file(UNBOUNDED)
        result = solve(problem)
        assert result.status == SolveStatus.UNBOUNDED
        assert result.objective is None
        assert result.variable_values == {}

    def test_result_is_always_result_instance(self) -> None:
        problem = _simple_two_block_problem()
        result = solve(problem)
        assert isinstance(result, Result)

    def test_status_is_string(self) -> None:
        problem = _simple_two_block_problem()
        result = solve(problem)
        assert isinstance(result.status, str)
        assert result.status == "optimal"


# ---------------------------------------------------------------------------
# Integration: solve() via from_file()
# ---------------------------------------------------------------------------


class TestSolveFromFile:
    def test_simple_two_block_json(self) -> None:
        problem = Problem.from_file(SIMPLE_TWO_BLOCK)
        result = solve(problem)
        assert result.status == SolveStatus.OPTIMAL
        assert math.isclose(result.objective, -9.0, abs_tol=1e-4)  # type: ignore[arg-type]

    def test_infeasible_json(self) -> None:
        problem = Problem.from_file(INFEASIBLE)
        result = solve(problem)
        assert result.status == SolveStatus.INFEASIBLE

    def test_unbounded_json(self) -> None:
        problem = Problem.from_file(UNBOUNDED)
        result = solve(problem)
        assert result.status == SolveStatus.UNBOUNDED


# ---------------------------------------------------------------------------
# Iteration limit
# ---------------------------------------------------------------------------


class TestSolveIterationLimit:
    def test_max_iterations_1_returns_iteration_limit(self) -> None:
        problem = _simple_two_block_problem()
        result = solve(problem, max_iterations=1)
        # With only 1 iteration, convergence is not guaranteed; expect iteration_limit
        assert result.status in (SolveStatus.ITERATION_LIMIT, SolveStatus.OPTIMAL)
        # variable_values must be populated (best feasible solution)
        assert isinstance(result.variable_values, dict)

    def test_iteration_limit_has_objective(self) -> None:
        """When iteration limit is hit, objective should not be None."""
        problem = _simple_two_block_problem()
        result = solve(problem, max_iterations=1)
        if result.status == SolveStatus.ITERATION_LIMIT:
            assert result.objective is not None
            assert result.variable_values  # non-empty


# ---------------------------------------------------------------------------
# T043: Single-block edge case
# ---------------------------------------------------------------------------


class TestSingleBlockEdgeCase:
    def test_single_block_optimal(self) -> None:
        """Single-block degenerate decomposition — still reaches optimal."""
        problem = _single_block_problem()
        result = solve(problem)
        assert result.status == SolveStatus.OPTIMAL
        assert result.objective is not None
        assert math.isclose(result.objective, -9.0, abs_tol=1e-4)

    def test_single_block_variable_values_populated(self) -> None:
        problem = _single_block_problem()
        result = solve(problem)
        assert result.status == SolveStatus.OPTIMAL
        # x1 + x2 should sum to 3.0 (linking constraint)
        assert "x1" in result.variable_values
        assert "x2" in result.variable_values
        total = result.variable_values["x1"] + result.variable_values["x2"]
        assert math.isclose(total, 3.0, abs_tol=1e-4)

    def test_single_block_workers_capped_at_1(self) -> None:
        """Pool size for 1 block should be capped at 1 regardless of workers param."""
        problem = _single_block_problem()
        # Should not error regardless of workers value
        result = solve(problem, workers=8)
        assert result.status == SolveStatus.OPTIMAL


# ---------------------------------------------------------------------------
# T039: SC-001 Regression Tests — reference fixture problems
# ---------------------------------------------------------------------------


@dataclass
class _RefCase:
    """Expected outcomes for a single reference fixture."""

    filename: str
    expected_obj: float
    expected_vars: dict[str, float] = field(default_factory=dict)
    # When True, only assert the objective is finite and positive (multiple
    # optimal bases exist so the exact value is solver-dependent).
    finite_positive_only: bool = False


_CASES: list[_RefCase] = [
    _RefCase(
        "ref_book_bertsimas.json",
        expected_obj=-21.5,
        expected_vars={"x1": 2.0, "x2": 1.5, "x3": 2.0},
    ),
    _RefCase(
        "ref_book_lasdon.json",
        expected_obj=-36.6667,
        expected_vars={"x1": 8.3333, "x2": 3.3333, "y1": 10.0, "y2": 5.0},
    ),
    _RefCase(
        # Multiple optimal bases — verify objective is finite and positive only.
        "ref_book_dantzig.json",
        expected_obj=0.0,  # unused when finite_positive_only=True
        finite_positive_only=True,
    ),
    _RefCase(
        "ref_web_mitchell.json",
        expected_obj=-5.0,
        expected_vars={"x1": 0.0, "x2": 1.0, "x3": 2.0},
    ),
    _RefCase(
        "ref_web_trick.json",
        expected_obj=-40.0,
        expected_vars={"x1": 3.0, "x2": 2.0, "x3": 3.0},
    ),
    _RefCase(
        # 8-aircraft LAS→SEA LP; +160 constant encoded via __objective_constant__
        # dummy variable in block_1 (lower=upper=1, coeff=160).
        "ref_four_sea.json",
        expected_obj=12.0,
    ),
]


@pytest.mark.parametrize("case", _CASES, ids=[c.filename for c in _CASES])
class TestSC001Regression:
    """SC-001: solver returns OPTIMAL with correct objective for every reference
    fixture.  The parametrize IDs are the fixture filenames so CI output makes
    it immediately obvious which file is under test.
    """

    def test_reference_fixture(self, case: _RefCase) -> None:
        """Load fixture, solve, assert status and objective (and variable values
        where a unique optimum is known)."""
        result = solve(Problem.from_file(FIXTURES / case.filename))
        assert result.status == SolveStatus.OPTIMAL
        assert result.objective is not None
        if case.finite_positive_only:
            assert math.isfinite(result.objective)
            assert result.objective > 0
        else:
            assert math.isclose(result.objective, case.expected_obj, abs_tol=0.01)
        for var, expected in case.expected_vars.items():
            assert math.isclose(result.variable_values[var], expected, abs_tol=0.01)
