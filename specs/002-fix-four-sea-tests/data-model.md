# Data Model: four_sea LP Encoding

**Branch**: `002-fix-four-sea-tests`  
**Phase**: 1 — Design  
**Input**: research.md

---

## Overview

The four_sea problem is encoded in the `dwsolver` JSON schema version 1.0.
This document specifies the exact entities, their fields, and the values
expected in `tests/fixtures/ref_four_sea.json`.

---

## Top-Level Structure

```
Problem
├── schema_version: "1.0"
├── metadata: { name, description }
├── master: Master
└── blocks: [Block × 4]
```

---

## Entity: Problem

| Field | Type | Value |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `metadata.name` | string | `"ref_four_sea"` |
| `metadata.description` | string | See spec FR-007 — remove placeholder status |

---

## Entity: Master

Encodes the 13 `Arrival_Rate(SEA, j)` coupling constraints.

| Field | Type | Value |
|---|---|---|
| `constraint_names` | list[str] | `["Arrival_Rate(SEA,1)", ..., "Arrival_Rate(SEA,13)"]` |
| `rhs` | list[float] | `[7.0] × 13` |
| `senses` | list[str] | `["<="] × 13` |

**Cardinality**: 13 constraints

**Constraint semantics**:  
For constraint j with window (t_start_j, t_end_j):
```
Σ_{k=1..8} [ w(AC_k, SEA, t_end_j) − w(AC_k, SEA, t_start_j) ] ≤ 7
```
Counts how many aircraft arrive at SEA within the time window. Limited to ≤ 7.

---

## Entity: Block

Four blocks, one per aircraft pair. Each block follows the same structure.

### Common fields

| Field | Value |
|---|---|
| `block_id` | `"block_1"` through `"block_4"` |
| `variable_names` | Sorted list of `w(AC_k, sector, t)` strings for both aircraft |
| `objective` | Per-variable coefficients (see Objective Coefficients below) |
| `bounds` | `[{"lower": 0.0, "upper": 1.0}]` for every variable |
| `constraints` | Temporality + Sector_Time constraints |
| `linking_columns` | Sparse COO matrix mapping block SEA vars → master constraint rows |

### Block contents summary

| Block | `block_id` | Aircraft | Approx. variables | Approx. constraints |
|---|---|---|---|---|
| 0 | `block_1` | AC8_7, AC7_6 | ~440 | ~1,760 |
| 1 | `block_2` | AC6_5, AC5_4 | ~440 | ~1,760 |
| 2 | `block_3` | AC4_3, AC3_2 | ~440 | ~1,760 |
| 3 | `block_4` | AC2_1, AC1_0 | ~440 | ~1,760 |

*Exact counts determined at parse time by the converter.*

---

## Objective Coefficients

Distributed across blocks. Per aircraft AC_k in a block:

| Variable | Coefficient |
|---|---|
| `w(AC_k, SEA, t)` for t = 199..218 | −2.0 |
| `w(AC_k, LAS, t)` for t = 20..39 | +1.0 |
| All other sector variables | 0.0 |

**Constant term**: The CPLEX master objective includes a constant of +160. This is
dropped in the JSON encoding (schema has no constant field). The variable-dependent
minimum is 12.0, which matches `ref_four_sea.expected.json`.

---

## Entity: BlockConstraints

Local constraints for each block (aircraft-local, no coupling).

### Temporality constraints

One per `(aircraft, sector, t)` except the first time step for each sector.

| Field | Value |
|---|---|
| matrix row | `[..., w_coeff_t = +1, w_coeff_{t-1} = −1, ...]` |
| rhs | 0.0 |
| sense | `">="` |

**Pattern**: `w(AC, sector, t) − w(AC, sector, t−1) ≥ 0`

### Sector_Time constraints

One per `(aircraft, sector, t)` for each sector transition.

| Field | Value |
|---|---|
| matrix row | `[..., w_next_coeff = +1, w_curr_coeff = −1, ...]` |
| rhs | 0.0 |
| sense | `"<="` |

**Pattern**: `w(AC, next_sector, t+offset) − w(AC, sector, t) ≤ 0`

---

## Entity: LinkingColumns

Sparse COO encoding of D_i for each block i.

- `rows[k]`: master constraint row index (0..12 for Arrival_Rate(SEA,1)..13)
- `cols[k]`: index of the block variable `w(AC, SEA, t_start_j)` or `w(AC, SEA, t_end_j)` in `variable_names`
- `values[k]`: −1.0 for t_start variables, +1.0 for t_end variables

**Cardinality per block**: 2 aircraft × 20 SEA vars/aircraft × potentially 2 appearances per var (once as t_start, once as t_end across different constraints) × 13 constraints. The exact count is derived from the CPLEX file by the converter.

---

## Variable Naming Convention

All variables follow the pattern:  
```
w(aircraft_id, sector_name, time_step)
```

Examples:
- `w(AC8_7,SEA,199)` — aircraft AC8_7 at sector SEA at time slot 199
- `w(AC1_0,LAS,20)` — aircraft AC1_0 at departure sector LAS at time slot 20
- `w(AC7_6,ZLA16,35)` — aircraft AC7_6 at intermediate sector ZLA16 at time 35

**Aircraft ordering within a block**: AC_higher index first, then AC_lower index
(e.g., block_1 = AC8_7 first, then AC7_6), matching subproblem file order.

---

## State Transitions

Variables represent monotone CDF occupancy:

```
w(AC, sector, t) = 0   →  aircraft has NOT yet entered sector by time t
w(AC, sector, t) = 1   →  aircraft HAS entered sector by time t

Once w transitions to 1, it stays 1 (enforced by Temporality constraints)
The first time t where w(AC, sector, t) = 1 is the aircraft's arrival time at that sector
```

---

## Validation Rules (from models.py)

- `len(objective) == len(variable_names)`  
- `len(bounds) == len(variable_names)`  
- `len(matrix) == len(rhs) == len(senses)`  
- `len(rows) == len(cols) == len(values)` (linking_columns)  
- `schema_version` must have major version 1  
- At least 1 block
