"""Data models for dwsolver input and output.

All Pydantic v2 models, constants, and exceptions are defined here.
Full validation logic is implemented in Phase 2 (T012–T014).
"""

from __future__ import annotations

import enum
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOLERANCE: float = 1e-6
DEFAULT_WORKERS: int | None = None
MAX_ITERATIONS: int = 1000


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DWSolverInputError(Exception):
    """Raised when the input problem JSON is missing, malformed, or invalid."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SolveStatus(enum.StrEnum):
    """Terminal status reported by the solver."""

    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    ITERATION_LIMIT = "iteration_limit"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Stub models (full Pydantic implementation follows in T012)
# ---------------------------------------------------------------------------


class Problem:
    """Block-angular LP problem.

    Full Pydantic v2 model implementation is in T012.
    This stub satisfies the public API and mypy strict-mode imports.
    """

    @classmethod
    def from_file(cls, path: str) -> Problem:
        """Load and validate a problem from a JSON file.

        Raises:
            DWSolverInputError: If the file is missing, malformed, or invalid.
        """
        raise NotImplementedError("from_file() implemented in T014")


class Result:
    """Solver output.

    Full Pydantic v2 model implementation is in T012.
    """

    def __init__(
        self,
        status: SolveStatus,
        objective: float | None,
        variable_values: dict[str, float],
        iterations: int,
        tolerance: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.objective = objective
        self.variable_values = variable_values
        self.iterations = iterations
        self.tolerance = tolerance
        self.metadata = metadata or {}
