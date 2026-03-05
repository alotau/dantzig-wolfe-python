# Research: four_sea CPLEX → JSON Conversion

**Branch**: `002-fix-four-sea-tests`  
**Phase**: 0 — Outline & Research  
**Sources**: `alotau/dwsolver` master branch, CPLEX LP files fetched 2026-03-04

---

## Decision 1: Converter Architecture

**Decision**: Write a single, standalone Python script that reads the 5 CPLEX LP files
from the reference repository (either fetched locally or via HTTP), parses them
programmatically, and emits `ref_four_sea.json`.

**Rationale**: The CPLEX files are large (~2000+ constraints per subproblem) and
machine-generated. Hand-transcription would be error-prone and unreproducible.
A script produces deterministic, auditable output.

**Alternatives considered**:
- Use the `cplex` Python SDK — rejected; adds a commercial dependency.
- Use `scipy` LP format readers — rejected; CPLEX format is non-standard.
- Write a general `.lp` parser — rejected; CPLEX syntax is complex and only
  the four_sea-specific patterns need to be handled.

---

## Decision 2: CPLEX File Sourcing

**Decision**: Fetch CPLEX files from the public GitHub raw URL at parse time, with
an option to read from a local cache directory.

**Rationale**: Avoids committing multi-MB CPLEX files to the repository. The files
are stable (fixed reference examples, not under active development).

**Repository base URL**:
```
https://raw.githubusercontent.com/alotau/dwsolver/master/examples/four_sea/
```

**Files**:
- `master.cplex`
- `subprob_1.cplex`
- `subprob_2.cplex`
- `subprob_3.cplex`
- `subprob_4.cplex`

**Alternatives considered**:
- Commit CPLEX files to `specs/002-fix-four-sea-tests/cplex/` — acceptable but
  adds 5–10 MB to the repo; rejected for now, can always add later.

---

## Decision 3: Objective Handling

**Decision**: Encode the objective entirely within block-level `objective` coefficient
vectors. The master-level constant term (+160) is dropped from the encoded fixture
because it is an additive constant that does not affect the optimal solution or
verification (the solver minimizes the variable-dependent terms only).

**Rationale**: The `dwsolver` JSON schema has no `constant` field in the master or
blocks. The known optimal objective `12.0` refers to the _total delay_ (variable
part), not 160 + 12. The `ref_four_sea.expected.json` already uses `12.0`.

**Master objective pattern per aircraft AC_k**:
- `+1` coefficient on every `w(AC_k, LAS, t)` for t = 20..39 (20 terms per aircraft)
- `-2` coefficient on every `w(AC_k, SEA, t)` for t = 199..218 (20 terms per aircraft)

Each block owns 2 aircraft, so the block objective has 80 non-zero terms (2 × 40).
All other variables (intermediate sectors) have 0 objective coefficient.

---

## Decision 4: Variable Relaxation (Integer → Continuous)

**Decision**: Declare all variables with bounds `lower=0, upper=1` and **no integer
declarations**. The `dwsolver` backend uses an LP relaxation for the DW pricing;
the GENERALS section of the CPLEX files is ignored.

**Rationale**: The DW decomposition operates on the LP relaxation. Integer programs
are not supported by the `dwsolver` JSON schema. The known optimum (12.0) is
achieved at the LP relaxation vertex.

---

## Finding: Master Problem Structure

**13 Arrival_Rate coupling constraints**, all `<= 7`.

Each constraint `Arrival_Rate(SEA, j)` for j = 1..13 has the form:
```
sum_{k=1}^{8}  [ -w(AC_k, SEA, t_start_j) + w(AC_k, SEA, t_end_j) ]  <= 7
```

The windows `(t_start_j, t_end_j)` slide across the SEA arrival horizon t = 199..218.
Exact window boundaries are read deterministically from the CPLEX file by the
converter — they do not need to be enumerated here.

**Linking variable dimension**:
- Per aircraft: 20 SEA variables (t=199..218), each with coefficient −1 or +1 in
  each of the 13 constraints.
- Per block (2 aircraft): up to 2 × 20 × 2 = **80 COO entries** in `linking_columns`
  per master constraint (40 with coeff −1, 40 with coeff +1).

---

## Finding: Subproblem Structure

**Variable schema**: `w(aircraft_id, sector_name, time_step)` ∈ [0, 1]

**Sector chain** (same for all 8 aircraft):
```
LAS → ZLA16 → ZOA46 → ZOA45 → ZLC43 → ZSE10 → ZSE05 → ZSE34 → ZSE02 → ZSESEA → SEA
```
Sectors: **11 per aircraft**

**Constraint types**:
1. **Temporality** (monotone non-decreasing occupancy):  
   `w(AC, sector, t) - w(AC, sector, t-1) >= 0`  
   sense `>=`, RHS `0`
   
2. **Sector_Time** (minimum transit time between consecutive sectors):  
   `w(AC, next_sector, t+offset) - w(AC, current_sector, t) <= 0`  
   sense `<=`, RHS `0`

**Constraint count**: ~1,760 per subproblem (confirmed by structure; exact count is
parsed by the converter).

---

## Finding: Block-to-Master Linking

**Linking variables** (variables appearing in master coupling constraints):
- `w(AC_k, SEA, t)` for t = 199..218 → appear in `Arrival_Rate(SEA, j)` constraints

**Non-linking variables** (subproblem-local only):
- `w(AC_k, LAS, t)` — appear in the objective but NOT in any `Arrival_Rate` constraint
- All intermediate sector variables (ZLA16, ZOA46, ..., ZSESEA) — purely local

**D_i matrix structure** (COO encoding for block i):
- Rows: master constraint index 0..12 (for each Arrival_Rate(SEA,j))
- Cols: index of `w(AC_k, SEA, t_start)` or `w(AC_k, SEA, t_end)` in the block's
  `variable_names` list
- Values: −1 for t_start variables, +1 for t_end variables

---

## Finding: Block Assignments

| Block index | `block_id` | Aircraft |
|---|---|---|
| 0 | `block_1` | AC8_7, AC7_6 |
| 1 | `block_2` | AC6_5, AC5_4 |
| 2 | `block_3` | AC4_3, AC3_2 |
| 3 | `block_4` | AC2_1, AC1_0 |

---

## Resolved Clarifications

All items are fully resolved. No outstanding NEEDS CLARIFICATION items remain.
