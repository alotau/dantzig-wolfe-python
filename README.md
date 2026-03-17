# dwsolver

A Python implementation of the **Dantzig-Wolfe decomposition algorithm** for block-angular linear programs.

[![CI](https://github.com/alotau/dantzig-wolfe-python/actions/workflows/ci.yml/badge.svg)](https://github.com/alotau/dantzig-wolfe-python/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Installation

```bash
pip install dwsolver
```

Or from source:

```bash
git clone https://github.com/alotau/dwsolver-vibes
cd dwsolver-vibes
pip install -e ".[dev]"
# Install git hooks (runs ruff format + lint before every push)
bash scripts/install-hooks.sh
```

Requires Python 3.11+ and automatically installs [`highspy`](https://pypi.org/project/highspy/) (the HiGHS LP solver).

---

## CLI Usage

Supports both **JSON** and **CPLEX LP** formats with automatic detection:

```bash
# JSON format
dwsolver problem.json
# → writes problem.solution.json

# CPLEX LP format: master file + one or more subproblem files
dwsolver master.lp sub1.lp sub2.lp
# → writes master.solution.json
```

**Options** (apply to both formats):

```bash
dwsolver master.lp sub1.lp --output results/solution.json  # explicit output path
dwsolver master.lp sub1.lp --workers 8                     # parallel subproblem solves
dwsolver master.lp sub1.lp --tolerance 1e-4                # custom convergence tolerance
dwsolver master.lp sub1.lp --format lp                     # override auto-detection
```

**Format detection**: File extension determines format (`.json` → JSON; `.lp` or `.cplex` → CPLEX LP).
Use `--format` to override. CPLEX LP requires a master file and at least one subproblem file.

**Exit codes**: `0` for all valid solver outcomes (optimal, infeasible, unbounded, iteration
limit); `1` for tool failures (missing file, invalid schema). Always check `status` in the
output JSON for the actual solver result.

---

## Library Usage

```python
from dwsolver import solve, Problem, SolveStatus, DWSolverInputError

# Load from JSON file
problem = Problem.from_file("problem.json")
result = solve(problem)

# Load from CPLEX LP files
problem = Problem.from_lp("master.lp", ["sub1.lp", "sub2.lp"])
result = solve(problem)

# Load from in-memory strings (CPLEX LP)
problem = Problem.from_lp_text(master_text, [sub1_text, sub2_text])
result = solve(problem)

print(result.status)            # "optimal" | "infeasible" | "unbounded" | "iteration_limit"
print(result.objective)         # float or None (infeasible/unbounded)
print(result.variable_values)   # {"x1": 3.0, "x2": 1.5, ...}

# Optional parameters
result = solve(problem, workers=8, tolerance=1e-4, max_iterations=500)

# Handle all outcomes
match result.status:
    case SolveStatus.OPTIMAL:
        print(f"Optimal: {result.objective}")
    case SolveStatus.INFEASIBLE:
        print("Problem is infeasible")
    case SolveStatus.UNBOUNDED:
        print("Problem is unbounded")
    case SolveStatus.ITERATION_LIMIT:
        print(f"Best feasible objective: {result.objective}")
```

### Error handling

```python
try:
    problem = Problem.from_file("problem.json")
    result = solve(problem)
except DWSolverInputError as exc:
    print(f"Invalid input: {exc}")
```

---

## Input Formats

Problems can be described in **JSON** or **CPLEX LP** format.

### JSON Format

Structured JSON ([full schema reference](specs/001-gherkin-bdd-specs/contracts/json_schema.md)):

```json
{
  "schema_version": "1.0",
  "master": {
    "constraint_names": ["linking_row"],
    "rhs": [3.0],
    "senses": ["="]
  },
  "blocks": [
    {
      "block_id": "block_0",
      "variable_names": ["x1"],
      "objective": [-2.0],
      "bounds": [{"lower": 0.0, "upper": 2.0}],
      "constraints": {"matrix": [], "rhs": [], "senses": []},
      "linking_columns": {"rows": [0], "cols": [0], "values": [1.0]}
    }
  ]
}
```

### CPLEX LP Format

Industrial-standard CPLEX LP format. Provide a master file defining coupling constraints
and one or more subproblem files defining local constraints, bounds, and subproblem objectives.
Format is auto-detected from file extension (`.lp`, `.cplex`):

**Master file** (`master.lp`):
```
Minimize
 obj: c1*x1 + c2*x2 + ...  
Subject To
 row1: expr1 <= rhs1
 row2: expr2 = rhs2
End
```

**Subproblem file** (`sub1.lp`):
```
Minimize
 obj: d1*x1 + ...          
Subject To
 local_row1: expr1 >= rhs1
Bounds
 0 <= x1 <= 10
 x2 free
End
```

Variables are matched by name across master and subproblem files; those appearing in master
coupling constraints form the linking structure automatically. Block variables are inferred
from subproblem bounds.

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/unit/        # unit tests
pytest tests/bdd/         # BDD / acceptance tests
mypy src/                 # type check
ruff check src/ tests/    # lint
ruff format src/ tests/   # format
```
