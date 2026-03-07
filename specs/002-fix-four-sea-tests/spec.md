# Feature Spec: Replace four_sea Placeholder Test Fixture

**Branch**: `002-fix-four-sea-tests`  
**Date**: 2026-03-04  
**Status**: Planning

---

## Background

During a previous session (spec 001, BDD scaffolding), `tests/fixtures/ref_four_sea.json`
was created as a placeholder to unblock CI. It contains a single dummy block with
no real LP data:

```json
{
  "metadata": { "status": "placeholder — full LP encoding required before regression use" },
  "master": { "constraint_names": ["sector_capacity_placeholder"], "rhs": [1.0], ... },
  "blocks": [{ "block_id": "block_0_placeholder", ... }]
}
```

The test infrastructure loads this fixture but the solver cannot produce a meaningful
result against it. The `ref_four_sea.expected.json` already records the correct known
optimal: `{"objective": 12.0}`.

The primary software is now implemented. This feature replaces the placeholder with
a complete, correct LP encoding, enabling end-to-end regression against the
Bertsimas–Stock–Patterson air-traffic-management reference problem.

---

## Problem Statement

The **four_sea** example is the canonical multi-block Dantzig-Wolfe test case from
the original C reference implementation at `alotau/dwsolver`. It models 8 aircraft
(AC0..AC7, indexed as AC1_0..AC8_7) flying from Las Vegas (LAS) to Seattle (SEA)
through 9 intermediate ATC sectors. Each aircraft must obey sector transit-time
constraints (Sector_Time) and monotone-time constraints (Temporality). A shared
arrival-rate capacity at SEA couples all aircraft and drives the decomposition.

**Known optimal objective: 12.0** (total delay, minutes or slots)

The reference C solver stores this as five CPLEX LP files:

| File | Contents |
|---|---|
| `master.cplex` | 2 Arrival_Rate coupling constraints (`SEA,13` and `SEA,14`) + full master objective |
| `subprob_1.cplex` | Block 1 — aircraft AC8_7, AC7_6 |
| `subprob_2.cplex` | Block 2 — aircraft AC6_5, AC5_4 |
| `subprob_3.cplex` | Block 3 — aircraft AC4_3, AC3_2 |
| `subprob_4.cplex` | Block 4 — aircraft AC2_1, AC1_0 |

---

## Requirements

### Functional

**FR-001** `tests/fixtures/ref_four_sea.json` MUST be replaced with a complete, valid
JSON encoding of the four_sea LP problem conforming to the `dwsolver` schema version 1.0.

**FR-002** The fixture MUST have exactly 4 blocks, one per aircraft pair, matching
the decomposition in the reference C solver's `subprob_1..4.cplex` files.

**FR-003** The master section MUST encode exactly 2 `Arrival_Rate(SEA,j)` coupling
constraints — `Arrival_Rate(SEA,13)` and `Arrival_Rate(SEA,14)` — both with RHS = 7
and sense `<=`. The master MUST NOT include placeholder constraints.

**FR-004** Each block's `constraints` section MUST include all Temporality (`>=`)
and Sector_Time (`<=`) constraints from the corresponding CPLEX subproblem file.

**FR-005** Each block's `linking_columns` MUST correctly encode the D_i matrix:
the sparse mapping from block variables (SEA time-step occupancy variables) to
both the master objective and master coupling constraint rows.

**FR-006** Running `dwsolver` against the completed fixture MUST produce objective
value `12.0`, matching `ref_four_sea.expected.json`.

**FR-007** The placeholder metadata fields (`status`, `TODO`) MUST be removed or
updated to reflect the completed encoding.

### Non-Functional

**NFR-001** The fixture JSON MUST be machine-generated, not hand-written, to ensure
correctness and reproducibility. A converter script MUST be committed alongside the
fixture.

**NFR-002** The converter script MUST be deterministic: running it twice against the
same CPLEX sources MUST produce bit-for-bit identical output.

**NFR-003** All existing CI tests MUST pass with the new fixture. No new test failures
are acceptable.

---

## Constraints

- The converter MUST target Python 3.11+ (project standard).
- The converter reads CPLEX LP files from the C reference implementation. It does NOT
  need to be a general-purpose CPLEX parser — it only needs to handle the exact syntax
  produced by the C solver.
- The converter is a developer tool, not a library feature. It lives in
  `specs/002-fix-four-sea-tests/tools/` and is not shipped with the package.
- The `ref_four_sea.expected.json` (`{"objective": 12.0}`) is already correct and
  MUST NOT be changed.

---

## Out of Scope

- Parsing arbitrary CPLEX files beyond the four_sea format.
- Adding a CPLEX import feature to the main `dwsolver` library (that is a separate
  feature, if ever needed).
- Changing any test assertion logic — only the fixture changes.
