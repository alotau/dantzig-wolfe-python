# Data Model: dwsolver Python Package

**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03  
**Source**: `src/dwsolver/models.py`

---

## Overview

All models are **Pydantic v2** dataclasses. Input models carry `extra="ignore"` for forward schema compatibility. Output models are strict. All models are exportable from `dwsolver` top-level (`from dwsolver import Problem, Result, SolveStatus`).

---

## Enumerations

### `SolveStatus`

```python
from enum import Enum

class SolveStatus(str, Enum):
    OPTIMAL         = "optimal"           # RMP converged; global optimum found
    INFEASIBLE      = "infeasible"        # Problem has no feasible solution
    UNBOUNDED       = "unbounded"         # Objective is unbounded below
    ITERATION_LIMIT = "iteration_limit"   # Max DW iterations reached; best feasible returned
```

The `str` mixin ensures JSON-serializable values without extra configuration.

---

## Input Models

### `Bounds`

Variable bound pair. `None` for upper represents `+∞`.

```python
class Bounds(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lower: float = 0.0          # Default: non-negative
    upper: float | None = None  # None → +∞ (free upper bound)
```

**Validation rule**: `lower <= upper` if upper is not None. Raises `DWSolverInputError` on violation.

---

### `BlockConstraints`

Local constraint system for one block (`F_i x_i = b_i`).

```python
class BlockConstraints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    matrix: list[list[float]]   # Shape: (num_constraints, num_variables)
    rhs: list[float]            # Shape: (num_constraints,)
    senses: list[str]           # Each: "=", "<=", ">="
```

**Validation rules**:
- `len(matrix) == len(rhs) == len(senses)`
- Each row of `matrix` has `len(matrix[i]) == len(variable_names)` of parent `Block`
- `senses` values ∈ `{"=", "<=", ">="}`

---

### `LinkingColumns`

Sparse COO-format representation of block `i`'s participation in the master linking constraints. Encodes the `D_i` matrix: `D_i[rows[k], cols[k]] = values[k]`.

```python
class LinkingColumns(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rows: list[int]     # Master constraint index (0-based into Master.constraint_names)
    cols: list[int]     # Variable index within this block (0-based into Block.variable_names)
    values: list[float] # Non-zero coefficient value
```

**Validation rules**:
- `len(rows) == len(cols) == len(values)`
- All `rows[k]` are valid indices into `Master.constraint_names`
- All `cols[k]` are valid indices into this block's `variable_names`

---

### `Block`

One subproblem in the decomposed LP. Corresponds to block `i` with variables `x_i`, constraints `F_i x_i = b_i`, and linking `D_i x_i`.

```python
class Block(BaseModel):
    model_config = ConfigDict(extra="ignore")

    block_id: str                       # Unique identifier (e.g., "block_0")
    variable_names: list[str]           # Names of x_i variables
    objective: list[float]              # c_i coefficients
    bounds: list[Bounds]                # One per variable; defaults to [0, +∞]
    constraints: BlockConstraints       # F_i, b_i
    linking_columns: LinkingColumns     # D_i (sparse)
```

**Validation rules**:
- `len(variable_names) == len(objective) == len(bounds)`
- `block_id` must be unique across all blocks in `Problem`

---

### `Master`

The linking (coupling) constraints shared across all blocks: `D_1 x_1 + ... + D_l x_l = b_0`.

```python
class Master(BaseModel):
    model_config = ConfigDict(extra="ignore")

    constraint_names: list[str]   # Human-readable names for linking constraints
    rhs: list[float]              # b_0 — RHS values
    senses: list[str]             # Each: "=", "<=", ">="
```

**Validation rules**:
- `len(constraint_names) == len(rhs) == len(senses)`
- `senses` values ∈ `{"=", "<=", ">="}`

---

### `Problem`

Top-level problem container. The root object for JSON deserialization.

```python
class Problem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0"    # Semver string; major version gates migration
    metadata: dict[str, str] = {}  # Optional freeform labels (name, description, etc.)
    master: Master
    blocks: list[Block]

    @classmethod
    def from_file(cls, path: str | Path) -> "Problem":
        """Load and validate a problem from a JSON file."""
        ...
```

**Validation rules**:
- `len(blocks) >= 1`
- All `block_id` values are unique
- All `constraint_indices` in `LinkingColumns` are valid indices into `master.constraint_names`
- `schema_version` major must be `"1"`; otherwise `DWSolverInputError` is raised

**State transitions**: `Problem` is **read-only** after construction (Pydantic frozen config). No mutation occurs during solve; each call to `solve()` treats the problem as immutable input.

---

## Output Models

### `Result`

Returned by `solve()` for all valid solver outcomes (optimal, infeasible, unbounded, iteration_limit). Never `None` for valid inputs — exceptions propagate only for input errors.

```python
class Result(BaseModel):
    status: SolveStatus
    objective: float | None          # Optimal objective value; None if infeasible/unbounded
    variable_values: dict[str, float] # var_name → value; empty dict if no primal solution
    iterations: int                   # Number of DW iterations completed
    tolerance: float                  # Convergence tolerance used for this solve
    solver_info: dict[str, Any] = {}  # Optional: wall time, simplex iterations, etc.
```

**Status → field rules**:

| `status`          | `objective` | `variable_values`               |
|-------------------|-------------|----------------------------------|
| `optimal`         | float       | populated (all block variables)  |
| `infeasible`      | `None`      | `{}` (empty)                     |
| `unbounded`       | `None`      | `{}` (empty)                     |
| `iteration_limit` | float       | populated (best feasible found)  |

**Variable naming**: keys are `variable_names` from each `Block`. Variable names must be globally unique across all blocks. If not unique, `DWSolverInputError` is raised before solve begins.

---

## Exceptions

### `DWSolverInputError`

Raised for all input validation failures (schema errors, file not found, unsupported schema_version, constraint dimension mismatches, duplicate variable names). Must be importable from the top-level package: `from dwsolver import DWSolverInputError`.

```python
class DWSolverInputError(ValueError):
    """Raised when problem input is invalid or cannot be parsed."""
```

This is a `ValueError` subclass, consistent with Python conventions for bad input.

---

## Constants

Defined in `models.py` (or a dedicated `constants.py` — decision for implementation phase):

```python
DEFAULT_TOLERANCE: float = 1e-6    # FR-014: convergence criterion; never inline
DEFAULT_WORKERS: int | None = None  # FR-012: None → cpu_count at runtime
MAX_ITERATIONS: int = 1000          # DW iteration cap; prevents infinite cycling
```

**Constitution requirement (Principle V)**: all tolerance references in solver code must use `DEFAULT_TOLERANCE`, never the literal `1e-6`.

---

## State-Transition Diagram

```
      Input JSON / Problem object
              │
              ▼
     DWSolverInputError?  ──yes──▶ raise DWSolverInputError
              │
              no
              ▼
         Phase I (feasibility)
              │
         infeasible? ─yes──▶ Result(status=INFEASIBLE, objective=None, variable_values={})
              │
              no
              ▼
         Phase II (DW iterations)
              │
          converged? ─yes──▶ Result(status=OPTIMAL, objective=z*, variable_values=x*)
              │
     iteration_limit? ─yes──▶ Result(status=ITERATION_LIMIT, objective=z_best, variable_values=x_best)
              │
          unbounded? ─yes──▶ Result(status=UNBOUNDED, objective=None, variable_values={})
```
