# Tasks: Performance Benchmark — Workers vs. Subproblems

**Branch**: `004-perf-benchmark`
**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md),
[contracts/cli_invocation.md](contracts/cli_invocation.md), [research.md](research.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other `[P]` tasks at the same phase (different files, no dependencies)
- **[US1]** / **[US2]**: User story scope marker
- All paths relative to repository root

---

## Phase 1: Setup

**Purpose**: Create the `benchmarks/` package skeleton and register it so the
Python toolchain can resolve it.

- [ ] T001 Create `benchmarks/__init__.py` (empty) to establish the package
- [ ] T002 Create `benchmarks/__main__.py` stub: `argparse` parser with `--repeats`, `--timeout`, `--save-chart` flags, `main()` that prints `"not implemented"` and exits 0
- [ ] T003 [P] Create `benchmarks/generator.py` stub: `make_bench_problem(n_blocks: int) -> Problem` that immediately raises `NotImplementedError`
- [ ] T004 [P] Create `benchmarks/runner.py` stub: `run_benchmark(config: BenchConfig) -> BenchMatrix` that immediately raises `NotImplementedError`
- [ ] T005 [P] Create `benchmarks/table.py` stub: `format_table(matrix: BenchMatrix) -> str` and `save_chart(matrix: BenchMatrix, path: Path) -> None` both raising `NotImplementedError`

**Checkpoint**: `python -m benchmarks` runs without `ImportError`; all stubs importable

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data model types (`BenchConfig`, `CellResult`, `BenchMatrix`, `CellError`)
that all three implementation modules (`generator.py`, `runner.py`, `table.py`) depend on.
No user story work can begin until this phase is complete.

- [ ] T006 Define `CellError` enum (`TIMEOUT`, `ERROR`) in `benchmarks/models.py`
- [ ] T007 Define `CellResult` dataclass in `benchmarks/models.py` — fields: `n_blocks: int`, `workers: int`, `elapsed: float | None`, `status: SolveStatus | CellError`, `iterations: int | None`
- [ ] T008 Define `BenchConfig` dataclass in `benchmarks/models.py` — fields: `subproblems: range`, `worker_counts: list[int]`, `repeats: int`, `timeout: float`, `save_chart: Path | None`; include default factory matching plan defaults
- [ ] T009 Define `BenchMatrix` dataclass in `benchmarks/models.py` — fields: `cells: list[list[CellResult]]`, `config: BenchConfig`; add invariant assertions in `__post_init__`
- [ ] T010 [P] Update stubs in `generator.py`, `runner.py`, `table.py` to import from `benchmarks/models.py` and `__main__.py` to construct a default `BenchConfig`

**Checkpoint**: `from benchmarks.models import BenchConfig, CellResult, BenchMatrix, CellError` works; all stubs still importable

---

## Phase 3: User Story 1 — Run the benchmark and read the results (Priority: P1) 🎯 MVP

**Goal**: A researcher runs `python -m benchmarks` and receives a fully populated
20×5 timing table; every cell shows a wall-clock time in seconds and optimality status.

**Independent Test**: `python -m benchmarks` completes without error and prints a
table with exactly 20 data rows, 5 columns of times ending in `s`, and all cells
showing the solve completed (no ERR or TIMEOUT tokens).

### Tests for User Story 1 (TDD — write before implementation; confirm failing first)

- [ ] T011 [P] [US1] Write `tests/unit/test_bench_generator.py` with all 10 generator tests from plan.md (parametrize n=1..20 for block-count test; use `pytest.mark.slow` on feasibility tests for n=5 and n=20)
- [ ] T012 [P] [US1] Write `tests/unit/test_bench_table.py` with all 7 table formatter tests from plan.md
- [ ] T013 [US1] Confirm tests in T011 and T012 all **fail** (the stubs raise `NotImplementedError`); record failure output

### Implementation for User Story 1

- [ ] T014 [US1] Implement `make_bench_problem(n_blocks)` in `benchmarks/generator.py`:
  - Validate `1 <= n_blocks <= 20`; raise `ValueError` otherwise
  - Build template block using `numpy.random.default_rng(0)`: 10 vars, 5 local `<=` constraints, bounds `[0, 1]`, coefficients from `Uniform(-2, 2)`, RHS by slack-from-known-point (`x*=0.5`, slack ~ `Uniform(0.1, 0.5)`)
  - Replicate template block `n_blocks` times
  - Add 10 master linking constraints (one per block variable, each `<= n_blocks * 0.6`)
  - Return validated `Problem`
- [ ] T015 [US1] Verify T011 generator tests pass; fix generator until all 10 tests are green
- [ ] T016 [US1] Implement `format_table(matrix: BenchMatrix) -> str` in `benchmarks/table.py`:
  - Header row: `"Workers →"` + right-aligned worker counts in 9-char columns
  - Section header: `"Subproblems"` on its own line
  - Body rows: 3-char right-aligned subproblem count + `{t:.2f}s` per cell (9-char columns); ERR/TIMEOUT cells show their token right-aligned in the same width
  - Trailing blank line
- [ ] T017 [US1] Verify T012 table tests pass; fix formatter until all 7 tests are green
- [ ] T018 [US1] Implement `run_benchmark(config: BenchConfig) -> BenchMatrix` in `benchmarks/runner.py`:
  - Pre-generate all `Problem` instances for `config.subproblems` before the timing loop
  - Outer loop over `n_blocks`, inner loop over `worker_counts`
  - Per cell: wrap `solve(prob, workers=w)` in `ThreadPoolExecutor(max_workers=1).submit(...).result(timeout=config.timeout)`; catch `TimeoutError` → `CellError.TIMEOUT`, other `Exception` → `CellError.ERROR`
  - When `config.repeats > 1`: repeat timing, record minimum elapsed
  - Print progress line to stderr after each cell: `[NNN/100] n_blocks= N, workers= W → Ts  status`
  - Return fully populated `BenchMatrix`
- [ ] T019 [US1] Wire `__main__.py`: parse args → build `BenchConfig` → call `run_benchmark` → call `format_table` → print to stdout; validate `--repeats >= 1` (exit 1) and `--timeout > 0` (exit 1)
- [ ] T020 [US1] Smoke-test end-to-end: run `python -m benchmarks` and confirm the table prints, all 100 cells are populated, no `ERR`/`TIMEOUT` tokens appear, and first column header reads `4`

**Checkpoint**: US1 is fully functional. `python -m benchmarks` prints the 20×5 table with all cells optimal.

---

## Phase 4: User Story 2 — Reproducible results (Priority: P2)

**Goal**: Two consecutive benchmark runs on the same machine produce cell times that
agree within 50%, demonstrating none of the reported times are catastrophically unstable.

**Independent Test**: Run `python -m benchmarks` twice and compare the two tables
cell-by-cell; assert no ratio exceeds 2.0 (i.e., neither run is more than 2× slower
than the other).

### Implementation for User Story 2

- [ ] T021 [US2] [P] Add `--repeats 3` support end-to-end: verify the runner reports the minimum over 3 timed runs per cell (the implementation skeleton already supports this via `config.repeats`; this task validates it with a real run and adjusts if needed)
- [ ] T022 [US2] Manually run `python -m benchmarks` twice in succession; capture both output tables; spot-check that the 5 largest cells agree within 50%

**Checkpoint**: Reproducibility criterion met for US2.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Optional chart output (FR-007), pyproject.toml exclusion from CI discovery,
ruff/mypy pass, and final documentation.

- [ ] T023 [P] Implement `save_chart(matrix: BenchMatrix, path: Path) -> None` in `benchmarks/table.py`: soft-import `matplotlib`; generate heatmap (imshow of elapsed grid, NaN for ERR/TIMEOUT) and line-chart (one line per worker count, x = subproblem count); save to `path`; print graceful warning to stderr if `matplotlib` is not installed
- [ ] T024 [P] Wire `--save-chart PATH` in `__main__.py` to call `save_chart` after printing the table
- [ ] T025 [P] Add `testpaths` exclusion in `pyproject.toml` to prevent pytest from discovering `benchmarks/` in CI runs (add or update `[tool.pytest.ini_options] testpaths = ["tests"]` if not already set)
- [ ] T026 [P] Run `ruff check benchmarks/ tests/unit/test_bench_*.py` and `mypy --strict benchmarks/` and fix all violations
- [ ] T027 Run full test suite `pytest tests/` and confirm all tests (including the new unit tests for generator and table) pass

**Checkpoint**: All tests green, linting clean, `benchmarks/` excluded from CI discovery, optional chart wired.

---

## Dependencies & Execution Order

```
Phase 1 (T001–T005)
  └─> Phase 2 (T006–T010)
        └─> Phase 3 US1 tests (T011–T013) — write & confirm failing
              └─> Phase 3 US1 implementation (T014–T020)
                    └─> Phase 4 US2 (T021–T022) — can start after T020
                    └─> Phase 5 polish (T023–T027) — can start after T020
```

### Parallel opportunities within Phase 3

Once the data model (Phase 2) is done, T011 and T012 can be written in parallel
(different test files). T014 (generator) and T016 (table formatter) have no
dependency on each other and can be implemented in parallel once their respective
tests are written.

### MVP scope

**User Story 1 only (T001–T020)**: delivers the complete 20×5 timing table and
all generator + formatter unit tests. UAS2 (reproducibility) and Phase 5 (polish)
are independent increments that can follow.

---

## Task Summary

| Phase | Tasks | Stories | Count |
|-------|-------|---------|-------|
| Phase 1: Setup | T001–T005 | — | 5 |
| Phase 2: Foundational | T006–T010 | — | 5 |
| Phase 3: User Story 1 (MVP) | T011–T020 | US1 | 10 |
| Phase 4: User Story 2 | T021–T022 | US2 | 2 |
| Phase 5: Polish | T023–T027 | — | 5 |
| **Total** | | | **27** |

Parallel opportunities: T003/T004/T005 (Phase 1), T011/T012 (Phase 3 tests),
T014/T016 (Phase 3 implementation), T021/T023/T024/T025/T026 (Phase 4/5).
