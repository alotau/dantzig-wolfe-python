# Research: Synthetic Block-Angular LP Generator

**Branch**: `003-generate-synthetic-block`
**Phase**: 0 — Outline & Research
**Date**: 2026-03-05

---

## Decision 1: Random Number Generation

**Decision**: Use `numpy.random.default_rng(seed)` throughout the generator.

**Rationale**: `numpy.random.default_rng` uses Philox-4×64-based PCG, which is
reproducible across platforms and NumPy versions within the same major version.
All coefficient arrays, constraint coefficients, and slack values derive from
a single RNG instance threaded through the generator — guaranteeing that the
same seed always produces bit-for-bit identical output (FR-002 determinism).

**numpy version pin**: `numpy>=1.24` (default_rng stable API introduced 1.17;
1.24 is the oldest version still receiving security patches as of 2026-03).

**Alternatives considered**:
- Python stdlib `random` — rejected; no vectorised array operations, slower for
  large coefficient matrices.
- `scipy.stats` — rejected; unnecessary extra dependency.

---

## Decision 2: Feasibility Construction Method

**Decision**: "Slack from known interior point" — fix `x* = 0.5` for all variables,
evaluate each constraint row at `x*`, then perturb RHS by a random slack drawn
from `Uniform(0.1, 0.5)`.

**Rationale**: This is unconditionally feasible with zero trial-and-error. The
perturbation is large enough that floating-point rounding in HiGHS never causes
spurious infeasibility. Equality constraints (`=`) set `rhs = a @ x*` exactly —
`x*` satisfies them by construction.

**Important**: Boundedness of the LP is guaranteed because all variables have
finite upper bounds (`upper=1.0`) in every generated Problem.

**Alternatives considered**:
- Rejection sampling (generate random LP, check feasibility) — rejected; no
  convergence guarantee, unpredictable runtime.
- Guarantee feasibility by adding artificial slacks — rejected; changes the
  problem structure, making the generated LP less representative.

---

## Decision 3: HiGHS API Usage for Monolithic Reference

**Decision**: Use `highspy`'s column-by-column + row-by-row build API (same
pattern already in `subproblem.py`), not the matrix-level `passLp` API.

**Confirmed API** (from `src/dwsolver/subproblem.py` and `src/dwsolver/solver.py`):

```python
h = Highs()
h.silent()
# Add variable: h.addCol(cost, lb, ub, num_nz, row_indices, row_values)
h.addCol(obj_coeff, 0.0, 1.0, 0, [], [])
# Add constraint row: h.addRow(lb_row, ub_row, num_nz, col_indices, values)
h.addRow(-kHighsInf, rhs, num_nz, col_indices, values)  # <= constraint
h.addRow(rhs, kHighsInf, num_nz, col_indices, values)   # >= constraint
h.addRow(rhs, rhs,       num_nz, col_indices, values)   # == constraint
h.run()
status = h.getModelStatus()          # HighsModelStatus.kOptimal
_, ref_obj = h.getInfoValue("primal_objective_value")
```

The monolithic LP is assembled as:
- **Columns**: all block variables concatenated in block order
- **Rows**: block-diagonal local constraints (each block's `constraints.matrix`),
  then master rows (reconstructed from `linking_columns` COO with global col offsets)

Column offsets per block are computed as a cumulative sum of `len(block.variable_names)`.

**Alternatives considered**:
- `h.passLp(...)` bulk matrix API — rejected; the COO reconstruction is easier to
  verify correct when done row-by-row, matching the pattern already in the codebase.

---

## Decision 4: Generator File Location

**Decision**: `tests/synthetic.py` — a standalone module at the `tests/` root, not
under `tests/unit/` or `tests/bdd/`.

**Rationale**:
- FR-008 forbids it from being imported by `src/dwsolver/` — placing it under
  `tests/` enforces this structurally.
- It is both importable (`from tests.synthetic import generate_problem`) and
  runnable as a CLI (`python tests/synthetic.py ...`).
- Placing it at `tests/synthetic.py` (not `tests/unit/synthetic.py`) separates
  it cleanly from pure unit tests while keeping it within the `tests/` package.

**Alternatives considered**:
- `specs/003-generate-synthetic-block/tools/generator.py` — rejected; the generator
  is a permanent test asset, not a one-off dev tool. It belongs in `tests/`.
- `src/dwsolver/testing.py` — explicitly rejected by FR-008.

---

## Decision 5: SyntheticCase Seed Table

**Decision**: Hard-code 12 cases directly in `tests/synthetic.py` as a module-level
constant `SYNTHETIC_CASES: list[SyntheticCase]`. Seeds are chosen to guarantee
structural diversity across blocks ∈ {2,3,4,5,6}, vars/block ∈ {5,8,10,15,20},
master constraints ∈ {1,2,3,4,5}, with mixed `<=` / `>=` / `=` master constraints.

| # | seed | blocks | vars/blk | local_cstr | master_cstr | label |
|---|------|--------|----------|------------|-------------|-------|
| 1 | 1    | 2      | 5        | 3          | 1           | seed=1-2blk-5var-1mc |
| 2 | 2    | 2      | 8        | 5          | 2           | seed=2-2blk-8var-2mc |
| 3 | 3    | 3      | 5        | 4          | 1           | seed=3-3blk-5var-1mc |
| 4 | 4    | 3      | 10       | 6          | 3           | seed=4-3blk-10var-3mc |
| 5 | 5    | 3      | 15       | 8          | 2           | seed=5-3blk-15var-2mc |
| 6 | 6    | 4      | 5        | 3          | 4           | seed=6-4blk-5var-4mc |
| 7 | 7    | 4      | 8        | 5          | 1           | seed=7-4blk-8var-1mc |
| 8 | 8    | 4      | 10       | 7          | 3           | seed=8-4blk-10var-3mc |
| 9 | 9    | 5      | 8        | 4          | 2           | seed=9-5blk-8var-2mc |
| 10| 10   | 5      | 10       | 5          | 4           | seed=10-5blk-10var-4mc |
| 11| 11   | 5      | 20       | 10         | 5           | seed=11-5blk-20var-5mc |
| 12| 12   | 6      | 15       | 8          | 3           | seed=12-6blk-15var-3mc |

Seeds 1–3 use `<=` master constraints only; seeds 4–8 mix `<=` and `>=`; seeds
9–12 include at least one `=` master constraint — meeting the equality requirement
from US2 scenario 3.

**Rationale for conservative sizes**: The largest case (seed=12: 6 blocks × 15
vars × 8 local cstr + 3 master cstr) produces a monolithic LP of 90 variables and
51 rows. DW should converge in <20 iterations. The full 12-case suite is expected
to complete in <10 seconds locally, well within the 60-second CI budget.

---

## Finding: numpy Not Yet a Dev Dependency

`pyproject.toml` dev extras currently: `pytest`, `pytest-bdd`, `ruff`, `mypy`,
`highspy`. `numpy` is absent.

**Required change**: Add `numpy>=1.24` to `[project.optional-dependencies] dev`
in `pyproject.toml`. This is the only `pyproject.toml` change needed.

`numpy` MUST NOT appear in `[project.dependencies]` — it is not required to
run `dwsolver`, only to run the synthetic generator.

---

## Finding: mypy Strict Mode and numpy

`mypy` in strict mode will require `numpy` stubs. The `numpy>=1.24` package ships
its own `py.typed` marker and inline stubs since numpy 1.20, so no separate
`types-numpy` package is needed. A `[[tool.mypy.overrides]]` entry may still be
needed to suppress the `numpy.random` generic type warnings under strict mode:

```toml
[[tool.mypy.overrides]]
module = ["numpy.*"]
ignore_missing_imports = false  # numpy ships stubs — leave as is
```

In practice, explicit `numpy.*` type annotations (`npt.NDArray[np.float64]`) are
only needed inside `tests/synthetic.py`; the generator's public API uses only
stdlib types (`Problem`, `float`, `list`), so mypy strict is satisfied without
special treatment.

---

## Resolved Clarifications

All items are fully resolved. No NEEDS CLARIFICATION items remain.
