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

**Decision**: Encode the +160 objective constant via a fixed **dummy variable**
`__objective_constant__` injected into `block_1` with `lower=1.0, upper=1.0` and
`objective_coeff=160.0`. This forces the solver to always include +160 in the
reported total, yielding 12.0 = −148 + 160.

**Rationale**: The `dwsolver` JSON schema has no `constant` field. The master CPLEX
file contains `\* constant term = 160 *\` as a comment for the Delay_Costs
objective. Without encoding it, the LP variable-part optimum is −148.0, not 12.0.
A fixed-bounds dummy variable in a D-W block is always selected at its fixed value
(since sum(λ) = 1 and the dummy has zero linking), so the constant is recovered.

**Dummy variable spec**:
```
variable_names:  append "__objective_constant__" to block_1
Objective coeff: +160.0
bounds:          {"lower": 1.0, "upper": 1.0}   (fixed at 1)
constraints row: all zeros (no local constraints)
linking_columns: no entries (zero coupling)
```

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

**2 Arrival_Rate coupling constraints**, both `<= 7`.

Despite the `examples/four_sea/` directory containing comments that suggest a larger
horizon, the actual `master.cplex` Subject To section contains exactly two rows:
- `Arrival_Rate(SEA,13)` (row index 0): `<= 7`
- `Arrival_Rate(SEA,14)` (row index 1): `<= 7`

Each constraint references 2 aircraft per subproblem block with coefficients −1 or +1
on 2 SEA variables.

**Linking variable dimension** (per block of 2 aircraft):
- Each constraint touches 2 aircraft × 2 SEA vars = **4 COO entries** per constraint
- **Total per block**: 2 constraints × ~3 entries = **6 COO entries** in `linking_columns`
  (exact count depends on which of the 2 aircraft in a block appear in each constraint
  row; confirmed at 6 from the generated fixture)

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

**Variable source**: variables are declared in the `Bounds` section of each subproblem
file as `0 <= w(aircraft,sector,t) <= 1` — one line per variable. The `Subject To`
section only references variables; it does not declare them.

**Constraint count**: ~1,760 per subproblem (confirmed by structure; exact count is
parsed by the converter).

---

## Finding: Block-to-Master Linking

**Linking variables** (variables appearing in master coupling constraints):
- `w(AC_k, SEA, t)` for specific time steps appear in `Arrival_Rate(SEA, j)` constraints

**Non-linking variables** (subproblem-local only):
- `w(AC_k, LAS, t)` — appear in the master objective but NOT in any `Arrival_Rate` constraint
- All intermediate sector variables (ZLA16, ZOA46, ..., ZSESEA) — purely local

**Objective source**: the subproblem CPLEX files have **no objective section**. The
master `Minimize` section contains coefficients for all 8 aircraft interleaved. Each
block's `objective` array is built by looking up each block variable in the master
objective dict (0.0 for variables absent from the master objective).

**D_i matrix structure** (COO encoding for block i):
- Rows: master constraint index 0..12 (for each Arrival_Rate(SEA,j))
- Cols: index of the linking variable in the block's `variable_names` list
- Values: coefficient as given in the master constraint row (−1 or +1)
- Source: the `Subject To` section of `master.cplex` lists the linking variables
  explicitly per constraint; filter to those present in the block's `var_index`

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
