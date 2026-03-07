"""Scalable block-angular LP generator for benchmarking.

All blocks are structurally identical (fixed seed=0) so that timing differences
arise only from parallelism, not from varying problem difficulty.
"""

from __future__ import annotations

import numpy as np

from dwsolver import Problem
from dwsolver.models import Block, BlockConstraints, Bounds, LinkingColumns, Master

_SEED = 0
_N_VARS = 10       # variables per block
_N_LOCAL = 5       # local constraints per block
_X_STAR = 0.5      # interior feasibility reference point
_MAX_N = 20        # maximum allowed n_blocks


def make_bench_problem(n_blocks: int) -> Problem:
    """Generate a scalable identical-block bench LP with n_blocks blocks.

    All blocks share the same coefficients (seed=0). Variable j in each block
    links to master constraint j (one per block variable), so the master has
    10 linking constraints whose RHS scales linearly with n_blocks.

    Construction guarantees:
    - Feasibility: local constraints use a slack-from-known-point at x*=0.5;
      master RHS = n_blocks * 0.6 > n_blocks * 0.5, so x*=0.5 is always feasible.
    - Reference scaling: obj(n) == n * obj(1) because all blocks are identical
      and the per-block optimal solution is independent of n.

    Args:
        n_blocks: Number of blocks; must be in [1, 20].

    Returns:
        Validated Problem instance ready for dwsolver.solve().

    Raises:
        ValueError: If n_blocks < 1 or n_blocks > 20.
    """
    if not (1 <= n_blocks <= _MAX_N):
        raise ValueError(f"n_blocks must be in [1, {_MAX_N}], got {n_blocks}")

    rng = np.random.default_rng(_SEED)

    objective: list[float] = rng.uniform(-2.0, 2.0, size=_N_VARS).tolist()

    a_local = rng.uniform(0.0, 2.0, size=(_N_LOCAL, _N_VARS))
    slacks = rng.uniform(0.1, 0.5, size=_N_LOCAL)
    rhs_local: list[float] = (a_local @ np.full(_N_VARS, _X_STAR) + slacks).tolist()

    constraints = BlockConstraints(
        matrix=a_local.tolist(),
        rhs=rhs_local,
        senses=["<="] * _N_LOCAL,
    )
    bounds = [Bounds(lower=0.0, upper=1.0) for _ in range(_N_VARS)]
    linking_columns = LinkingColumns(
        rows=list(range(_N_VARS)),
        cols=list(range(_N_VARS)),
        values=[1.0] * _N_VARS,
    )

    blocks = [
        Block(
            block_id=f"block_{i}",
            variable_names=[f"b{i}_x{j}" for j in range(_N_VARS)],
            objective=objective,
            bounds=bounds,
            constraints=constraints,
            linking_columns=linking_columns,
        )
        for i in range(n_blocks)
    ]

    master = Master(
        constraint_names=[f"link_{j}" for j in range(_N_VARS)],
        rhs=[float(n_blocks) * 0.6] * _N_VARS,
        senses=["<="] * _N_VARS,
    )

    return Problem(master=master, blocks=blocks)
