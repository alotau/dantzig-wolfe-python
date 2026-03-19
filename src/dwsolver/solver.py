"""Dantzig-Wolfe column-generation solver — T017 + T018.

Algorithm outline
-----------------
Phase I  — find a feasible basis by minimising Big-M artificial variables.
           Column generation uses the Phase I master's duals to price
           subproblems, adding improving columns until artificials reach zero.

Phase II — optimise the real objective via DW column generation:
           solve master → extract duals → price subproblems in parallel →
           add improving columns → repeat until no column has rc < -tol.

Threading
---------
dispatch_subproblems() uses ThreadPoolExecutor.  HiGHS releases the GIL
during C++ solve, so worker threads achieve true CPU parallelism.
The pool size is  min(workers or cpu_count*2, len(blocks))  to avoid
spawning more OS threads than there are subproblems.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import IO

from highspy import Highs, HighsModelStatus, kHighsInf

from dwsolver.models import (
    DEFAULT_TOLERANCE,
    DEFAULT_WORKERS,
    MAX_ITERATIONS,
    Block,
    Problem,
    Result,
    SolveStatus,
)
from dwsolver.subproblem import SubproblemResult, solve_subproblem

# Big-M cost for Phase I artificial variables.
_BIG_M: float = 1e6

# Phase I gets a generous private iteration budget independent of max_iterations.
_PHASE1_ITER_BUDGET: int = 500


# ---------------------------------------------------------------------------
# Internal column tracker
# ---------------------------------------------------------------------------


@dataclass
class _RMPColumn:
    """Metadata for one lambda column added to the master LP."""

    block_idx: int
    primal_values: list[float]  # x_i^k — for primal reconstruction
    col_obj: float  # c_i' x_i^k — real objective coefficient


# ---------------------------------------------------------------------------
# Master LP wrapper
# ---------------------------------------------------------------------------


class _MasterLP:
    """Restricted Master Problem managed in HiGHS for incremental column generation.

    Row layout (fixed):
        0 … n_master-1                   linking constraints  (from problem.master)
        n_master … n_master+n_blocks-1   convexity constraints  (= 1.0 each)

    Column layout (built up over time):
        0 … n_art-1             Phase I artificial variables
        n_art … n_art+n_cols-1  lambda columns (one per generated extreme point)
    """

    def __init__(self, problem: Problem) -> None:
        self.n_master = len(problem.master.constraint_names)
        self.n_blocks = len(problem.blocks)
        self._senses = list(problem.master.senses)
        self._columns: list[_RMPColumn] = []
        self._art_indices: list[int] = []
        self._n_art = 0

        h = Highs()
        h.silent()
        h.setOptionValue("solver", "simplex")
        self._h = h

        # Add linking constraint rows
        for j in range(self.n_master):
            sense = problem.master.senses[j]
            rhs = problem.master.rhs[j]
            lb_row = rhs if sense in ("=", ">=") else -kHighsInf
            ub_row = rhs if sense in ("=", "<=") else kHighsInf
            self._h.addRow(lb_row, ub_row, 0, [], [])

        # Add convexity rows: sum_k lambda_i^k = 1
        for _ in range(self.n_blocks):
            self._h.addRow(1.0, 1.0, 0, [], [])

        self._add_phase1_artificials()

    def _add_phase1_artificials(self) -> None:
        for j, sense in enumerate(self._senses):
            if sense in ("=", ">="):
                idx = self._h.getNumCol()
                self._h.addCol(_BIG_M, 0.0, kHighsInf, 1, [j], [1.0])
                self._art_indices.append(idx)
                self._n_art += 1
            if sense in ("=", "<="):
                idx = self._h.getNumCol()
                self._h.addCol(_BIG_M, 0.0, kHighsInf, 1, [j], [-1.0])
                self._art_indices.append(idx)
                self._n_art += 1

    def add_column(
        self,
        block_idx: int,
        col_obj_real: float,
        col_linking: list[float],
        primal_values: list[float],
        phase: int,
    ) -> None:
        cost = 0.0 if phase == 1 else col_obj_real

        row_indices: list[int] = []
        row_values: list[float] = []

        for j in range(self.n_master):
            v = col_linking[j] if j < len(col_linking) else 0.0
            if abs(v) > 1e-12:
                row_indices.append(j)
                row_values.append(v)

        conv_row = self.n_master + block_idx
        row_indices.append(conv_row)
        row_values.append(1.0)

        self._h.addCol(cost, 0.0, kHighsInf, len(row_indices), row_indices, row_values)
        self._columns.append(
            _RMPColumn(block_idx=block_idx, primal_values=primal_values, col_obj=col_obj_real)
        )

    def set_phase2_costs(self) -> None:
        # Fix artificials at zero so they cannot skew Phase II objective.
        for art_idx in self._art_indices:
            self._h.changeColBounds(art_idx, 0.0, 0.0)
        for i, col in enumerate(self._columns):
            self._h.changeColCost(self._n_art + i, col.col_obj)

    def solve(self) -> tuple[str, list[float], list[float]]:
        self._h.run()
        ms = self._h.getModelStatus()

        if ms == HighsModelStatus.kOptimal:
            sol = self._h.getSolution()
            all_duals: list[float] = list(sol.row_dual)
            row_duals = all_duals[: self.n_master]
            conv_duals = all_duals[self.n_master : self.n_master + self.n_blocks]
            return "optimal", row_duals, conv_duals

        if ms == HighsModelStatus.kInfeasible:
            return "infeasible", [], []

        return "other", [], []

    def get_objective(self) -> float:
        return float(self._h.getInfoValue("objective_function_value")[1])

    def get_artificial_sum(self) -> float:
        sol = self._h.getSolution()
        all_vals: list[float] = list(sol.col_value)
        return sum(all_vals[idx] for idx in self._art_indices if idx < len(all_vals))

    def get_lambda_values(self) -> list[tuple[int, float, list[float]]]:
        sol = self._h.getSolution()
        all_vals: list[float] = list(sol.col_value)
        out: list[tuple[int, float, list[float]]] = []
        for i, col in enumerate(self._columns):
            hi_idx = self._n_art + i
            if hi_idx < len(all_vals):
                lam = all_vals[hi_idx]
                if abs(lam) > 1e-8:
                    out.append((col.block_idx, lam, col.primal_values))
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_column_data(
    block: Block, n_master: int, primal_values: list[float]
) -> tuple[float, list[float]]:
    n_vars = len(block.variable_names)
    col_obj = sum(block.objective[j] * primal_values[j] for j in range(n_vars))
    col_linking: list[float] = [0.0] * n_master
    for k in range(len(block.linking_columns.rows)):
        row_idx = block.linking_columns.rows[k]
        col_idx = block.linking_columns.cols[k]
        coeff = block.linking_columns.values[k]
        if row_idx < n_master:
            col_linking[row_idx] += coeff * primal_values[col_idx]
    return col_obj, col_linking


def _initial_extreme_point(block: Block) -> list[float] | None:
    """Find any feasible extreme point of the block's local feasible set.

    Returns None if infeasible (block's local constraints unsatisfiable).
    Uses zero objective so HiGHS returns any feasible point.
    """
    n_vars = len(block.variable_names)
    h = Highs()
    h.silent()
    h.setOptionValue("solver", "simplex")

    for j in range(n_vars):
        lb = block.bounds[j].lower
        ub = block.bounds[j].upper if block.bounds[j].upper is not None else kHighsInf
        h.addCol(0.0, lb, ub, 0, [], [])

    for row_coeffs, rhs_val, sense in zip(
        block.constraints.matrix, block.constraints.rhs, block.constraints.senses, strict=True
    ):
        lb_row = rhs_val if sense in ("=", ">=") else -kHighsInf
        ub_row = rhs_val if sense in ("=", "<=") else kHighsInf
        nz_idx = [j for j, v in enumerate(row_coeffs) if abs(v) > 1e-12]
        nz_val = [row_coeffs[j] for j in nz_idx]
        h.addRow(lb_row, ub_row, len(nz_idx), nz_idx, nz_val)

    h.run()

    if h.getModelStatus() != HighsModelStatus.kOptimal:
        return None

    sol = h.getSolution()
    return list(sol.col_value)[:n_vars]


def _reconstruct_primal(problem: Problem, master: _MasterLP) -> dict[str, float]:
    var_values: dict[str, float] = {
        vname: 0.0 for block in problem.blocks for vname in block.variable_names
    }
    for block_idx, lam, primal_x in master.get_lambda_values():
        block = problem.blocks[block_idx]
        for j, vname in enumerate(block.variable_names):
            if j < len(primal_x):
                var_values[vname] += lam * primal_x[j]
    return var_values


def _reduced_cost(
    sub_result: SubproblemResult,
    row_duals: list[float],
    convexity_dual: float,
) -> float:
    link_dot = sum(
        row_duals[j] * sub_result.col_linking[j]
        for j in range(min(len(row_duals), len(sub_result.col_linking)))
    )
    return sub_result.col_obj - link_dot - convexity_dual


# ---------------------------------------------------------------------------
# T018: dispatch_subproblems
# ---------------------------------------------------------------------------


def dispatch_subproblems(
    blocks: list[Block],
    row_duals: list[float],
    convexity_duals: list[float],
    workers: int | None,
    tolerance: float,
) -> list[SubproblemResult]:
    """Solve all block subproblems in parallel using ThreadPoolExecutor.

    Pool is capped at min(workers or cpu_count*2, len(blocks)).
    Results are returned in original block order regardless of completion order.
    """
    cpu_default = (os.cpu_count() or 1) * 2
    n_workers = min(workers if workers is not None else cpu_default, len(blocks))
    n_workers = max(1, n_workers)

    results: list[SubproblemResult | None] = [None] * len(blocks)

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(
                solve_subproblem,
                block,
                row_duals,
                convexity_duals[i] if i < len(convexity_duals) else 0.0,
                tolerance,
            ): i
            for i, block in enumerate(blocks)
        }
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()

    assert all(r is not None for r in results), "dispatch_subproblems: missing result"
    return results  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# T017: solve
# ---------------------------------------------------------------------------


def solve(
    problem: Problem,
    workers: int | None = DEFAULT_WORKERS,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = MAX_ITERATIONS,
    verbose_stream: IO[str] | None = None,
) -> Result:
    """Solve a block-angular LP using Dantzig-Wolfe decomposition.

    Args:
        problem: The block-angular LP to solve.
        workers: Number of parallel subproblem workers. None → cpu_count * 2.
        tolerance: DW convergence tolerance (reduced-cost threshold).
        max_iterations: Maximum Phase II iterations before ITERATION_LIMIT.
        verbose_stream: Optional writable stream for per-iteration diagnostic
            lines.  Pass ``sys.stderr`` from the CLI or a ``StringIO`` in
            tests.  ``None`` (default) produces no output.

    Returns:
        Result with status, objective, variable values, and iteration count.
    """
    n_master = len(problem.master.constraint_names)
    blocks = list(problem.blocks)

    master = _MasterLP(problem)

    # --- Initial extreme points (one per block to bootstrap convexity rows) ---
    for i, block in enumerate(blocks):
        x0 = _initial_extreme_point(block)
        if x0 is None:
            return Result(
                status=SolveStatus.INFEASIBLE,
                objective=None,
                variable_values={},
                iterations=0,
                tolerance=tolerance,
                solver_info={"message": "Block local constraints are infeasible."},
            )
        col_obj, col_linking = _compute_column_data(block, n_master, x0)
        master.add_column(i, col_obj, col_linking, x0, phase=1)

    # ------------------------------------------------------------------
    # Phase I — drive artificials to zero
    # ------------------------------------------------------------------
    phase1_iters = 0
    phase1_budget = max(_PHASE1_ITER_BUDGET, max_iterations * 2)

    for _ in range(phase1_budget):
        ms, row_duals, conv_duals = master.solve()

        if ms != "optimal":
            return Result(
                status=SolveStatus.INFEASIBLE,
                objective=None,
                variable_values={},
                iterations=phase1_iters,
                tolerance=tolerance,
                solver_info={"message": "Master LP infeasible during Phase I."},
            )

        if master.get_artificial_sum() < tolerance:
            break  # feasible basis found

        sub_results = dispatch_subproblems(blocks, row_duals, conv_duals, workers, tolerance)

        if any(r.status == "unbounded" for r in sub_results):
            return Result(
                status=SolveStatus.UNBOUNDED,
                objective=None,
                variable_values={},
                iterations=phase1_iters,
                tolerance=tolerance,
                solver_info={"message": "Unbounded subproblem in Phase I."},
            )

        improved = False
        for i, r in enumerate(sub_results):
            if r.status == "optimal":
                rc = _reduced_cost(r, row_duals, conv_duals[i] if i < len(conv_duals) else 0.0)
                if rc < -tolerance:
                    master.add_column(i, r.col_obj, r.col_linking, r.primal_values, phase=1)
                    improved = True

        if not improved:
            break  # no improving column; artificials will be checked below

        phase1_iters += 1

        if verbose_stream is not None:
            art_sum = master.get_artificial_sum()
            n_cols = master.num_columns()
            print(
                f"DW Phase I  iter {phase1_iters:4d} | cols {n_cols:4d} | art_sum {art_sum:.3e}",
                file=verbose_stream,
            )

    # Final Phase I check
    ms, _, _ = master.solve()
    if ms != "optimal" or master.get_artificial_sum() > tolerance:
        return Result(
            status=SolveStatus.INFEASIBLE,
            objective=None,
            variable_values={},
            iterations=phase1_iters,
            tolerance=tolerance,
            solver_info={
                "message": ("Infeasible: Phase I could not drive artificial variables to zero.")
            },
        )

    # ------------------------------------------------------------------
    # Phase II — optimise real objective
    # ------------------------------------------------------------------
    master.set_phase2_costs()

    best_result: Result | None = None
    phase2_iters = 0

    for _ in range(max_iterations):
        ms, row_duals, conv_duals = master.solve()

        if ms != "optimal":
            break

        obj_val = master.get_objective()
        var_values = _reconstruct_primal(problem, master)

        best_result = Result(
            status=SolveStatus.OPTIMAL,
            objective=obj_val,
            variable_values=var_values,
            iterations=phase1_iters + phase2_iters,
            tolerance=tolerance,
            solver_info={},
        )

        sub_results = dispatch_subproblems(blocks, row_duals, conv_duals, workers, tolerance)

        if any(r.status == "unbounded" for r in sub_results):
            return Result(
                status=SolveStatus.UNBOUNDED,
                objective=None,
                variable_values={},
                iterations=phase1_iters + phase2_iters,
                tolerance=tolerance,
                solver_info={"message": "Unbounded subproblem in Phase II."},
            )

        improving_any = False
        for i, r in enumerate(sub_results):
            if r.status == "optimal":
                rc = _reduced_cost(r, row_duals, conv_duals[i] if i < len(conv_duals) else 0.0)
                if rc < -tolerance:
                    master.add_column(i, r.col_obj, r.col_linking, r.primal_values, phase=2)
                    improving_any = True

        if not improving_any:
            if verbose_stream is not None:
                total = phase1_iters + phase2_iters
                print(
                    f"DW converged  iter {total:4d} | optimal obj {obj_val:.6g}",
                    file=verbose_stream,
                )
            return best_result  # converged

        phase2_iters += 1

        if verbose_stream is not None:
            n_cols = len(master._columns)
            print(
                f"DW Phase II iter {phase2_iters:4d} | cols {n_cols:4d} | obj {obj_val:.6g}",
                file=verbose_stream,
            )

    # Hit iteration limit
    if best_result is not None:
        return Result(
            status=SolveStatus.ITERATION_LIMIT,
            objective=best_result.objective,
            variable_values=best_result.variable_values,
            iterations=phase1_iters + phase2_iters,
            tolerance=tolerance,
            solver_info={"message": f"Iteration limit ({max_iterations}) reached."},
        )

    return Result(
        status=SolveStatus.INFEASIBLE,
        objective=None,
        variable_values={},
        iterations=phase1_iters,
        tolerance=tolerance,
        solver_info={"message": "No feasible Phase II solution found."},
    )


__all__ = ["dispatch_subproblems", "solve"]
