# Tasks: Replace four_sea Placeholder Test Fixture

**Feature branch**: `002-fix-four-sea-tests`  
**Input**: `specs/002-fix-four-sea-tests/` — spec.md, research.md, data-model.md, quickstart.md  
**Generated**: 2026-03-04

---

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- **[US1], [US2]**: Which user story this task belongs to
- Exact file paths are included in every task description

---

## Phase 1: Setup

**Purpose**: Create the tool directory structure and confirm the current test failure

- [x] T001 Create `specs/002-fix-four-sea-tests/tools/` directory and add empty `__init__.py` placeholder
- [x] T002 Run `pytest tests/ -k four_sea -v` and confirm the scenario currently fails or produces a result ≠ 12.0 (placeholder fixture); note the actual failure message in the git commit message for T018 as the "before" baseline

**Checkpoint**: Tool directory exists; baseline failure mode is documented

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Assets and knowledge that both user stories depend on — the `dwsolver` schema contracts and parser architecture decisions

**⚠️ CRITICAL**: No US1 or US2 work can begin until this phase is complete

- [x] T003 Read `src/dwsolver/models.py` in full and record the exact field names, types, and validator constraints for `Problem`, `Master`, `Block`, `BlockConstraints`, `LinkingColumns`, and `Bounds` — add a schema reference comment block at the top of `specs/002-fix-four-sea-tests/tools/cplex_to_json.py` (create stub file) confirming each required field
- [x] T004 Fetch `master.cplex` from `https://raw.githubusercontent.com/alotau/dwsolver/master/examples/four_sea/master.cplex` and save a local copy to `specs/002-fix-four-sea-tests/tools/master.cplex` for offline reference during development

**Checkpoint**: Schema understood; converter stub file exists; master CPLEX available locally

---

## Phase 3: User Story 1 — Build CPLEX-to-JSON Converter (Priority: P1) 🎯 MVP

**Goal**: Deliver a working `specs/002-fix-four-sea-tests/tools/cplex_to_json.py` that fetches all five CPLEX files from the alotau/dwsolver GitHub repo and emits a valid `dwsolver` JSON fixture.

**Acceptance criteria (FR-001, NFR-001, NFR-002)**:
- Script accepts `--output PATH` CLI argument
- Running it twice produces bit-for-bit identical output
- Final JSON passes `Problem.model_validate()` without raising

**Independent Test**: `python specs/002-fix-four-sea-tests/tools/cplex_to_json.py --output /tmp/test_four_sea.json && python -c "import json; from dwsolver.models import Problem; Problem.model_validate(json.load(open('/tmp/test_four_sea.json')))"`

### Implementation for User Story 1

- [x] T005 [US1] Implement CLI entry point with `argparse` (`--output` required, `--cplex-base-url` optional with default pointing to alotau/dwsolver) and an HTTPS fetch helper (`urllib.request.urlopen`) in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`

- [x] T006 [US1] Implement `parse_master(text: str) -> dict` in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`:
  - Parse `Minimize` section: scan for `[+/-][coeff] w(aircraft,sector,t)` tokens → build `master_obj: dict[str, float]` covering all 8 aircraft (−2.0 for SEA vars t=199..218, +1.0 for LAS vars t=20..39)
  - Parse `Subject To` section: extract 2 `Arrival_Rate(SEA,j)` constraint rows
    (`Arrival_Rate(SEA,13)` and `Arrival_Rate(SEA,14)` — only 2 rows in master.cplex):
    - `constraint_names: list[str]`
    - `rhs: list[float]` — all 7.0
    - `senses: list[str]` — all `"<="` (schema uses `"<="` not `"L"`)
    - `master_rows: list[dict[str, float]]` — per-constraint sparse `{var_name: coeff}` (used later for linking_columns)
  - Return `{"constraint_names": ..., "rhs": ..., "senses": ..., "master_obj": ..., "master_rows": ...}`

- [x] T007 [US1] Implement `parse_subproblem_vars(text: str, block_id: str, master_obj: dict) -> dict` in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`:
  - Parse `Bounds` section: each `0 <= w(...) <= 1` line declares one variable → collect into list, sort alphabetically → `variable_names: list[str]`
  - Build `var_index: dict[str, int]` from sorted list
  - Build `objective: list[float]` by looking up each variable in `master_obj` (0.0 if absent) — subproblem files have **no objective section**; objective comes entirely from master
  - Build `bounds: list[[float, float]]` — all `[0.0, 1.0]` (ignore `GENERALS` section per research.md Decision 4)
  - Return `{"block_id": ..., "variable_names": ..., "var_index": ..., "objective": ..., "bounds": ...}`

- [x] T008 [US1] Implement `parse_subproblem_constraints(text: str, var_index: dict) -> dict` in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`:
  - Parse `Subject To` section; each constraint line has the form:
    `CONSTRAINT_NAME: VAR_A - VAR_B [<=|>=] 0`
    (two variables with coefficients +1 and −1; RHS always 0)
  - `Sector_Time(...)` rows → sense `"L"`, RHS `0.0`, two non-zeros: +1.0 on LHS var, −1.0 on RHS var
  - `Temporality(...)` rows → sense `"G"`, RHS `0.0`, two non-zeros: +1.0 on LHS var, −1.0 on RHS var
  - Accumulate sparse COO triplets `(row_idx, col_idx, value)` using `var_index` for column lookup
  - Return `{"names": ..., "senses": ..., "rhs": ..., "rows": ..., "cols": ..., "values": ...}`

- [x] T009 [US1] Implement `build_linking_columns(master_rows: list[dict], var_index: dict) -> dict` in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`:
  - `master_rows` is the list of 13 sparse dicts `{var_name: coeff}` produced by `parse_master`
  - For each constraint row `(row_idx, row_dict)`: iterate `row_dict.items()`; if `var_name` is present in this block's `var_index`, emit COO triplet `(row_idx, var_index[var_name], coeff)`
  - Source of truth for which variables link: the master CPLEX file itself — no time-window arithmetic needed
  - Return `{"rows": [...], "cols": [...], "values": [...]}`
  - Expected cardinality: 2 master constraints, each touching 2–4 variables in this block = **6 COO entries** per block (confirmed from generated fixture)

- [x] T010 [US1] Implement `assemble_problem(master: dict, blocks: list[dict]) -> dict` in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`:
  - Build the top-level `Problem` dict matching the `dwsolver` schema:
    - `master`: `constraint_names`, `rhs`, `senses` — drop `master_obj` and `master_rows` (objective contributions go into each block's `objective` array, not the master dict)
    - Each `block`: `block_id`, `variable_names`, `objective`, `bounds`, `constraints` (with `names`, `senses`, `rhs`, `matrix` as `{"rows":…,"cols":…,"values":…}`), `linking_columns`
  - Determinism: `variable_names` already sorted alphabetically by T007; use `json.dumps(sort_keys=True, indent=2)`
  - Write to `args.output` path

- [x] T011 [US1] Wire all helpers together in `main()` function in `specs/002-fix-four-sea-tests/tools/cplex_to_json.py`:
  - Fetch `master.cplex`, `subprob_1.cplex`, `subprob_2.cplex`, `subprob_3.cplex`, `subprob_4.cplex`
  - Block assignments (from research.md): block_1 → AC8_7/AC7_6; block_2 → AC6_5/AC5_4; block_3 → AC4_3/AC3_2; block_4 → AC2_1/AC1_0
  - Parse, assemble, write fixture
  - Print confirmation line: `Written: {output_path}  ({num_blocks} blocks, {total_vars} vars, {total_constraints} constraints)`

**Checkpoint**: US1 complete — `python specs/002-fix-four-sea-tests/tools/cplex_to_json.py --output /tmp/test_four_sea.json` succeeds and `Problem.model_validate()` passes without error

---

## Phase 4: User Story 2 — Generate and Validate the Complete Fixture (Priority: P2)

**Goal**: Produce the final `tests/fixtures/ref_four_sea.json`, confirm it satisfies all FR-001..FR-007 acceptance criteria, and verify the `dwsolver` solver returns `objective: 12.0`.

**Acceptance criteria (FR-001..FR-007, NFR-003)**:
- `ref_four_sea.json` has exactly 4 blocks with correct `block_id` values
- Master has exactly 13 `Arrival_Rate(SEA,j)` constraints, all `senses = "L"`, all `rhs = 7.0`
- Each block's `linking_columns` has non-empty `rows`/`cols`/`values` lists
- Placeholder metadata fields (`status`, `TODO`) are absent
- Solver output: `{"objective": 12.0}`
- All other `pytest` tests continue to pass

**Independent Test**: `dwsolver tests/fixtures/ref_four_sea.json` (or equivalent solver invocation) → `{"objective": 12.0, ...}`

### Implementation for User Story 2

- [x] T012 [US2] Run converter to produce the real fixture, replacing the placeholder in `tests/fixtures/ref_four_sea.json`:
  ```
  python specs/002-fix-four-sea-tests/tools/cplex_to_json.py --output tests/fixtures/ref_four_sea.json
  ```
  Inspect the output file: confirm 4 blocks, 2 master constraints, no placeholder fields

- [x] T013 [US2] Validate fixture against `dwsolver` Pydantic schema in a one-off script or interactive session:
  ```python
  import json
  from dwsolver.models import Problem
  data = json.load(open("tests/fixtures/ref_four_sea.json"))
  problem = Problem.model_validate(data)
  assert len(problem.blocks) == 4
  assert len(problem.master.constraint_names) == 2
  for b in problem.blocks:
      assert len(b.linking_columns.rows) > 0, f"{b.block_id} has empty linking_columns"
  print("Schema validation passed")
  ```
  If validation fails, debug `cplex_to_json.py` and re-run T012

- [x] T014 [US2] Run `dwsolver` against the new fixture and confirm `objective: 12.0` (FR-006):
  - Invoke the solver using the project's standard CLI (see `quickstart.md`)
  - Compare solver output to `tests/fixtures/ref_four_sea.expected.json`
  - If result ≠ 12.0: record the actual value, diff the new vs old fixture structure, debug the block constraint or linking_columns encoding

- [x] T015 [US2] Run the full test suite and confirm no regressions (NFR-003):
  ```
  pytest tests/ -v
  ```
  All previously-passing tests must still pass; the `ref_four_sea` scenario must now produce a meaningful result

**Checkpoint**: US2 complete — fixture is correct, solver confirms optimality, CI suite is green

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Fix the broken `plan.md`, confirm commit history is clean, and close the feature branch

- [x] T016 ~~Fix `specs/002-fix-four-sea-tests/plan.md`~~ — **DONE** (plan.md written 2026-03-05 during consistency analysis session)

- [x] T017 [P] Verify `specs/002-fix-four-sea-tests/tools/cplex_to_json.py` has a `"""module docstring"""` and each function has a one-line docstring describing its purpose

- [ ] T018 Commit all changes with a descriptive message covering: converter script, regenerated fixture, plan.md fix, e.g.:
  ```
  feat(002): replace four_sea placeholder fixture with complete LP encoding

  - Add specs/002-fix-four-sea-tests/tools/cplex_to_json.py: CPLEX→JSON converter
  - Regenerate tests/fixtures/ref_four_sea.json from alotau/dwsolver CPLEX files
  - Fix specs/002-fix-four-sea-tests/plan.md (was still template boilerplate)
  - Solver confirms objective: 12.0 against ref_four_sea.expected.json
  ```

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS US1 and US2
- **US1 (Phase 3)**: Depends on Phase 2 — converter must be built before fixture can be generated
- **US2 (Phase 4)**: Depends on Phase 3 (US1 complete) — converter must exist to generate fixture
- **Polish (Phase 5)**: Depends on Phase 4 passing

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Foundational — no dependency on US2
- **US2 (P2)**: Sequential dependency on US1 — converter is prerequisite for fixture generation

### Within Each User Story

```
US1 dependency chain:
T005 (CLI + fetch) → T006 (parse_master) → T007 (parse_subproblem)
                                          → T008 (parse_constraints) [P with T007]
                                          → T009 (build_linking_columns) [depends on T006+T007]
                                          → T010 (assemble_problem)
                                          → T011 (main/wire-up)

US2 dependency chain:
T011 complete → T012 (run converter) → T013 (schema validate) → T014 (solver verify) → T015 (full pytest)
```

---

## Parallel Execution Within US1

```
# T007 and T008 can run in parallel (different parsing concerns, same file):
Task: "parse_subproblem — variables, objective, bounds"          → T007
Task: "parse_subproblem_constraints — Temporality + Sector_Time" → T008

# These depend on T006 and T007 completing first:
Task: "build_linking_columns — D_i COO encoding"  → T009
```

---

## Implementation Strategy

### MVP: Complete US1 and US2 as a single increment

This feature is a single cohesive delivery — the converter script serves no purpose without the fixture it generates, and the fixture has no value without the solver verification. Treat US1 → US2 as one MVP.

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (schema read + CPLEX reference copy)
3. Complete Phase 3: US1 — build and smoke-test the converter
4. **Validate checkpoint**: `Problem.model_validate()` passes on converter output
5. Complete Phase 4: US2 — generate fixture, verify solver, run full pytest
6. **Validate checkpoint**: `objective: 12.0`, all tests green
7. Complete Phase 5: Polish and commit

### Debug Protocol (if solver returns wrong objective)

1. Check `linking_columns` — are `rows`/`cols`/`values` non-empty for all 4 blocks?
2. Check master `senses` — must all be `"L"` (≤), not `"G"` (≥)
3. Check objective coefficients in each block — SEA vars must be −2, LAS vars must be +1
4. Check COO sign convention — `w(ac,SEA,t_end_j)` is +1, `w(ac,SEA,t_start_j)` is −1 per master constraint row
5. Run with a single block isolated and verify partial objective before assembling all 4

---

## Notes

- The converter is a dev tool in `specs/002-fix-four-sea-tests/tools/` — it is NOT shipped with the `dwsolver` package and does not need to be importable from the package namespace
- `ref_four_sea.expected.json` (`{"objective": 12.0}`) is already correct and **MUST NOT be changed**
- The +160 constant term in the CPLEX objective is dropped per research.md Decision 3 — the solver objective of 12.0 is net of this constant
- All `bounds` are `[0.0, 1.0]` — the LP relaxation of the integer program (GENERALS section ignored per research.md Decision 4)
- Variable naming convention: `w(aircraft_id,sector_name,time_step)` — spaces are significant; match the CPLEX file exactly
