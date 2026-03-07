# Research: CPLEX LP Input Format Support

**Feature**: 005-cplex-lp-input  
**Date**: 2026-03-07  
**Status**: Complete — no NEEDS CLARIFICATION remaining

---

## 1. Variable Name Regex

**Decision**: Use a general CPLEX LP variable name pattern, not the `w(...)` wrapper.  
**Rationale**: The existing `cplex_to_json.py` tool is hardcoded to the four_sea `w(...)` convention. A general parser needs to support any valid CPLEX LP variable name. Per the CPLEX LP format spec, variable names start with a letter or underscore, followed by letters, digits, underscores, dots, or parentheses/commas (the latter is used by `w(AC8_7,SEA,199)` style names).

**Pattern (Python)**:
```python
_VARNAME = r"[a-zA-Z_][a-zA-Z0-9_.,()]*"
_COEFF_VAR = re.compile(
    r"([+-]?\s*(?:\d+(?:\.\d+)?)?\s*)(" + _VARNAME + r")"
)
```

**Alternatives considered**: Reusing the `w(...)` specific regex — rejected because it would break any problem file that uses ordinary variable names like `x1`, `y2`, `flow_AB`.

---

## 2. CPLEX LP Section Keywords

**Decision**: Support the canonical section header names (case-insensitive), with no abbreviation aliases needed for the target scope (alotau/dwsolver examples).  
**Rationale**: The four_sea files from alotau/dwsolver use `Minimize`, `Subject To`, `Bounds`, `Generals`, `End` — no aliases. Handling `ST`, `S.T.`, `Maximize` covers the spec scope (FR-008 mentions `Maximize` direction for edge cases).

**Supported headers**:

| Section | Regex pattern |
|---------|---------------|
| Objective | `(?:Minimize\|Maximize)` |
| Constraints | `Subject\s+To` |
| Bounds | `Bounds` |
| Integer (ignored) | `(?:Generals\|General\|Gen\|Binary\|Bin)` |
| Terminator | `End\b` |

**Alternatives considered**: Adding `ST`, `S.T.` aliases — deferred; not present in target files and would complicate the regex without adding test coverage.

---

## 3. Objective Direction (Maximize)

**Decision**: When the master or subproblem file uses `Maximize`, negate all extracted objective coefficients before storing them. The solver always minimises.  
**Rationale**: Consistent with how LP relaxations are typically handled; matches spec edge case FR-008. Negation at parse time avoids leaking a direction flag into downstream models.

**Implementation**:
```python
direction = "maximize" if re.match(r"maximize", text, re.IGNORECASE) else "minimize"
...
if direction == "maximize":
    obj_coeffs = {k: -v for k, v in obj_coeffs.items()}
```

**Alternatives considered**: Passing a direction enum through to the `Problem` model — rejected; the existing `Problem` model has no direction field and all existing problems are minimize.

---

## 4. Objective Constant Term

**Decision**: Parse CPLEX LP block comments in the objective section for `\* constant term = N *\`; if found, inject a dummy variable `__objective_constant__` fixed at 1.0 with objective coefficient N into block 0 (first subproblem).  
**Rationale**: The four_sea `master.cplex` file contains `\* constant term = 160 *\` at line 83. Without injecting 160, the solver reports −148.0 instead of the expected 12.0. This is the same approach used and validated by `cplex_to_json.py`. Placing the constant in block 0 is correct because Dantzig-Wolfe's convexity constraint for block 0 ensures exactly one lambda from block 0 is selected (sum = 1), so the constant is included exactly once in the master objective.

**Pattern**:
```python
_OBJ_CONSTANT = re.compile(r"\\\*\s*constant\s+term\s*=\s*(-?\d+(?:\.\d+)?)\s*\*\\")
```

**Alternatives considered**: Ignoring the constant — rejected; causes SC-001 regression (wrong objective value). Adding a constant field to `Problem` — rejected; the existing model has no constant term and injecting a pinned dummy variable is already battle-tested.

---

## 5. Subproblem Objective Fallback

**Decision**: Parse each subproblem's `Minimize`/`Maximize` section. If the result has zero coefficients (empty or all-zero), fall back to master objective coefficients for that block's variables.  
**Rationale**: The four_sea `subprob_N.cplex` files have a `Minimize` section that references only a single dummy variable not in the Bounds section — confirmed not used. All block objectives come from `master_obj`. A general parser should try the subproblem first, then fall back, so that non-four_sea CPLEX LP files with explicit subproblem objectives work correctly.

**Fallback logic**:
```python
sub_obj = parse_objective_section(subprob_text)
if not any(sub_obj.get(v, 0.0) != 0.0 for v in var_names):
    obj_list = [master_obj.get(v, 0.0) for v in var_names]
else:
    obj_list = [sub_obj.get(v, 0.0) for v in var_names]
```

**Alternatives considered**: Always using master objective — rejected; breaks cases where subproblem has its own explicit costs. Always using subproblem objective — rejected; breaks four_sea reference problem.

---

## 6. Bounds Format

**Decision**: Support full CPLEX LP bounds syntax: double-sided (`l <= x <= u`), lower-only (`x >= l`), upper-only (`x <= u`), free (`x free`). Default if not declared: `lower=0.0, upper=None` (non-negative, unbounded above) — the CPLEX LP default.  
**Rationale**: Four_sea uses only `0 <= w(...) <= 1`. The existing tool's hardcoded `0 <= w(...) <= 1` pattern would fail silently on any other bound format. Supporting all formats ensures correctness for other problem files while passing all existing tests.

**Patterns**:
```python
_DOUBLE_BOUND = re.compile(r"(-?\d+(?:\.\d+)?)\s*<=\s*(" + _VARNAME + r")\s*<=\s*(-?\d+(?:\.\d+)?)")
_LOWER_BOUND  = re.compile(r"(" + _VARNAME + r")\s*>=\s*(-?\d+(?:\.\d+)?)")
_UPPER_BOUND  = re.compile(r"(" + _VARNAME + r")\s*<=\s*(-?\d+(?:\.\d+)?)")
_FREE_VAR     = re.compile(r"(" + _VARNAME + r")\s+free", re.IGNORECASE)
```

**Alternatives considered**: Restricting to `0 <= x <= upper` — rejected; insufficient for a general parser. Requiring the `Bounds` section to list all variables — accepted; variables not in Bounds use the CPLEX LP default (lower=0, upper=+∞).

---

## 7. Linking Inference Strategy

**Decision**: Infer linking columns by matching variable names from the subproblem's Bounds section (= "this block owns these variables") against the master's `Subject To` constraint expressions.  
**Rationale**: Validated by `cplex_to_json.py::build_linking_columns()` which uses exactly this approach and produces the correct JSON fixture for four_sea. The Bounds section is the canonical place where a subproblem declares its variables in CPLEX LP format.

**Algorithm**:
```
For each master constraint row_idx, row_dict in master_rows:
    For each var_name, coeff in row_dict.items():
        If var_name in this_block.var_index:
            append (row_idx, col_idx, coeff) to COO triplets
```

**Alternatives considered**: Using explicit "COLUMNS" section (MPS format) — N/A; CPLEX LP format does not have a COLUMNS section. Parsing the subproblem's `Subject To` for variable declarations — rejected; variables not always in constraints (objective-only variables would be missed).

---

## 8. CLI Multi-File Argument Design

**Decision**: Use Click's `nargs=-1, type=click.Path(exists=False)` on a single `FILES` positional argument. First element = master, remaining = subproblems. Format auto-detected from the first file's extension; `--format lp|json` overrides.  
**Rationale**: `nargs=-1` is the standard Click idiom for variadic positional arguments. Backward compatibility: a single `.json` file is still handled identically to the current CLI.

**Detection logic**:
```
if --format json  → JSON mode (requires single file)
if --format lp    → LP mode (requires ≥2 files)
elif files[0].suffix in {".json"}     → JSON mode
elif files[0].suffix in {".lp", ".cplex"} → LP mode
else                                  → error: specify --format
```

**Alternatives considered**: Separate `--master` and `--subproblem` options — rejected; more verbose than positional args and inconsistent with the reference C solver's command-line convention. Subcommands (`dwsolver lp master.lp sub1.lp`) — rejected; adds a non-backward-compatible change.

---

## 9. New Module Placement

**Decision**: `src/dwsolver/lp_parser.py` — CPLEX LP parsing functions and intermediate dataclasses, all internal to the package.  
**Rationale**: Stays alongside `models.py` and `solver.py`; importable from both `cli.py` and `models.py` without circular imports. The public API (`Problem.from_lp`, `Problem.from_lp_text`) lives on the existing `Problem` class; `lp_parser.py` is an implementation detail.

**Alternatives considered**: Separate top-level package — rejected; over-engineered for a single module. Inlining parser into `models.py` — rejected; would bloat models.py past 500 lines and mix responsibilities.

---

## 10. CPLEX LP Fixture Files

**Decision**: Download and store the four_sea CPLEX LP files as static test fixtures in `tests/fixtures/four_sea/` (5 files: `master.cplex`, `subprob_1.cplex`–`subprob_4.cplex`). Fetch once via a test setup utility; do not embed raw download in tests.  
**Rationale**: The existing `tests/fixtures/ref_four_sea.json` was generated from these files. Having them locally enables offline testing, avoids network flakiness in CI, and lets the BDD test reference them with simple `Path` lookups.

**Alternatives considered**: Fetching from GitHub in the test — rejected; network dependency violates CI reliability. Reconstructing from JSON — not possible (lossy conversion).
