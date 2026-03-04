# CLI API Contract

**Command**: `dwsolver`  
**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03  
**Entry point**: `dwsolver.cli:main` (registered via `[project.scripts]` in `pyproject.toml`)

---

## Synopsis

```
dwsolver [OPTIONS] PROBLEM_FILE
```

---

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `PROBLEM_FILE` | `PATH` | Path to the JSON problem file (required) |

---

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output PATH` | path | `<PROBLEM_FILE>.solution.json` | Output file for the solution JSON |
| `--workers INTEGER` | int | `cpu_count` | Number of parallel worker threads |
| `--tolerance FLOAT` | float | `1e-6` | DW convergence tolerance |
| `--help` | flag | — | Show help and exit |

---

## Exit Codes

| Code | Condition |
|------|-----------|
| `0` | All valid solver outcomes: `optimal`, `infeasible`, `unbounded`, `iteration_limit` |
| `1` | Tool failure: malformed/unreadable input file, missing file, unsupported schema, internal error |

> **Rationale (FR-004)**: A non-zero exit for infeasible/unbounded would conflate algorithmic results with tool failures, breaking scripting pipelines. The solution JSON always carries the `status` field for programmatic consumption.

---

## Stdout / Stderr

| Stream | Content |
|--------|---------|
| `stdout` | Silent on success (solution goes to `--output` file) |
| `stderr` | All error messages (malformed input, missing file, internal error) |

The CLI never writes human-readable results to `stdout` — this ensures it is pipe-safe.

---

## Output File Format

When `--output` is provided (or defaults to `<input>.solution.json`), the CLI writes a JSON file with the same structure as `Result`:

```json
{
  "status": "optimal",
  "objective": 42.5,
  "variable_values": {
    "x_0": 3.0,
    "x_1": 1.5
  },
  "iterations": 7,
  "tolerance": 1e-6,
  "solver_info": {}
}
```

For infeasible/unbounded outcomes, `variable_values` is `{}` and `objective` is `null`.

---

## Examples

```bash
# Basic solve — output defaults to problem.json.solution.json
dwsolver problem.json

# Explicit output path
dwsolver problem.json --output results/solution.json

# Parallel solve with 8 workers
dwsolver problem.json --workers 8

# Custom convergence tolerance
dwsolver problem.json --tolerance 1e-4

# Exit code check in a script
dwsolver problem.json && echo "Solver ran successfully"
# (note: exit 0 even for infeasible — check status field in output)
```

---

## Determinism Note (SC-006)

Results are identical regardless of `--workers` value. The `--workers` parameter controls concurrency (parallelism / speed) only, not correctness. Two invocations:

```bash
dwsolver problem.json --workers 1
dwsolver problem.json --workers 8
```

must produce the same `status`, `objective`, and `variable_values`.
