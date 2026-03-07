# Contract: LP Parser Module API

**Module**: `src/dwsolver/lp_parser.py`  
**Feature**: 005-cplex-lp-input  
**Date**: 2026-03-07  
**Visibility**: Internal (not exported from `dwsolver.__init__`)

---

## Purpose

`lp_parser.py` provides the CPLEX LP parsing and problem assembly functions that back
the two public `Problem` class methods (`from_lp` and `from_lp_text`). It is an
implementation detail of the `dwsolver` package, not part of the public API.

---

## Dataclasses

```python
@dataclasses.dataclass(frozen=True)
class MasterLP:
    constraint_names: list[str]
    rhs: list[float]
    senses: list[str]
    objective: dict[str, float]         # var_name → coeff; includes master obj vars
    row_coefficients: list[dict[str, float]]  # per-constraint sparse {var: coeff}
    obj_constant: float                  # extracted from \* constant term = N *\; 0.0 if absent

@dataclasses.dataclass(frozen=True)
class SubproblemLP:
    block_id: str
    variable_names: list[str]           # parse-order; determines column indices
    bounds: list[tuple[float, float | None]]  # (lower, upper); upper=None = +∞
    objective: dict[str, float]         # sparse; empty if section absent/empty
    constraints_matrix: list[list[float]]
    constraints_rhs: list[float]
    constraints_senses: list[str]
    constraints_names: list[str]

@dataclasses.dataclass(frozen=True)
class LinkingSpec:
    rows: list[int]
    cols: list[int]
    values: list[float]
```

---

## Public Functions

### `parse_master(text: str) -> MasterLP`

Parse the text of a master CPLEX LP file.

**Inputs**:
- `text`: Full UTF-8 text of the master `.lp` or `.cplex` file.

**Output**: `MasterLP` dataclass.

**Raises**: `DWSolverInputError` if:
- No `Subject To` section found (likely not a valid CPLEX LP file)
- No coupling constraints found in `Subject To` section

**Notes**:
- Objective direction (`Minimize`/`Maximize`) is absorbed: `Maximize` negates all objective coefficients.
- Block comments `\* constant term = N *\` within the objective section set `obj_constant`.

---

### `parse_subproblem(text: str, block_id: str) -> SubproblemLP`

Parse the text of one subproblem CPLEX LP file.

**Inputs**:
- `text`: Full UTF-8 text of a subproblem `.lp` or `.cplex` file.
- `block_id`: String identifier assigned by the caller (`"block_0"`, `"block_1"`, …).

**Output**: `SubproblemLP` dataclass.

**Raises**: `DWSolverInputError` if:
- No `Bounds` section found OR `Bounds` section declares no variables — no variables means this subproblem cannot be used.

**Notes**:
- Variables are collected from the `Bounds` section in file order.
- If the `Minimize`/`Maximize` section has no matching variable terms, `objective` is empty.

---

### `infer_linking(master: MasterLP, sub: SubproblemLP) -> LinkingSpec`

Build the sparse COO linking matrix for one subproblem by matching its variables
against the master's coupling constraint expressions.

**Inputs**:
- `master`: Parsed master.
- `sub`: Parsed subproblem.

**Output**: `LinkingSpec` — COO triplets `(row_idx, col_idx, coeff)` for every
`(master_constraint, subproblem_variable)` pair with a non-zero coefficient.

**Raises**: never raises. An empty `LinkingSpec` (all lists empty) is valid and
means the subproblem has no variables appearing in the master constraints.

---

### `resolve_block_objective(master: MasterLP, sub: SubproblemLP) -> list[float]`

Determine the objective coefficient list for a block using a master-first,
subproblem-fallback strategy.

**Inputs**:
- `master`: Parsed master (provides primary coefficients).
- `sub`: Parsed subproblem (provides fallback coefficients).

**Output**: `list[float]` of length `len(sub.variable_names)`.

**Logic**:
1. If any variable in `sub.variable_names` has a non-zero entry in `master.objective`, use `master.objective` (missing vars default to 0.0).
2. Otherwise, use `sub.objective` (missing vars default to 0.0).

---

### `assemble_problem(master: MasterLP, subs: list[SubproblemLP]) -> Problem`

Assemble a validated `Problem` from parsed intermediate objects.

**Inputs**:
- `master`: Parsed master.
- `subs`: Parsed subproblems in argument order (determines `block_id` and block index).

**Output**: Validated `Problem` instance.

**Side effects**: If `master.obj_constant != 0.0`, a dummy variable
`__objective_constant__` is injected into `subs[0]` before assembly.

**Raises**: `DWSolverInputError` if:
- `subs` is empty.
- A variable name appears in more than one subproblem (duplicate variable across blocks).
- A variable appearing in any master coupling constraint is not declared in any subproblem's `Bounds` section.
- Pydantic validation fails (re-wrapped as `DWSolverInputError`).

---

### `load_problem_from_lp(master_path: Path, subproblem_paths: list[Path]) -> Problem`

Convenience function: read files, parse, and assemble.

**Inputs**:
- `master_path`: Path to the master LP file.
- `subproblem_paths`: Ordered list of subproblem LP file paths.

**Output**: Validated `Problem`.

**Raises**: `DWSolverInputError` for any file I/O, parse, or assembly error.

---

## Error Handling

All functions raise `DWSolverInputError` (from `dwsolver.models`) on any detectable
structural problem. Error messages MUST identify the source file by name and describe
the problem clearly enough for the user to fix it.

Examples of required error message patterns:

| Condition | Message pattern |
|-----------|-----------------|
| File not found | `"Master file not found: 'master.lp'"` |
| Subproblem has no variables | `"Subproblem 'sub1.lp' (block_0): no variables declared in Bounds section"` |
| Empty master constraints | `"Master file 'master.lp': no coupling constraints found in Subject To section"` |
| Duplicate variable | `"Variable 'x1' appears in both 'sub1.lp' (block_0) and 'sub2.lp' (block_1)"` |
| Master variable unassigned | `"Variable 'w(AC1_0,SEA,199)' appears in master coupling constraints but is not declared in any subproblem Bounds section"` |
| Unknown `--format` value | `"Unknown format 'xyz'; accepted values: json, lp"` |

---

## Supported CPLEX LP Syntax Subset

| Feature | Supported |
|---------|-----------|
| `Minimize` / `Maximize` | Yes (Maximize negates coefficients) |
| `Subject To` | Yes |
| `Bounds` — double-sided: `l <= x <= u` | Yes |
| `Bounds` — lower-only: `x >= l` | Yes |
| `Bounds` — upper-only: `x <= u` | Yes |
| `Bounds` — free: `x free` | Yes (lower=-∞, upper=+∞) |
| `Generals` / `General` / `Gen` / `Binary` / `Bin` | Silently ignored (LP relaxation) |
| `End` | Treated as section terminator |
| Backslash line comments (`\ ...`) | Ignored |
| CPLEX block comments (`\* ... *\`) | Parsed for `constant term = N`; otherwise ignored |
| Multi-line expressions (continuation by indentation) | Yes |
| Variable names: `[a-zA-Z_][a-zA-Z0-9_.,()]*` | Yes |
| Coefficient-free terms (`+ x`) | Yes (defaults to ±1.0) |
| SOS constraints | Not supported |
| Piecewise-linear objective | Not supported |
| Quadratic objective | Not supported |
