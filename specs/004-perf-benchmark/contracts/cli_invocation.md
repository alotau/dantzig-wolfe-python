# CLI Contract: Benchmark Entry Point

**Contract type**: Command-line invocation schema  
**Scope**: `benchmarks/__main__.py` — the benchmark tool entry point

---

## Invocation

```
python -m benchmarks [OPTIONS]
```

No positional arguments. All options are optional (FR-006).

---

## Options

| Flag                    | Type    | Default | Description                                        |
|-------------------------|---------|---------|----------------------------------------------------|
| `--repeats N`           | `int`   | `1`     | Timed runs per cell; minimum time is reported      |
| `--timeout SECONDS`     | `float` | `120.0` | Per-cell wall-clock timeout in seconds             |
| `--save-chart PATH`     | `str`   | (none)  | Write heatmap + line-chart PNG to this path        |

---

## Exit codes

| Code | Meaning                                                          |
|------|------------------------------------------------------------------|
| `0`  | Run completed; all cells populated (some may be ERR or TIMEOUT) |
| `1`  | Invalid arguments (e.g. `--repeats 0`)                          |
| `2`  | Fatal error before any cell was measured                        |

---

## Stdout

All output is written to **stdout**. The result table is printed after all
100 cells have been measured (or marked ERR/TIMEOUT).

### Table format

```
Workers →        4         8        12        16        20
Subproblems
  1           0.12s     0.09s     0.08s     0.08s     0.09s
  2           0.23s     0.17s     0.12s     0.11s     0.12s
  3           0.35s     0.22s     0.17s     0.14s     0.14s
 ...
 20          12.44s     6.81s     4.92s     3.98s     4.10s
```

Rules:
- Column header row: `"Workers →"` followed by right-aligned worker counts.
- Section header: `"Subproblems"` on its own line.
- Body rows: two-space-padded subproblem count (right-aligned in 3 chars),
  followed by time formatted as `{t:.2f}s` right-aligned in 9-char columns.
- Non-optimal cells: display the error token instead (`ERR` or `TIMEOUT`)
  right-aligned in the same 9-char column.
- Final blank line after the table.

### Progress indicator

While running, each completed cell prints a single progress line to **stderr**:
```
[004/100] n_blocks= 1, workers= 4 → 0.12s  optimal
[005/100] n_blocks= 1, workers= 8 → 0.09s  optimal
...
```

---

## Stderr

Progress and error diagnostics only. Exceptions from individual cells are
logged here and do not abort the benchmark run:
```
[ERR] n_blocks=7, workers=4: <exception message>
[TIMEOUT] n_blocks=15, workers=20: exceeded 120.0s
```

---

## Chart output (--save-chart)

If `--save-chart PATH` is given and `matplotlib` is installed, two subplots
are saved to `PATH`:
1. **Heatmap**: 20 rows × 5 columns; colour encodes wall-clock time; cells
   with ERR/TIMEOUT shown as grey with a cross-hatch pattern.
2. **Line chart**: x-axis = subproblem count (1–20); one line per worker
   count; y-axis = wall-clock time in seconds.

If `matplotlib` is not installed, print to stderr:
```
Warning: matplotlib not installed; --save-chart ignored.
```
and exit with code `0`.
