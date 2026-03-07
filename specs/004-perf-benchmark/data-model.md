# Data Model: Performance Benchmark — Workers vs. Subproblems

**Phase 1 output for `004-perf-benchmark`**
**Date**: 2026-03-06

---

## Entities

### 1. `BenchConfig`

Runtime configuration for a single benchmark run. Populated from CLI flags.

| Field          | Type            | Default          | Notes                                          |
|----------------|-----------------|------------------|------------------------------------------------|
| `subproblems`  | `range`         | `range(1, 21)`   | Subproblem counts to benchmark                 |
| `worker_counts`| `list[int]`     | `[4,8,12,16,20]` | Fixed by FR-003                                |
| `repeats`      | `int`           | `1`              | Number of timed runs per cell (FR-008)         |
| `timeout`      | `float`         | `120.0`          | Per-cell wall-clock timeout in seconds         |
| `save_chart`   | `Path \| None`  | `None`           | If set, write heatmap/line-chart to this path  |

---

### 2. `CellResult`

Outcome of a single (subproblems, workers) cell.

| Field        | Type               | Notes                                              |
|--------------|--------------------|----------------------------------------------------|
| `n_blocks`   | `int`              | Number of subproblems (row key)                    |
| `workers`    | `int`              | Worker count (column key)                          |
| `elapsed`    | `float \| None`    | Wall-clock seconds (minimum over repeats)          |
| `status`     | `SolveStatus \| CellError` | `SolveStatus.OPTIMAL`, `CellError.TIMEOUT`, or `CellError.ERROR` |
| `iterations` | `int \| None`      | DW iteration count from `Result`                   |

---

### 3. `BenchMatrix`

The full 20×5 result matrix.

| Field    | Type                      | Notes                          |
|----------|---------------------------|--------------------------------|
| `cells`  | `list[list[CellResult]]`  | Indexed `[n_blocks-1][w_idx]`  |
| `config` | `BenchConfig`             | The config used to produce it  |

**Invariants**:
- `len(cells) == 20` (one row per subproblem count 1–20)
- `len(cells[i]) == 5` (one column per worker count)
- No cell is `None`; every cell has a status (optimal, TIMEOUT, or ERROR)

---

### 4. `CellError` (enum)

Distinguishes timeout from other errors in cell status.

| Value     | Meaning                                             |
|-----------|-----------------------------------------------------|
| `TIMEOUT` | `solve()` did not return within `config.timeout` s  |
| `ERROR`   | `solve()` raised an unexpected exception            |

---

### 5. `IdenticalBlockProblem` (generated, not persisted)

A `dwsolver.Problem` with `n` identical blocks.

| Attribute          | Value / Rule                                             |
|--------------------|----------------------------------------------------------|
| Template block     | Fixed seed=0, 10 variables, 5 local constraints          |
| Block replication  | Same `Block` structure repeated `n` times                |
| Linking constraint | 1 master constraint per block variable (coefficient=1.0) |
| Objective          | Identical across blocks; minimise total                  |
| Feasibility        | Guaranteed by slack-from-known-point (x*=0.5)            |
| Reference optimum  | `n × block_optimum` (linear in n by design)              |

**Note**: The reference optimum scaling property makes it easy to verify
correctness at all block counts with a single unit-test assertion.

---

## Validation Rules

| Entity            | Rule                                             | Violation response         |
|-------------------|--------------------------------------------------|----------------------------|
| `BenchConfig`     | `repeats >= 1`                                   | `argparse` error on startup |
| `BenchConfig`     | `timeout > 0`                                    | `argparse` error on startup |
| `CellResult`      | `elapsed >= 0` when `status == OPTIMAL`          | assertion in runner         |
| `IdenticalBlockProblem` | All produced `Problem` instances validate via `Problem.model_validate()` | assertion in generator |

---

## State Transitions

```
BenchConfig
    │
    ▼
for each (n_blocks, workers):
    generate IdenticalBlockProblem(n_blocks)
    ─── [solve timeout] ──► CellResult(status=TIMEOUT)
    ─── [solve exception] ─► CellResult(status=ERROR)
    ─── [solve success] ───► CellResult(status=OPTIMAL, elapsed=t)
    │
    ▼
BenchMatrix (all 100 cells populated)
    │
    ▼
print table to stdout
    │
    ├── [--save-chart] ──► write PNG to file
    └── done
```
