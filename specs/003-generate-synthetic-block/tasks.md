# Tasks: Synthetic Block-Angular LP Generator & Cross-Validation Suite

**Input**: Design documents from `specs/003-generate-synthetic-block/`
**Branch**: `003-generate-synthetic-block`
**Date**: 2026-03-05

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different concerns, no dependency on sibling task)
- **[Story]**: User story from spec.md (US1 = P1 generator+validate, US2 = P2 12-seed suite)
- Exact file paths in every description

---

## Phase 1: Setup

**Purpose**: Add the one missing dependency so subsequent tasks can import numpy.

- [ ] T001 Add `"numpy>=1.24"` to `[project.optional-dependencies] dev` in `pyproject.toml`

**Checkpoint**: `pip install -e ".[dev]"` installs numpy; `python -c "import numpy"` exits 0.

---

## Phase 2: Foundational — Test Skeleton (RED State)

**Purpose**: Write the failing test that drives all implementation. Per constitution
Principle III, tests are written before the module they test — `tests/synthetic.py`
does not exist yet, so collection will raise `ImportError`.

- [ ] T002 Create `tests/unit/test_synthetic.py` with a single US1 skeleton test that imports `generate_problem` from `tests.synthetic` and calls `dwsolver.solver.solve()` — file must be importable by pytest but fail at collection with `ModuleNotFoundError` until T003 is complete

**Checkpoint**: `pytest tests/unit/test_synthetic.py` reports `ERROR ... ModuleNotFoundError`
(not "0 items collected" — the file exists and pytest tried to collect it).

---

## Phase 3: User Story 1 — Generator + Single Cross-Validation (Priority: P1) 🎯 MVP

**Goal**: A developer calls `generate_problem(seed=42)`, gets a `GeneratedProblem` whose
`reference_objective` came from HiGHS, then passes `gp.problem` to `dwsolver.solve()` and
confirms the two objectives agree within `abs_tol=1e-4`.

**Independent Test**: `pytest tests/unit/test_synthetic.py -k test_cross_validate_single -v`
→ 1 item collected, PASS.

### Implementation for User Story 1

- [ ] T003 [US1] Scaffold `tests/synthetic.py` — module docstring, imports (`dataclasses`, `numpy`, `highspy`, `dwsolver.models`), `SyntheticCase` dataclass, `GeneratedProblem` dataclass as specified in `specs/003-generate-synthetic-block/data-model.md`
- [ ] T004 [P] [US1] Implement `solve_monolithic_highs(problem: Problem) -> float` in `tests/synthetic.py` — column-by-column + row-by-row HiGHS build using `_col_offsets` helper, sense map `{"<=": (-inf, rhs), ">=": (rhs, +inf), "=": (rhs, rhs)}`, `h.run()`, assert `kOptimal`, return `h.getInfoValue("primal_objective_value")[1]`
- [ ] T005 [US1] Implement `generate_problem(seed, num_blocks=3, vars_per_block=10, local_constraints=5, master_constraints=2) -> GeneratedProblem` in `tests/synthetic.py` — full body: RNG init, variable names (`b{i}_x{j}`), objective coefficients, bounds (0,1), local constraint matrix with slack-from-`x*=0.5`, linking column COO with 2 link vars per block, master rows with slack, assemble `Problem.model_validate()`, call `solve_monolithic_highs`, return `GeneratedProblem`
- [ ] T006 [US1] Add `if __name__ == "__main__"` CLI block to `tests/synthetic.py` — `argparse` with `--seed` (required int) and `--output` (optional path), call `generate_problem`, optionally write `gp.problem.model_dump_json()` to `--output`, print reference objective to stdout (satisfies SC-006: `python tests/synthetic.py --seed 42 --output /tmp/out.json`)
- [ ] T007 [US1] Update `tests/unit/test_synthetic.py` — complete the skeleton so `test_cross_validate_single` generates `seed=42`, solves via `dwsolver.solver.solve(gp.problem)`, asserts status `OPTIMAL`, and asserts `abs(dw_obj - gp.reference_objective) < 1e-4`

**Checkpoint**: `pytest tests/unit/test_synthetic.py -k test_cross_validate_single -v` → 1 collected,
PASS. `python tests/synthetic.py --seed 42` prints a finite float and exits 0.

---

## Phase 4: User Story 2 — Parametrized Cross-Validation Suite (Priority: P2)

**Goal**: 12 structurally diverse seeds are exercised in a single parametrized class.
CI output shows human-readable IDs. All 12 pass in under 60 seconds.

**Independent Test**: `pytest tests/unit/test_synthetic.py -v` → exactly 12 items collected,
all PASS, IDs match `seed=N-Mblk-Vvar-Cmc` pattern.

### Implementation for User Story 2

- [ ] T008 [P] [US2] Add `SYNTHETIC_CASES: list[SyntheticCase]` module-level constant to `tests/synthetic.py` with all 12 entries from the seed table in `specs/003-generate-synthetic-block/research.md` (seeds 1–12, blocks 2–6, vars/blk 5–20, labels verbatim from the table)
- [ ] T009 [US2] Replace the single-seed test in `tests/unit/test_synthetic.py` with `TestSC002Synthetic` — `@pytest.mark.parametrize("case", SYNTHETIC_CASES, ids=[c.label for c in SYNTHETIC_CASES])` wrapping a single `test_cross_validate` method that generates and solves each case
- [ ] T010 [US2] Verify: `pytest tests/unit/test_synthetic.py -v` collects exactly 12 items, all PASS; confirm test IDs contain the `seed=N-Mblk-Vvar-Cmc` shape (SC-001, SC-002, SC-003)

**Checkpoint**: 12/12 pass. IDs visible in output. `SC-004` (globally unique variable names) is
implicitly verified by `Problem.model_validate()` inside `generate_problem`.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Satisfy mypy strict, ruff clean, and confirm no regressions.

- [ ] T011 [P] Run `mypy --strict tests/synthetic.py` and fix any type errors — add `npt.NDArray[np.float64]` annotations for numpy arrays; ensure `SyntheticCase` and `GeneratedProblem` have complete type hints; no `type: ignore` comments unless unavoidable
- [ ] T012 [P] Run `ruff check --fix tests/synthetic.py tests/unit/test_synthetic.py` then `ruff format tests/synthetic.py tests/unit/test_synthetic.py` — zero lint errors, consistent formatting
- [ ] T013 Run full `pytest tests/ -v` and confirm all tests pass (existing 121 + 12 new = 133 total); no regressions in `tests/unit/` or `tests/bdd/`

---

## Dependencies

```
T001 → T002 → T003 → T004 (parallel with T005) → T005 → T006 → T007
                                                               ↓
                                                  T008 (parallel) → T009 → T010
                                                               ↓
                                               T011 (parallel) + T012 (parallel) → T013
```

**Story completion order**:
- US1 (P1): T001 → T002 → T003 → T004+T005 → T006 → T007 — independently testable
- US2 (P2): US1 complete → T008 → T009 → T010 — independently testable
- Polish: US2 complete → T011+T012 → T013

**Parallel opportunities per story**:
- T004 and T005 can be implemented in the same pass (different functions, no mutual dependency)
- T008 (`SYNTHETIC_CASES` constant) can start while T007 (US1 test) is being verified
- T011 (mypy) and T012 (ruff) are fully independent

---

## Implementation Strategy

**Suggested MVP scope**: Phase 1 + Phase 2 + Phase 3 (T001–T007) — US1 only.
This delivers a working generator, verified reference objective, and one passing cross-validation
test. US2 (T008–T010) is additive parametrization with no new algorithmic complexity.

**Key invariants to preserve**:
- All random values in `generate_problem` from a single `numpy.random.default_rng(seed)` instance
  threaded top-to-bottom (determinism guarantee from Decision 1)
- No changes to `src/dwsolver/` — pure test infrastructure
- `numpy` in `[dev]` only, never in `[project.dependencies]`
- Variable names globally unique: `b{block_id}_x{var_index}` — enforced by schema validator
