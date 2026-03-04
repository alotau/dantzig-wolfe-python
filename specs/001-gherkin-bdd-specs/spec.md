# Feature Specification: BDD Specification via Gherkin Feature Files

**Feature Branch**: `001-gherkin-bdd-specs`  
**Created**: 2026-03-03  
**Status**: Draft  
**Input**: User description: "Use Gherkin for specifying the behavior of the software. Create an initial feature file for command line usage wherein a user calls the software from the command line with appropriately formatted input files and is given an output file with the solution or a message indicating why a solution is not provided. Create an additional feature file for library usage. Populate with some initial, simple scenarios."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CLI Solve a Valid Problem (Priority: P1)

A researcher or engineer has a linear program in block-angular form expressed as a
modern structured input file. They invoke the solver from the command line, passing
the input file, and receive a solution output file containing the optimal objective
value and variable assignments.

**Why this priority**: This is the foundational use case — the entire purpose of the
tool. Without a working CLI solve path, no other scenario has value.

**Independent Test**: Provide the bundled `simple_two_block.json` example problem;
verify the output file is produced and the objective value matches the known optimum.

**Acceptance Scenarios** (see also `features/cli_usage.feature`):

1. **Given** a valid block-angular LP input file, **When** the user runs `dwsolver solve <input_file>`, **Then** an output file is written containing the optimal objective value and the values of all decision variables.
2. **Given** a valid input file and an explicit `--output` path, **When** the user runs `dwsolver solve <input_file> --output <path>`, **Then** the solution is written to that path.
3. **Given** a valid input file, **When** the solve completes successfully, **Then** the exit code is 0.

---

### User Story 2 - CLI Graceful Reporting of Non-Solvable Problems (Priority: P2)

A user submits a problem that cannot be solved — because it is infeasible, unbounded,
or structurally malformed. Instead of crashing or silently producing wrong output,
the solver writes a structured output that clearly states why no solution was found.

**Why this priority**: Optimization problems often expose modeling errors through
infeasibility or unboundedness. Clear diagnostics are essential for users to
correct their models.

**Independent Test**: Provide a known-infeasible problem file; verify the output
contains a `status` of `"infeasible"` and a human-readable reason, and that no
solution values are reported.

**Acceptance Scenarios** (see also `features/cli_usage.feature`):

1. **Given** an infeasible LP input file, **When** the user runs `dwsolver solve <input_file>`, **Then** the output indicates status `"infeasible"` and includes a diagnostic message; no variable values are included.
2. **Given** an unbounded LP input file, **When** the user runs `dwsolver solve <input_file>`, **Then** the output indicates status `"unbounded"` and includes a diagnostic message.
3. **Given** a malformed or structurally invalid input file, **When** the user runs `dwsolver solve <input_file>`, **Then** a clear error message is written to stderr, the exit code is non-zero, and no output file is created.
4. **Given** an input file that does not exist, **When** the user runs `dwsolver solve <missing_file>`, **Then** an error message is written to stderr and the exit code is non-zero.

---

### User Story 3 - Library Solve a Problem Programmatically (Priority: P3)

A developer integrates the solver into their own application or workflow. They import
the `dwsolver` package, construct or load a problem, invoke the solver, and inspect
the result — all without using the command line.

**Why this priority**: The library interface unlocks embedded and automated use cases.
It depends on the same core solve machinery as the CLI (P1), so it comes after the
CLI path is established.

**Independent Test**: In a Python script (no CLI), import `dwsolver`, construct a
minimal two-block LP, call `solve()`, and assert the returned result object carries
the expected optimal objective value.

**Acceptance Scenarios** (see also `features/library_usage.feature`):

1. **Given** a `Problem` object with a valid block-angular structure, **When** `solver.solve(problem)` is called, **Then** the returned result has `status == "optimal"` and contains an objective value.
2. **Given** an optimal result, **When** the caller accesses `result.variable_values`, **Then** a mapping of variable names to their optimal values is returned.
3. **Given** a `Problem` object describing an infeasible LP, **When** `solver.solve(problem)` is called, **Then** the returned result has `status == "infeasible"` and no variable values are populated.

---

### User Story 4 - Library Error Handling (Priority: P4)

A developer passes an improperly constructed problem object to the solver. Rather
than raising an unhandled exception with an opaque traceback, the solver surfaces a
clear, documented exception type that the caller can catch and inspect.

**Why this priority**: Predictable error contracts are a quality-of-life requirement
for any library. Comes last because it refines, rather than extends, the library
interface.

**Independent Test**: Pass a `Problem` with a missing required field; assert that
the specific documented exception type is raised with an informative message.

**Acceptance Scenarios** (see also `features/library_usage.feature`):

1. **Given** a `Problem` object missing required structural fields, **When** `solver.solve(problem)` is called, **Then** a `DWSolverInputError` is raised with a message identifying the missing or invalid field.
2. **Given** a valid `Problem` object, **When** `solver.solve(problem)` is called multiple times, **Then** each call returns an independent result without state leaking between calls.

---

### Edge Cases

- What happens when an input file is syntactically valid JSON but semantically
  incorrect (e.g., constraint matrix dimensions do not match variable count)?
- How does the solver behave when a subblock yields no improving columns (degenerate
  pricing step)?
- What is reported when the solver hits a maximum-iteration limit before convergence?
- How are problems with a single block handled (degenerate decomposition)?
- What happens when the output file path is not writable (permissions error)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST accept a structured input file path as a required positional argument and an optional `--output` flag specifying the solution file path.
- **FR-002**: The CLI MUST write a structured solution file when a problem is solved optimally; the file MUST contain at minimum the objective value, solve status, and variable assignments.
- **FR-003**: The CLI MUST write a structured output file when a problem is determined infeasible or unbounded; the file MUST contain the status and a human-readable diagnostic message.
- **FR-004**: The CLI MUST exit with code 0 when the solver runs to completion for any valid solver outcome (`optimal`, `infeasible`, `unbounded`, `iteration_limit`). The CLI MUST exit non-zero only for tool-level failures (missing input file, parse/schema error, I/O error writing output). This allows calling scripts to distinguish "solver executed correctly" from "solver failed to run."
- **FR-005**: All error and diagnostic messages MUST be written to stderr; solution output MUST go to the designated output file, not stdout.
- **FR-006**: The library MUST expose a `Solver` class (or equivalent entry point) with a `solve(problem)` method that accepts a `Problem` object and returns a `Result` object.
- **FR-007**: The `Result` object MUST carry a `status` field with values from a defined set: `"optimal"`, `"infeasible"`, `"unbounded"`, `"iteration_limit"`. When status is `"infeasible"` or `"unbounded"`, `variable_values` MUST be empty and no objective value is reported. When status is `"iteration_limit"`, the best feasible solution found before the limit was reached MUST be returned: `variable_values` is populated and an objective value (for that incumbent) is present alongside a diagnostic message.
- **FR-011**: A `Result` with status `"iteration_limit"` MUST include a diagnostic message describing the limit reached (e.g., maximum iteration count) so the caller can decide whether to re-run with adjusted parameters.
- **FR-012**: Both the CLI and the library MUST accept a caller-specified maximum worker count that controls how many subproblem blocks are solved concurrently. The CLI MUST expose this as a `--workers` flag (default: number of available CPU cores). The library `Solver` MUST accept it as a constructor or per-call parameter. The solver MUST NOT hard-code a concurrency level.
- **FR-013**: Subproblem LPs MUST be solved using HiGHS (via the `highspy` Python package). HiGHS is the sole supported LP solver backend in this version. The solver core MUST NOT depend on GLPK, SciPy `linprog`, or any other LP library.
- **FR-014**: The solver MUST terminate when the relative optimality gap falls at or below a configurable tolerance. The default tolerance MUST be `1e-6`. The CLI MUST expose this as a `--tolerance` flag and the library `Solver` MUST accept it as a constructor or per-call `tolerance=` parameter. The tolerance value MUST be a named constant in the codebase, documented with its mathematical definition.
- **FR-008**: The library MUST raise a `DWSolverInputError` (or named equivalent) when the provided `Problem` object is structurally invalid; this exception type MUST be importable from the top-level package.
- **FR-009**: The library API MUST be stateless across calls — repeated calls to `solver.solve()` with different problems MUST produce independent results.
- **FR-010**: Input files consumed by the CLI MUST use a documented, modern structured format (JSON or TOML); the format schema MUST be specified and versioned.

### Key Entities

- **Problem**: A block-angular linear program. Contains a master constraint set and one or more subproblem blocks, each with its own constraint matrix, objective coefficients, and variable bounds.
- **Block**: One independent subproblem in the decomposition. Has its own variables, constraints, and objective. The master problem links blocks via linking constraints.
- **Result**: The outcome of a solve attempt. Carries solve status, objective value (when optimal), variable assignments (when optimal), iteration count, and any diagnostic messages.
- **Input File**: A structured document (JSON or TOML) describing a `Problem` in a versioned schema. Read by both the CLI and a `Problem.from_file()` loader in the library.

## Clarifications

### Session 2026-03-03

- Q: What is the exit code contract — should infeasible/unbounded outcomes exit 0 or non-zero? → A: Exit 0 for all valid solver outcomes (optimal, infeasible, unbounded, iteration_limit); non-zero only for tool-level failures (missing file, parse error, I/O error).
- Q: When the solver hits an iteration limit, should variable_values be populated in the Result? → A: Yes — return the best feasible solution found (variable_values populated, objective value present) with status "iteration_limit" and a diagnostic message.
- Q: What is the target subproblem block count that drives scale and parallelism design? → A: Number of parallel workers is a runtime input parameter supplied by the caller, not fixed at design time.
- Q: Which LP solver backend is used to solve subproblems? → A: HiGHS via `highspy` (MIT licensed, modern, fast). A pluggable backend interface is deferred as a future improvement.
- Q: What is the convergence termination criterion and is it configurable? → A: Default relative optimality gap of 1e-6; exposed as a `--tolerance` flag on the CLI and a `tolerance=` parameter in the library.

## Assumptions

- The initial set of scenarios covers the most common user-facing paths; edge cases
  (degenerate decomposition, iteration limits, numerical tolerance failures) will be
  added in subsequent refinement passes.
- Output file format defaults to JSON when `--output` is not specified; the default
  output path is derived from the input filename with a `.solution.json` suffix.
- The `Problem.from_file()` library helper mirrors the CLI's file-reading behavior
  so that CLI and library paths exercise the same parsing logic.
- "Modern format" means JSON as the primary format, with TOML as an optional
  alternative; the decision between them will be made during the planning phase.
- The LP solver backend is HiGHS (`highspy`). A pluggable backend interface — where
  the caller can inject any solver satisfying a defined protocol — is explicitly
  deferred as a future improvement and MUST NOT be over-engineered into this version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can run the solver against all canonical reference problems
  (derived from the original C solver's example suite) and receive correct optimal
  objective values for 100% of those problems.
- **SC-002**: Every infeasible or unbounded reference problem produces an output
  with the correct status classification and a non-empty diagnostic message.
- **SC-003**: A developer can import the library and solve a simple two-block LP
  in under 10 lines of Python with no CLI interaction.
- **SC-004**: All documented exception types are catchable without importing
  internal submodules — the public API surface is self-contained.
- **SC-005**: The Gherkin feature files serve as executable specifications: all
  scenarios defined in `features/cli_usage.feature` and `features/library_usage.feature`
  pass as automated tests as part of the CI gate.
- **SC-006**: The solver produces correct results regardless of the `--workers` /
  `workers` parameter value; results for a given problem MUST be identical whether
  run with 1 worker or N workers (deterministic correctness under any concurrency level).

