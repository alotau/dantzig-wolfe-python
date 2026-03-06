# Feature Specification: Synthetic Block-Angular LP Generator & Cross-Validation Suite

**Feature Branch**: `003-generate-synthetic-block`
**Created**: 2026-03-05
**Status**: Draft
**Input**: User description: "Generate synthetic block-angular LPs, solve with both HiGHS directly and dwsolver, verify objective values match"

## Overview

The existing regression suite tests dwsolver against 6 hand-crafted reference problems.
This feature adds a **synthetic generator** that:

1. Produces random but fully feasible, bounded block-angular LPs from a seed
2. Solves the **monolithic form** of each LP with HiGHS directly (ground truth)
3. Encodes the same LP in dwsolver JSON format and solves it via Dantzig-Wolfe
4. Asserts both objectives match within tolerance

This catches DW decomposition bugs that the hand-crafted fixtures might not exercise
(e.g., degenerate linking structure, asymmetric block sizes, many master constraints)
and gives users concrete worked examples of the JSON schema.

---

## User Scenarios & Testing

### User Story 1 — Generator + Single Cross-Validation (Priority: P1)

A developer can call a generator function with a seed and get back a fully described
block-angular LP together with the HiGHS-verified optimal objective. They then call
`dwsolver.solve()` on the JSON encoding and confirm the two objectives agree.

**Why this priority**: Core capability — everything else is parametrization on top of it.

**Independent Test**: Call `generate_problem(seed=42)` → returns `(Problem, float)` where
the float is the HiGHS reference objective. Call `solve(problem)` and assert they match.

**Acceptance Scenarios**:

1. **Given** a seed integer, **When** `generate_problem(seed)` is called, **Then** it returns a
   `Problem` instance that passes `Problem.model_validate()` without error and a finite
   reference objective from HiGHS.
2. **Given** the same seed called twice, **When** the results are compared, **Then** the
   `Problem` and reference objective are bit-for-bit identical (determinism guaranteed).
3. **Given** a generated `Problem`, **When** `dwsolver.solve()` is called, **Then** the returned
   objective is within `abs_tol=1e-4` of the HiGHS reference.

---

### User Story 2 — Parametrized Cross-Validation Suite (Priority: P2)

A parametrized pytest suite runs the full cross-validation across 12 structurally
diverse seeds. Test IDs show the seed and structural shape so CI output is immediately
readable.

**Why this priority**: The generator (US1) must exist first; the suite is parametrization over it.

**Independent Test**: `pytest tests/unit/test_synthetic.py -v` collects 12 items, all pass.

**Acceptance Scenarios**:

1. **Given** a table of 12 `SyntheticCase` entries, **When** `pytest tests/unit/test_synthetic.py` runs,
   **Then** each item is displayed with a human-readable ID
   (e.g. `test_cross_validate[seed=42-2blk-5var-4mc]`) and passes.
2. **Given** the suite runs on a cold CI machine, **When** all 12 tests complete,
   **Then** total elapsed time is under 60 seconds.
3. **Given** a structural diversity requirement, **When** inspecting the 12 seeds,
   **Then** they collectively cover: 2–6 blocks, 5–20 vars/block, 3–15 local
   constraints/block, 1–5 master constraints, and at least one equality master constraint.

---

### Edge Cases

- What if HiGHS declares the generated problem infeasible? — the generator MUST guarantee
  feasibility by construction; an infeasible HiGHS result is a generator bug and MUST
  raise `AssertionError` with a clear message, not silently pass.
- What if dwsolver returns `ITERATION_LIMIT`? — the test MUST fail with the actual status;
  the generator SHOULD produce problems small enough that DW converges quickly.
- What if two seeds produce structurally identical problems? — seeds are chosen explicitly
  to guarantee diversity; the `SyntheticCase` table documents each seed's shape.
- What if `numpy` is not installed? — `numpy` MUST be added to `[dev]` dependencies in
  `pyproject.toml`; the generator MUST NOT be importable by the main `dwsolver` library.

---

## Requirements

### Functional Requirements

- **FR-001**: `generate_problem(seed, num_blocks, vars_per_block, local_constraints,
  master_constraints)` MUST accept an integer seed and optional structural parameters
  with documented defaults.
- **FR-002**: The generator MUST guarantee feasibility and boundedness by construction
  using the slack-from-known-point approach described in *Feasibility Design* below.
- **FR-003**: The generator MUST return a `Problem` that passes `Problem.model_validate()`
  without modification and a `float` reference objective from HiGHS.
- **FR-004**: The monolithic HiGHS form MUST be reconstructed solely from the data in
  the `Problem` — this verifies that the JSON encoding is self-consistent.
- **FR-005**: The dwsolver and HiGHS objectives MUST agree within `abs_tol=1e-4`.
- **FR-006**: The parametrized suite MUST include exactly 12 seeds with documented
  structural shapes covering the diversity described in US2 scenario 3.
- **FR-007**: The generator module MUST be importable as
  `from tests.synthetic import generate_problem` and runnable as a CLI:
  `python tests/synthetic.py --seed 42 --output /tmp/out.json`
  which writes the dwsolver JSON and prints the reference objective to stdout.
- **FR-008**: `numpy` MUST be added to `[project.optional-dependencies] dev` in
  `pyproject.toml`. The generator MUST NOT be imported by any module under `src/dwsolver/`.

### Key Entities

- **`SyntheticCase`**: dataclass holding `seed: int`, `num_blocks: int`,
  `vars_per_block: int`, `local_constraints: int`, `master_constraints: int`,
  `label: str` (used as pytest ID, e.g. `"seed=42-2blk-5var-4mc"`).
- **`GeneratedProblem`**: return type of `generate_problem` holding
  `problem: Problem` and `reference_objective: float`.

### Feasibility Design (non-negotiable)

The generator MUST guarantee feasibility using the following construction:

1. All variables have bounds `[0, 1]`. Set `x* = 0.5` for all (midpoint → strictly
   interior to the box).
2. For each local constraint row: draw random coefficients `a` from `Uniform(-1, 1)`,
   compute `b = a @ x_block`, then:
   - `<=` constraints: `rhs = b + |slack|` (slack > 0)
   - `>=` constraints: `rhs = b - |slack|` (slack < 0)
   - `=`  constraints: `rhs = b` (x* satisfies exactly)
   where `slack ~ Uniform(0.1, 0.5)` to ensure strict feasibility.
3. For master (linking) constraints: for each block select `k` linking variables
   (`k = min(2, vars_per_block)`), draw random coefficients, compute the linking row
   value at `x*` across all blocks, apply the same slack approach.
4. Objective coefficients are drawn from `Uniform(-2, 2)`.
5. All random values come from `numpy.random.default_rng(seed)`.

### Monolithic Reconstruction

To build the HiGHS reference LP from a `Problem`:

1. Concatenate all blocks' `variable_names` in block order → global variable list
   (globally unique by schema guarantee).
2. Build a block-diagonal local constraint matrix from each block's dense
   `constraints.matrix`.
3. Append master rows: map each `linking_columns` COO `(row, col, val)` to the correct
   global column offset and assemble the master constraint rows.
4. Solve with `highspy`; extract `model.getInfoValue("primal_objective_value")[1]`.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: `pytest tests/unit/test_synthetic.py -v` collects exactly 12 items, all pass.
- **SC-002**: Each test ID contains seed and structural shape
  (e.g., `test_cross_validate[seed=7-3blk-8var-2mc]`).
- **SC-003**: The 12 seeds span: blocks ∈ {2,3,4,5,6}, vars/block ∈ {5,8,10,15,20},
  master constraints ∈ {1,2,3,4,5}.
- **SC-004**: Every generated `Problem` has globally unique `variable_names` across all
  blocks (enforced by the schema validator, confirmed by the test).
- **SC-005**: Full `pytest tests/` suite passes in under 90 seconds on CI.
- **SC-006**: `python tests/synthetic.py --seed 42 --output /tmp/out.json` exits 0,
  writes a valid dwsolver JSON, and prints the HiGHS reference objective to stdout.
