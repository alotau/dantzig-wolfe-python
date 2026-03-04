<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 2.0.0 (MAJOR: mandatory input-format compatibility constraint removed from Principle II)
Modified principles:
  - II. CLI Interface — removed requirement to support original C solver input formats;
    original test files/expected outputs are now a guide, not a format mandate.
Added sections: N/A
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md  ✅ aligned (no changes required)
  - .specify/templates/spec-template.md  ✅ aligned (no changes required)
  - .specify/templates/tasks-template.md ✅ aligned (no changes required)
Follow-up TODOs: none — all placeholders resolved.
-->

# DWSolver Constitution

## Core Principles

### I. Library-First

The solver core MUST be implemented as a self-contained, independently importable
Python package (`dwsolver`). Every algorithmic capability — problem parsing, master
problem management, subproblem dispatch, and result extraction — MUST be accessible
programmatically via the library API with no dependency on the CLI layer.

Libraries MUST be independently testable and documented with clear public interfaces.
No module exists solely for organizational purposes; every module MUST have a clear
algorithmic or structural responsibility.

### II. CLI Interface

Every capability exposed by the library MUST also be reachable via a standalone
command-line interface (`dwsolver` entry point). The CLI is a first-class artifact,
not an afterthought.

Protocol: problem files and options via arguments/stdin → solution output to stdout
→ errors and diagnostics to stderr. Input formats are NOT required to be
compatible with the original C solver. Modern, well-structured formats (e.g., JSON,
TOML, or a purpose-designed schema) are preferred where they better serve usability
and tooling. The original C solver's example input files and expected outputs MUST
be used as a guide for problem coverage and reference solutions, but format
conversion or compatibility shims are not required.

### III. Test-First (NON-NEGOTIABLE)

TDD is mandatory. The Red-Green-Refactor cycle MUST be strictly enforced:

- Tests are written and reviewed before implementation begins.
- Tests MUST be confirmed to fail before implementation.
- Implementation proceeds only to make failing tests pass.

Automated tests run on every push to the remote repository via CI. Merging to
`main` is **blocked** unless all tests are passing. This is enforced by branch
protection rules — no exceptions. Reference problems from the original C solver
example suite MUST be used as regression baselines to validate numerical fidelity.

### IV. Massively Parallel by Design

Dantzig-Wolfe decomposition is inherently parallel at the subproblem level.
The architecture MUST exploit this: subproblem solving MUST be dispatched
concurrently, targeting thousands of simultaneous workers using Python's
`concurrent.futures` (with `ThreadPoolExecutor` as the default executor).

No sequential subproblem loops are permitted in the hot path. Thread safety of
shared data structures (master problem state, column pool, convergence criteria)
MUST be explicitly designed, documented, and tested. Parallelism strategy changes
MUST be treated as architectural decisions requiring constitutional review.

### V. Numerical Correctness

This is a mathematical optimization program. Correctness of results is
non-negotiable and supersedes performance considerations.

- All floating-point tolerances (primal feasibility, dual feasibility, optimality
  gap) MUST be named constants, documented with their mathematical justification,
  and consistent across the codebase.
- Every solver result MUST be verifiable against a known reference solution. New
  problem types MUST include a reference optimum in their test fixtures.
- Numerical instability, degenerate cases, and infeasible/unbounded subproblems
  MUST be handled explicitly — silent wrong answers are a critical defect.

## CI/CD & Quality Gates

All code pushed to the remote repository triggers the full automated test suite
via GitHub Actions. The following gates MUST pass before any merge to `main`:

1. **Unit tests** — all unit tests pass.
2. **Integration tests** — all integration tests pass, including execution of the
   canonical example problems from the original C solver suite.
3. **Linting / formatting** — code MUST conform to the project's style rules
   (e.g., `ruff` for linting and format checking).
4. **Type checking** — static type checking MUST pass (e.g., `mypy` or `pyright`
   in strict mode).

Branch protection on `main` enforces these gates. Direct pushes to `main` are
forbidden. All changes arrive via pull requests.

## Development Workflow

1. **Spec first** — new capabilities begin with a feature spec (`/speckit.spec`)
   before any code is written.
2. **Plan before build** — an implementation plan (`/speckit.plan`) is produced
   and reviewed before tasks are created.
3. **Tasks drive execution** — a task list (`/speckit.tasks`) breaks the plan into
   independently implementable, testable slices.
4. **Tests before implementation** — per Principle III, tests are written, reviewed,
   and confirmed failing before implementation begins.
5. **PR review** — all PRs MUST verify compliance with this constitution before
   merge. The reviewer is responsible for raising constitutional violations.

Reference material: the original C implementation at
`https://github.com/alotau/dwsolver` serves as the algorithmic reference. When
behavior is ambiguous, the C solver's documented behavior is the ground truth
until explicitly superseded by a constitutional amendment.

## Governance

This constitution supersedes all other development practices and guidelines.
When a conflict exists between this document and any other guideline, this
document prevails.

**Amendment procedure**:
1. Proposed amendments are documented in a PR with a clear rationale.
2. The amendment MUST specify the version bump type (MAJOR / MINOR / PATCH) and
   justify the classification.
3. Any amendment that removes or redefines a principle is a MAJOR bump and
   requires explicit acknowledgment of the migration impact on existing code and
   tests.
4. `LAST_AMENDED_DATE` MUST be updated to the date the amended constitution is
   merged to `main`.

**Versioning policy** (semantic):
- **MAJOR**: Backward-incompatible governance changes — principle removal,
  redefinition, or mandatory-constraint removal.
- **MINOR**: New principle or section added; materially expanded guidance.
- **PATCH**: Clarifications, wording improvements, typo fixes.

**Compliance review**: Every PR reviewer MUST check compliance with this
constitution. Non-compliance blocks merge, same as a failing test.

**Version**: 2.0.0 | **Ratified**: 2026-03-03 | **Last Amended**: 2026-03-03
