# Quickstart: CPLEX LP Input Format

**Feature**: 005-cplex-lp-input  
**Date**: 2026-03-07

---

## What changed

You can now provide CPLEX LP files directly to `dwsolver` instead of (or alongside)
the existing JSON format. Supply the master file first, then each subproblem file:

```bash
dwsolver master.lp sub1.lp sub2.lp sub3.lp sub4.lp
```

Files with `.lp` or `.cplex` extensions are detected automatically. The existing
JSON workflow is unchanged:

```bash
dwsolver problem.json          # still works exactly as before
```

---

## From the command line

### Solve a block-angular LP expressed as CPLEX LP files

```bash
# Auto-detection by extension (.lp or .cplex)
dwsolver master.lp sub1.lp sub2.lp

# Explicit format override
dwsolver --format lp master.cplex sub1.cplex sub2.cplex

# Specify output location
dwsolver master.lp sub1.lp sub2.lp -o solution.json

# Control parallelism
dwsolver master.lp sub1.lp sub2.lp --workers 8
```

The solution is written to `master.solution.json` by default (or the path given
with `--output`).

---

## From Python (library API)

### Load from files

```python
from dwsolver import Problem, solve

problem = Problem.from_lp("master.lp", ["sub1.lp", "sub2.lp"])
result = solve(problem, workers=4)

print(result.status)           # "optimal"
print(result.objective)        # e.g., 12.0
```

### Load from in-memory strings

Useful when the LP text comes from a database, network stream, or generation tool:

```python
from dwsolver import Problem, solve

master_text = open("master.lp").read()
sub_texts = [open(f"sub{i}.lp").read() for i in range(1, 5)]

problem = Problem.from_lp_text(master_text, sub_texts)
result = solve(problem)
```

### Error handling

All input errors raise `DWSolverInputError` with a descriptive message:

```python
from dwsolver import Problem, DWSolverInputError

try:
    problem = Problem.from_lp("master.lp", ["sub1.lp"])
except DWSolverInputError as exc:
    print(f"Input error: {exc}")
    # e.g.: "Subproblem 'sub1.lp' (block_0): no variables declared in Bounds section"
```

---

## CPLEX LP File Structure

The parser supports the subset of CPLEX LP format used by `alotau/dwsolver`
reference files. A minimal problem has this structure:

**master.lp** — coupling constraints + global objective:
```
Minimize
 obj: + 3 x1 + 5 x2 + 2 y1 + 4 y2

Subject To
 c1: x1 + y1 <= 10
 c2: x2 + y2 <= 8

End
```

**sub1.lp** — subproblem 1 variables and local constraints:
```
Subject To
 local1: x1 - x2 >= 0

Bounds
 0 <= x1 <= 5
 0 <= x2 <= 5

End
```

**sub2.lp** — subproblem 2 variables and local constraints:
```
Subject To
 local2: y1 + y2 <= 6

Bounds
 0 <= y1 <= 4
 0 <= y2 <= 4

End
```

### Key rules

- **Master file**: must have a `Subject To` section with at least one constraint.
- **Subproblem files**: must have a `Bounds` section declaring at least one variable.
- **Variable ownership**: A variable belongs to the subproblem that declares it in `Bounds`.
- **Objective fallback**: If the subproblem has no `Minimize`/`Maximize` section (or it's empty), the master's objective coefficients for that block's variables are used.
- **Block ordering**: The position of a subproblem file on the command line determines its `block_id` (`block_0` first, `block_1` second, etc.).
- **Integer variables**: `Generals` / `Binary` sections are silently ignored (LP relaxation only).
- **Maximise**: A `Maximize` section is supported — coefficients are internally negated to convert to minimisation.

---

## Implementation guide for developers

### New module

`src/dwsolver/lp_parser.py` implements:

```python
parse_master(text: str) -> MasterLP
parse_subproblem(text: str, block_id: str) -> SubproblemLP
infer_linking(master: MasterLP, sub: SubproblemLP) -> LinkingSpec
resolve_block_objective(master: MasterLP, sub: SubproblemLP) -> list[float]
assemble_problem(master: MasterLP, subs: list[SubproblemLP]) -> Problem
load_problem_from_lp(master_path: Path, subproblem_paths: list[Path]) -> Problem
```

See [contracts/lp_parser_api.md](contracts/lp_parser_api.md) for full signatures.

### Modified files

| File | Change |
|------|--------|
| `src/dwsolver/models.py` | Add `Problem.from_lp()` and `Problem.from_lp_text()` |
| `src/dwsolver/cli.py` | Change `PROBLEM_FILE` arg to `FILES...` nargs=-1; add `--format` option |
| `src/dwsolver/__init__.py` | Export `from_lp` and `from_lp_text` (they live on `Problem`, already exported) |

### Test files

| File | Purpose |
|------|---------|
| `tests/unit/test_lp_parser.py` | Unit tests for `lp_parser.py` (written before implementation) |
| `tests/bdd/steps/test_cplex_lp_usage.py` | BDD step implementations |
| `specs/005-cplex-lp-input/features/cplex_lp_usage.feature` | Gherkin scenarios |
| `tests/fixtures/four_sea/*.cplex` | CPLEX LP fixture files for four_sea regression |

### Reference implementation

`specs/002-fix-four-sea-tests/tools/cplex_to_json.py` is the reference for parsing
logic. The general parser in `lp_parser.py` extends it to support:
- Arbitrary variable names (not just `w(...)`)
- General bounds formats (not just `0 <= x <= 1`)
- Explicit subproblem objectives
- `Maximize` direction
