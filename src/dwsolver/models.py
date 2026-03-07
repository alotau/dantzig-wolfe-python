"""Data models for dwsolver input and output.

All Pydantic v2 models, constants, and exceptions are defined here.
Implements T012 (models) + T013 (cross-field validators) + T014 (from_file).
"""

from __future__ import annotations

import enum
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOLERANCE: float = 1e-6
DEFAULT_WORKERS: int | None = None
MAX_ITERATIONS: int = 1000

_VALID_SENSES: frozenset[str] = frozenset({"=", "<=", ">="})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DWSolverInputError(ValueError):
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


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class Bounds(BaseModel):
    """Variable bound pair. upper=None represents +∞."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    lower: float = 0.0
    upper: float | None = None

    @model_validator(mode="after")
    def _lower_le_upper(self) -> Bounds:
        if self.upper is not None and self.lower > self.upper:
            raise ValueError(f"lower ({self.lower}) must be <= upper ({self.upper})")
        return self


class BlockConstraints(BaseModel):
    """Local constraint system for one block: F_i x_i {sense} b_i."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    matrix: list[list[float]]
    rhs: list[float]
    senses: list[str]

    @field_validator("senses", mode="after")
    @classmethod
    def _validate_senses(cls, v: list[str]) -> list[str]:
        bad = [s for s in v if s not in _VALID_SENSES]
        if bad:
            raise ValueError(f"Invalid sense value(s) {bad!r}; must be one of '=', '<=', '>='")
        return v

    @model_validator(mode="after")
    def _dimensions_consistent(self) -> BlockConstraints:
        n_rows = len(self.matrix)
        if len(self.rhs) != n_rows:
            raise ValueError(f"len(rhs)={len(self.rhs)} must equal len(matrix)={n_rows}")
        if len(self.senses) != n_rows:
            raise ValueError(f"len(senses)={len(self.senses)} must equal len(matrix)={n_rows}")
        return self


class LinkingColumns(BaseModel):
    """Sparse COO encoding of D_i: D_i[rows[k], cols[k]] = values[k]."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    rows: list[int]
    cols: list[int]
    values: list[float]

    @model_validator(mode="after")
    def _lengths_equal(self) -> LinkingColumns:
        n = len(self.rows)
        if len(self.cols) != n or len(self.values) != n:
            raise ValueError(
                f"rows/cols/values must have equal length; got "
                f"{len(self.rows)}/{len(self.cols)}/{len(self.values)}"
            )
        return self


class Block(BaseModel):
    """One subproblem in the decomposed LP."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    block_id: str
    variable_names: list[str]
    objective: list[float]
    bounds: list[Bounds]
    constraints: BlockConstraints
    linking_columns: LinkingColumns

    @model_validator(mode="after")
    def _dimensions_consistent(self) -> Block:
        n = len(self.variable_names)
        if len(self.objective) != n:
            raise ValueError(
                f"len(objective)={len(self.objective)} must equal len(variable_names)={n}"
            )
        if len(self.bounds) != n:
            raise ValueError(f"len(bounds)={len(self.bounds)} must equal len(variable_names)={n}")
        return self


class Master(BaseModel):
    """Coupling constraints shared across all blocks: b_0."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    constraint_names: list[str]
    rhs: list[float]
    senses: list[str]

    @field_validator("senses", mode="after")
    @classmethod
    def _validate_senses(cls, v: list[str]) -> list[str]:
        bad = [s for s in v if s not in _VALID_SENSES]
        if bad:
            raise ValueError(f"Invalid sense value(s) {bad!r}; must be one of '=', '<=', '>='")
        return v

    @model_validator(mode="after")
    def _dimensions_consistent(self) -> Master:
        n = len(self.constraint_names)
        if len(self.rhs) != n:
            raise ValueError(f"len(rhs)={len(self.rhs)} must equal len(constraint_names)={n}")
        if len(self.senses) != n:
            raise ValueError(f"len(senses)={len(self.senses)} must equal len(constraint_names)={n}")
        return self


class Problem(BaseModel):
    """Top-level problem container. Root object for JSON deserialization.

    Frozen (read-only) after construction — solve() treats Problem as immutable input.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: str = "1.0"
    metadata: dict[str, str] = {}
    master: Master
    blocks: list[Block]

    # -- T013: cross-field validators ----------------------------------------

    @field_validator("schema_version", mode="after")
    @classmethod
    def _validate_schema_version(cls, v: str) -> str:
        parts = v.split(".")
        try:
            major = int(parts[0])
        except (ValueError, IndexError) as exc:
            raise ValueError(f"schema_version {v!r} is not a valid semver string") from exc
        if major != 1:
            raise ValueError(
                f"Unsupported schema_version major={major}; only major version 1 is supported"
            )
        return v

    @model_validator(mode="after")
    def _validate_blocks_and_references(self) -> Problem:
        if len(self.blocks) < 1:
            raise ValueError("blocks must contain at least one block")

        # Unique block_ids
        block_ids = [b.block_id for b in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            seen: set[str] = set()
            dups = [bid for bid in block_ids if bid in seen or seen.add(bid)]  # type: ignore[func-returns-value]
            raise ValueError(f"Duplicate block_id(s): {dups!r}")

        # Unique variable names across all blocks
        all_names: list[str] = []
        for b in self.blocks:
            all_names.extend(b.variable_names)
        if len(all_names) != len(set(all_names)):
            seen_vars: set[str] = set()
            dup_vars = [n for n in all_names if n in seen_vars or seen_vars.add(n)]  # type: ignore[func-returns-value]
            raise ValueError(f"Duplicate variable_name(s) across blocks: {dup_vars!r}")

        n_master = len(self.master.constraint_names)

        # COO index range checks per block
        for b in self.blocks:
            n_vars = len(b.variable_names)
            lc = b.linking_columns
            for k, row in enumerate(lc.rows):
                if row < 0 or row >= n_master:
                    raise ValueError(
                        f"Block {b.block_id!r}: linking_columns.rows[{k}]={row} is out of range "
                        f"[0, {n_master - 1}] (master has {n_master} constraints)"
                    )
            for k, col in enumerate(lc.cols):
                if col < 0 or col >= n_vars:
                    raise ValueError(
                        f"Block {b.block_id!r}: linking_columns.cols[{k}]={col} is out of range "
                        f"[0, {n_vars - 1}] (block has {n_vars} variables)"
                    )

        return self

    @classmethod
    def from_file(cls, path: str | Path) -> Problem:
        """Load and validate a problem from a JSON file.

        Args:
            path: Path to the JSON file (str or Path).

        Returns:
            Validated Problem instance.

        Raises:
            DWSolverInputError: If the file is not found, JSON is malformed,
                or the schema fails validation.
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise DWSolverInputError(f"Problem file not found: {path!r}") from exc
        except OSError as exc:
            raise DWSolverInputError(f"Error reading {path!r}: {exc}") from exc

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DWSolverInputError(f"Invalid JSON in {path!r}: {exc}") from exc

        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise DWSolverInputError(f"Schema validation failed for {path!r}: {exc}") from exc

    @classmethod
    def from_lp(
        cls,
        master_path: str | Path,
        subproblem_paths: list[str | Path],
    ) -> Problem:
        """Load and assemble a Problem from CPLEX LP files.

        Args:
            master_path: Path to the master LP/CPLEX file.
            subproblem_paths: Ordered list of subproblem LP/CPLEX file paths.

        Returns:
            Validated Problem instance.

        Raises:
            DWSolverInputError: For I/O, parse, or assembly errors.
        """
        from dwsolver.lp_parser import load_problem_from_lp

        return load_problem_from_lp(
            Path(master_path),
            [Path(p) for p in subproblem_paths],
        )

    @classmethod
    def from_lp_text(
        cls,
        master_text: str,
        subproblem_texts: list[str],
    ) -> Problem:
        """Parse and assemble a Problem from CPLEX LP text strings.

        Args:
            master_text: Full text of the master LP/CPLEX file.
            subproblem_texts: Ordered list of subproblem LP/CPLEX texts.
                Position determines block_id (``"block_0"``, ``"block_1"``, …).

        Returns:
            Validated Problem instance.

        Raises:
            DWSolverInputError: For parse or assembly errors.
        """
        from dwsolver.lp_parser import assemble_problem, parse_master, parse_subproblem

        master = parse_master(master_text)
        subs = [parse_subproblem(text, f"block_{i}") for i, text in enumerate(subproblem_texts)]
        return assemble_problem(master, subs)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class Result(BaseModel):
    """Solver output. Always returned for valid inputs; never None."""

    status: SolveStatus
    objective: float | None
    variable_values: dict[str, float]
    iterations: int
    tolerance: float
    solver_info: dict[str, Any] = {}
