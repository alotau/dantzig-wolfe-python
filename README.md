# dwsolver

A Python implementation of the **Dantzig-Wolfe decomposition algorithm** for block-angular linear programs.

[![CI](https://github.com/alotau/dwsolver-vibes/actions/workflows/ci.yml/badge.svg)](https://github.com/alotau/dwsolver-vibes/actions/workflows/ci.yml)
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
```

Requires Python 3.11+ and automatically installs [`highspy`](https://pypi.org/project/highspy/) (the HiGHS LP solver).

---

## CLI Usage

```bash
dwsolver problem.json
# → writes problem.solution.json
```

```bash
dwsolver problem.json --output results/solution.json  # explicit output path
dwsolver problem.json --workers 8                     # parallel subproblem solves
dwsolver problem.json --tolerance 1e-4                # custom convergence tolerance
```

**Exit codes**: `0` for all valid solver outcomes (optimal, infeasible, unbounded, iteration
limit); `1` for tool failures (missing file, invalid schema). Always check `status` in the
output JSON for the actual solver result.

---

## Library Usage

```python
from dwsolver import solve, Problem, SolveStatus, DWSolverInputError

# Load from file
problem = Problem.from_file("problem.json")
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

## Input Format

Problems are described in JSON ([full schema reference](specs/001-gherkin-bdd-specs/contracts/json_schema.md)):

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
