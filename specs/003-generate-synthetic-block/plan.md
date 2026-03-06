# Implementation Plan: Synthetic Block-Angular LP Generator & Cross-Validation Suite

**Branch**: `003-generate-synthetic-block` | **Date**: 2026-03-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-generate-synthetic-block/spec.md`

## Summary

Add `tests/synthetic.py` — a module that generates random, guaranteed-feasible
block-angular LPs from a seed, solves both the monolithic form (HiGHS) and the
D-W decomposed form (dwsolver), and asserts their objectives match. Wire a
12-seed parametrized pytest suite in `tests/unit/test_synthetic.py` with
human-readable test IDs. Add `numpy>=1.24` to dev dependencies.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `numpy>=1.24` (new), `highspy` (existing dev dep), `dwsolver` (this project)
**Storage**: N/A — generator runs entirely in memory; optional `--output` flag writes JSON
**Testing**: pytest, `@pytest.mark.parametrize` over 12 `SyntheticCase` entries
**Target Platform**: developer workstation + CI (ubuntu-latest)
**Project Type**: dev test tooling — `tests/synthetic.py` is not part of the shipped library
**Performance Goals**: Full 12-case suite completes in <60s on CI (expected <10s locally)
**Constraints**: `numpy` must NOT appear in `[project.dependencies]` (only `[dev]`); generator
must NOT be imported by any `src/dwsolver/` module; no new runtime dependencies
**Scale/Scope**: Largest case: 6 blocks × 15 vars/block = 90 monolithic variables, 51 rows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I (Library-First) | ✅ Pass | Generator lives in `tests/`, not `src/dwsolver/`. No library API changes. |
| II (CLI Interface) | ✅ Pass | No changes to CLI layer. Generator's own CLI (`python tests/synthetic.py`) is a dev tool, not a shipped command. |
| III (Test-First) | ✅ Pass | Tests written before generator implementation. Baseline: `test_synthetic.py` collects 0 items (module missing) → write tests → make them pass. |
| IV (Parallel by Design) | ✅ Pass | No changes to subproblem dispatch. Test suite itself may exercise parallel dispatch (default workers). |
| V (Numerical Correctness) | ✅ Pass | HiGHS reference objective is computed from the same `Problem` JSON encoding — self-consistency check. `abs_tol=1e-4` is appropriate for LP optimization. |
| Dev Workflow Step 0 | ✅ Pass | Branch `003-generate-synthetic-block` in use. `git merge origin/main` before every push. |

**Post-Design Re-check**: No violations identified. `numpy` is a well-understood dependency
with stable semantics. The generator produces `Problem` objects that go through the existing
Pydantic validators, so all existing schema invariants are exercised automatically.

## Project Structure

### Documentation (this feature)

```text
specs/003-generate-synthetic-block/
├── plan.md          ← this file
├── spec.md
├── research.md      ✅ complete
├── data-model.md    ✅ complete
├── quickstart.md    ✅ complete
└── tasks.md         ← Phase 2 output (not yet created)
```

### Source Code Changes

```text
pyproject.toml                          ← ADD numpy>=1.24 to [dev]
tests/
├── synthetic.py                        ← NEW: generator module + CLI
└── unit/
    └── test_synthetic.py               ← NEW: 12-seed parametrized cross-validation suite
```

No changes to `src/dwsolver/` or `tests/bdd/` or `tests/unit/test_solver.py`.

**Structure Decision**: Single new module at `tests/synthetic.py` alongside existing
`tests/unit/`, `tests/bdd/`, `tests/fixtures/`. The generator is a peer of the test
subdirectories, keeping it importable as `from tests.synthetic import ...`.

## Generator Algorithm

### `generate_problem(seed, num_blocks, vars_per_block, local_constraints, master_constraints)`

```
rng ← numpy.random.default_rng(seed)

For each block i = 1..num_blocks:
  variable_names[i] ← ["b{i}_x{j}" for j in 0..vars_per_block]
  objective[i]      ← rng.uniform(-2, 2, vars_per_block)
  bounds[i]         ← all {"lower": 0.0, "upper": 1.0}

  x_star = [0.5] * vars_per_block

  For each local row r = 0..local_constraints:
    a[r]   ← rng.uniform(-1, 1, vars_per_block)
    b[r]    = a[r] @ x_star
    sense   = cycle through ["<=", ">=", "<=", ...]  (1/3 ">=", 2/3 "<=")
    slack  ← rng.uniform(0.1, 0.5)
    rhs[r]  = b[r] + slack if "<=" else b[r] - slack

# Linking structure (same linking vars selected for each block)
link_count = min(2, vars_per_block)
linking_var_indices ← rng.integers(0, vars_per_block, size=(num_blocks, link_count))

For each master row m = 0..master_constraints:
  master_total = 0
  For each block i:
    link_coeffs[i][m] ← rng.uniform(-1, 1, link_count)
    master_total += link_coeffs[i][m] @ x_star[linking_var_indices[i]]
  sense_m = "=" if m == master_constraints-1 and master_constraints >= 3 else "<="
  slack_m ← rng.uniform(0.1, 0.5)
  master_rhs[m] = master_total + slack_m  (or exact for "=")

Assemble Block objects → Problem.model_validate() → assertion on validity
solve_monolithic_highs(problem) → reference_objective
return GeneratedProblem(problem, reference_objective)
```

### `solve_monolithic_highs(problem)`

```
h = Highs(); h.silent()
col_offsets ← cumulative sum of [len(b.variable_names) for b in problem.blocks]

For each block i:
  For j in 0..n_vars:
    h.addCol(block.objective[j], 0.0, 1.0, 0, [], [])

For each block i, local row r:
  col_indices = [col_offsets[i] + j for j, coeff in enumerate(matrix[r]) if coeff != 0]
  values      = [coeff for coeff in matrix[r] if coeff != 0]
  apply sense/rhs → h.addRow(lb_row, ub_row, len(col_indices), col_indices, values)

For each master row m:
  Collect all (global_col, value) from each block's linking_columns COO where rows[k]==m
  h.addRow(lb_row, ub_row, ..., col_indices, values)

h.run()
assert h.getModelStatus() == HighsModelStatus.kOptimal, "Generator produced infeasible LP"
_, ref_obj = h.getInfoValue("primal_objective_value")
return ref_obj
```

## Key Decisions Summary

| # | Decision |
|---|----------|
| 1 | `numpy.random.default_rng(seed)` for reproducibility |
| 2 | Feasibility by slack-from-`x*=0.5` construction (no rejection sampling) |
| 3 | HiGHS monolithic reference built row-by-row via `addCol`/`addRow` (matches existing pattern) |
| 4 | Generator at `tests/synthetic.py` (permanent test asset, not `specs/` tool) |
| 5 | 12 hard-coded seeds covering blocks∈{2..6}, vars∈{5..20}, mc∈{1..5} |
| 6 | Contract note: no change to `src/dwsolver/` API — this is pure test infrastructure |
