# Research: Performance Benchmark — Workers vs. Subproblems

**Phase 0 output for `004-perf-benchmark`**
**Date**: 2026-03-06

---

## Decision 1 — Identical-block generator design

**Decision**: Generate a single template block with fixed seed (`seed=0`) using
`numpy.random.default_rng(0)`. Replicate the block `n_blocks` times (same
coefficients, same objective, same bounds). Add a single master linking
constraint per block variable (row k links `x_k` across all blocks via
identical coefficients), ensuring the master is always binding and the DW
decomposition must generate columns.

**Rationale**: Identical blocks guarantee constant per-block difficulty; timing
differences at a given `n_blocks` arise solely from solver parallelism and not
from varying LP sizes or conditioning. This is an explicit requirement:
"timing differences arise only from parallelism, not from varying problem
difficulty."

**Alternatives considered**:
- Reuse `tests/synthetic.py:generate_problem()` with a fixed seed and varying
  `num_blocks`: rejected because that function varies `master_constraints` and
  `local_constraints` per design, and the rng is threaded through all
  parameters — changing `num_blocks` changes the entire random stream.
- Generate completely independent random blocks per configuration: rejected
  because inter-block coefficient variation would confound the timing signal.

**Guarantees**:
- The slack-from-known-point construction used in `tests/synthetic.py` is
  reused to guarantee feasibility: `x* = 0.5` for all variables; RHS values
  set from `x*` with a positive slack drawn from `Uniform(0.1, 0.5)`.
- A single deterministic seed makes the generator side-effect-free and
  reproducible (SC-005).

---

## Decision 2 — Module placement

**Decision**: New `benchmarks/` directory at the repository root.

```
benchmarks/
├── __init__.py        # empty, makes directory a Python package
├── __main__.py        # python -m benchmarks entry point
├── generator.py       # scalable identical-block LP generator
├── runner.py          # timing loop + result matrix assembly
└── table.py           # 2-D table formatter + optional chart
```

Tests live in `tests/unit/test_bench_generator.py` and
`tests/unit/test_bench_table.py`.

**Rationale**: Isolates benchmark code from the production library
(`src/dwsolver/`) and from test fixtures (`tests/`). The benchmark is neither
a library feature nor a test — it is a measurement tool. A top-level
`benchmarks/` directory is the standard Python convention for this category.

The `tests/synthetic.py` module is a permanent test asset and must not be
imported by production code (per its own docstring). The new `benchmarks/`
module similarly must not be imported by `src/dwsolver/`.

**Alternatives considered**:
- `tests/bench/`: rejected because it would be discovered and executed by
  `pytest` by default, causing the expensive timing loop to run on every CI
  push. A separate top-level directory makes pytest exclusion easy.
- A new `dwsolver benchmark` CLI sub-command: rejected because the spec
  explicitly states "the benchmark targets the library API, not the CLI, to
  avoid process-launch overhead contaminating timing results."

---

## Decision 3 — Entry point mechanism

**Decision**: `python -m benchmarks` (via `benchmarks/__main__.py`) with
`argparse` for optional flags.

**Default invocation** (no required arguments, FR-006):
```bash
python -m benchmarks
```

**Optional flags**:
```bash
python -m benchmarks --repeats 3
python -m benchmarks --save-chart results.png
python -m benchmarks --timeout 60
```

**Rationale**: `python -m benchmarks` is the idiomatic single-command
invocation for a Python package without requiring installation. `argparse` is
stdlib, adds zero new dependencies, and is sufficient for the 3–4 flags needed.

**Alternatives considered**:
- `click` (already a project dependency): possible but adds import overhead
  that would contaminate the first-cell timing measurement. Rejected.
- A plain script `benchmarks/run.py` called directly: works but `python -m`
  is cleaner and plays better with `PYTHONPATH` management.

---

## Decision 4 — Wall-clock timing method

**Decision**: `time.perf_counter()` bracketing only the `solve()` call.

```python
t0 = time.perf_counter()
result = solve(problem, workers=w)
elapsed = time.perf_counter() - t0
```

Problem generation (constructing the `Problem` object) is excluded from
timing, consistent with the spec assumption: "Wall-clock time is measured as
elapsed time from when the solve call is initiated to when it returns; problem
generation time is excluded."

**Rationale**: `time.perf_counter()` is the highest-resolution monotonic clock
available in Python stdlib on all platforms; it is unaffected by system clock
adjustments.

**Alternatives considered**:
- `time.process_time()`: measures CPU time, not wall-clock time. Rejected
  because wall-clock time is the user-visible quantity.
- `timeit.timeit()`: adds a setup/loop abstraction that makes it harder to
  capture the `Result` object for status checking. Rejected.

---

## Decision 5 — Per-cell timeout and error handling

**Decision**: Wrap each `solve()` call in a `concurrent.futures.ThreadPoolExecutor`
with `submit(...).result(timeout=T)` where the default `T = 120` seconds. A
`TimeoutError` → cell value `"TIMEOUT"`; any other exception → `"ERR"`.

**Rationale**: The spec and requirements checklist both flag timeout handling as
important. A 2-minute per-cell ceiling is generous relative to SC-004 (full
run in 10 minutes ÷ 100 cells = 6 seconds/cell average) yet guards against
runaway solvers. Using a `ThreadPoolExecutor` with a single worker thread is the
simplest way to enforce a timeout without `subprocess` overhead.

**Alternative**: `signal.alarm` (UNIX only) — rejected for portability reasons.
`multiprocessing` with a timeout — rejected due to serialization overhead and
complexity.

---

## Decision 6 — Table rendering

**Decision**: Manual string formatting using `str.ljust()` / `str.rjust()` and
`textwrap`; no third-party table library.

**Rationale**: Adding `tabulate` (or `rich`) solely for this benchmark output
would be a dependency cost not justified by the complexity. The table is a
fixed-size 20×5 grid; manual column-width calculation is straightforward and
keeps the dependency list clean. The spec says "readable at a glance" (SC-003),
not "beautifully styled."

**Alternatives considered**:
- `tabulate`: easy to use but an extra dependency not already in `pyproject.toml`.
- `rich.table`: visually polished but a heavy dependency. Rejected.

**Format**:
```
Workers →        4         8        12        16        20
Subproblems
  1           0.12s     0.09s     0.08s     0.08s     0.09s
  2           0.23s     0.17s     0.12s     0.11s     0.12s
  ...
 20          12.44s     6.81s     4.92s     3.98s     4.10s
```
Status appended in parentheses only on non-optimal cells, e.g. `ERR` or `TIMEOUT`.

---

## Decision 7 — Optional visualisation (FR-007, SHOULD)

**Decision**: Use `matplotlib` (not already a project dependency) when
`--save-chart` is requested. Import is deferred to the chart-generation code
path with a clear `ImportError` message if `matplotlib` is not installed.

**Artifacts**:
- Heatmap: `seaborn.heatmap` or raw `matplotlib.imshow` — times as a colour
  gradient, subproblems on y-axis, workers on x-axis.
- Line chart: one line per worker count, x-axis = subproblem count.

**Rationale**: `matplotlib` is the de facto Python visualisation library;
`seaborn` is optional since `imshow` alone satisfies the requirement. Deferring
the import means `--save-chart` is a soft dependency: users who don't need
charts need not install it.

**Alternatives considered**:
- Always require `matplotlib`: rejected to avoid polluting the core dev
  install for users who only want the timing table.
- Output CSV and let users plot externally: too much friction.

---

## Decision 8 — Repeat count / averaging (FR-008)

**Decision**: `--repeats N` (default `1`). When `N > 1`, run `solve()` N times
for that cell and report the **minimum** time (not the mean).

**Rationale**: The minimum is the standard statistical estimator for benchmark
timing because it approximates "OS scheduling noise removed." The mean
conflates noise with signal. The spec allows either average or minimum; minimum
is more defensible for a performance benchmark.

**Alternatives considered**:
- Report mean: common but inflates results when the first run is slower due to
  JIT/caching effects (HiGHS internal setup).
- Report median: reasonable but requires N ≥ 3 to be meaningful. Users are
  unlikely to run 3+ repeats for a 100-cell benchmark given the time cost.
