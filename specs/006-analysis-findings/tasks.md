# Tasks: Analysis Findings Polish

**Source**: `ANALYSIS.md` (produced 2026-03-18)
**Input**: Cross-project analysis of spec-to-implementation alignment
**Total tasks**: 10
**Tests**: TDD mandatory per constitution Principle III — tests written before
implementation, confirmed failing before implementation begins.

---

## Analysis Validation Notes

The following ANALYSIS.md findings were **verified as false positives** and do
NOT require tasks:

| Finding | Verdict | Evidence |
|---|---|---|
| Gap 1: BDD feature files not auto-discovered | ❌ False positive | `bdd_features_base_dir = "specs/001-gherkin-bdd-specs/features"` in `pyproject.toml`; 41 BDD tests collected, all 259 tests pass |
| Gap 2: `ref_four_sea.json` is a placeholder | ❌ False positive | File exists, 24 MB — fully populated |
| Document solver constants | ❌ False positive | `_BIG_M` and `_PHASE1_ITER_BUDGET` are already named constants with explanatory comments in `src/dwsolver/solver.py` |

The following findings are **confirmed valid** and drive the tasks below:

| Finding | Verdict | Action |
|---|---|---|
| Gap 3: `matplotlib` absent from `pyproject.toml` | ✅ Valid | Add optional extras group; update README |
| Enhancement: `--verbose` CLI flag missing | ✅ Valid | TDD cycle: BDD scenario → step → implementation |
| Gap 4: BDD "solve" terminology undocumented | ✅ Minor | Single comment in each feature file (no code change) |

---

## Phase 1: Setup

**Purpose**: Branch setup

- [ ] T001 Create feature branch `006-analysis-findings` from current `main`

---

## Phase 2: User Story 1 — Document and Expose Optional matplotlib Dependency (P2)

**Goal**: Users who want `--save-chart` output can discover and install the
optional `matplotlib` dependency through standard tooling (`pip install
dwsolver[charts]`). The existing graceful no-op fallback is preserved.

**Independent Test**: `pip install -e ".[charts]"` succeeds; running
`python -m benchmarks --save-chart /tmp/bench.png` produces a PNG file.

### Tests for User Story 1 ⚠️ Write and confirm FAILING before implementation

- [X] T002 [P] [US1] Add unit test asserting `save_chart()` writes a valid PNG
  when matplotlib is installed, in `tests/unit/test_bench_table.py`

### Implementation for User Story 1

- [X] T003 [US1] Add `[project.optional-dependencies] charts = ["matplotlib>=3.7"]`
  extras group to `pyproject.toml` (after existing `dev` group)
- [X] T004 [P] [US1] Update `README.md` — add one-line note under the benchmark
  section: install with `pip install dwsolver[charts]` to enable `--save-chart`

**Checkpoint**: `pip install -e ".[charts]"` works; PNG produced by `--save-chart`

---

## Phase 3: User Story 2 — Add `--verbose` CLI Flag for Iteration Logging (P3)

**Goal**: Operators and researchers can pass `--verbose` (or `-v`) to see
per-iteration solver diagnostics (iteration number, entering phase, column count,
reduced-cost gap) on stderr. Silent by default; flag is opt-in.

**Independent Test**: Running `dwsolver --verbose simple_two_block.json` emits
at least one iteration line to stderr and still produces a correct solution file.

### Tests for User Story 2 ⚠️ Write and confirm FAILING before implementation

- [X] T005 [P] [US2] Add BDD scenario "Verbose output is emitted to stderr when
  --verbose is passed" to
  `specs/001-gherkin-bdd-specs/features/cli_usage.feature`
- [X] T006 [P] [US2] Implement BDD step for the verbose scenario in
  `tests/bdd/steps/test_cli_usage.py` — confirm it **fails** before
  proceeding to implementation
- [ ] T007 [P] [US2] Add unit test in `tests/unit/test_solver.py` asserting that
  `solve(..., verbose=True)` emits iteration lines to a provided stream

### Implementation for User Story 2

- [X] T008 [US2] Add `verbose: bool = False` parameter to `solve()` in
  `src/dwsolver/__init__.py` and propagate to `solver.py`
- [X] T009 [US2] Emit per-iteration diagnostic lines to a `verbose_stream`
  inside the column-generation loop in `src/dwsolver/solver.py` (stderr when
  invoked from CLI; injectable stream for unit tests)
- [X] T010 [US2] Add `--verbose / -v` flag to the Click command in
  `src/dwsolver/cli.py`; pass it through to `solve()` with `sys.stderr`

**Checkpoint**: `dwsolver --verbose <file>` emits iteration diagnostics to
stderr; solution output is unaffected; BDD and unit test pass

---

## Phase 4: Micro-Polish (No User Story)

**Purpose**: Low-effort documentation clarification identified in analysis

- [X] T011 Add a one-line comment at the top of the `Feature:` block in each
  `.feature` file (`cli_usage.feature`, `library_usage.feature`,
  `cplex_lp_usage.feature`) clarifying that "dwsolver solve FILE" is a
  readability convention mapped to the flat CLI by the `_invoke` helper in the
  step implementations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends only on Phase 1; independent of US2
- **US2 (Phase 3)**: Depends only on Phase 1; independent of US1
- **Polish (Phase 4)**: Can run at any time

### Parallel Opportunities

- T002 (US1 test) and T005–T007 (US2 tests) can all run in parallel after T001
- T003 and T004 (US1 implementation) can run in parallel
- T008–T010 (US2 implementation) must be sequential: API → solver → CLI
- T011 (polish) is independently parallelizable at any time

### Execution Order (Sequential Path)

```
T001 → T002 → T003 → T004    (US1: test then implement)
     ↘ T005 → T006 → T007
             → T008 → T009 → T010    (US2: test then implement)
T011 (anytime)
```

---

## Implementation Strategy

**MVP**: US1 only (T001–T004) — documents an already-working optional feature
with a single `pyproject.toml` edit and README note. Zero risk.

**Full scope**: US1 + US2 + Polish — adds verbose diagnostics useful for
debugging and research demos. Moderate effort (~2 hours including TDD).

**Skip**: The false-positive findings require no action.
