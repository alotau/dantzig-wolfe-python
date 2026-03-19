# Implementation Plan: Test Coverage Reporting & Live README Badges

**Branch**: `007-coverage-badge` | **Date**: 2026-03-18 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/007-coverage-badge/spec.md`

## Summary

Add end-to-end test quality visibility to the project: (1) `pytest-cov` integrated into the standard test run producing per-module line coverage with a 90% minimum threshold; (2) a live coverage badge in the README auto-updated by CI via `python-coverage-comment-action`; (3) a custom `scripts/bdd_report.py` script that counts Gherkin scenarios from feature files + JUnit XML and generates a shields.io endpoint JSON for a BDD completeness badge; (4) per-feature BDD traceability Markdown table uploaded as a CI artefact. All three badge signals are grouped in the README and update within 5 minutes of a `main` merge.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `pytest-cov` (new dev dep), `py-cov-action/python-coverage-comment-action@v3` (GitHub Action), `actions/upload-artifact@v4` (already available), `stdlib xml.etree.ElementTree` + `re` (for `bdd_report.py`)  
**Storage**: `python-coverage-comment-action-data` branch (badge JSON files); GitHub Actions artifacts (traceability Markdown)  
**Testing**: pytest 9+, pytest-bdd 8+, pytest-cov 7+ — existing suite (263 tests, 97% coverage)  
**Target Platform**: GitHub Actions (ubuntu-latest), developer workstation (macOS/Linux)  
**Project Type**: library/cli — this feature adds CI/tooling infrastructure only; no changes to `src/dwsolver/`  
**Performance Goals**: Full test suite with coverage completes in < 60 seconds locally (currently ~12 s without coverage)  
**Constraints**: No new third-party runtime deps; no external SaaS accounts required; `pytest --no-cov` must remain a valid opt-out  
**Scale/Scope**: Single repo, ~800 source statements, 40 Gherkin scenarios across 3 feature files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | ✅ Pass | No changes to `src/dwsolver/`; this feature is pure CI/tooling infrastructure |
| II. CLI Interface | ✅ Pass | Not applicable — `bdd_report.py` is a CI utility script, not a user-facing CLI command |
| III. Test-First (TDD) | ✅ Pass | `bdd_report.py` will be covered by unit tests written before implementation; pytest-cov config changes are verified by running the suite red→green |
| IV. Massively Parallel | ✅ Pass | Not applicable to this feature |
| V. Numerical Correctness | ✅ Pass | Not applicable to this feature |
| CI/CD Gates | ✅ Pass | Feature adds new CI steps; all existing gates (ruff, mypy, pytest) remain required |
| Branch Discipline | ✅ Pass | Work on `007-coverage-badge`; merge from `origin/main` before every push |

**No violations — no Complexity Tracking required.**

## Project Structure

### Documentation (this feature)

```text
specs/007-coverage-badge/
├── plan.md              ← this file
├── research.md          ← Phase 0: all unknowns resolved
├── data-model.md        ← Phase 1: entity definitions
├── quickstart.md        ← Phase 1: developer guide
├── contracts/
│   └── badges.md        ← Phase 1: badge JSON schemas
├── checklists/
│   └── requirements.md  ← quality gate
└── tasks.md             ← Phase 2 (created by /speckit.tasks, not this command)
```

### Source Code (repository root)

```text
pyproject.toml                    ← add pytest-cov dep + [tool.coverage.*] sections + addopts

scripts/
└── bdd_report.py                 ← NEW: generates bdd-badge.json + bdd-traceability.md

tests/
└── unit/
    └── test_bdd_report.py        ← NEW: unit tests for bdd_report.py

.github/workflows/
└── ci.yml                        ← updated: add coverage upload step + BDD report step

README.md                         ← updated: add coverage + BDD scenario badges
```

**No changes to `src/dwsolver/`**.

## Complexity Tracking

No constitutional violations. No complexity tracking required.
