# Contract: CLI API (Updated)

**Feature**: 005-cplex-lp-input  
**Date**: 2026-03-07  
**Supersedes**: `specs/001-gherkin-bdd-specs/contracts/cli_api.md` for the CLI invocation signature

---

## Entry Point

```
dwsolver [OPTIONS] FILES...
```

`FILES...` is a variadic positional argument (one or more file paths).

---

## Arguments

| Argument | Description |
|----------|-------------|
| `FILES...` | One or more input file paths. Behaviour depends on count and extension (see Format Detection below). |

---

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output` | `-o` | PATH | `<stem>.solution.json` | Path for the solution output file. Default: strip the first `FILES` extensión, append `.solution.json`. |
| `--workers` | `-w` | INT | None (auto) | Number of parallel subproblem workers. |
| `--tolerance` | `-t` | FLOAT | 1e-6 | Dantzig-Wolfe convergence tolerance. |
| `--format` | | `json\|lp` | (auto) | Override format auto-detection. `json` requires a single file; `lp` requires ≥2 files. |

---

## Format Detection

The input format is determined as follows, in priority order:

1. **`--format json`** explicitly given → JSON mode. Exactly one `FILES` element required.
2. **`--format lp`** explicitly given → LP mode. At least two `FILES` elements required (master + ≥1 subproblem).
3. **Auto-detect from `FILES[0]` extension**:
   - Extension `.json` → JSON mode
   - Extension `.lp` or `.cplex` → LP mode
   - Any other extension → error (user must specify `--format`)

---

## Positional Argument Semantics

### JSON mode (single file)

```
dwsolver problem.json [OPTIONS]
```

Backward-compatible with the pre-005 CLI. `FILES[0]` is the JSON problem file.
Any additional files in `FILES` are an error.

### LP mode (multiple files)

```
dwsolver master.lp sub1.lp [sub2.lp ...] [OPTIONS]
dwsolver master.cplex sub1.cplex [sub2.cplex ...] [OPTIONS]
dwsolver --format lp master.lp sub1.lp [OPTIONS]
```

- `FILES[0]` — master LP file (coupling constraints + global objective)
- `FILES[1:]` — subproblem LP files in order; position determines `block_id` (`block_0`, `block_1`, …)
- At least one subproblem file is required.

---

## Output

- Solution written to the designated output file (not stdout) as JSON (`Result` schema).
- Errors and diagnostics written to **stderr**.
- Normal progress/status messages: none (silent on success).

## Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Solver ran successfully (optimal, infeasible, unbounded, or iteration limit) |
| 1 | Tool failure: bad input file(s), I/O error, invalid `--format` value, wrong file count for format |

---

## Examples

```bash
# JSON mode (unchanged)
dwsolver problem.json
dwsolver problem.json --output result.json --workers 4

# LP mode — auto-detected
dwsolver master.lp sub1.lp sub2.lp
dwsolver master.cplex sub1.cplex --output solution.json

# LP mode — explicit format
dwsolver --format lp master.lp sub1.lp

# Override output location
dwsolver master.lp sub1.lp sub2.lp -o /tmp/out.solution.json
```

---

## Backward Compatibility

All existing `dwsolver PROBLEM_FILE` invocations (single `.json` file) continue
to work unchanged. The only visible change to existing users is the renamed
argument in `--help` output (`FILES...` instead of `PROBLEM_FILE`).
