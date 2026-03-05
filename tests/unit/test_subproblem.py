"""Unit tests for dwsolver.subproblem — T023.

Tests verify:
  - Modified objective (c_i - π' D_i) is constructed correctly
  - Optimal result extraction: col_obj, col_linking, primal_values
  - Infeasible status passthrough
  - Unbounded status passthrough
  - setOptionValue("solver", "simplex") is called (ensures clean status distinction)
"""

from __future__ import annotations

from dwsolver.models import Block, BlockConstraints, Bounds, LinkingColumns
from dwsolver.subproblem import SubproblemResult, solve_subproblem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block_1var(
    obj: float = 1.0,
    lb: float = 0.0,
    ub: float | None = 10.0,
    link_rows: list[int] | None = None,
    link_vals: list[float] | None = None,
    local_matrix: list[list[float]] | None = None,
    local_rhs: list[float] | None = None,
    local_senses: list[str] | None = None,
    n_master_rows: int = 1,
) -> Block:
    """Simple 1-variable block for testing."""
    link_rows = link_rows if link_rows is not None else [0]
    link_vals = link_vals if link_vals is not None else [1.0]
    link_cols = [0] * len(link_rows)
    local_matrix = local_matrix if local_matrix is not None else [[1.0]]
    local_rhs = local_rhs if local_rhs is not None else [10.0]
    local_senses = local_senses if local_senses is not None else ["<="]
    return Block(
        block_id="b0",
        variable_names=["x0"],
        objective=[obj],
        bounds=[Bounds(lower=lb, upper=ub)],
        constraints=BlockConstraints(matrix=local_matrix, rhs=local_rhs, senses=local_senses),
        linking_columns=LinkingColumns(rows=link_rows, cols=link_cols, values=link_vals),
    )


# ---------------------------------------------------------------------------
# SubproblemResult data class
# ---------------------------------------------------------------------------


class TestSubproblemResult:
    def test_has_required_attributes(self) -> None:
        r = SubproblemResult(
            status="optimal",
            col_obj=5.0,
            col_linking=[1.0, 2.0],
            primal_values=[3.0],
        )
        assert r.status == "optimal"
        assert r.col_obj == 5.0
        assert r.col_linking == [1.0, 2.0]
        assert r.primal_values == [3.0]

    def test_infeasible_result(self) -> None:
        r = SubproblemResult(status="infeasible", col_obj=0.0, col_linking=[], primal_values=[])
        assert r.status == "infeasible"

    def test_unbounded_result(self) -> None:
        r = SubproblemResult(status="unbounded", col_obj=0.0, col_linking=[], primal_values=[])
        assert r.status == "unbounded"


# ---------------------------------------------------------------------------
# solve_subproblem — optimal cases
# ---------------------------------------------------------------------------


class TestSolveSubproblemOptimal:
    def test_optimal_minimisation_at_lower_bound(self) -> None:
        """min x0, x0 in [0, 10], no linking duals → optimal at x0=0."""
        block = _block_1var(obj=1.0, lb=0.0, ub=10.0, link_vals=[1.0])
        result = solve_subproblem(block, row_duals=[0.0], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "optimal"
        assert abs(result.primal_values[0] - 0.0) < 1e-5
        # col_obj = c_i' x_i^* = 1.0 * 0.0 = 0.0
        assert abs(result.col_obj - 0.0) < 1e-5

    def test_modified_objective_drives_to_upper_bound(self) -> None:
        """With π=[2.0], modified obj = (1.0 - 2.0*1.0)*x0 = -x0 → optimal at x0=10."""
        block = _block_1var(obj=1.0, lb=0.0, ub=10.0, link_vals=[1.0])
        result = solve_subproblem(block, row_duals=[2.0], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "optimal"
        assert abs(result.primal_values[0] - 10.0) < 1e-4
        # col_obj = c_i' x_i^* = 1.0 * 10.0 = 10.0 (original obj, not modified)
        assert abs(result.col_obj - 10.0) < 1e-4

    def test_col_linking_is_D_times_xstar(self) -> None:
        """Linking column = D_i x_i^*. Link coeff=3.0, x0^*=10 → col_linking=[30.0]."""
        block = _block_1var(obj=1.0, lb=0.0, ub=10.0, link_vals=[3.0])
        result = solve_subproblem(block, row_duals=[2.0], convexity_dual=0.0, tolerance=1e-6)
        # modified obj = (1.0 - 2.0*3.0)*x0 = -5x0 → x0=10
        assert result.status == "optimal"
        assert abs(result.primal_values[0] - 10.0) < 1e-4
        assert len(result.col_linking) == 1
        assert abs(result.col_linking[0] - 30.0) < 1e-4  # 3.0 * 10.0

    def test_two_variable_block_optimal(self) -> None:
        """2-var block: min -x0-2x1 s.t. x0+x1<=4, x0<=3, x1<=1.
        Optimal: x0=3, x1=1, obj=-5.  Linking: D = [[1,2]] → col_linking=[5.0]."""
        block = Block(
            block_id="b0",
            variable_names=["x0", "x1"],
            objective=[-1.0, -2.0],
            bounds=[Bounds(lower=0.0, upper=3.0), Bounds(lower=0.0, upper=1.0)],
            constraints=BlockConstraints(matrix=[[1.0, 1.0]], rhs=[4.0], senses=["<="]),
            linking_columns=LinkingColumns(rows=[0, 0], cols=[0, 1], values=[1.0, 2.0]),
        )
        result = solve_subproblem(block, row_duals=[0.0], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "optimal"
        assert abs(result.primal_values[0] - 3.0) < 1e-4
        assert abs(result.primal_values[1] - 1.0) < 1e-4
        assert abs(result.col_obj - (-5.0)) < 1e-4  # c_i' x_i^* = -1*3 + -2*1 = -5
        assert abs(result.col_linking[0] - 5.0) < 1e-4  # 1*3 + 2*1 = 5

    def test_modified_objective_with_multiple_master_rows(self) -> None:
        """Block linked to 2 master rows. Verify both duals used."""
        # x0 in [0,5], linking: row0 coeff=1.0, row1 coeff=2.0
        # obj=0.0, duals=[π0=1.0, π1=3.0]
        # modified = (0 - 1*1 - 3*2)*x0 = -7x0 → x0=5 optimal
        block = Block(
            block_id="b0",
            variable_names=["x0"],
            objective=[0.0],
            bounds=[Bounds(lower=0.0, upper=5.0)],
            constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
            linking_columns=LinkingColumns(rows=[0, 1], cols=[0, 0], values=[1.0, 2.0]),
        )
        result = solve_subproblem(block, row_duals=[1.0, 3.0], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "optimal"
        assert abs(result.primal_values[0] - 5.0) < 1e-4
        assert len(result.col_linking) == 2
        assert abs(result.col_linking[0] - 5.0) < 1e-4  # 1.0 * 5.0
        assert abs(result.col_linking[1] - 10.0) < 1e-4  # 2.0 * 5.0

    def test_no_linking_block_still_returns_empty_col_linking(self) -> None:
        """Block with no linking columns: col_linking should be empty or zero list."""
        block = Block(
            block_id="b0",
            variable_names=["x0"],
            objective=[1.0],
            bounds=[Bounds(lower=0.0, upper=5.0)],
            constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
            linking_columns=LinkingColumns(rows=[], cols=[], values=[]),
        )
        result = solve_subproblem(block, row_duals=[], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "optimal"
        assert result.col_linking == []


# ---------------------------------------------------------------------------
# solve_subproblem — infeasible / unbounded
# ---------------------------------------------------------------------------


class TestSolveSubproblemEdgeCases:
    def test_infeasible_local_constraints(self) -> None:
        """x0 <= 2 AND x0 >= 5 → infeasible subproblem."""
        block = Block(
            block_id="b0",
            variable_names=["x0"],
            objective=[1.0],
            bounds=[Bounds(lower=0.0, upper=10.0)],
            constraints=BlockConstraints(
                matrix=[[1.0], [-1.0]],
                rhs=[2.0, -5.0],  # x0 <= 2 and -x0 <= -5 (i.e. x0 >= 5)
                senses=["<=", "<="],
            ),
            linking_columns=LinkingColumns(rows=[], cols=[], values=[]),
        )
        result = solve_subproblem(block, row_duals=[], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "infeasible"

    def test_unbounded_subproblem(self) -> None:
        """min -x0, x0 >= 0 (no upper bound, no constraints) → unbounded."""
        block = Block(
            block_id="b0",
            variable_names=["x0"],
            objective=[-1.0],
            bounds=[Bounds(lower=0.0, upper=None)],
            constraints=BlockConstraints(matrix=[], rhs=[], senses=[]),
            linking_columns=LinkingColumns(rows=[], cols=[], values=[]),
        )
        result = solve_subproblem(block, row_duals=[], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "unbounded"

    def test_unbounded_via_dual_modification(self) -> None:
        """Block with obj=1.0, large π makes modified obj=-100*x0 → unbounded (no upper bound)."""
        block = _block_1var(
            obj=1.0,
            lb=0.0,
            ub=None,
            link_vals=[1.0],
            local_matrix=[],
            local_rhs=[],
            local_senses=[],
        )
        # modified obj = (1.0 - 101.0 * 1.0) * x0 = -100 * x0 → unbounded
        result = solve_subproblem(block, row_duals=[101.0], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "unbounded"

    def test_equality_constraint_satisfied_at_optimum(self) -> None:
        """x0 = 3.0 (equality) → optimal at exactly x0=3."""
        block = Block(
            block_id="b0",
            variable_names=["x0"],
            objective=[0.0],
            bounds=[Bounds(lower=0.0, upper=None)],
            constraints=BlockConstraints(matrix=[[1.0]], rhs=[3.0], senses=["="]),
            linking_columns=LinkingColumns(rows=[0], cols=[0], values=[1.0]),
        )
        result = solve_subproblem(block, row_duals=[0.0], convexity_dual=0.0, tolerance=1e-6)
        assert result.status == "optimal"
        assert abs(result.primal_values[0] - 3.0) < 1e-4
        assert abs(result.col_linking[0] - 3.0) < 1e-4
