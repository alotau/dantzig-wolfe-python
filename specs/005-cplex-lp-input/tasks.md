# Tasks: CPLEX LP Input Format Support

**Input**: Design documents from `specs/005-cplex-lp-input/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Total tasks**: 23  
**Tests**: TDD mandatory per constitution Principle III — tests written before implementation, confirmed failing before implementation begins.

---

## Phase 1: Setup

**Purpose**: Fixture files and Gherkin specification in place before any code changes.

- [ ] T001 Download four_sea CPLEX LP files (master.cplex, subprob_1–4.cplex) from alotau/dwsolver and store as static fixtures in `tests/fixtures/four_sea/`
- [ ] T002 [P] Write Gherkin feature file `specs/001-gherkin-bdd-specs/features/cplex_lp_usage.feature` covering all US1 acceptance scenarios (LP files CLI, backward compat JSON, .cplex extension, --format lp, --output flag)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `lp_parser.py` module skeleton must exist before any tests or implementations can import it.

**⚠️ CRITICAL**: No user story work can begin until T003 is complete.

- [ ] T003 Create `src/dwsolver/lp_parser.py` with `MasterLP`, `SubproblemLP`, `LinkingSpec` dataclasses and stub functions (`parse_master`, `parse_subproblem`, `infer_linking`, `resolve_block_objective`, `assemble_problem`, `load_problem_from_lp`) — all stubs raise `NotImplementedError`

**Checkpoint**: Foundation ready — US1, US2, and US3 test tasks can now be written in parallel.

---

## Phase 3: User Story 1 — CLI Solve Using CPLEX LP Files (Priority: P1) 🎯 MVP

**Goal**: Users can run `dwsolver master.lp sub1.lp [sub2.lp ...]` from the command line and receive a solution file. Existing `dwsolver problem.json` use continues unchanged.

**Independent Test**: Run `dwsolver tests/fixtures/four_sea/master.cplex tests/fixtures/four_sea/subprob_1.cplex … subprob_4.cplex`; assert exit code 0 and solution file `objective == 12.0`.

### Tests for User Story 1 ⚠️ Write and confirm FAIL before implementing T006–T011

- [ ] T004 [P] [US1] Write unit tests for `parse_master()`, `infer_linking()`, `resolve_block_objective()` in `tests/unit/test_lp_parser.py` covering four_sea master (constraint count, objective coefficients, constant term) — confirm FAIL
- [ ] T005 [P] [US1] Write BDD step implementations in `tests/bdd/steps/test_cplex_lp_usage.py` wiring `specs/001-gherkin-bdd-specs/features/cplex_lp_usage.feature` scenarios — confirm FAIL

### Implementation for User Story 1

- [ ] T006 [US1] Implement `parse_master()` in `src/dwsolver/lp_parser.py` — section extraction (Minimize/Maximize direction, Subject To constraints, `\* constant term = N *\` comment → `obj_constant`)
- [ ] T007 [P] [US1] Implement `parse_subproblem()` in `src/dwsolver/lp_parser.py` — Bounds section variable discovery (all four bound formats), local constraints dense matrix, objective section extraction
- [ ] T008 [US1] Implement `infer_linking()` in `src/dwsolver/lp_parser.py` — match subproblem `var_index` against `master.row_coefficients` to emit sparse COO `LinkingSpec`
- [ ] T009 [US1] Implement `resolve_block_objective()` in `src/dwsolver/lp_parser.py` — subproblem-first then master-fallback strategy
- [ ] T010 [US1] Implement `assemble_problem()` and `load_problem_from_lp()` in `src/dwsolver/lp_parser.py` — objective constant injection into block 0, `Problem.model_validate()` call
- [ ] T011 [US1] Update `src/dwsolver/cli.py` — replace `PROBLEM_FILE` with `FILES` (`nargs=-1`), add `--format lp|json` option, implement format detection logic (extension → mode → load)

**Checkpoint**: `dwsolver master.cplex sub1.cplex … sub4.cplex` solves four_sea and produces `objective == 12.0`. All BDD and unit tests for US1 GREEN.

---

## Phase 4: User Story 2 — Library API for CPLEX LP Problems (Priority: P2)

**Goal**: `Problem.from_lp(master_path, subproblem_paths)` and `Problem.from_lp_text(master_text, sub_texts)` are callable from Python with no CLI involvement and appear in the public `dwsolver` API.

**Independent Test**: `problem = Problem.from_lp("master.cplex", [...])` → `solve(problem).objective == 12.0`, no CLI invoked.

### Tests for User Story 2 ⚠️ Write and confirm FAIL before implementing T013–T015

- [ ] T012 [US2] Write unit tests for `Problem.from_lp()` and `Problem.from_lp_text()` (happy path, four_sea regression, from-text equivalence) in `tests/unit/test_lp_parser.py` — confirm FAIL

### Implementation for User Story 2

- [ ] T013 [US2] Add `Problem.from_lp(master_path, subproblem_paths)` class method in `src/dwsolver/models.py` — delegates to `load_problem_from_lp()` from `lp_parser`
- [ ] T014 [US2] Add `Problem.from_lp_text(master_text, subproblem_texts)` class method in `src/dwsolver/models.py` — parses from strings, no file I/O
- [ ] T015 [P] [US2] Update `src/dwsolver/__init__.py` docstring to document `Problem.from_lp` and `Problem.from_lp_text` in the public API comment header

**Checkpoint**: `Problem.from_lp()` and `Problem.from_lp_text()` callable from Python, four_sea yields `objective == 12.0`. All US2 tests GREEN.

---

## Phase 5: User Story 3 — Clear Diagnostics for Invalid CPLEX LP Input (Priority: P3)

**Goal**: Every invalid input path raises `DWSolverInputError` with a message naming the file and describing the problem. No silent wrong answers.

**Independent Test**: Invoke CLI with a truncated `.lp` file (empty Subject To); assert non-zero exit code, no output file written, descriptive message on stderr.

### Tests for User Story 3 ⚠️ Write and confirm FAIL before implementing T017–T020

- [ ] T016 [US3] Write unit tests for all `DWSolverInputError` error paths (missing file, empty Subject To, no Bounds variables, duplicate variable across blocks, single LP with no subproblems, unknown --format) in `tests/unit/test_lp_parser.py` — confirm FAIL

### Implementation for User Story 3

- [ ] T017 [US3] Implement `DWSolverInputError` raises in `parse_master()` in `src/dwsolver/lp_parser.py` — no `Subject To` section found, zero constraints parsed
- [ ] T018 [P] [US3] Implement `DWSolverInputError` raises in `parse_subproblem()` in `src/dwsolver/lp_parser.py` — no `Bounds` section, zero variables declared
- [ ] T019 [US3] Implement `DWSolverInputError` raises in `assemble_problem()` in `src/dwsolver/lp_parser.py` — empty `subs` list, duplicate variable name across blocks
- [ ] T020 [US3] Implement CLI error handling in `src/dwsolver/cli.py` — file-not-found for any LP file, unknown `--format` value, single LP file with no subproblems and no `--format json`, extra files in JSON mode

**Checkpoint**: All US3 error paths raise `DWSolverInputError` / non-zero CLI exit. All US3 tests GREEN.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Type correctness, lint compliance, and full regression confirmation.

- [ ] T021 [P] Fix all mypy strict errors in `src/dwsolver/lp_parser.py`, `src/dwsolver/models.py`, `src/dwsolver/cli.py` (`mypy --strict src/dwsolver/`)
- [ ] T022 [P] Fix all ruff lint and format violations in `src/dwsolver/lp_parser.py`, `src/dwsolver/models.py`, `src/dwsolver/cli.py` (`ruff check src/ && ruff format src/`)
- [ ] T023 Run full test suite (`pytest tests/`) and confirm all unit + BDD tests pass with zero regressions against pre-005 baseline

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — begin immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Phase 2; tests (T004, T005) before implementation (T006–T011)
- **US2 (Phase 4)**: Depends on Phase 2 (T003) and US1 implementation (T010 — `assemble_problem` used by `from_lp`)
- **US3 (Phase 5)**: Depends on US1 implementation (T006–T010 — adds error raises to existing functions)
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — independent baseline
- **US2 (P2)**: Depends on US1 complete (`Problem.from_lp` delegates to `load_problem_from_lp`)
- **US3 (P3)**: Depends on US1 complete (adds error paths to parser functions implemented in T006–T010)

### Within Each User Story

1. Tests MUST be written and confirmed **failing** before implementation begins
2. `parse_master` (T006) and `parse_subproblem` (T007) are logically independent
3. `infer_linking` (T008) depends on both T006 and T007
4. `resolve_block_objective` (T009) depends on T006 and T007
5. `assemble_problem` / `load_problem_from_lp` (T010) depends on T008 and T009
6. CLI update (T011) depends on T010

---

## Parallel Opportunities

### Phase 1
```
T001 (download fixtures)       T002 (write Gherkin feature)
          ↓                              ↓
          └──────────── T003 ────────────┘
```

### Phase 3 (US1) — after T003
```
T004 (unit tests — parse_master, infer_linking)
T005 (BDD steps)
  ↓ both confirmed FAIL
T006 (parse_master)    T007 (parse_subproblem)
         └────────────────────┘
                    ↓
     T008 (infer_linking)  T009 (resolve_block_objective)
                    ↓
             T010 (assemble_problem)
                    ↓
              T011 (cli.py update)
```

### Phase 6
```
T021 (mypy)    T022 (ruff)
      └────────────┘
           ↓
         T023 (full pytest)
```

---

## Implementation Strategy

**MVP = Phase 3 (US1) complete**: The four_sea end-to-end CLI test passing is the
minimum viable deliverable. US2 and US3 build on the same parser code; they add
API surface and robustness but not new algorithmic capability.

**Suggested order for a single implementer**:
1. T001, T002 (fixtures + Gherkin) — no code changes
2. T003 (skeleton) — unblocks everything
3. T004, T005 (US1 tests RED) — verify test harness
4. T006, T007, T008, T009, T010 (parser implementation) — core logic
5. T011 (CLI wiring) — end-to-end GREEN
6. T012, T013, T014, T015 (US2 library API)
7. T016, T017, T018, T019, T020 (US3 diagnostics)
8. T021, T022, T023 (Polish)
