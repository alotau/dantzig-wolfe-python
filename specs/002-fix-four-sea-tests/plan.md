# Implementation Plan: Replace four_sea Placeholder Test Fixture

**Branch**: `002-fix-four-sea-tests` | **Date**: 2026-03-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-fix-four-sea-tests/spec.md`

## Summary

Replace `tests/fixtures/ref_four_sea.json` (currently a placeholder) with a complete,
machine-generated JSON encoding of the four_sea Dantzig-Wolfe LP by writing a
standalone Python converter script (`cplex_to_json.py`) that fetches the five reference
CPLEX files from `alotau/dwsolver`, parses them, and emits a fixture that causes the
solver to return `objective: 12.0`.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: stdlib only — `urllib.request`, `re`, `json`, `argparse`  
**Storage**: N/A (reads remote HTTPS; writes one JSON file)  
**Testing**: pytest (existing suite); no new tests for the converter itself  
**Target Platform**: developer workstation (macOS/Linux); not shipped  
**Project Type**: dev tool (one-off script, lives in `specs/` not `src/`)  
**Performance Goals**: completes in <60s on a standard connection  
**Constraints**: no third-party packages; deterministic output (bit-for-bit identical runs)  
**Scale/Scope**: 5 input files; ~1,760 constraints × 4 blocks; ~440 vars × 4 blocks

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I (Library-First) | ✅ Pass | Converter is a dev tool in `specs/`, not a library module |
| II (CLI Interface) | ✅ Pass | No changes to the CLI layer |
| III (TDD) | ✅ Pass | Existing `ref_four_sea` regression test (spec 001) is the failing test being fulfilled; T002 documents baseline failure before implementation |
| IV (Parallel by Design) | ✅ Pass | No changes to subproblem dispatch |
| V (Numerical Correctness) | ✅ Pass | T014 verifies `objective: 12.0` against `ref_four_sea.expected.json` |
| Dev Workflow Step 0 (Branch) | ✅ Pass | `002-fix-four-sea-tests` branch in use |

## Project Structure

### Documentation (this feature)

```text
specs/002-fix-four-sea-tests/
├── plan.md        ← this file
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── tools/
    └── cplex_to_json.py   ← NEW: converter script (dev tool, not shipped)
```

### Affected repository files

```text
tests/
└── fixtures/
    └── ref_four_sea.json  ← MODIFIED: placeholder replaced with complete LP encoding
```

No changes to `src/dwsolver/` or `tests/bdd/` or `tests/unit/`.

## Converter Algorithm

The converter is a single Python script. Execution order:

1. **Fetch** `master.cplex` and `subprob_1..4.cplex` via HTTPS from `alotau/dwsolver`

2. **Parse `master.cplex`**:
   - `Minimize` section → `master_obj: dict[str, float]` mapping variable name to coefficient (−2 for SEA vars, +1 for LAS vars, across all 8 aircraft)
   - `Subject To` section → 13 `Arrival_Rate(SEA,j)` rows:
     - `constraint_names: list[str]`
     - `rhs: list[float]` — all 7.0
     - `senses: list[str]` — all `"L"`
     - `master_rows: list[dict[str, float]]` — per-constraint `{var_name: coeff}` sparse map (used for linking_columns)

3. **For each `subprob_N.cplex`** (blocks 1–4):
   - `Bounds` section → `variable_names: list[str]` (each `0 <= w(...) <= 1` line declares one variable); sort alphabetically for determinism
   - Build `var_index: dict[str, int]` from sorted list
   - `Subject To` section → parse each constraint line:
     - Name: `Sector_Time(...)` or `Temporality(...)`
     - Pattern: `VAR_A - VAR_B <= 0` or `VAR_A - VAR_B >= 0`
     - All RHS = 0.0; senses are `"L"` (Sector_Time) or `"G"` (Temporality)
     - Build sparse matrix COO: `(row_idx, col_idx, value)` per non-zero
   - Objective: for each var in `variable_names`, look up in `master_obj` dict (0.0 if absent)
   - `linking_columns`: for each of the 13 `master_rows`, filter entries to vars present in this block's `var_index` → emit `(master_row_idx, var_index[var_name], coeff)` COO triplets

4. **Assemble** top-level `Problem` dict matching `dwsolver` schema and write to `--output` path with `json.dumps(sort_keys=True, indent=2)`

## Key Decisions (from research.md)

| # | Decision |
|---|----------|
| 1 | Standalone Python script; no CPLEX SDK or scipy |
| 2 | HTTPS fetch from `raw.githubusercontent.com/alotau/dwsolver/master/examples/four_sea/` |
| 3 | Drop master `+160` constant; `objective: 12.0` is the variable-part optimum |
| 4 | Ignore `GENERALS` section; all bounds are `[0.0, 1.0]` (LP relaxation) |
