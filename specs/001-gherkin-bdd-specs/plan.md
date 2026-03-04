# Implementation Plan: BDD Specification via Gherkin Feature Files

**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/001-gherkin-bdd-specs/spec.md`

## Summary

Implement a Python Dantzig-Wolfe decomposition solver delivered as both an
importable library (`dwsolver` package) and a `dwsolver` CLI command. The solver
accepts block-angular linear programs in a modern JSON input format, solves them
using massively parallel subproblem dispatch (via `concurrent.futures`), and
returns structured results indicating the solve status, optimal objective value,
and variable assignments. Subproblems are solved using HiGHS (`highspy`). The CLI
and library share the same solve core. All behavior is specified via executable
Gherkin feature files that run as part of the CI gate.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `highspy` (HiGHS LP solver), `concurrent.futures` (stdlib), `click` (CLI), `pytest` + BDD runner (testing), `ruff` (lint/format), `mypy` (type checking)  
**Storage**: N/A — input/output via files; no persistent storage  
**Testing**: `pytest` + Gherkin BDD runner (behave or pytest-bdd — resolved in Phase 0 research); reference problems from original C solver example suite as regression fixtures  
**Target Platform**: Linux (CI/GitHub Actions), macOS (primary dev); pure Python — no platform-specific code  
**Project Type**: library + CLI (single-package, dual-entry-point)  
**Performance Goals**: Correct results at any worker count; subproblem dispatch scales linearly with worker count; convergence at relative gap ≤ 1e-6 (default)  
**Constraints**: Thread-safe shared state (master problem, column pool, convergence criteria); all tolerance values are named constants; stateless Solver API across calls  
**Scale/Scope**: Single Python package; worker count is a runtime parameter (no fixed cap); problem size bounded only by available memory and HiGHS LP capacity

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Gate | Status |
|---|-----------|------|--------|
| I | Library-First | Does the design expose all solver capabilities via an importable `dwsolver` package with no CLI dependency? | ✅ PASS — library is the core; CLI wraps it |
| I | Library-First | Does every module have a clear algorithmic or structural responsibility? | ✅ PASS — module boundaries defined in Project Structure |
| II | CLI Interface | Does the CLI expose every library capability, including `--workers` and `--tolerance`? | ✅ PASS — FR-001, FR-012, FR-014 + Gherkin scenarios |
| II | CLI Interface | Does the protocol route solution output to file, errors to stderr? | ✅ PASS — FR-005, Gherkin scenario "Error message goes to stderr" |
| III | Test-First | Are Gherkin feature files written before implementation begins? | ✅ PASS — feature files are the primary deliverable of this spec |
| III | Test-First | Will CI block merge to `main` without all tests passing? | ✅ PASS — addressed in CI/CD section of plan |
| IV | Massively Parallel | Is `concurrent.futures.ThreadPoolExecutor` used for subproblem dispatch? | ✅ PASS — Technical Context + research task |
| IV | Massively Parallel | Is sequential subproblem looping in the hot path prohibited? | ✅ PASS — FR-012 requires caller-controlled concurrency; architecture must not serialize |
| IV | Massively Parallel | Is thread safety of shared state explicitly designed, documented, tested? | ✅ PASS — addressed in data-model.md (Phase 1) and research (Phase 0) |
| V | Numerical Correctness | Is the convergence tolerance a named constant? | ✅ PASS — FR-014 explicitly requires this |
| V | Numerical Correctness | Are reference solutions from original C solver used as regression fixtures? | ✅ PASS — SC-001/SC-002, constitution Development Workflow reference |
| V | Numerical Correctness | Are infeasible/unbounded/degenerate cases handled explicitly, not silently? | ✅ PASS — FR-003, FR-007, FR-011 + Gherkin scenarios |

**No violations. Gate passed. Phase 0 research may proceed.**

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design artifacts (data-model.md, contracts/, quickstart.md).*

| # | Principle | Design Decision Reviewed | Status |
|---|-----------|--------------------------|--------|
| I | Library-First | `solve()` / `Problem` / `Result` / `DWSolverInputError` form the complete library surface; CLI is a thin `click` wrapper with no logic | ✅ PASS |
| II | CLI Interface | `library_api.md` and `cli_api.md` confirm all capabilities (`--workers`, `--tolerance`, `--output`) are CLI-accessible | ✅ PASS |
| III | Test-First | All contracts written before implementation; data-model defines validation rules that BDD steps will assert against | ✅ PASS |
| IV | Massively Parallel | `dispatch_subproblems()` in `subproblem.py` uses futures-collect pattern; pool size is `min(workers or cpu_count()*2, len(blocks))`; no sequential hot path in any contract | ✅ PASS |
| V | Numerical Correctness | `DEFAULT_TOLERANCE: float = 1e-6` declared in `models.py`; `json_schema.md` and `data-model.md` explicitly reference it; `Result.tolerance` echoes the value used | ✅ PASS |

**Post-design review: No new violations. All gates hold.**

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
dwsolver-vibes/
├── pyproject.toml               # hatchling build; [project.scripts] dwsolver = "dwsolver.cli:main"
├── README.md
├── src/
│   └── dwsolver/
│       ├── __init__.py          # public API: solve(), Problem, Result, DWSolverInputError
│       ├── py.typed             # PEP 561 marker; enables mypy for downstream consumers
│       ├── models.py            # Pydantic v2 input/output models (Problem, Block, Master, Result)
│       ├── solver.py            # DW iteration loop; Restricted Master Problem management
│       ├── subproblem.py        # per-block HiGHS solve; pricing; column preparation
│       └── cli.py               # click CLI entry point
├── tests/
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_subproblem.py
│   │   └── test_solver.py
│   └── bdd/
│       ├── conftest.py          # bdd_features_base_dir; shared fixtures
│       └── steps/
│           ├── test_cli_usage.py        # BDD steps for cli_usage.feature
│           └── test_library_usage.py   # BDD steps for library_usage.feature
├── specs/
│   └── 001-gherkin-bdd-specs/
│       ├── features/
│       │   ├── cli_usage.feature
│       │   └── library_usage.feature
│       ├── spec.md
│       ├── plan.md              # this file
│       ├── research.md
│       ├── data-model.md
│       ├── quickstart.md
│       ├── contracts/
│       │   ├── library_api.md
│       │   ├── cli_api.md
│       │   └── json_schema.md
│       └── checklists/
│           └── requirements.md
└── .github/
    └── workflows/
        └── ci.yml               # ruff → mypy → pytest unit → pytest BDD
```

**Structure Decision**: Single `src/`-layout Python package. Library is the core (`solver.py` + `subproblem.py` + `models.py`); CLI wraps it (`cli.py`). BDD feature files live under `specs/` (already written); step files live under `tests/bdd/steps/` and reference features via `bdd_features_base_dir` in `pyproject.toml`. No frontend, no monorepo.

## Complexity Tracking

*No Constitution Check violations. No entries required.*
