# Tasks: Test Coverage Reporting & Live README Badges

**Input**: Design documents from `specs/007-coverage-badge/`  
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with adjacent tasks (different files, no unmet dependencies)
- **[Story]**: User story label — US1 through US5
- Setup/Foundational/Polish phases: no story label
- Every task includes an exact file path

---

## Phase 1: Setup

**Purpose**: Add the coverage measurement dependency so all downstream tasks can build on it.

- [X] T001 Add `pytest-cov` to `dev` optional-dependencies list in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configure coverage measurement, scoping, threshold, and output formats. These settings are consumed by every subsequent phase — US1 (local report), US2/US3 (CI badge and gate), and US4/US5 (script integration).

**⚠️ CRITICAL**: Must be complete before any user story work begins.

- [X] T002 Add `[tool.coverage.run]` section (`source = ["dwsolver"]`, `omit` for benchmarks and tests) to `pyproject.toml`
- [X] T003 Add `[tool.coverage.report]` section (`fail_under = 90`, `show_missing = true`, `exclude_lines` for `TYPE_CHECKING` and `...`) to `pyproject.toml`
- [X] T004 Append `--cov=dwsolver --cov-report=term-missing --cov-report=xml:coverage.xml` to `addopts` in `[tool.pytest.ini_options]` in `pyproject.toml`

**Checkpoint**: `pyproject.toml` fully configured — coverage scoping, threshold, and output formats ready for all stories.

---

## Phase 3: User Story 1 — Local Coverage Report (Priority: P1) 🎯 MVP

**Goal**: A developer runs `pytest` and immediately sees per-module coverage with missing line numbers. No extra flags required.

**Independent Test**: Run `pip install -e ".[dev]" && pytest` and verify the terminal output contains a `Name / Stmts / Miss / Cover / Missing` table and an overall percentage.

- [X] T005 [US1] Install local dev dependencies with `pip install -e ".[dev]"` and run `pytest` to confirm per-module coverage report appears in terminal with missing lines — verify `coverage.xml` is written

**Checkpoint**: US1 complete. Developers get instant local line coverage feedback. ✅

---

## Phase 4: User Story 2 — Live README Badge (Priority: P2)

**Goal**: The README on `main` shows a dynamically-updated coverage badge sourced from the `python-coverage-comment-action-data` branch via shields.io.

**Independent Test**: Merge to `main` and within 5 minutes the badge in the README reflects the current coverage percentage.

- [X] T006 [US2] Add `python-coverage-comment-action` step (triggered on push to `main`, reads `coverage.xml`, writes `endpoint.json` to data branch) to `.github/workflows/ci.yml`

**Checkpoint**: US2 complete. Coverage badge auto-updates on every `main` push. ✅

---

## Phase 5: User Story 3 — Coverage Regression Guard (Priority: P3)

**Goal**: CI blocks any PR that would lower overall coverage below 90% with a clear failure message.

**Independent Test**: Open a PR adding source lines without tests and confirm the coverage gate step fails.

- [X] T007 [US3] Add a dedicated combined `pytest --cov=dwsolver --cov-fail-under=90 --cov-report=xml:coverage.xml -q` coverage-gate step (runs full suite on all Python matrix versions) to `.github/workflows/ci.yml`

**Checkpoint**: US3 complete. Coverage threshold enforced automatically in CI on every PR. ✅

---

## Phase 6: User Story 4 — Gherkin Scenario Completeness Badge (Priority: P4)

**Goal**: A README badge shows the number of passing Gherkin scenarios out of the total defined (e.g., `42 / 42`), auto-updated by CI on each `main` push.

**Independent Test**: After merging to `main`, the BDD badge in README reads `42 / 42` in green. Verify `bdd-badge.json` exists on the `python-coverage-comment-action-data` branch with correct `message` value.

> **TDD required per constitution** — write T008 tests, confirm RED, then implement T009.

- [X] T008 [P] [US4] Write unit tests for `scripts/bdd_report.py` in `tests/unit/test_bdd_report.py` covering: (a) feature file regex parsing returns correct scenario count per file, (b) JUnit XML parsed for pass/fail counts per test file, (c) `bdd-badge.json` output matches shields.io endpoint schema from `specs/007-coverage-badge/contracts/badges.md`, (d) `bdd-traceability.md` output matches table format from contracts — confirm tests FAIL before T009
- [X] T009 [US4] Implement `scripts/bdd_report.py` with CLI args `--junit`, `--features`, `--badge-output`, `--report-output`; feature file `re` parser counting `Scenario:` and `Scenario Outline:` definitions; JUnit XML parser mapping test classnames to feature file names; badge JSON writer; Markdown traceability table writer — make T008 GREEN
- [X] T010 [US4] Add BDD steps to `.github/workflows/ci.yml` on `main` push: run `pytest tests/bdd/ --junitxml=.bdd-results.xml --no-cov -q`; run `python scripts/bdd_report.py`; commit `bdd-badge.json` to `python-coverage-comment-action-data` branch; upload `bdd-traceability.md` as artifact `bdd-traceability-report` via `actions/upload-artifact@v4`

**Checkpoint**: US4 complete. BDD badge auto-updates, traceability report available as CI artifact. ✅

---

## Phase 7: User Story 5 — Feature-level BDD Traceability Report (Priority: P5)

**Goal**: A per-feature file breakdown (scenario pass/total per `.feature` file) is available as a downloadable CI artifact after every `main` run.

**Independent Test**: Download the `bdd-traceability-report` artifact from the latest `main` CI run and confirm it lists each feature file with correct scenario counts.

> US5 is fully satisfied by T008–T010: `bdd_report.py` writes `bdd-traceability.md` and T010's CI step uploads it as an artifact. No additional implementation tasks required.

**Checkpoint**: US5 complete. Per-feature BDD traceability downloadable from CI. ✅

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Surface all test quality signals together in the README for first-time visitors.

- [X] T011 [P] [US2][US4][US5] Add a `## Test Quality` section to `README.md` containing the line coverage badge (shields.io endpoint URL from `python-coverage-comment-action-data/endpoint.json`) and the BDD scenarios badge (shields.io endpoint URL from `python-coverage-comment-action-data/bdd-badge.json`), both linking to the GitHub Actions CI workflow page; group badges on adjacent lines following the schema in `specs/007-coverage-badge/contracts/badges.md`

**Checkpoint**: All visible test quality signals live in README. Feature complete. ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: No dependencies — start immediately
- **Foundational (T002–T004)**: Depends on T001 (pytest-cov installed)
- **US1 (T005)**: Depends on T001–T004 — verifies foundational config
- **US2 (T006)**: Depends on T005 (coverage.xml being produced by the test run)
- **US3 (T007)**: Depends on T006 (CI structure established) — same file, sequential
- **US4 (T008–T010)**: T008 can start after T005 (independent file — marked [P]); T009 depends on T008; T010 depends on T009 and T007 (same ci.yml, T007 must be done first)
- **US5**: Fully covered by T008–T010 — no separate tasks
- **Polish (T011)**: Depends on T006 (badge URL known) and T010 (BDD badge URL known); marked [P] because it edits README.md (different from ci.yml)

### User Story Completion Dependencies

```
T001 → T002 → T003 → T004 → T005 [US1 ✅]
                               ↓
                              T006 [US2]
                               ↓
                              T007 [US3 ✅]
                               ↓
          T008 [P] ──────────→ T009 → T010 [US4 ✅ US5 ✅]
          (can start after T005)        ↓
                                       T011 [P] [README]
```

### Parallel Execution Example: Phase 5 → Phase 6

After T007 is done, batch the following:

```bash
# Terminal A — BDD report tests (T008, independent file)
# Write tests/unit/test_bdd_report.py

# Terminal B — README badge section (T011, independent file, badge URLs already known from contracts)
# Add ## Test Quality section to README.md
```

Then sequentially:
```bash
# T009: implement scripts/bdd_report.py until T008 tests go GREEN
# T010: update .github/workflows/ci.yml with BDD reporting steps
```

---

## Implementation Strategy

**MVP = US1 only (T001–T005)**  
After T005, developers immediately get per-module line coverage output with every `pytest` run. No CI required. This is independently valuable and takes only `pyproject.toml` changes.

**Increment 2 = US2 + US3 (T006–T007)**  
The coverage badge appears in the README and CI enforces the 90% threshold. Both are CI-only changes — no Python source edits.

**Increment 3 = US4 + US5 (T008–T010)**  
New Python script `scripts/bdd_report.py` written TDD-first. This is the only increment that produces new executable code and associated unit tests.

**Increment 4 = Polish (T011)**  
README grouped badge section — final cosmetic step, can be done any time after T006 and T010.

---

## Task Count Summary

| Phase | Tasks | User Stories |
|---|---|---|
| Setup | 1 (T001) | — |
| Foundational | 3 (T002–T004) | — |
| US1 — Local Coverage | 1 (T005) | US1 ✅ |
| US2 — Live Badge | 1 (T006) | US2 ✅ |
| US3 — Regression Guard | 1 (T007) | US3 ✅ |
| US4/US5 — BDD Badge + Traceability | 3 (T008–T010) | US4 ✅ US5 ✅ |
| Polish | 1 (T011) | — |
| **Total** | **11** | **5 user stories** |

**Parallel opportunities**: T008 (alongside T006/T007), T011 (alongside T010)  
**MVP scope**: T001–T005 (US1 only — local coverage report, no CI required)
