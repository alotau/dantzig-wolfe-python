"""Synthetic block-angular LP generator and HiGHS cross-validation reference.

Usage (library):
    from tests.synthetic import generate_problem, CROSS_VALIDATION_ABS_TOL
    gp = generate_problem(seed=42)
    # gp.problem  — Problem instance ready for dwsolver.solver.solve()
    # gp.reference_objective  — HiGHS ground-truth objective

Usage (CLI):
    python tests/synthetic.py --seed 42
    python tests/synthetic.py --seed 42 --output /tmp/out.json

This module is a permanent test asset; it MUST NOT be imported by any module
under src/dwsolver/.  See FR-008.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from highspy import Highs, HighsModelStatus, kHighsInf

from dwsolver.models import Block, BlockConstraints, Bounds, LinkingColumns, Master, Problem

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Named tolerance constant — Constitution Principle V (FR-005)
# Justification: all generated variables are bounded [0, 1]; objective
# coefficients are drawn from Uniform(-2, 2); constraint coefficients from
# Uniform(-1, 1).  HiGHS solves to dual feasibility tolerance 1e-7, and the
# LP Lipschitz constant for this problem class is small, making 1e-4 a
# conservative cross-validation bound.
# ---------------------------------------------------------------------------
CROSS_VALIDATION_ABS_TOL: float = 1e-4


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticCase:
    """Structural parameters for one generated test case.

    label: human-readable pytest ID, e.g. "seed=6-4blk-5var-4mc"
    """

    seed: int
    num_blocks: int
    vars_per_block: int
    local_constraints: int
    master_constraints: int
    label: str


@dataclass(frozen=True)
class GeneratedProblem:
    """Return value of generate_problem().

    problem: fully validated Problem instance (passes Problem.model_validate())
    reference_objective: HiGHS monolithic optimal objective value
    """

    problem: Problem
    reference_objective: float


# ---------------------------------------------------------------------------
# 12-seed diversity table (research.md Decision 5)
# Seeds 1-3: <= master constraints only
# Seeds 4-8: mixed <= and >= master constraints
# Seeds 9-12: include at least one = master constraint
# ---------------------------------------------------------------------------
SYNTHETIC_CASES: list[SyntheticCase] = [
    SyntheticCase(1, 2, 5, 3, 1, "seed=1-2blk-5var-1mc"),
    SyntheticCase(2, 2, 8, 5, 2, "seed=2-2blk-8var-2mc"),
    SyntheticCase(3, 3, 5, 4, 1, "seed=3-3blk-5var-1mc"),
    SyntheticCase(4, 3, 10, 6, 3, "seed=4-3blk-10var-3mc"),
    SyntheticCase(5, 3, 15, 8, 2, "seed=5-3blk-15var-2mc"),
    SyntheticCase(6, 4, 5, 3, 4, "seed=6-4blk-5var-4mc"),
    SyntheticCase(7, 4, 8, 5, 1, "seed=7-4blk-8var-1mc"),
    SyntheticCase(8, 4, 10, 7, 3, "seed=8-4blk-10var-3mc"),
    SyntheticCase(9, 5, 8, 4, 2, "seed=9-5blk-8var-2mc"),
    SyntheticCase(10, 5, 10, 5, 4, "seed=10-5blk-10var-4mc"),
    SyntheticCase(11, 5, 20, 10, 5, "seed=11-5blk-20var-5mc"),
    SyntheticCase(12, 6, 15, 8, 3, "seed=12-6blk-15var-3mc"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _col_offsets(problem: Problem) -> list[int]:
    """Return cumulative column offsets per block.

    result[i] = first global column index of block i.
    len(result) == len(problem.blocks) + 1 (last entry = total columns).
    """
    offsets: list[int] = [0]
    for block in problem.blocks:
        offsets.append(offsets[-1] + len(block.variable_names))
    return offsets


def _sense_bounds(sense: str, rhs: float) -> tuple[float, float]:
    """Convert a constraint sense + rhs to HiGHS (lb_row, ub_row) encoding."""
    if sense == "<=":
        return (-kHighsInf, rhs)
    if sense == ">=":
        return (rhs, kHighsInf)
    # "="
    return (rhs, rhs)


# ---------------------------------------------------------------------------
# Monolithic HiGHS reference solver (T004)
# ---------------------------------------------------------------------------


def solve_monolithic_highs(problem: Problem) -> float:
    """Solve the monolithic form of a Problem with HiGHS and return the optimal objective.

    The LP is built solely from the data in `problem` (FR-004).  If HiGHS does not
    return kOptimal, AssertionError is raised — a non-optimal result means the
    generator produced an infeasible or unbounded LP, which is a generator bug.

    Args:
        problem: Fully validated Problem instance.

    Returns:
        Optimal objective value as a float.

    Raises:
        AssertionError: If HiGHS status is not kOptimal.
    """
    h = Highs()
    h.silent()
    h.setOptionValue("solver", "simplex")

    offsets = _col_offsets(problem)

    # Add all variables column-by-column in block order.
    for block in problem.blocks:
        for j in range(len(block.variable_names)):
            lb = block.bounds[j].lower
            ub = block.bounds[j].upper if block.bounds[j].upper is not None else kHighsInf
            h.addCol(block.objective[j], lb, ub, 0, [], [])

    # Add block-local (block-diagonal) constraints.
    for i, block in enumerate(problem.blocks):
        offset = offsets[i]
        for row_coeffs, rhs_val, sense in zip(
            block.constraints.matrix,
            block.constraints.rhs,
            block.constraints.senses,
            strict=True,
        ):
            lb_row, ub_row = _sense_bounds(sense, rhs_val)
            nz_idx = [offset + j for j, v in enumerate(row_coeffs) if abs(v) > 1e-12]
            nz_val = [v for v in row_coeffs if abs(v) > 1e-12]
            h.addRow(lb_row, ub_row, len(nz_idx), nz_idx, nz_val)

    # Add master (linking) constraint rows.
    n_master = len(problem.master.constraint_names)
    for m in range(n_master):
        sense = problem.master.senses[m]
        rhs_val = problem.master.rhs[m]
        lb_row, ub_row = _sense_bounds(sense, rhs_val)
        # Collect all (global_col, value) from each block's COO for this row.
        col_indices: list[int] = []
        col_values: list[float] = []
        for i, block in enumerate(problem.blocks):
            offset = offsets[i]
            lc = block.linking_columns
            for k in range(len(lc.rows)):
                if lc.rows[k] == m:
                    col_indices.append(offset + lc.cols[k])
                    col_values.append(lc.values[k])
        h.addRow(lb_row, ub_row, len(col_indices), col_indices, col_values)

    h.run()

    model_status = h.getModelStatus()
    assert model_status == HighsModelStatus.kOptimal, (
        f"Monolithic HiGHS solve returned {model_status!r} — "
        "generator produced an infeasible or unbounded LP (generator bug)"
    )

    _, ref_obj = h.getInfoValue("objective_function_value")
    return float(ref_obj)


# ---------------------------------------------------------------------------
# Generator (T005)
# ---------------------------------------------------------------------------


def generate_problem(
    seed: int,
    num_blocks: int = 3,
    vars_per_block: int = 10,
    local_constraints: int = 5,
    master_constraints: int = 2,
) -> GeneratedProblem:
    """Generate a random, guaranteed-feasible block-angular LP and solve it with HiGHS.

    Feasibility is guaranteed by the slack-from-known-point construction:
    x* = 0.5 for all variables (strictly interior to [0, 1]), and RHS values
    are set so that x* satisfies every constraint with a random positive slack
    drawn from Uniform(0.1, 0.5).

    All random values come from a single numpy.random.default_rng(seed) instance
    threaded top-to-bottom — the same seed always produces bit-for-bit identical
    output (within the same numpy major version).

    Args:
        seed: Integer seed for the random number generator.
        num_blocks: Number of blocks (default 3).
        vars_per_block: Number of variables per block (default 10).
        local_constraints: Number of local constraints per block (default 5).
        master_constraints: Number of master (linking) constraints (default 2).

    Returns:
        GeneratedProblem with a validated Problem and HiGHS reference objective.
    """
    rng = np.random.default_rng(seed)

    x_star = 0.5  # known interior point for all variables

    # Local constraint sense pattern: cycle [<=, >=, <=, <=, >=, ...]
    # (ratio 2:1 <=/>= per research.md D6; no local = constraints)
    _local_sense_cycle = ["<=", ">=", "<="]

    # Master constraint senses: = for last row when master_constraints >= 3
    # (seeds 9-12), <= otherwise.
    def _master_sense(m: int) -> str:
        if master_constraints >= 3 and m == master_constraints - 1:
            return "="
        if m % 2 == 1 and master_constraints >= 2:
            return ">="
        return "<="

    link_count = min(2, vars_per_block)

    # Per-block linking variable indices: shape (num_blocks, link_count).
    # replace=False guarantees distinct columns per block, preventing duplicate
    # (row, col) COO entries in LinkingColumns that cause DW degeneracy.
    linking_var_indices: npt.NDArray[np.intp] = np.array(
        [rng.choice(vars_per_block, size=link_count, replace=False) for _ in range(num_blocks)],
        dtype=np.intp,
    )

    # Master constraint coefficients: shape (num_blocks, master_constraints, link_count)
    master_link_coeffs: npt.NDArray[np.float64] = rng.uniform(
        -1.0, 1.0, size=(num_blocks, master_constraints, link_count)
    )

    # Compute master RHS from x* = 0.5 across all blocks.
    master_totals: npt.NDArray[np.float64] = np.zeros(master_constraints)
    for i in range(num_blocks):
        for m in range(master_constraints):
            # Each linking variable contributes 0.5 * coefficient.
            master_totals[m] += float(np.sum(master_link_coeffs[i, m] * x_star))

    master_slacks: npt.NDArray[np.float64] = rng.uniform(0.1, 0.5, size=master_constraints)
    master_rhs_vals: list[float] = []
    master_senses: list[str] = []
    for m in range(master_constraints):
        sense = _master_sense(m)
        master_senses.append(sense)
        if sense == "=":
            master_rhs_vals.append(float(master_totals[m]))
        elif sense == "<=":
            master_rhs_vals.append(float(master_totals[m]) + float(master_slacks[m]))
        else:  # ">="
            master_rhs_vals.append(float(master_totals[m]) - float(master_slacks[m]))

    # Build each block.
    blocks: list[Block] = []
    for i in range(num_blocks):
        block_id = f"b{i + 1}"
        variable_names = [f"b{i + 1}_x{j}" for j in range(vars_per_block)]

        obj_coeffs: npt.NDArray[np.float64] = rng.uniform(-2.0, 2.0, size=vars_per_block)
        bounds = [Bounds(lower=0.0, upper=1.0)] * vars_per_block

        # Local constraints (block-diagonal).
        local_matrix: list[list[float]] = []
        local_rhs: list[float] = []
        local_senses: list[str] = []
        for r in range(local_constraints):
            a: npt.NDArray[np.float64] = rng.uniform(-1.0, 1.0, size=vars_per_block)
            b_val = float(np.dot(a, np.full(vars_per_block, x_star)))
            sense = _local_sense_cycle[r % len(_local_sense_cycle)]
            slack = float(rng.uniform(0.1, 0.5))
            rhs_val = b_val + slack if sense == "<=" else b_val - slack
            local_matrix.append(a.tolist())
            local_rhs.append(rhs_val)
            local_senses.append(sense)

        # Linking columns (COO): link_count variables per block per master row.
        lc_rows: list[int] = []
        lc_cols: list[int] = []
        lc_values: list[float] = []
        for m in range(master_constraints):
            for k in range(link_count):
                lc_rows.append(m)
                lc_cols.append(int(linking_var_indices[i, k]))
                lc_values.append(float(master_link_coeffs[i, m, k]))

        blocks.append(
            Block(
                block_id=block_id,
                variable_names=variable_names,
                objective=obj_coeffs.tolist(),
                bounds=bounds,
                constraints=BlockConstraints(
                    matrix=local_matrix,
                    rhs=local_rhs,
                    senses=local_senses,
                ),
                linking_columns=LinkingColumns(
                    rows=lc_rows,
                    cols=lc_cols,
                    values=lc_values,
                ),
            )
        )

    master = Master(
        constraint_names=[f"mc{m}" for m in range(master_constraints)],
        rhs=master_rhs_vals,
        senses=master_senses,
    )

    problem = Problem.model_validate(
        {"master": master.model_dump(), "blocks": [b.model_dump() for b in blocks]}
    )

    reference_objective = solve_monolithic_highs(problem)
    return GeneratedProblem(problem=problem, reference_objective=reference_objective)


# ---------------------------------------------------------------------------
# CLI entry point (T006) — SC-006
# ---------------------------------------------------------------------------


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic block-angular LP and print the HiGHS reference objective."
    )
    parser.add_argument("--seed", type=int, required=True, help="Integer RNG seed")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the dwsolver JSON problem",
    )
    parser.add_argument("--num-blocks", type=int, default=3)
    parser.add_argument("--vars-per-block", type=int, default=10)
    parser.add_argument("--local-constraints", type=int, default=5)
    parser.add_argument("--master-constraints", type=int, default=2)
    args = parser.parse_args(argv)

    gp = generate_problem(
        seed=args.seed,
        num_blocks=args.num_blocks,
        vars_per_block=args.vars_per_block,
        local_constraints=args.local_constraints,
        master_constraints=args.master_constraints,
    )

    if args.output is not None:
        args.output.write_text(gp.problem.model_dump_json(indent=2), encoding="utf-8")

    print(gp.reference_objective)


if __name__ == "__main__":
    _main(sys.argv[1:])
