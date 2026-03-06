# Quickstart: Regenerating the four_sea Fixture

**Branch**: `002-fix-four-sea-tests`

---

## What this feature produces

A complete LP encoding of the Bertsimas–Stock–Patterson four_sea air-traffic
problem in `tests/fixtures/ref_four_sea.json`, replacing the previous placeholder.

---

## One-liner: regenerate the fixture

```bash
# From repo root, with the virtual environment active:
python specs/002-fix-four-sea-tests/tools/cplex_to_json.py \
    --output tests/fixtures/ref_four_sea.json
```

This fetches the 5 CPLEX LP files from the reference C solver repository over
HTTPS, parses them, and writes the JSON fixture.

**With a local CPLEX cache** (faster, works offline):

```bash
# Download CPLEX files first
python specs/002-fix-four-sea-tests/tools/cplex_to_json.py \
    --cplex-dir specs/002-fix-four-sea-tests/cplex/ \
    --output tests/fixtures/ref_four_sea.json
```

---

## Verify the result

```bash
# Run the solver against the new fixture
dwsolver tests/fixtures/ref_four_sea.json \
    --output /tmp/four_sea_result.json

cat /tmp/four_sea_result.json
# Expected: {"objective": 12.0, "status": "optimal", ...}

# Run the full test suite
pytest tests/
```

---

## Prerequisites

```bash
# Standard project environment — no extra dependencies needed
# The converter only uses the stdlib (urllib, json, re)
pip install -e .
```

---

## How it works

1. **Fetch** (or read locally) `master.cplex` and `subprob_1..4.cplex`
2. **Parse** the master:
   - Extract the 13 `Arrival_Rate(SEA,j)` constraint names, RHS values (7), and senses (`<=`)
   - Extract the time windows `(t_start_j, t_end_j)` from each constraint expression
   - Extract the objective coefficients for each aircraft's SEA and LAS variables
3. **Parse** each subproblem:
   - Enumerate all variable names (one pass)
   - Extract the Temporality (`>=`) and Sector_Time (`<=`) constraints
   - Build the variable name → index lookup table
4. **Assemble** the linking columns D_i:
   - For each master constraint j and each SEA variable `w(AC, SEA, t)` in the block:
     - If t == t_start_j → row=j, col=var_index, value=−1.0
     - If t == t_end_j   → row=j, col=var_index, value=+1.0
5. **Write** the JSON fixture with `json.dumps(indent=2)` for readability

---

## Known optimal

The four_sea problem has a known LP-relaxation optimal of **12.0** total delay
(slot-minutes). This value is verified by `ref_four_sea.expected.json` and confirmed
against the reference C solver's documented output.
