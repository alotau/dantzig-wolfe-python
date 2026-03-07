# Data Model: Synthetic Block-Angular LP Generator

**Branch**: `003-generate-synthetic-block`
**Phase**: 1 — Design

---

## Entities

### `SyntheticCase`

Describes one entry in the static test table. Drives `@pytest.mark.parametrize`.

| Field | Type | Description |
|-------|------|-------------|
| `seed` | `int` | RNG seed; uniquely identifies the problem |
| `num_blocks` | `int` | Number of D-W blocks (2–6) |
| `vars_per_block` | `int` | Variables per block (5–20) |
| `local_constraints` | `int` | Local constraints per block (3–10) |
| `master_constraints` | `int` | Linking / master constraint rows (1–5) |
| `label` | `str` | Pytest ID string: `"seed=N-XblkYvarZmc"` |

**Validation rules**:
- All integer fields > 0
- `label` is derived, not stored separately — computed as `f"seed={seed}-{num_blocks}blk-{vars_per_block}var-{master_constraints}mc"`
- `vars_per_block >= 2` (need at least 2 linking variable candidates per block)

**Source**: module-level constant `SYNTHETIC_CASES: list[SyntheticCase]` in `tests/synthetic.py`

---

### `GeneratedProblem`

Return type of `generate_problem(...)`. Bundles the dwsolver JSON encoding and the
HiGHS-verified reference objective.

| Field | Type | Description |
|-------|------|-------------|
| `problem` | `Problem` | Fully validated dwsolver `Problem` instance |
| `reference_objective` | `float` | HiGHS optimal objective for the monolithic LP |

**Invariants**:
- `problem` has passed `Problem.model_validate()` without error
- `reference_objective` is finite (not ±∞, not NaN)
- `reference_objective` is the result of solving the monolithic form reconstructed
  **solely** from `problem` — verifying self-consistency of the encoding

---

### `Problem` (existing schema, from `src/dwsolver/models.py`)

Listed here for the generator's reference — no changes to this entity.

```
Problem
├── schema_version: "1.0"
├── metadata: dict (optional)
├── master: Master
│   ├── constraint_names: list[str]
│   ├── rhs: list[float]
│   └── senses: list[str]   # "=", "<=", ">="
└── blocks: list[Block]
    ├── block_id: str
    ├── variable_names: list[str]   # globally unique
    ├── objective: list[float]
    ├── bounds: list[Bounds]
    │   ├── lower: float
    │   └── upper: float | None
    ├── constraints: BlockConstraints
    │   ├── matrix: list[list[float]]  # DENSE row-major
    │   ├── rhs: list[float]
    │   └── senses: list[str]
    └── linking_columns: LinkingColumns
        ├── rows: list[int]   # master row index
        ├── cols: list[int]   # block-local variable index
        └── values: list[float]
```

---

## State Transitions

### Generator construction sequence (within `generate_problem`)

```
seed
  │
  ▼
rng = default_rng(seed)          # deterministic RNG
  │
  ├─▶ draw objective coefficients  (Uniform[-2, 2], n_blocks × vars_per_block)
  ├─▶ draw local constraint coefficients (Uniform[-1, 1], n_blocks × local_cstr × vars_per_block)
  ├─▶ compute local rhs from x*=0.5 + slack (Uniform[0.1, 0.5])
  ├─▶ draw linking variable selections     (choose min(2, vars_per_block) indices per block)
  ├─▶ draw linking coefficients            (Uniform[-1, 1], master_cstr × n_blocks × k)
  ├─▶ compute master rhs from x*=0.5 + slack
  │
  ▼
assemble Block objects (one per block)
  │
  ▼
Problem.model_validate(...)       # raises AssertionError if invalid — generator bug
  │
  ▼
solve_monolithic_highs(problem)   # build monolithic LP row-by-row, run HiGHS
  │
  ▼                               # raises AssertionError if infeasible — generator bug
GeneratedProblem(problem, reference_objective)
```

---

## Variable Naming Convention

Variables in generated problems use the pattern:

```
b{block_id}_x{var_index}
```

e.g. `b1_x0`, `b1_x1`, ..., `b1_x4` for block 1 with 5 variables;  
`b2_x0`, `b2_x1`, ..., `b2_x4` for block 2.

This guarantees:
- **Global uniqueness** across all blocks (block prefix disambiguates)
- **Alphabetical sort** preserves block ordering
- **Human-readability** in test output and JSON inspection

Constraint names follow the same pattern:
- Local: `b{block_id}_c{row_index}` (e.g., `b1_c0`)
- Master: `mc{row_index}` (e.g., `mc0`, `mc1`)

---

## Monolithic Reconstruction Algorithm

Given a `Problem`, build the equivalent single LP for HiGHS:

```
global_vars = concat(block.variable_names for block in problem.blocks)
col_offset[i] = sum(len(problem.blocks[j].variable_names) for j in range(i))

For each block i:
  For each local row r in block.constraints:
    Add HiGHS row with coefficients at column positions [col_offset[i] + col for col in 0..n_vars_i]

For each master row m in 0..len(problem.master.rhs):
  Build sparse row: for each COO entry (rows[k], cols[k], values[k]) where rows[k]==m:
    global_col = col_offset[block_idx] + cols[k]  # block_idx from which block's COO
  Apply sense/rhs from problem.master.senses[m] and problem.master.rhs[m]

Objective: for each block i, set global column costs from block.objective
```

The global column offset mapping is the only non-trivial bookkeeping step.
A helper `_col_offsets(problem) -> list[int]` computes it once.
