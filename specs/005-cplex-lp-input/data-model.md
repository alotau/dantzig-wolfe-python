# Data Model: CPLEX LP Input Format Support

**Feature**: 005-cplex-lp-input  
**Date**: 2026-03-07  
**Status**: Final

---

## Overview

This feature introduces one new source module (`lp_parser.py`) with three internal
intermediate dataclasses that represent parsed CPLEX LP state before it is assembled
into the existing `Problem` model hierarchy. No changes are made to the output models
(`Result`, `SolveStatus`) or the solver internals.

```
CPLEX LP files
    │
    ▼
lp_parser.py ──► MasterLP ──┐
                SubproblemLP ┤──► assemble_problem() ──► Problem (existing model)
                LinkingSpec  ┘
    │
    ▼
Problem.from_lp() / Problem.from_lp_text()  (in models.py)
```

---

## Intermediate Dataclasses (lp_parser.py)

These are implementation-internal dataclasses, not public API. They are used inside
`lp_parser.py` and passed to the assembler.

### MasterLP

Parsed representation of the master CPLEX LP file.

| Field | Type | Description |
|-------|------|-------------|
| `constraint_names` | `list[str]` | Names of all coupling constraints in parse order |
| `rhs` | `list[float]` | Right-hand side value for each coupling constraint |
| `senses` | `list[str]` | Sense for each constraint: `"<="`, `">="`, or `"="` |
| `objective` | `dict[str, float]` | Sparse map: variable name → objective coefficient from master `Minimize`/`Maximize` section |
| `row_coefficients` | `list[dict[str, float]]` | Per-constraint sparse coefficient maps: `[{var: coeff, ...}, ...]` indexed by constraint position |
| `obj_constant` | `float` | Scalar constant term extracted from `\* constant term = N *\` comment; 0.0 if absent |

**Constraints**:
- `len(constraint_names) == len(rhs) == len(senses) == len(row_coefficients)`
- `senses` values are a subset of `{"<=", ">=", "="}`

**Derived from**: `parse_master(text: str) -> MasterLP`

---

### SubproblemLP

Parsed representation of one subproblem CPLEX LP file.

| Field | Type | Description |
|-------|------|-------------|
| `block_id` | `str` | Caller-supplied block identifier, e.g., `"block_0"` |
| `variable_names` | `list[str]` | All variables declared in the `Bounds` section, in parse order |
| `bounds` | `list[tuple[float, float \| None]]` | `(lower, upper)` per variable; `upper=None` = +∞ |
| `objective` | `dict[str, float]` | Sparse: variable name → objective coefficient from this file's `Minimize`/`Maximize` section; empty dict if section absent or has no terms |
| `constraints_matrix` | `list[list[float]]` | Dense matrix: one row per constraint, one column per variable (in `variable_names` order) |
| `constraints_rhs` | `list[float]` | Right-hand side per constraint |
| `constraints_senses` | `list[str]` | Sense per constraint |
| `constraints_names` | `list[str]` | Name per constraint |

**Constraints**:
- `len(variable_names) == len(bounds)`
- `len(constraints_matrix) == len(constraints_rhs) == len(constraints_senses) == len(constraints_names)`
- Each row in `constraints_matrix` has length `len(variable_names)`

**Derived from**: `parse_subproblem(text: str, block_id: str) -> SubproblemLP`

---

### LinkingSpec

Sparse COO encoding of the linking matrix D_i between one subproblem's variables
and the master's coupling constraint rows.

| Field | Type | Description |
|-------|------|-------------|
| `rows` | `list[int]` | Master constraint row indices (0-based) |
| `cols` | `list[int]` | Subproblem variable column indices (0-based, relative to this block's `variable_names`) |
| `values` | `list[float]` | Coefficient values at `(rows[k], cols[k])` |

**Constraints**:
- `len(rows) == len(cols) == len(values)`
- All `rows[k]` in `[0, len(master.constraint_names))` 
- All `cols[k]` in `[0, len(sub.variable_names))`

**Derived from**: `infer_linking(master: MasterLP, sub: SubproblemLP) -> LinkingSpec`

---

## Mapping: Intermediate → Problem Models

The `assemble_problem()` function converts intermediate dataclasses into the
existing `Problem` Pydantic model:

| Source | Target |
|--------|--------|
| `MasterLP.constraint_names` | `Master.constraint_names` |
| `MasterLP.rhs` | `Master.rhs` |
| `MasterLP.senses` | `Master.senses` |
| `SubproblemLP.block_id` | `Block.block_id` |
| `SubproblemLP.variable_names` | `Block.variable_names` |
| resolved objective (§ below) | `Block.objective` |
| `SubproblemLP.bounds` → `Bounds(lower, upper)` | `Block.bounds` |
| `SubproblemLP.constraints_*` → `BlockConstraints` | `Block.constraints` |
| `LinkingSpec.rows/cols/values` → `LinkingColumns` | `Block.linking_columns` |

### Objective Resolution

For each sub `s` and its variable list `V`:

```
if any(s.objective.get(v, 0.0) != 0.0 for v in V):
    block_obj = [s.objective.get(v, 0.0) for v in V]
else:
    block_obj = [master.objective.get(v, 0.0) for v in V]
```

### Objective Constant Injection

If `master.obj_constant != 0.0`, a dummy variable is appended to block 0:

```
block_0.variable_names.append("__objective_constant__")
block_0.objective.append(master.obj_constant)
block_0.bounds.append(Bounds(lower=1.0, upper=1.0))
# Append a 0.0 column to every constraint row in block_0
```

---

## Existing Models (unchanged)

All existing models in `models.py` remain structurally unchanged. The only
modifications are additive:

- `Problem.from_lp(master_path, subproblem_paths)` — new class method
- `Problem.from_lp_text(master_text, subproblem_texts)` — new class method

The existing `Problem.from_file()`, `Master`, `Block`, `Bounds`, `BlockConstraints`,
`LinkingColumns`, `Result`, `SolveStatus`, and `DWSolverInputError` are unmodified.

---

## State Transitions (LP loading)

```
text input
    │
    ├─ parse_master()     →  MasterLP  (senses validated: {"<=", ">=", "="})
    │
    ├─ parse_subproblem() →  SubproblemLP  (dimensions validated: matrix rows = len(names))
    │
    ├─ infer_linking()    →  LinkingSpec  (indices in range; deduplicated)
    │
    └─ assemble_problem() →  dict
                                │
                                └─ Problem.model_validate(dict)
                                        │ on error: → DWSolverInputError
                                        │ on success: → Problem (frozen)
```

Any step that encounters a structural error raises `DWSolverInputError` with
a message identifying the file and the specific problem.
