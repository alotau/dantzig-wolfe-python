# dwsolver: Quickstart Guide

**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03

---

## Installation

```bash
pip install dwsolver
# or, from source:
git clone https://github.com/alotau/dwsolver-vibes
cd dwsolver-vibes
pip install -e ".[dev]"
```

`dwsolver` requires Python 3.11+ and automatically installs `highspy` (the HiGHS LP solver).

---

## CLI Usage

### Solve a problem file

```bash
dwsolver problem.json
# Solution written to: problem.json.solution.json
```

### Specify output path

```bash
dwsolver problem.json --output results/solution.json
```

### Use 8 parallel workers

```bash
dwsolver problem.json --workers 8
```

### Custom convergence tolerance

```bash
dwsolver problem.json --tolerance 1e-4
```

### Exit code

`dwsolver` exits `0` for all valid solver outcomes (optimal, infeasible, unbounded, iteration limit). Exit `1` indicates a tool failure (unreadable file, invalid input). Always check the `status` field in the output JSON for the solver result.

```bash
dwsolver problem.json && cat problem.json.solution.json | python -m json.tool
```

---

## Library Usage

### Basic solve

```python
from dwsolver import solve, Problem

problem = Problem.from_file("problem.json")
result = solve(problem)

print(result.status)        # "optimal", "infeasible", "unbounded", or "iteration_limit"
print(result.objective)     # e.g., 42.5 (or None if infeasible/unbounded)
print(result.variable_values)  # {"x0": 3.0, "x1": 1.5, ...}
```

### Parallel solve with custom tolerance

```python
result = solve(problem, workers=8, tolerance=1e-4)
```

### Handle all outcomes

```python
from dwsolver import solve, Problem, SolveStatus, DWSolverInputError

try:
    problem = Problem.from_file("problem.json")
    result = solve(problem, workers=4)
except DWSolverInputError as e:
    print(f"Bad input: {e}", file=sys.stderr)
    sys.exit(1)

match result.status:
    case SolveStatus.OPTIMAL:
        print(f"Optimal: {result.objective}")
        for name, val in result.variable_values.items():
            print(f"  {name} = {val}")
    case SolveStatus.INFEASIBLE:
        print("Problem is infeasible")
    case SolveStatus.UNBOUNDED:
        print("Problem is unbounded")
    case SolveStatus.ITERATION_LIMIT:
        print(f"Iteration limit reached. Best objective: {result.objective}")
        # result.variable_values is populated with best feasible solution
```

### Build a Problem programmatically

```python
from dwsolver import solve
from dwsolver.models import Problem, Master, Block, BlockConstraints, LinkingColumns, Bounds

problem = Problem(
    master=Master(
        constraint_names=["shared_capacity"],
        rhs=[10.0],
        senses=["<="],
    ),
    blocks=[
        Block(
            block_id="block_0",
            variable_names=["x0", "x1"],
            objective=[1.0, 2.0],
            bounds=[Bounds(lower=0.0), Bounds(lower=0.0, upper=5.0)],
            constraints=BlockConstraints(
                matrix=[[1.0, 1.0]],
                rhs=[4.0],
                senses=["<="],
            ),
            linking_columns=LinkingColumns(
                rows=[0, 0],
                cols=[0, 1],
                values=[1.0, 1.0],
            ),
        ),
    ],
)

result = solve(problem)
```

---

## Input File Format

See [contracts/json_schema.md](contracts/json_schema.md) for the full JSON schema reference and a complete worked example.

---

## Algorithm Reference

`dwsolver` implements the Dantzig-Wolfe decomposition algorithm for block-angular linear programs:

- **Original paper**: Dantzig, G.B. & Wolfe, P. (1960). "Decomposition Principle for Linear Programs." *Operations Research*, 8(1): 101–111.
- **This implementation**: Rios, J. (2013). "Algorithm 928: A general, parallel implementation of Dantzig–Wolfe decomposition." *ACM Trans. Math. Softw.*, 39(3), Article 21. DOI: 10.1145/2450153.2450159
