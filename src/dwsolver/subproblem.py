"""Subproblem solver for a single block in Dantzig-Wolfe decomposition — T016.

Each block i's subproblem is:

    min (c_i - π' D_i) x_i
    s.t. F_i x_i {senses} b_i
         x_i in [lb_i, ub_i]

The modified objective uses the row duals (π) from the current master solution.
One Highs() instance per call; never shared across threads.
"""

from __future__ import annotations

from dataclasses import dataclass

from highspy import Highs, HighsModelStatus, kHighsInf

from dwsolver.models import Block


@dataclass
class SubproblemResult:
    """Result returned by solve_subproblem for one block."""

    status: str  # "optimal" | "infeasible" | "unbounded"
    col_obj: float  # c_i' x_i^*  — original-objective contribution (RMP column cost)
    col_linking: list[float]  # D_i x_i^* — linking-column vector (one entry per master row)
    primal_values: list[float]  # x_i^*  — for primal solution reconstruction


def solve_subproblem(
    block: Block,
    row_duals: list[float],
    convexity_dual: float,
    tolerance: float,
) -> SubproblemResult:
    """Solve the pricing subproblem for one block.

    Args:
        block: Block definition (variables, bounds, local constraints, D_i matrix).
        row_duals: π — dual prices of master linking constraints (one per master row).
        convexity_dual: μ_i — dual of the convexity constraint for this block.
            (Passed for interface consistency; reduced cost = modified_obj_val - μ_i
            is computed in the caller.)
        tolerance: Convergence tolerance (not used internally but kept for API symmetry).

    Returns:
        SubproblemResult with status, column data, and primal values.
    """
    n_vars = len(block.variable_names)
    n_master = len(row_duals)

    # Build modified objective: c_i[j] - Σ_k π[rows[k]] * D_i[rows[k], cols[k]]
    # D_i is COO-encoded: linking_columns.{rows, cols, values}
    modified_obj: list[float] = list(block.objective)
    for k in range(len(block.linking_columns.rows)):
        row_idx = block.linking_columns.rows[k]
        col_idx = block.linking_columns.cols[k]
        coeff = block.linking_columns.values[k]
        if row_idx < n_master:
            modified_obj[col_idx] -= row_duals[row_idx] * coeff

    h = Highs()
    h.silent()
    h.setOptionValue("solver", "simplex")

    # Add variables with modified objective and bounds
    for j in range(n_vars):
        lb = block.bounds[j].lower
        ub = block.bounds[j].upper if block.bounds[j].upper is not None else kHighsInf
        # addCol(cost, lb, ub, num_nz, row_indices, row_values)
        h.addCol(modified_obj[j], lb, ub, 0, [], [])

    # Add local constraints F_i x_i {sense} b_i
    for row_coeffs, rhs_val, sense in zip(
        block.constraints.matrix, block.constraints.rhs, block.constraints.senses, strict=True
    ):
        lb_row = rhs_val if sense in ("=", ">=") else -kHighsInf
        ub_row = rhs_val if sense in ("=", "<=") else kHighsInf
        nz_idx = [j for j, v in enumerate(row_coeffs) if abs(v) > 1e-12]
        nz_val = [row_coeffs[j] for j in nz_idx]
        h.addRow(lb_row, ub_row, len(nz_idx), nz_idx, nz_val)

    h.run()

    model_status = h.getModelStatus()

    if model_status == HighsModelStatus.kOptimal:
        sol = h.getSolution()
        primal_values: list[float] = list(sol.col_value)[:n_vars]

        # col_obj = c_i' x_i^*  (original objective, not modified)
        col_obj = sum(block.objective[j] * primal_values[j] for j in range(n_vars))

        # col_linking[j] = Σ_k D_i[j, cols[k]] * primal_values[cols[k]]  for row j
        col_linking: list[float] = [0.0] * n_master
        for k in range(len(block.linking_columns.rows)):
            row_idx = block.linking_columns.rows[k]
            col_idx = block.linking_columns.cols[k]
            coeff = block.linking_columns.values[k]
            if row_idx < n_master:
                col_linking[row_idx] += coeff * primal_values[col_idx]

        return SubproblemResult(
            status="optimal",
            col_obj=col_obj,
            col_linking=col_linking,
            primal_values=primal_values,
        )

    if model_status == HighsModelStatus.kInfeasible:
        return SubproblemResult(
            status="infeasible",
            col_obj=0.0,
            col_linking=[0.0] * n_master,
            primal_values=[0.0] * n_vars,
        )

    # Unbounded or any other status
    return SubproblemResult(
        status="unbounded",
        col_obj=0.0,
        col_linking=[0.0] * n_master,
        primal_values=[0.0] * n_vars,
    )


__all__ = ["SubproblemResult", "solve_subproblem"]
