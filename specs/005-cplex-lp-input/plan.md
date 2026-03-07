# Implementation Plan: CPLEX LP Input Format Support

**Branch**: `005-cplex-lp-input` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-cplex-lp-input/spec.md`

## Summary

Add CPLEX LP as a first-class input format alongside the existing JSON format. A new
`lp_parser.py` module parses CPLEX LP text into intermediate Python dataclasses, which
are then assembled into the existing `Problem` model. The CLI gains a variadic positional
argument (master file + one or more subproblem files) and a `--format` flag for override.
Two new `Problem` class methods (`from_lp` and `from_lp_text`) are added to the public
library API. The four_sea reference problem is used as the primary regression fixture.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: click, pydantic>=2, highspy — all existing; no new runtime deps  
**Storage**: File I/O via `pathlib.Path`; `.lp` and `.cplex` files read as UTF-8 text  
**Testing**: pytest, pytest-bdd, mypy strict, ruff  
**Target Platform**: macOS / Linux (wherever Python 3.11 runs)  
**Project Type**: library + CLI  
**Performance Goals**: CPLEX LP parsing is one-time pre-solve I/O; no new performance targets  
**Constraints**: mypy strict must pass; ruff must pass; zero existing test regressions; no new mandatory runtime dependencies  
**Scale/Scope**: CPLEX LP subset used by alotau/dwsolver examples — up to ~200 constraints, ~500 variables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | ✅ PASS | `Problem.from_lp()` and `Problem.from_lp_text()` are public library API; no CLI dependency |
| II. CLI Interface | ✅ PASS | CLI extended with multi-file positional args and `--format` flag; backward-compatible with `.json` |
| III. Test-First | ✅ PASS | BDD feature file and unit tests for `lp_parser` written and confirmed failing before implementation |
| IV. Massively Parallel | ✅ PASS | LP parser is one-time pre-solve I/O; solver parallelism unchanged |
| V. Numerical Correctness | ✅ PASS | SC-001 mandates four_sea regression (objective=12.0); SC-002 mandates format-roundtrip agreement within 1e-6 |

**No violations → Complexity Tracking table not required.**

## Project Structure

### Documentation (this feature)

```text
specs/005-cplex-lp-input/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── lp_parser_api.md # LP parser module interface contract
│   └── cli_api.md       # Updated CLI contract (multi-file + --format)
├── features/
│   └── cplex_lp_usage.feature  # BDD feature file (pre-implementation)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/dwsolver/
├── __init__.py          # MODIFY: export from_lp, from_lp_text
├── cli.py               # MODIFY: FILES... nargs=-1, --format flag
├── lp_parser.py         # NEW: CPLEX LP parser + assembler
├── models.py            # MODIFY: Problem.from_lp(), Problem.from_lp_text()
├── solver.py            # UNCHANGED
├── subproblem.py        # UNCHANGED
└── py.typed             # UNCHANGED

tests/
├── unit/
│   └── test_lp_parser.py        # NEW: unit tests for lp_parser module
├── bdd/
│   └── steps/
│       └── test_cplex_lp_usage.py  # NEW: BDD step implementations
└── fixtures/
    ├── four_sea/                # NEW: CPLEX LP fixtures for four_sea
    │   ├── master.cplex
    │   ├── subprob_1.cplex
    │   ├── subprob_2.cplex
    │   ├── subprob_3.cplex
    │   └── subprob_4.cplex
    └── ... (existing unchanged)
```

**Structure Decision**: Single-project layout (Option 1). No new packages or top-level directories.
The LP parser lives in `src/dwsolver/lp_parser.py` to keep it alongside `models.py` and
accessible from both CLI and library paths.
