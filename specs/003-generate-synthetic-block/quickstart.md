# Quickstart: Synthetic Block-Angular LP Generator

**Branch**: `003-generate-synthetic-block`

---

## What This Does

`tests/synthetic.py` provides two things:

1. **`generate_problem(seed, ...)`** — generates a random, guaranteed-feasible
   block-angular LP and returns both the dwsolver `Problem` and the HiGHS reference
   objective.

2. **`SYNTHETIC_CASES`** — a table of 12 pre-chosen seeds driving
   `tests/unit/test_synthetic.py`'s parametrized cross-validation suite.

---

## Prerequisites

```bash
pip install -e ".[dev]"   # installs numpy (added to dev deps by this feature)
```

---

## Run the Cross-Validation Suite

```bash
pytest tests/unit/test_synthetic.py -v
```

Expected output:
```
tests/unit/test_synthetic.py::TestSC002Synthetic::test_cross_validate[seed=1-2blk-5var-1mc] PASSED
tests/unit/test_synthetic.py::TestSC002Synthetic::test_cross_validate[seed=2-2blk-8var-2mc] PASSED
...
tests/unit/test_synthetic.py::TestSC002Synthetic::test_cross_validate[seed=12-6blk-15var-3mc] PASSED
12 passed in Xs
```

---

## Generate a Single Fixture (CLI)

```bash
# Generate a 3-block LP with seed 42 and inspect it
python tests/synthetic.py --seed 42 --output /tmp/synth_42.json

# Output:
# Written: /tmp/synth_42.json  (3 blocks, 10 vars/block, 6 local cstr/block, 2 master cstr)
# HiGHS reference objective: -3.1415...
```

---

## Use the Generator Programmatically

```python
from tests.synthetic import generate_problem
from dwsolver.solver import solve

# Generate with defaults (3 blocks, 10 vars/block, 5 local cstr, 2 master cstr)
gp = generate_problem(seed=42)
print(f"Reference objective: {gp.reference_objective:.6f}")

# Solve with dwsolver
result = solve(gp.problem)
print(f"DW objective:        {result.objective:.6f}")

from tests.synthetic import CROSS_VALIDATION_ABS_TOL
assert abs(result.objective - gp.reference_objective) < CROSS_VALIDATION_ABS_TOL
print("Match confirmed ✓")
```

---

## Custom Structural Parameters

```python
gp = generate_problem(
    seed=99,
    num_blocks=4,
    vars_per_block=8,
    local_constraints=6,
    master_constraints=3,
)
```

All parameters are optional; defaults are:
- `num_blocks=3`
- `vars_per_block=10`
- `local_constraints=5`
- `master_constraints=2`

---

## How Feasibility Is Guaranteed

The generator sets the known feasible point `x* = 0.5` for all variables, then
builds constraints _around_ it:

- `<=` constraints: `rhs = a @ x* + slack`  where `slack ∈ [0.1, 0.5]`
- `>=` constraints: `rhs = a @ x* - slack`  where `slack ∈ [0.1, 0.5]`
- `=`  constraints: `rhs = a @ x*`          (x* satisfies exactly)

This means `x* = 0.5` is always strictly feasible for inequality constraints and
feasible for equalities, with no trial-and-error.

---

## Inspecting the Generated JSON

```bash
python tests/synthetic.py --seed 1 --output /tmp/s1.json
python -c "
import json
d = json.load(open('/tmp/s1.json'))
print('Blocks:', len(d['blocks']))
for b in d['blocks']:
    print(f\"  {b['block_id']}: {len(b['variable_names'])} vars, \"
          f\"{len(b['constraints']['matrix'])} cstr, \"
          f\"{len(b['linking_columns']['rows'])} linking entries\")
print('Master constraints:', len(d['master']['constraint_names']))
"
```
