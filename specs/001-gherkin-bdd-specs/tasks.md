# Tasks: dwsolver — Dantzig-Wolfe Decomposition Solver

**Input**: Design documents from `/specs/001-gherkin-bdd-specs/`  
**Branch**: `001-gherkin-bdd-specs`  
**Generated**: 2026-03-03

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label: US1–US4
- All paths relative to repository root

---

## Phase 1: Setup

**Purpose**: Project scaffolding, toolchain, CI skeleton, and example fixtures used
by all subsequent phases.

- [ ] T001 Create `pyproject.toml` with hatchling build, `[project.scripts] dwsolver = "dwsolver.cli:main"`, and `[project.optional-dependencies] dev = [pytest, pytest-bdd, ruff, mypy, highspy]` in repo root
- [ ] T002 Create `src/dwsolver/__init__.py` with empty public API stubs (exports `solve`, `Problem`, `Result`, `SolveStatus`, `DWSolverInputError`)
- [ ] T003 [P] Create `src/dwsolver/py.typed` (empty PEP 561 marker file)
- [ ] T004 [P] Configure `ruff` in `pyproject.toml` — lint + format, target Python 3.11
- [ ] T005 [P] Configure `mypy` strict mode in `pyproject.toml`
- [ ] T006 [P] Configure `pytest` and `pytest-bdd` in `pyproject.toml` — set `bdd_features_base_dir = "specs/001-gherkin-bdd-specs/features"`
- [ ] T007 Create `.github/workflows/ci.yml` — steps: `pip install -e ".[dev]"` → `ruff check` → `ruff format --check` → `mypy src/` → `pytest tests/unit/` → `pytest tests/bdd/`
- [ ] T008 [P] Create `tests/unit/__init__.py`, `tests/bdd/__init__.py`, `tests/bdd/steps/__init__.py` (empty init files for test discovery)
- [ ] T009 [P] Create `tests/fixtures/simple_two_block.json` — minimal 2-block, 1-linking-constraint LP with known optimal value (used by SC-001 and all BDD CLI scenarios)
- [ ] T010 [P] Create `tests/fixtures/infeasible.json` — infeasible block-angular LP (empty feasible region)
- [ ] T011 [P] Create `tests/fixtures/unbounded.json` — unbounded block-angular LP (no upper bound on objective)

**Checkpoint**: `pip install -e ".[dev]"` succeeds; `ruff check` and `mypy` pass on stubs; CI workflow is parseable.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and constants that every user story depends on. Must
be complete and passing mypy/ruff before any story implementation begins.

- [ ] T012 Implement `src/dwsolver/models.py` — all Pydantic v2 models: `SolveStatus`, `Bounds`, `BlockConstraints`, `LinkingColumns`, `Block`, `Master`, `Problem` (with `from_file()` stub), `Result`, `DWSolverInputError`, and constants `DEFAULT_TOLERANCE = 1e-6`, `DEFAULT_WORKERS = None`, `MAX_ITERATIONS = 1000`
- [ ] T013 Add cross-field Pydantic validators to `src/dwsolver/models.py`: dimension consistency (`len(variable_names) == len(objective) == len(bounds)`), unique `block_id` values, valid `constraint_indices` in `LinkingColumns`, `senses` values ∈ `{"=", "<=", ">="}`, `lower <= upper` in `Bounds`, `schema_version` major == `"1"`
- [ ] T014 Implement `Problem.from_file()` in `src/dwsolver/models.py` — read JSON from path, call `model_validate`, raise `DWSolverInputError` on `FileNotFoundError`, `JSONDecodeError`, and `ValidationError`
- [ ] T015 [P] Write `tests/unit/test_models.py` — unit tests for all validators (happy path + each error condition), `from_file()` with valid/missing/malformed files, `SolveStatus` string values, `Result` field constraints per status

**Checkpoint**: `pytest tests/unit/test_models.py` passes; `mypy src/dwsolver/models.py` passes with strict mode.

---

## Phase 3: User Story 1 — CLI Solve a Valid Problem (Priority: P1) 🎯 MVP

**Goal**: A user can run `dwsolver problem.json` and receive a `problem.json.solution.json`
file containing the optimal objective value and variable assignments.

**Independent Test**: Run `dwsolver tests/fixtures/simple_two_block.json`; verify
`simple_two_block.json.solution.json` is written and `status == "optimal"` with
the known objective value; exit code is 0.

### Implementation

- [ ] T016 [US1] Implement `src/dwsolver/subproblem.py` — `solve_subproblem(block, row_duals, convexity_dual, tolerance) -> SubproblemResult`: create a `Highs()` instance, build the subproblem LP with modified objective `(c_i - π' D_i)`, call `h.setOptionValue("solver", "simplex")`, run, extract primal solution and reduced cost; return status (`optimal`, `infeasible`, `unbounded`) and the column data (`D_i x_i`, objective coefficient `c_i' x_i`)
- [ ] T017 [US1] Implement `src/dwsolver/solver.py` — `solve(problem, workers, tolerance, max_iterations) -> Result`: Phase I (build initial Restricted Master with one artificial per linking constraint, iterate until artificials zero or infeasible); Phase II (DW column generation loop: solve master → extract duals → `dispatch_subproblems` via `ThreadPoolExecutor` futures-collect → add improving columns → re-solve master → check convergence); reconstruct primal solution from lambda values
- [ ] T018 [US1] Implement `dispatch_subproblems()` in `src/dwsolver/solver.py` — `ThreadPoolExecutor(max_workers=min(workers or cpu_count()*2, len(blocks)))`, submit all blocks, `as_completed` collect; pass `row_duals` and `convexity_duals` as immutable arguments; aggregate `SubproblemResult` list in main thread only
- [ ] T019 [US1] Implement `src/dwsolver/cli.py` — `@click.command()` with `PROBLEM_FILE` positional arg, `--output`, `--workers`, `--tolerance`; call `Problem.from_file()` then `solve()`; write `Result` as JSON to output path (default `<input>.solution.json`); all errors to stderr; exit 0 for valid solver outcomes, exit 1 for tool failures
- [ ] T020 [US1] Export `solve` in `src/dwsolver/__init__.py` — wire up imports from `models.py` and `solver.py` so `from dwsolver import solve, Problem, Result, SolveStatus, DWSolverInputError` works
- [ ] T021 [US1] Implement BDD steps for `features/cli_usage.feature` scenarios 1–3 ("Solve a valid problem", "Explicit output path", "Variable assignments in output") in `tests/bdd/steps/test_cli_usage.py` using `click.testing.CliRunner`
- [ ] T022 [P] [US1] Write `tests/unit/test_solver.py` — unit tests for `dispatch_subproblems` (mock `solve_subproblem`), Phase I artificial variable injection, Phase II column generation loop termination, `workers=1` vs `workers=N` produce identical results
- [ ] T023 [P] [US1] Write `tests/unit/test_subproblem.py` — unit tests for `solve_subproblem`: verify modified objective construction (`c_i - π' D_i`), optimal result extraction, infeasible/unbounded status passthrough, `high.setOptionValue("solver", "simplex")` is called

**Checkpoint**: `dwsolver tests/fixtures/simple_two_block.json` produces correct solution file; all US1 BDD scenarios pass; exit code 0.

---

## Phase 4: User Story 2 — CLI Graceful Reporting of Non-Solvable Problems (Priority: P2)

**Goal**: Infeasible, unbounded, and malformed inputs each produce a structured,
informative response; no crashes; correct exit codes.

**Independent Test**: Run `dwsolver tests/fixtures/infeasible.json`; verify output
`status == "infeasible"`, `variable_values == {}`, `objective == null`, exit code 0.
Run `dwsolver missing.json`; verify error on stderr, exit code 1.

### Implementation

- [ ] T024 [US2] Implement BDD steps for `features/cli_usage.feature` — infeasible scenario ("Output indicates infeasible") in `tests/bdd/steps/test_cli_usage.py` — assert on output JSON `status`, empty `variable_values`, null `objective`, exit code 0
- [ ] T025 [US2] Implement BDD steps for `features/cli_usage.feature` — unbounded scenario ("Output indicates unbounded") in `tests/bdd/steps/test_cli_usage.py` — same assertions for `status == "unbounded"`
- [ ] T026 [P] [US2] Implement BDD steps for `features/cli_usage.feature` — error handling scenarios ("Malformed input file", "Missing input file", "Error message goes to stderr") in `tests/bdd/steps/test_cli_usage.py` — use `CliRunner`; assert stderr content, non-zero exit, no output file created
- [ ] T027 [US2] Verify `solver.py` Phase I returns `Result(status=INFEASIBLE)` when artificials cannot be driven to zero — add integration test in `tests/unit/test_solver.py` using `tests/fixtures/infeasible.json`
- [ ] T028 [P] [US2] Verify `solver.py` returns `Result(status=UNBOUNDED)` when a subproblem is unbounded — add integration test in `tests/unit/test_solver.py` using `tests/fixtures/unbounded.json`

**Checkpoint**: All US2 BDD scenarios pass; `pytest tests/bdd/` shows 0 failures for cli_usage.feature scenarios 1–7.

---

## Phase 5: User Story 3 — Library Solve a Problem Programmatically (Priority: P3)

**Goal**: A developer imports `dwsolver`, constructs a `Problem`, calls `solve()`,
and inspects the `Result` — with no CLI interaction required.

**Independent Test**: In a Python script, `from dwsolver import solve, Problem`;
construct a two-block LP object; call `result = solve(problem)`; assert
`result.status == SolveStatus.OPTIMAL` and `result.objective` matches known value.

### Implementation

- [ ] T029 [US3] Implement BDD steps for `features/library_usage.feature` — optimal solve scenarios ("Solve a valid problem via library", "Access variable_values") in `tests/bdd/steps/test_library_usage.py` — construct `Problem` directly from Python objects (no file I/O); call `solve()`; assert result fields
- [ ] T030 [P] [US3] Implement BDD steps for `features/library_usage.feature` — stateless-call scenario ("Stateless calls produce consistent results") in `tests/bdd/steps/test_library_usage.py` — call `solve()` twice with same problem; assert results are equal
- [ ] T031 [P] [US3] Implement BDD steps for `features/library_usage.feature` — infeasible/unbounded library scenarios ("Infeasible problem via library", "Unbounded problem via library") in `tests/bdd/steps/test_library_usage.py` — assert `variable_values == {}`, correct status
- [ ] T032 [P] [US3] Implement BDD steps for `features/library_usage.feature` — `workers` and `tolerance` scenarios ("Deterministic results across worker counts", "Custom tolerance recorded in result") in `tests/bdd/steps/test_library_usage.py`
- [ ] T033 [P] [US3] Implement BDD step for `features/library_usage.feature` — `Problem.from_file()` scenario ("Load problem from file via library") in `tests/bdd/steps/test_library_usage.py`

**Checkpoint**: All US3 BDD scenarios pass; `from dwsolver import solve, Problem, Result, SolveStatus` works without touching `cli.py`.

---

## Phase 6: User Story 4 — Library Error Handling (Priority: P4)

**Goal**: Invalid `Problem` inputs raise a well-typed, catchable `DWSolverInputError`
with an informative message. No unhandled exceptions with opaque tracebacks.

**Independent Test**: Call `solve()` with a `Problem` having mismatched dimension
arrays; assert `DWSolverInputError` is raised and `str(exc)` identifies the field.

### Implementation

- [ ] T034 [US4] Implement BDD steps for `features/library_usage.feature` — error handling scenario ("DWSolverInputError raised for invalid input", "Exception importable from top-level") in `tests/bdd/steps/test_library_usage.py` — use `pytest.raises(DWSolverInputError)`, assert message content, assert `from dwsolver import DWSolverInputError` works
- [ ] T035 [US4] Implement BDD step for `features/library_usage.feature` — `iteration_limit` partial result scenario ("Iteration limit returns best feasible solution") in `tests/bdd/steps/test_library_usage.py` — pass `max_iterations=1`, assert `status == "iteration_limit"`, `variable_values` populated, `objective` is float
- [ ] T036 [P] [US4] Add remaining `DWSolverInputError` trigger paths to `tests/unit/test_models.py`: unsupported `schema_version`, duplicate `variable_names` across blocks, `lower > upper`, invalid sense string, `constraint_indices` out of range

**Checkpoint**: All US4 BDD scenarios pass; `pytest tests/unit/` and `pytest tests/bdd/` show 0 failures.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: CI wire-up, type-checking cleanliness, SC-001 regression verification,
and documentation completeness.

- [ ] T037 Run `mypy src/` in strict mode and resolve all remaining type errors across `models.py`, `solver.py`, `subproblem.py`, `cli.py`, `__init__.py`
- [ ] T038 Run `ruff check src/ tests/` and `ruff format --check src/ tests/` — fix all lint/format violations
- [ ] T039 Verify SC-001: run `dwsolver` against all reference fixture problems in `tests/fixtures/`; assert 100% correct status classification and objective values match known optima; add failures as regression test cases in `tests/unit/test_solver.py`
- [ ] T040 [P] Write `README.md` — install instructions, one-line CLI example, 10-line library example (matching `quickstart.md`), link to JSON schema reference
- [ ] T041 [P] Verify CI pipeline passes end-to-end on a clean `git push` — all 5 stages green: ruff, mypy, pytest unit, pytest BDD

---

## Dependencies

Story completion order (each depends on Foundation being complete):

```
Phase 1 (Setup)
    └── Phase 2 (Foundation: models.py + validators)
            ├── Phase 3 (US1: CLI solve) ← MVP
            │       └── Phase 4 (US2: CLI error handling)  [can start after T017]
            ├── Phase 5 (US3: Library API)                  [independent of US2]
            └── Phase 6 (US4: Library errors)               [independent of US2]
                    └── Phase 7 (Polish)
```

US3 and US4 are independent of US2 — they can be worked on in parallel once Phase 2 and Phase 3 are done.

---

## Parallel Execution Examples

**Within Phase 3 (US1)**:
- T022 (unit tests for solver) and T023 (unit tests for subproblem) can run in parallel with T016–T018 (implementation) once T015 (models) is done.

**Within Phase 4 (US2)**:
- T026 (error scenario BDD steps), T027, T028 can all be worked in parallel.

**Across US3 and US4**:
- After T019 (CLI) is done, US3 (T029–T033) and US4 (T034–T036) can proceed simultaneously.

---

## Implementation Strategy

**Suggested MVP scope**: Phases 1 + 2 + Phase 3 (US1 only).

After Phase 3, the system is fully functional for the happy path: a user can install `dwsolver`, run it against a JSON problem file, and receive a correct solution. US2–US4 add robustness and the full library surface but do not block the core demonstration.

---

## Format Validation

All tasks follow `- [ ] T### [P?] [US?] Description with file path`.

| Check | Result |
|-------|--------|
| Every task has a checkbox `- [ ]` | ✅ |
| Every task has a sequential T### ID | ✅ |
| `[P]` present only on parallelizable tasks | ✅ |
| `[US#]` present on all Phase 3–6 tasks | ✅ |
| Setup/Foundation/Polish phases have no `[US#]` label | ✅ |
| Every task includes an explicit file path | ✅ |
| Total tasks | **41** |

### Task count by user story

| Phase | Story | Tasks |
|-------|-------|-------|
| Phase 1 | Setup | T001–T011 (11) |
| Phase 2 | Foundation | T012–T015 (4) |
| Phase 3 | US1 (CLI solve) | T016–T023 (8) |
| Phase 4 | US2 (CLI errors) | T024–T028 (5) |
| Phase 5 | US3 (Library API) | T029–T033 (5) |
| Phase 6 | US4 (Library errors) | T034–T036 (3) |
| Phase 7 | Polish | T037–T041 (5) |
