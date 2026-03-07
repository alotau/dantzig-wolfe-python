# Quickstart: Performance Benchmark

**Feature**: 004-perf-benchmark  
**Date**: 2026-03-06

---

## Prerequisites

The project must be installed in editable mode:

```bash
git checkout 004-perf-benchmark
pip install -e ".[dev]"
```

No additional dependencies are needed for the timing table. For the optional
chart (`--save-chart`), install `matplotlib`:

```bash
pip install matplotlib
```

---

## Running the benchmark

**Default run** (100 cells, 1 repeat each, 120 s timeout):

```bash
python -m benchmarks
```

**With 3 repeats per cell** (minimum time reported):

```bash
python -m benchmarks --repeats 3
```

**Save a heatmap + line-chart**:

```bash
python -m benchmarks --save-chart results.png
```

**Custom timeout** (30 s per cell):

```bash
python -m benchmarks --timeout 30
```

---

## Expected output

Progress lines appear on stderr as each cell completes:

```
[001/100] n_blocks= 1, workers= 4 → 0.12s  optimal
[002/100] n_blocks= 1, workers= 8 → 0.09s  optimal
...
```

After all cells, the result table is printed to stdout:

```
Workers →        4         8        12        16        20
Subproblems
  1           0.12s     0.09s     0.08s     0.08s     0.09s
  2           0.23s     0.17s     0.12s     0.11s     0.12s
  ...
 20          12.44s     6.81s     4.92s     3.98s     4.10s
```

---

## Running the tests

Generator and table-formatter unit tests:

```bash
pytest tests/unit/test_bench_generator.py tests/unit/test_bench_table.py -v
```

All unit tests (including the benchmark tests):

```bash
pytest tests/unit/ -v
```

> **Note**: The full `pytest` run (all 100 cells) is **not** triggered by
> `pytest` automatically. The timing loop lives in `benchmarks/`, which is
> excluded from pytest discovery by default.

---

## CI note

The benchmark is excluded from the CI pipeline (`pytest` discovery does not
recurse into `benchmarks/`). Run it manually on a developer machine when
evaluating solver performance changes.
