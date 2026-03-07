"""dwsolver — Dantzig-Wolfe decomposition solver.

Public API::

    from dwsolver import solve, Problem, Result, SolveStatus, DWSolverInputError

Load from JSON::

    problem = Problem.from_file("problem.json")

Load from CPLEX LP files::

    problem = Problem.from_lp("master.cplex", ["subprob_1.cplex", "subprob_2.cplex"])
    problem = Problem.from_lp_text(master_text, [sub1_text, sub2_text])
"""

from __future__ import annotations

from dwsolver.models import (
    DWSolverInputError,
    Problem,
    Result,
    SolveStatus,
)
from dwsolver.solver import solve

__all__ = [
    "DWSolverInputError",
    "Problem",
    "Result",
    "SolveStatus",
    "solve",
]
