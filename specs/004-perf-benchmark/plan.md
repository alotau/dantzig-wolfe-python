# Implementation Plan: Performance Benchmark — Workers vs. Subproblems

**Branch**: `004-perf-benchmark` | **Date**: 2026-03-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-perf-benchmark/spec.md`

## Summary

Implement a standalone benchmark tool that generates a scalable, identical-block
block-angular LP (1–20 subproblems), solves it across five worker counts
{4, 8, 12, 16, 20}, and prints a 20×5 timing table to stdout. The benchmark
lives in `benchmarks/` at the repository root, targets the library API
(`dwsolver.solve`), and is invoked via `python -m benchmarks`.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: `dwsolver` (library under test), `highspy`, `pydantic >= 2`,
`numpy >= 1.24` (generator), `argparse` (stdlib); `matplotlib` optional (chart output, FR-007)  
**Storage**: N/A — no persistent state; results printed to stdout  
**Testing**: pytest; unit tests in `tests/unit/`  
**Target Platform**: Developer laptop / Linux CI (macOS + Linux)  
**Project Type**: standalone benchmark tool (measurement script)  
**Performance Goals**: Full 100-cell run under 10 minutes on a developer laptop (SC-004);
per-cell wall-clock timeout 120 s  
**Constraints**: No new required production dependencies; `benchmarks/` excluded from
pytest CI discovery  
**Scale/Scope**: 100 cells (20 subproblem sizes × 5 worker counts); 4 new benchmark
modules; 2 new unit-test files

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Library-First** | ✅ PASS | Benchmark calls `dwsolver.solve()` directly; no CLI subprocess. Generator lives in `benchmarks/`, not `src/dwsolver/`. |
| **II. CLI Interface** | ✅ PASS | `python -m benchmarks` single-command entry point satisfies FR-006. This is a measurement tool, not a solver feature requiring a `dwsolver` sub-command. |
| **III. Test-First (NON-NEGOTIABLE)** | ✅ PASS (with commitment) | Tests for `generator.py` and `table.py` are written and confirmed failing before implementation begins. The timing loop itself is not a pytest test, but all components are fully unit-tested. |
| **IV. Massively Parallel by Design** | ✅ PASS | Benchmark exercises `ThreadPoolExecutor` parallelism at varying worker counts. No new sequential hot paths introduced. |
| **V. Numerical Correctness** | ✅ PASS | Generator uses slack-from-known-point construction. Reference scaling validated in unit tests. Non-optimal cells are reported, not silently ignored. |
| **Branch discipline** | ✅ PASS | All work on `004-perf-benchmark`; merge `origin/main` before every push. |
| **CI gates** | ✅ PASS | New unit tests pass ruff + mypy strict + pytest before merge. `benchmarks/` excluded from pytest discovery. |

**Post-Phase-1 re-check**: No new violations. `benchmarks/` imports only `dwsolver`
(library) and stdlib; `matplotlib` is a soft optional import. Constitution satisfied.

---

## Project Structure

### Documentation (this feature)

```text
specs/004-perf-benchmark/
├── plan.md                      # This file
├── research.md                  # Phase 0 output ✅
├── data-model.md                # Phase 1 output ✅
├── quickstart.md                # Phase 1 output ✅
├── contracts/
│   └── cli_invocation.md        # Phase 1 output ✅
└── tasks.md                     # Phase 2 output (speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
benchmarks/                        # NEW — benchmark tool (not under src/)
├── __init__.py                    # empty
├── __main__.py                    # python -m benchmarks entry point; argparse
├── generator.py                   # identical-block LP generator (FR-001, FR-002)
├── runner.py                      # timing loop; assembles BenchMatrix (FR-003)
└── table.py                       # 2-D table formatter + optional chart (FR-004, FR-007)

tests/unit/
├── test_bench_generator.py        # NEW — generator unit tests (TDD: fail first)
└── test_bench_table.py            # NEW — table formatter unit tests (TDD: fail first)

# Existing files (unchanged):
src/dwsolver/
├── __init__.py
├── cli.py
├── models.py
├── solver.py
└── subproblem.py
```

**Structure Decision**: Top-level `benchmarks/` package (standalone measurement tool).
Selected because: (a) `tests/` is for automated pytest suites, not manually-run timing
scripts; (b) `src/dwsolver/` is the production library; (c) `benchmarks/` is the
conventional Python location for performance measurement scripts run manually, not by CI.

---

## Phase 0: Research Summary

All design decisions resolved. See [research.md](research.md) for full rationale.

| # | Decision | Choice |
|---|----------|--------|
| D1 | Generator design | Identical-block replication with fixed seed=0; slack-from-known-point |
| D2 | Module placement | `benchmarks/` at repository root |
| D3 | Entry point | `python -m benchmarks` with `argparse` |
| D4 | Timing method | `time.perf_counter()` around `solve()` call only |
| D5 | Timeout / error handling | `ThreadPoolExecutor.submit().result(timeout=T)` |
| D6 | Table rendering | Manual string formatting; no third-party table library |
| D7 | Visualisation | `matplotlib` soft-imported; graceful fallback if absent |
| D8 | Repeat averaging | `--repeats N`; report minimum over repeats |

---

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](data-model.md). Key entities:

- `BenchConfig` — CLI options with defaults
- `CellResult` — single (n_blocks, workers) outcome: elapsed time + status
- `BenchMatrix` — 20×5 matrix of `CellResult`; invariant: no empty cells
- `CellError` — enum: `TIMEOUT | ERROR`
- `IdenticalBlockProblem` — `dwsolver.Problem` with n identical blocks

### Contracts

- [contracts/cli_invocation.md](contracts/cli_invocation.md) — `python -m benchmarks`
  flags, stdout table format, stderr progress format, exit codes, chart output spec.

### Quickstart

- [quickstart.md](quickstart.md) — install, run, expected output, test commands.

---

## Implementation Breakdown

### Module: `benchmarks/generator.py`

**Responsibility**: Produce a `dwsolver.Problem` with exactly `n` identical blocks. Deterministic (fixed seed=0), guaranteed-feasible, reference optimum scales linearly with `n`.

**Public interface**:
```python
def make_bench_problem(n_blocks: int) -> Problem:
    """Generate a scalable identical-block bench LP with n_blocks blocks.

    All blocks share the same coefficients (seed=0). One master linking
    constraint per block variable couples the blocks.

    Args:
        n_blocks: Number of blocks; must be in [1, 20].

    Returns:
        Validated Problem instance ready for dwsolver.solve().

    Raises:
        ValueError: If n_blocks < 1 or n_blocks > 20.
    """
```

**Internal design**:
1. `numpy.random.default_rng(0)` — fixed seed.
2. Template block: 10 variables, 5 local `<=` constraints, bounds `[0, 1]`.
3. RHS from slack-from-known-point (`x* = 0.5`): `b_row = dot(A_row, x*) + slack`, `slack ~ Uniform(0.1, 0.5)`.
4. Objective coefficients from `Uniform(-2, 2)`.
5. Replicate the template block `n_blocks` times (`Block` is a frozen Pydantic model — same instance is safe).
6. Master linking constraints: 10 constraints (one per block variable j); constraint j: `sum_i x_{i,j} <= n_blocks * 0.6`.
7. Validate via `Problem.model_validate()`.

**Reference optimum property**: `objective(n) ≈ n × objective(1)` (used in unit tests).

---

### Module: `benchmarks/runner.py`

**Responsibility**: Execute the 20×5 timing loop, enforce per-cell timeout, collect `CellResult` instances.

**Public interface**:
```python
def run_benchmark(config: BenchConfig) -> BenchMatrix:
    """Run the full timing grid and return the populated result matrix."""
```

**Internal design**:
1. Pre-generate all 20 `Problem` instances before any timing begins.
2. Outer loop: `n_blocks` in 1–20. Inner loop: `workers` in `[4, 8, 12, 16, 20]`.
3. Per cell: `ThreadPoolExecutor(max_workers=1)`, `submit(solve, prob, workers=w)`, `future.result(timeout=config.timeout)`.
4. `TimeoutError` → `CellResult(status=CellError.TIMEOUT)`.
5. Other `Exception` → `CellResult(status=CellError.ERROR)`, log to stderr.
6. When `repeats > 1`: repeat steps 3–5, keep minimum `elapsed`.
7. Print progress to stderr after each cell.

---

### Module: `benchmarks/table.py`

**Responsibility**: Format `BenchMatrix` as a readable text table; optionally write heatmap + line-chart.

**Public interfaces**:
```python
def format_table(matrix: BenchMatrix) -> str:
    """Render the 20x5 matrix as a formatted text table string."""

def save_chart(matrix: BenchMatrix, path: Path) -> None:
    """Save heatmap and line-chart to path. Requires matplotlib."""
```

Table format: header row (`Workers →` + 5 right-aligned worker-count columns, 9 chars each), `Subproblems` section header, body rows with 3-char right-aligned subproblem count + `{t:.2f}s` cells. ERR/TIMEOUT cells shown as text tokens in the same column width.

---

### Module: `benchmarks/__main__.py`

**Responsibility**: Parse CLI args, invoke `run_benchmark`, print table, optionally save chart.

```python
def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m benchmarks", ...)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--save-chart", type=Path, default=None)
    args = parser.parse_args()
    # validate; build BenchConfig; run_benchmark; print; save_chart
```

Exit codes: 0 (success, even with ERR/TIMEOUT cells), 1 (bad args), 2 (fatal pre-run error).

---

### Tests: `tests/unit/test_bench_generator.py`

*Written before `generator.py`; must fail on first run (Principle III).*

| Test | Assertion |
|------|-----------|
| `test_make_bench_problem_returns_valid_problem` | `make_bench_problem(3)` returns `Problem` without exception |
| `test_make_bench_problem_block_count[1..20]` | `len(problem.blocks) == n` for n in 1..20 (parametrize) |
| `test_make_bench_problem_identical_blocks` | all blocks in result of n=5 have identical `objective` list |
| `test_make_bench_problem_feasibility_n1` | `solve(make_bench_problem(1)).status == SolveStatus.OPTIMAL` |
| `test_make_bench_problem_feasibility_n5` | `solve(make_bench_problem(5)).status == SolveStatus.OPTIMAL` |
| `test_make_bench_problem_feasibility_n20` | `solve(make_bench_problem(20)).status == SolveStatus.OPTIMAL` |
| `test_make_bench_problem_reference_scaling` | `abs(obj(n=2) - 2*obj(n=1)) < 1e-4` |
| `test_make_bench_problem_deterministic` | two calls with same n return equal `Problem` dicts |
| `test_make_bench_problem_invalid_n_zero` | `make_bench_problem(0)` raises `ValueError` |
| `test_make_bench_problem_invalid_n_21` | `make_bench_problem(21)` raises `ValueError` |

---

### Tests: `tests/unit/test_bench_table.py`

*Written before `table.py`; must fail on first run.*

| Test | Assertion |
|------|-----------|
| `test_format_table_header_contains_worker_counts` | header row contains "4", "8", "12", "16", "20" |
| `test_format_table_has_20_data_rows` | 20 non-header, non-section-header rows in output |
| `test_format_table_optimal_cell_matches_pattern` | all optimal cells match `r'\d+\.\d{2}s'` |
| `test_format_table_err_cell_displayed` | matrix with one ERR cell shows `"ERR"` in output |
| `test_format_table_timeout_cell_displayed` | matrix with one TIMEOUT cell shows `"TIMEOUT"` in output |
| `test_format_table_all_optimal_no_err_tokens` | all-optimal matrix has no "ERR" or "TIMEOUT" token |
| `test_format_table_returns_string` | return type is `str` |

---

## Complexity Tracking

> No constitution violations requiring justification.

---

## Open Questions / Deferral Notes

- **FR-007 (SHOULD — chart output)**: `save_chart()` is in scope; deferred to a later
  task slice if time-constrained. The `--save-chart` flag must be wired with a graceful
  fallback if `matplotlib` is absent.
- **SC-004 (10-minute target)**: Per-cell timeout (120 s default) bounds pathological
  cases. `--timeout` flag allows machine-specific tuning.
- **SC-005 (50% reproducibility)**: Deterministic generator + pre-generation step
  removes warm-up effects. `--repeats 3` with minimum reporting resolves residual
  OS scheduling noise if it appears.
