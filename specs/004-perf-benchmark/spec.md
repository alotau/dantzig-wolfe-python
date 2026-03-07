# Feature Specification: Performance Benchmark — Workers vs. Subproblems

**Feature Branch**: `004-perf-benchmark`
**Created**: 2026-03-06
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Run the benchmark and read the results (Priority: P1)

A researcher or engineer wants to understand how the solver scales: does adding
more workers reduce wall-clock time, and does that effect grow or shrink as the
number of subproblems increases? They run a single benchmark command and receive
a formatted table that shows solve time for each combination of subproblem count
and worker count, allowing them to choose an appropriate configuration for their
production workload.

**Why this priority**: The entire feature is this story. Without a readable
result the benchmark has no value.

**Independent Test**: Can be fully tested by running the benchmark entry point
and verifying that a result table is printed showing runtime values for every
(subproblems, workers) cell, with all cells showing status "optimal".

**Acceptance Scenarios**:

1. **Given** the benchmark tool is available, **When** I run it with default
   settings, **Then** I see a table with rows for subproblem counts 1-20 and
   columns for worker counts 4, 8, 12, 16, 20, with each cell showing a
   measured wall-clock time in seconds.
2. **Given** the benchmark tool is available, **When** I run it, **Then** all
   solve results in the table show status "optimal", confirming the scalable
   problem is well-formed at every decomposition size.
3. **Given** a complete result table, **When** I inspect it, **Then** I can
   identify the (subproblems, workers) combination with the shortest runtime
   without any post-processing.

---

### User Story 2 — Reproduce results deterministically (Priority: P2)

A researcher re-runs the benchmark on the same machine and expects to obtain
comparable timing figures, so they can compare before and after a code change.

**Why this priority**: Reproducibility is required for the results to be
scientifically useful. A benchmark that produces wildly unstable times cannot
be used to evaluate solver improvements.

**Independent Test**: Run the benchmark twice in succession on an idle machine
and verify that corresponding cells agree within a reasonable tolerance.

**Acceptance Scenarios**:

1. **Given** the benchmark is run twice consecutively on the same hardware,
   **When** timing results are compared cell-by-cell, **Then** no cell differs
   by more than 50% between runs (a generous bound that rules out order-of-
   magnitude instability while accepting normal OS scheduling noise).

---

### Edge Cases

- What happens when `workers` exceeds the number of subproblems? The solver
  must still return an optimal result; extra workers are unused.
- What happens when `subproblems = 1`? The problem degenerates to a single
  block; the benchmark must still complete and record a valid runtime.
- What if a specific (subproblems, workers) combination fails or times out?
  The table must mark that cell clearly (e.g., "ERR" or "TIMEOUT") rather
  than crashing entirely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a scalable block-angular LP problem
  generator that produces a valid, feasible, bounded LP decomposable into any
  integer number of subproblems from 1 to 20 inclusive.
- **FR-002**: The generated problem at every subproblem count MUST be solvable
  to optimality, producing a consistent objective value (within numerical
  tolerance) regardless of how many blocks it is split into.
- **FR-003**: The benchmark MUST measure and record the wall-clock solve time
  for every combination of subproblem count in {1, 2, ..., 20} and worker
  count in {4, 8, 12, 16, 20} — 100 cells in total.
- **FR-004**: The benchmark MUST present results as a 2-D table: subproblem
  count on the row axis, worker count on the column axis, and measured time in
  seconds (at least two decimal places) in each cell.
- **FR-005**: The benchmark MUST indicate, for each cell, whether the solve
  reached optimality or encountered an error.
- **FR-006**: The benchmark MUST be runnable as a single command or script
  invocation with no required arguments beyond the entry point itself.
- **FR-007**: The benchmark SHOULD support an optional flag to also produce a
  heatmap or line-chart visualisation saved to a file.
- **FR-008**: Each (subproblems, workers) combination MUST be timed at least
  once; the benchmark MAY support a configurable repeat count so that the
  reported time is an average over multiple runs.

### Key Entities

- **Scalable benchmark problem**: A parameterisable block-angular LP where the
  number of blocks is the sole structural input. All blocks are identical in
  size and coefficients so that timing differences arise only from parallelism,
  not from varying problem difficulty.
- **Benchmark result**: A 20x5 matrix of (wall-clock solve time in seconds,
  solve status) indexed by (subproblem count in 1-20, worker count in
  {4, 8, 12, 16, 20}).
- **Result table**: A human-readable formatted table printed to stdout, with
  worker counts as column headers and subproblem counts as row labels.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete benchmark run (20 subproblem sizes x 5 worker counts =
  100 cells) completes without crashing and produces a fully populated result
  table with no empty cells.
- **SC-002**: Every cell in the result table shows status "optimal", confirming
  the scalable problem is correctly specified at all decomposition sizes.
- **SC-003**: The result table is readable at a glance — column headers identify
  worker counts and row labels identify subproblem counts — without requiring
  any external tool to interpret.
- **SC-004**: On a developer laptop, the full 100-cell benchmark completes in
  under 10 minutes.
- **SC-005**: Results from two consecutive runs on the same machine agree within
  50% per cell, demonstrating acceptable reproducibility.

## Assumptions

- The scalable benchmark problem is generated programmatically (not loaded from
  a static file) so that block count can be varied at runtime.
- "Wall-clock time" is measured as elapsed time from when the solve call is
  initiated to when it returns; problem generation time is excluded.
- Worker counts {4, 8, 12, 16, 20} are fixed by the requirement; no
  interpolation between these values is needed.
- The benchmark targets the library API, not the CLI, to avoid process-launch
  overhead contaminating timing results.
- Subproblem count 1 is valid and serves as a serial-execution baseline.
- The feature does not require statistical significance testing; a single timed
  run per cell (with optional repeats for averaging) is sufficient.
