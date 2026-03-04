# Library API Contract

**Module**: `dwsolver`  
**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03

---

## Public API Surface

Everything listed here must be importable directly from the top-level `dwsolver` package.

```python
from dwsolver import (
    solve,
    Problem,
    Result,
    SolveStatus,
    DWSolverInputError,
)
```

---

## `solve()`

The primary entry point. Solves a block-angular LP using Dantzig-Wolfe decomposition.

```python
def solve(
    problem: Problem,
    workers: int | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = MAX_ITERATIONS,
) -> Result:
    ...
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `problem` | `Problem` | required | Validated problem instance |
| `workers` | `int \| None` | `None` | Number of parallel workers; `None` → `os.cpu_count() * 2` at runtime (HiGHS releases the GIL; 2× gives CPU + I/O overlap) |
| `tolerance` | `float` | `1e-6` | DW convergence tolerance (reduced cost threshold) |
| `max_iterations` | `int` | `1000` | Maximum DW iterations before returning `iteration_limit` |

### Returns

`Result` — always returned for valid inputs. Never `None`.

| `result.status` | Condition |
|-----------------|-----------|
| `SolveStatus.OPTIMAL` | DW converged; global optimum found |
| `SolveStatus.INFEASIBLE` | Phase I could not drive artificials to zero |
| `SolveStatus.UNBOUNDED` | At least one subproblem is unbounded and no column bounds it |
| `SolveStatus.ITERATION_LIMIT` | `max_iterations` reached; best feasible solution returned |

### Raises

| Exception | Condition |
|-----------|-----------|
| `DWSolverInputError` | `problem` fails validation (invalid dimensions, bad schema, etc.) |

### Guarantees

- **Stateless**: no shared state between calls; calling `solve()` multiple times with the same `problem` object is safe and produces identical results.
- **Deterministic given fixed `workers` and `tolerance`**: simplex is deterministic; result does not depend on thread scheduling order (workers only compute columns; master aggregation is sequential).
- **No side effects**: does not write files, modify `problem`, or print to stdout.

---

## `Problem`

See [data-model.md](../data-model.md) for the full field specification.

### `Problem.from_file()`

```python
@classmethod
def from_file(cls, path: str | Path) -> Problem:
    ...
```

Loads and validates a problem from a JSON file.

| Raises | Condition |
|--------|-----------|
| `DWSolverInputError` | File not found, JSON parse error, schema validation failure, unsupported `schema_version` |

---

## `Result`

See [data-model.md](../data-model.md) for the full field specification.

### Key fields

| Field | Type | Notes |
|-------|------|-------|
| `status` | `SolveStatus` | Enum value; also a `str` (e.g., `"optimal"`) |
| `objective` | `float \| None` | `None` for infeasible/unbounded |
| `variable_values` | `dict[str, float]` | Empty `{}` for infeasible/unbounded |
| `iterations` | `int` | DW iterations completed |
| `tolerance` | `float` | Tolerance used (echoed from input) |

---

## `SolveStatus`

```python
class SolveStatus(str, Enum):
    OPTIMAL         = "optimal"
    INFEASIBLE      = "infeasible"
    UNBOUNDED       = "unbounded"
    ITERATION_LIMIT = "iteration_limit"
```

---

## `DWSolverInputError`

```python
class DWSolverInputError(ValueError): ...
```

Raised for all input validation failures. Subclasses `ValueError` for idiomatic Python error handling.
