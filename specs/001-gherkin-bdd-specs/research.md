# Phase 0 Research: dwsolver Python Reimplementation

**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03

---

## 1. Dantzig-Wolfe Algorithm (Algorithmic Reference)

### Sources
- **Primary**: Rios, J. (2013). "Algorithm 928: A general, parallel implementation of Dantzig–Wolfe decomposition." *ACM Trans. Math. Softw.*, 39(3), Article 21. DOI: 10.1145/2450153.2450159
- **Original**: Dantzig, G.B. and Wolfe, P. (1960). "Decomposition Principle for Linear Programs." *Operations Research*, 8(1): 101–111. DOI: 10.1287/opre.8.1.101
- **Original C implementation**: https://github.com/alotau/dwsolver (by the same author)

### 1.1 Problem Form (Block-Angular LP)

The solver targets LPs of **block-angular form** (notation from Rios 2013, Section 2, which borrows from Bertsimas & Tsitsiklis 1997):

```
Minimize:   c'_1 x_1 + c'_2 x_2 + ... + c'_l x_l           (eq. 1)
Subject to: D_1 x_1 + D_2 x_2 + ... + D_l x_l = b_0         (eq. 2)  ← linking constraints
            F_1 x_1 = b_1                                      (eq. 3)
            F_2 x_2 = b_2                                      (eq. 4)
            ...
            F_l x_l = b_l                                      (eq. 5)
            x_i >= 0
```

**Notation:**
- `l` — number of blocks (subproblems)
- `x_i` — decision variables for block `i`
- `c_i` — objective coefficients for block `i`
- `D_i` — linking/coupling constraint matrix for block `i` (block's participation in shared constraints)
- `F_i` — block-local constraint matrix (constraints private to block `i`)
- `b_0` — RHS of linking constraints (shared resource limits)
- `b_i` — RHS of block `i` constraints

The constraint matrix has a characteristic **block-diagonal shape with a coupling band** at the top (the `D_i` rows).

### 1.2 DW Reformulation

Each block's feasible polytope is:
```
P_i = { x_i : F_i x_i = b_i, x_i >= 0 }
```

By the Minkowski–Weyl theorem, any point in a bounded `P_i` is a **convex combination of its extreme points** `{x_i^k, k=1..K_i}`. DW substitutes:
```
x_i = sum_k lambda_i^k * x_i^k,   where sum_k lambda_i^k = 1,  lambda_i^k >= 0
```

This yields the **Restricted Master Problem (RMP)** in lambda variables:
```
Minimize:   sum_i sum_k (c'_i x_i^k) lambda_i^k
Subject to: sum_i sum_k (D_i x_i^k) lambda_i^k = b_0    ← linking constraints
            sum_k lambda_i^k = 1,  for i=1..l             ← convexity constraints
            lambda_i^k >= 0
```

The RMP is solvable with a small working subset of lambda columns; the remaining columns are **generated on demand** (column generation).

In the C implementation: lambda columns are named `lambda_{block_id}_{iteration}`. Extreme rays (when a subproblem is unbounded) are named `theta_{block_id}_{iteration}`.

### 1.3 Column Generation Loop

Each DW iteration:

1. **Solve RMP** (simplex) → extract dual prices:
   - `π` — dual prices of linking constraints (one per row of `b_0`)
   - `μ_i` — dual price of convexity constraint for block `i` (the "target to beat")

2. **Solve all subproblems** (independently, in parallel):
   For each block `i`, solve:
   ```
   Minimize:   (c'_i - π' D_i) x_i          ← modified objective using pricing duals
   Subject to: F_i x_i = b_i
               x_i >= 0
   ```
   The subproblem's reduced cost for its solution `x_i^*` is:
   ```
   rc_i = (c'_i - π' D_i) x_i^*  - μ_i
   ```
   - If `rc_i < -tolerance`: column improves objective → generate new lambda column, add to RMP
   - If subproblem is unbounded: generate theta column (extreme ray)

3. **Add all improving columns** to RMP.

4. **Convergence check**: if no block produced an improving column (`max_i rc_i >= -tolerance`), the current RMP solution is **globally optimal**.

5. **Reconstruct primal solution**: for each block `i`, recover `x_i = sum_k lambda_i^k x_i^k` from the nonzero lambda values.

### 1.4 Phase I (Feasibility)

When no initial feasible basis exists, artificial variables `y_j` are added (one per linking constraint row), with objective coefficients `+1` (`+M` / big-M variant in some texts). Phase I minimizes `sum_j y_j`. If the Phase I optimal value is 0, all artificials are zero and Phase II begins. Otherwise, the problem is infeasible.

In the C implementation, Phase I is a full DW loop with the artificials in the master; the subproblems use the pricing duals from this modified master.

### 1.5 Convergence and Stopping Criteria

**Optimality**: No subproblem produces a column with reduced cost `< -tolerance`.

**Iteration limit**: Maximum DW iterations is a configurable parameter. When hit, the best feasible solution found so far is returned with status `iteration_limit`. (FR-007, FR-011 in spec.)

**Divergence/Degeneracy**: DW can cycle on degenerate problems. The original C implementation detects stagnation (no simplex progress despite columns being added) and terminates.

**Decision — Convergence tolerance** (FR-014):
- Default: `DEFAULT_TOLERANCE = 1e-6` (named constant, never inline literal)
- Exposed via `--tolerance` CLI flag and `tolerance=` library parameter

### 1.6 Relationship to Column Generation

DW decomposition is the original column generation scheme. The "columns" in the RMP are weighted extreme points of the subproblem polytopes. Re-solving the master after each batch of columns is standard **delayed column generation**. The Python implementation follows this batch model: all `l` subproblems are solved simultaneously per iteration, all improving columns are added, then the master is re-solved once.

---

## 2. BDD Framework

### Decision: pytest-bdd v8.1.0

**Rationale:**
- Pytest-native: uses pytest fixtures for step injection; no second test runner
- `scenarios()` shortcut auto-registers all scenarios in a feature file (less boilerplate than `@scenario` per test)
- Active maintenance (v8.1.0 current as of 2026-03); designed to evolve with pytest
- Feature files are in standard Gherkin syntax — portable to other runners if ever needed

**Rejected:** `behave` — requires separate runner, cannot share pytest fixtures directly, has less active maintenance trajectory.

### Step file layout
```
tests/
└── bdd/
    ├── conftest.py          # bdd_features_base_dir setting, shared fixtures
    ├── steps/
    │   ├── test_cli_usage.py        # steps for features/cli_usage.feature
    │   └── test_library_usage.py   # steps for features/library_usage.feature
```

`pytest.ini` / `pyproject.toml` entry:
```toml
[tool.pytest.ini_options]
bdd_features_base_dir = "specs/001-gherkin-bdd-specs/features"
```

Feature files live under `specs/001-gherkin-bdd-specs/features/` (already written); step files under `tests/bdd/steps/` import from those feature files via the `bdd_features_base_dir` config — no symlinks needed.

---

## 3. HiGHS LP Solver (highspy)

### Decision: highspy (Python bindings to HiGHS v1.x)

**Rationale:**
- MIT licensed; actively maintained (v1.13.1 February 2026)
- HiGHS ranked among fastest open-source LP solvers (competition benchmark results 2023)
- Python bindings via `highspy` pip package — no system dependency beyond `pip install highspy`
- GIL is released during the C++ solve → true CPU parallelism across workers (not GIL-bound)

### Key API Pattern

One `Highs()` instance **per subproblem call** — the `Highs` class has extensive mutable C++ state and is **not thread-safe to share**. Instantiate inside each worker function.

```python
from highspy import Highs

def solve_subproblem(
    obj_coeffs: list[float],
    constraint_matrix: ...,
    rhs: list[float],
    bounds: ...,
    pricing_duals: list[float],   # π vector — READ ONLY
    linking_cols: ...,             # D_i matrix  — READ ONLY
) -> SubproblemResult:
    h = Highs()
    h.silent()                    # suppress HiGHS stdout
    # ... build LP with modified objective: c_i - π' D_i ...
    status = h.run()
    model_status = h.getModelStatus()
    if model_status == HighsModelStatus.kOptimal:
        sol = h.getSolution()
        primal_values = list(sol.col_value)
        # reduced cost = obj_val - mu_i  (mu_i passed separately)
        obj_val = h.getInfoValue("objective_function_value")[1]
        return SubproblemResult(status="optimal", values=primal_values, obj=obj_val)
    elif model_status == HighsModelStatus.kInfeasible:
        return SubproblemResult(status="infeasible", values=[], obj=None)
    elif model_status == HighsModelStatus.kUnbounded:
        # Extract extreme ray for theta column
        return SubproblemResult(status="unbounded", values=[], obj=None)
    ...
```

**Dual extraction** (for pricing in next iteration):
```python
sol = h.getSolution()
row_duals = list(sol.row_dual)   # π for linking constraints
```

**Infeasible vs Unbounded detection**: set `h.setOptionValue("solver", "simplex")` before calling `h.run()`. IPX (interior point) may return `kUnboundedOrInfeasible`; simplex gives a clean `kInfeasible` or `kUnbounded` distinction.

**Model status constants** (highspy 1.x):
```python
from highspy import HighsModelStatus
# HighsModelStatus.kOptimal
# HighsModelStatus.kInfeasible
# HighsModelStatus.kUnbounded
# HighsModelStatus.kObjectiveBound / kObjectiveTarget (iteration limit variants)
```

---

## 4. Parallelism Architecture (ThreadPoolExecutor)

### Decision: concurrent.futures.ThreadPoolExecutor — futures-collect pattern

**Key insight on thread count**: The constitution says "thousands of simultaneous workers." This means **thousands of subproblem tasks submitted per DW iteration**, NOT thousands of simultaneous OS threads. The executor maintains an internal work queue.

**Pool sizing**: `max_workers = min(cpu_count * 2, num_blocks)`. Subproblem count (`l`) may exceed CPU count by orders of magnitude; the pool queues excess tasks automatically.

**Rationale for threads over processes:**
- HiGHS releases the GIL during C++ solve → true CPU parallelism without multiprocessing overhead
- Subproblems are read-only w.r.t. input data (duals passed as immutable args)
- Results (new columns) are collected in main thread only — no shared mutable state during execution
- Thread startup overhead is negligible vs LP solve time

### Futures-Collect Pattern

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

def dispatch_subproblems(
    blocks: list[Block],
    row_duals: list[float],          # π — immutable, passed by value
    convexity_duals: list[float],    # μ_i — immutable
    workers: int | None,
    tolerance: float,
) -> list[SubproblemResult]:
    n_workers = workers or min(os.cpu_count() * 2, len(blocks))
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(solve_subproblem, block, row_duals, convexity_duals[i], tolerance): i
            for i, block in enumerate(blocks)
        }
        results = [None] * len(blocks)
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()   # propagates exceptions
    return results
```

**Thread safety guarantees:**
- `row_duals` and `convexity_duals` are passed as arguments (Python list → immutable during iteration)
- Workers produce `SubproblemResult` objects returned through futures — no shared write target
- Main thread aggregates results after `as_completed` loop — single-threaded aggregation
- `Highs()` instances are local to each worker call — never shared

**Warning for future implementors**: Do NOT use `ThreadPoolExecutor(max_workers=len(blocks))` when `len(blocks)` is in the thousands — this creates thousands of OS threads. Always cap at `cpu_count * 2` (or user-specified `--workers`).

---

## 5. Project Structure

### Decision: src-layout, hatchling build backend

**Rationale:**
- `src/` layout prevents accidental imports of the package source during testing (avoids import shadowing bugs)
- `hatchling` is the modern PEP 517 build backend; no setup.py required
- `py.typed` marker enables mypy to type-check downstream consumers

### Final Layout

```
dwsolver-vibes/
├── pyproject.toml
├── README.md
├── src/
│   └── dwsolver/
│       ├── __init__.py          # public API: solve(), Problem, Result, DWSolverInputError
│       ├── py.typed             # enables mypy for consumers
│       ├── models.py            # Pydantic v2 input/output models
│       ├── solver.py            # DW iteration loop, master RMP management
│       ├── subproblem.py        # per-block HiGHS solve, pricing, column prep
│       └── cli.py               # click CLI entry point
├── tests/
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_subproblem.py
│   │   └── test_solver.py
│   └── bdd/
│       ├── conftest.py
│       └── steps/
│           ├── test_cli_usage.py
│           └── test_library_usage.py
├── specs/
│   └── 001-gherkin-bdd-specs/
│       ├── features/
│       │   ├── cli_usage.feature
│       │   └── library_usage.feature
│       ├── spec.md
│       ├── plan.md
│       ├── research.md          # this file
│       ├── data-model.md
│       ├── quickstart.md
│       ├── contracts/
│       └── checklists/
└── .github/
    └── workflows/
        └── ci.yml
```

**pyproject.toml entry point:**
```toml
[project.scripts]
dwsolver = "dwsolver.cli:main"
```

**Dev install:** `pip install -e ".[dev]"`

**Dev extras:**
```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-bdd", "ruff", "mypy", "highspy"]
```

---

## 6. JSON Input Schema (Pydantic v2)

### Decision: Pydantic v2 with schema_version for forward evolution

**Rationale:**
- `model_validate()` + `extra="ignore"` allows adding future fields without breaking existing parsers
- `schema_version` string field at the top enables explicit migration functions (`migrate_v1_to_v2()`) keyed on `schema_version` major
- Pydantic v2 is significantly faster than v1 for validation and has cleaner mypy integration

### Block-Angular JSON Structure

```json
{
  "schema_version": "1.0",
  "metadata": {
    "name": "my_problem",
    "description": "optional human label"
  },
  "master": {
    "constraint_names": ["shared_resource_1", "shared_resource_2"],
    "rhs": [100.0, 50.0],
    "senses": ["=", "="]
  },
  "blocks": [
    {
      "block_id": "block_0",
      "variable_names": ["x_0", "x_1"],
      "objective": [3.0, 5.0],
      "bounds": [
        {"lower": 0.0, "upper": null},
        {"lower": 0.0, "upper": 10.0}
      ],
      "constraints": {
        "matrix": [[1.0, 2.0], [0.0, 1.0]],
        "rhs": [4.0, 3.0],
        "senses": ["=", "<="]
      },
      "linking_columns": {
        "rows": [0, 1],
        "cols": [0, 1],
        "values": [1.0, 0.5]
      }
    }
  ]
}
```

**`linking_columns`** maps block variables into the master's linking constraints — this is the `D_i` matrix in COO sparse form (`D_i[rows[k], cols[k]] = values[k]`). `rows[k]` references a row of `master.constraint_names`; `cols[k]` references a variable index within this block's `variable_names`.

**Schema evolution strategy:**
```python
def load_problem(path: Path) -> Problem:
    raw = json.loads(path.read_text())
    version = raw.get("schema_version", "1.0")
    major = int(version.split(".")[0])
    if major == 1:
        return Problem.model_validate(raw)
    raise DWSolverInputError(f"Unsupported schema_version: {version}")
```

**Constraint senses**: `"="`, `"<="`, `">="` — normalized to equality internally (slack/surplus added during master construction, analogous to Phase I setup in original C code).

---

## 7. Resolved Clarifications from Spec

| ID | Question | Decision |
|----|----------|----------|
| Q1 | Exit code contract | `0` for all valid solver outcomes (optimal, infeasible, unbounded, iteration_limit); non-zero only for tool failures (bad input, missing file) |
| Q2 | Iteration limit partial results | Return best feasible solution with status `iteration_limit`; `variable_values` populated |
| Q3 | Worker count | Runtime parameter `--workers` / `workers=`; default `cpu_count`; pool capped at `cpu_count * 2` internally |
| Q4 | LP solver backend | HiGHS only (`highspy`); pluggable interface deferred to future improvement |
| Q5 | Convergence tolerance | Default `DEFAULT_TOLERANCE = 1e-6` (named constant); exposed as `--tolerance` / `tolerance=` |

---

## 8. Open Questions / Risks

| # | Item | Risk Level | Mitigation |
|---|------|-----------|------------|
| R1 | HiGHS TOML input format | Low | FR-010 specifies JSON primary, TOML optional; TOML can be deferred post-v1 |
| R2 | DW cycling on degenerate problems | Medium | Honor iteration limit; document as known DW limitation in README |
| R3 | Extreme ray handling (unbounded subproblems) | Medium | Return `theta` column (extreme ray direction); add to RMP with unbounded lambda; test explicitly |
| R4 | Phase I feasibility method | Low | Add one artificial per linking constraint; minimize sum; standard Big-M approach |
| R5 | `highspy` API stability | Low | Pin `highspy>=1.13,<2` in pyproject.toml; GIL release behavior documented since 1.7 |
