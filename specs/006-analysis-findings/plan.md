# Implementation Plan: Analysis Findings Polish

**Source**: `ANALYSIS.md` cross-project analysis (2026-03-18)

## Overview

Address the two confirmed gaps found in ANALYSIS.md:

1. **matplotlib optional dependency** — the `--save-chart` benchmark feature
   works at runtime (graceful no-op if absent) but `matplotlib` is undiscoverable
   via standard `pip install` extras syntax.

2. **`--verbose` CLI flag** — no mechanism exists for operators or researchers to
   observe per-iteration solver diagnostics without modifying source code.

A minor documentation clarification for BDD feature file terminology is also
included.

## Tech Stack

- **Language**: Python 3.11
- **CLI**: Click (already in use in `src/dwsolver/cli.py`)
- **Testing**: pytest, pytest-bdd (already in use)
- **Package metadata**: `pyproject.toml` (PEP 517/518 hatch build)

## File Targets

| Task | File(s) |
|---|---|
| matplotlib optional dep | `pyproject.toml`, `README.md` |
| `--verbose` flag | `src/dwsolver/__init__.py`, `src/dwsolver/solver.py`, `src/dwsolver/cli.py` |
| `--verbose` tests | `tests/bdd/steps/test_cli_usage.py`, `tests/unit/test_solver.py` |
| BDD feature file docs | `specs/001-gherkin-bdd-specs/features/cli_usage.feature`, `library_usage.feature`, `cplex_lp_usage.feature` |

## Architecture Notes

### matplotlib Extras

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
charts = ["matplotlib>=3.7"]
```

No code changes required — `benchmarks/table.py` already gracefully handles the
absent import.

### `--verbose` Propagation Path

```
cli.py  --verbose flag
  └─ solve(problem, verbose_stream=...)
       └─ solver.py  _solve_inner() column-generation loop
            └─ emits lines: "iter N | phase P | cols C | gap G"
```

The `verbose_stream` parameter makes the stream injectable for unit testing
(avoids sys.stderr capture complexity).

## Execution Order

1. matplotlib dep (smallest, zero-risk, ship independently)
2. `--verbose` TDD cycle (test → fail → implement → pass)
3. Feature file doc comments (cosmetic, any time)
