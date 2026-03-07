# Feature Specification: CPLEX LP Input Format Support

**Feature Branch**: `005-cplex-lp-input`  
**Created**: 2026-03-06  
**Status**: Approved  
**Input**: User description: "Add support for CPLEX LP format as an alternative input format alongside the existing JSON format. Users provide a master .lp file and one or more subproblem .lp files via CLI arguments or library API to solve Dantzig-Wolfe decomposition problems."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — CLI Solve Using CPLEX LP Files (Priority: P1)

A researcher or engineer has a Dantzig-Wolfe decomposed LP expressed as a set of
CPLEX LP files — one master file defining the coupling constraints and one file
per block defining local constraints, local objective, and variable bounds. They
invoke the solver from the command line, providing the master file first followed
by the subproblem files, and receive the same solution output file they would get
from the JSON workflow.

**Why this priority**: This is the new capability the feature delivers. Without a
working CLI path for CPLEX LP input, the feature has no value.

**Independent Test**: Provide the four_sea CPLEX LP files from `alotau/dwsolver`
(`master.cplex`, `subprob_1.cplex` – `subprob_4.cplex`) to the CLI; verify the
solution output file is produced and the objective value matches the known optimum
of 12.0 (the same value the JSON fixture produces).

**Acceptance Scenarios**:

1. **Given** a master `.lp` file and one or more subproblem `.lp` files, **When**
   the user runs `dwsolver master.lp sub1.lp sub2.lp`, **Then** a solution output
   file is written containing the optimal objective value and variable assignments.
2. **Given** valid CPLEX LP input files, **When** the solver completes successfully,
   **Then** the exit code is 0.
3. **Given** a single `.json` file, **When** the user runs `dwsolver problem.json`,
   **Then** the existing JSON workflow proceeds unchanged (backward compatibility).
4. **Given** CPLEX LP files with `.cplex` extension, **When** the user runs
   `dwsolver master.cplex sub1.cplex sub2.cplex`, **Then** the files are recognised
   as CPLEX LP format and solved correctly.
5. **Given** CPLEX LP files and the explicit `--format lp` flag, **When** the user
   runs `dwsolver --format lp master.lp sub1.lp`, **Then** format auto-detection is
   overridden and CPLEX LP parsing is used regardless of extension.
6. **Given** an explicit `--output` path, **When** the user supplies CPLEX LP files,
   **Then** the solution is written to that path (same behaviour as JSON mode).

---

### User Story 2 — Library API for CPLEX LP Problems (Priority: P2)

A developer integrates the solver into their application or analysis pipeline. They
have CPLEX LP files on disk describing a block-angular LP. They want to load the
problem programmatically, solve it, and inspect the result without using the CLI.

**Why this priority**: The project constitution requires every CLI capability to
also be available as a library call. The library API makes it possible for other
tools to consume CPLEX LP problems without shelling out to the CLI.

**Independent Test**: In a Python script with no CLI, call
`Problem.from_lp("master.lp", ["sub1.lp", "sub2.lp"])` on the four_sea files;
pass the result to `solve()`; assert `result.objective == 12.0`.

**Acceptance Scenarios**:

1. **Given** paths to a master file and one or more subproblem files, **When** a
   developer calls `Problem.from_lp(master_path, subproblem_paths)`, **Then** a
   fully validated `Problem` object is returned.
2. **Given** the returned `Problem` object, **When** `solve(problem)` is called,
   **Then** the returned `Result` has the same fields, types, and non-zero
   `objective` as a `Result` produced by solving the same problem loaded via
   `Problem.from_file()` with an equivalent JSON fixture.
3. **Given** CPLEX LP content already in memory as strings, **When** a developer
   calls `Problem.from_lp_text(master_text, [sub1_text, sub2_text])`, **Then** a
   validated `Problem` is returned without any file I/O.
4. **Given** a JSON-loaded and CPLEX-LP-loaded encoding of the same problem, **When**
   both are solved, **Then** their objective values agree within solver tolerance.

---

### User Story 3 — Clear Diagnostics for Invalid CPLEX LP Input (Priority: P3)

A user attempts to solve CPLEX LP files that are missing, malformed, or structurally
inconsistent (e.g., a subproblem file declares no variables, or the master references
no coupling constraints). They receive a clear, actionable error message rather than
an opaque crash.

**Why this priority**: Good error handling is essential usability; without it, users
cannot debug their CPLEX LP files.

**Independent Test**: Invoke the CLI with a `.lp` file whose `Subject To` section
is empty (zero coupling constraints); verify a descriptive error message on stderr,
a non-zero exit code, and no output file created.

**Acceptance Scenarios**:

1. **Given** CPLEX LP files with one or more files missing, **When** the user invokes
   the CLI, **Then** an error message naming the missing file(s) is written to stderr
   and the exit code is non-zero.
2. **Given** a master file whose `Subject To` section is empty or absent, **When**
   the CLI is invoked, **Then** an error message states that no coupling constraints
   were found.
3. **Given** a subproblem file with no variable declarations, **When** loaded via the
   library, **Then** a `DWSolverInputError` is raised with a message identifying
   which subproblem has no variables.
4. **Given** CPLEX LP files where a variable appears in more than one subproblem's
   declaration section, **When** the problem is loaded, **Then** an error message
   identifies the conflicting variable name and the files involved.
5. **Given** a `.lp` file provided as the only positional argument (no subproblem
   files), **When** the CLI is invoked with no `--format json` override, **Then** a
   clear error message explains that CPLEX LP format requires both a master file and
   at least one subproblem file.
6. **Given** the `--format` flag is set to an unrecognised value, **When** the CLI
   is invoked, **Then** an error message lists the accepted format values.

---

### Edge Cases

- **Objective location**: A subproblem file with a non-empty `Minimize`/`Maximize`
  section uses that as the block objective. If empty or absent, the objective
  coefficients for that block's variables are taken from the master file's objective
  section. If neither contains coefficients for a variable, its objective coefficient
  is zero.
- **`Generals`/`Binary` sections**: Silently ignored; the solver operates on the LP
  relaxation (integer constraints are not supported). (See also FR-009.)
- **Maximisation direction**: A `Maximize` section in either master or subproblem is
  honoured by negating the objective (consistent with the solver's minimisation
  convention).
- **Variable in no subproblem**: A variable referenced in the master's coupling
  constraints that does not appear in any subproblem's `Bounds` section raises
  `DWSolverInputError` identifying the offending variable name(s). Silent partial
  zeroing of coupling constraints would alter the LP without notice, violating
  SC-005 (no silent wrong answers).
- **Comments and blank lines**: Lines beginning with `\` and blank lines are ignored
  in all sections.
- **Coefficient-free terms**: A term with no explicit coefficient (e.g., `+ x1`)
  defaults to `+1.0`; a lone `-` before a variable defaults to `-1.0`.
- **Unknown file extension with multiple files**: If the primary file's extension is
  not `.json`, `.lp`, or `.cplex`, and no `--format` flag is provided, an error
  prompts the user to specify `--format`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST accept a master LP file as the first positional argument and
  one or more subproblem LP files as additional positional arguments:
  `dwsolver master.lp sub1.lp [sub2.lp ...]`.
- **FR-002**: The CLI MUST auto-detect input format from file extension: `.json`
  triggers JSON mode; `.lp` or `.cplex` on the primary file triggers CPLEX LP mode.
- **FR-003**: The CLI MUST accept a `--format` flag (`json` or `lp`) to override
  auto-detection.
- **FR-004**: The library MUST expose `Problem.from_lp(master_path, subproblem_paths)`
  as a public class method that returns a validated `Problem` instance.
- **FR-005**: The library MUST expose `Problem.from_lp_text(master_text, subproblem_texts)`
  for loading from in-memory strings.
- **FR-006**: The parser MUST extract block objectives from each subproblem's
  `Minimize`/`Maximize` section; for any subproblem with an absent or zero objective,
  coefficients are populated from the master file's objective section by matching
  variable names.
- **FR-007**: The parser MUST infer each block's linking columns by matching variable
  names declared in the subproblem's `Bounds` section against the master's
  `Subject To` constraint expressions.
- **FR-008**: The parser MUST support CPLEX LP sense operators `<=`, `>=`, and `=` in
  both `Subject To` and `Bounds` sections.
- **FR-009**: The parser MUST silently ignore `Generals`, `General`, `Gen`, `Binary`,
  and `Bin` sections (LP relaxation). (See also `Generals`/`Binary` sections edge
  case.)
- **FR-010**: The parser MUST support backslash-prefixed comment lines and multi-line
  expressions (continuation lines with leading whitespace).
- **FR-011**: Existing `dwsolver problem.json` invocations MUST continue to work
  unchanged; this feature MUST be backward-compatible.
- **FR-012**: All CPLEX LP loading errors MUST be reported as `DWSolverInputError`
  from the library, and as messages on stderr with a non-zero exit code from the CLI.
- **FR-013**: `Problem.from_lp` and `Problem.from_lp_text` MUST be exported through
  the `dwsolver` package's public `__init__.py` API.

### Key Entities

- **MasterLP**: The parsed representation of the master CPLEX LP file — coupling
  constraint names, senses, RHS values, and an optional objective section used as a
  fallback for block objectives.
- **SubproblemLP**: The parsed representation of one subproblem CPLEX LP file —
  variable names and bounds, local constraint matrix and RHS, and the subproblem's
  own objective coefficients.
- **LinkingSpec**: The derived mapping between each subproblem's variable positions
  and the master's coupling constraint row indices, expressed as the sparse COO
  `(rows, cols, values)` triples already used in the JSON schema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The four_sea CPLEX LP example files from `alotau/dwsolver` can be
  solved directly by the CLI and produce objective value 12.0, matching the
  reference fixture `ref_four_sea.expected.json`.
- **SC-002**: Solving the same block-angular LP expressed first as JSON and then as
  CPLEX LP files produces objective values that agree within `1e-6`.
- **SC-003**: All existing test suite tests continue to pass; zero regressions
  introduced by this feature.
- **SC-004**: A user can go from having CPLEX LP files to a solved result without
  any intermediate conversion step or JSON authoring.
- **SC-005**: Invalid or missing CPLEX LP input never produces a silent wrong
  answer — every error path raises `DWSolverInputError` with a message that
  identifies the affected file.

## Assumptions

- The CPLEX LP format variant supported is the subset used by `alotau/dwsolver`
  reference examples: `Minimize`/`Maximize`, `Subject To`, `Bounds`,
  `Generals`/`Binary`, `End` sections, with backslash comments and multi-line
  expressions. Full CPLEX LP spec features (e.g., SOS constraints, piecewise
  linear objectives) are out of scope.
- Subproblem ordering on the command line determines `block_id` assignment
  (`block_0`, `block_1`, …). No identifier is inferred from file names.
- Variable names follow the CPLEX LP convention: start with a letter or `_`, may
  contain letters, digits, `_`, `.`, `(`, `)`, and `,` (as required by the four_sea
  variable naming scheme `w(AC1_0,SEA,199)`).
- The master file never declares variables in its `Bounds` section that should be
  treated as block variables; all decision variables belong to subproblems.
