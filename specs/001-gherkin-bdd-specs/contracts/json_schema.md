# JSON Input Schema Contract

**File format**: JSON  
**Schema version**: `1.0`  
**Branch**: `001-gherkin-bdd-specs` | **Date**: 2026-03-03

---

## Top-Level Structure

```json
{
  "schema_version": "1.0",
  "metadata": { "name": "string", "description": "string" },
  "master": { ... },
  "blocks": [ ... ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | yes | Semver string; major version `1` supported |
| `metadata` | object | no | Freeform key-value labels (ignored by solver) |
| `master` | object | yes | Linking constraints: `D_1 x_1 + ... + D_l x_l = b_0` |
| `blocks` | array | yes | Array of block objects (min length 1) |

---

## `master` Object

Defines the coupling constraints shared across all blocks (the `b_0` row in the block-angular form).

```json
"master": {
  "constraint_names": ["resource_A", "resource_B"],
  "rhs": [100.0, 50.0],
  "senses": ["=", "<="]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `constraint_names` | string[] | yes | Human-readable names (used in error messages and solution output) |
| `rhs` | number[] | yes | Right-hand side values (`b_0`) |
| `senses` | string[] | yes | Constraint sense per row: `"="`, `"<="`, or `">="` |

**Constraint**: `len(constraint_names) == len(rhs) == len(senses)`.

---

## `blocks` Array — Block Object

Each block encodes one subproblem: variables `x_i`, local constraints `F_i x_i = b_i`, and the block's participation in the master (`D_i`).

```json
{
  "block_id": "block_0",
  "variable_names": ["x_0", "x_1", "x_2"],
  "objective": [3.0, 5.0, 2.0],
  "bounds": [
    {"lower": 0.0, "upper": null},
    {"lower": 0.0, "upper": 10.0},
    {"lower": 0.0, "upper": null}
  ],
  "constraints": {
    "matrix": [
      [1.0, 2.0, 0.5],
      [0.0, 1.0, 1.0]
    ],
    "rhs": [4.0, 3.0],
    "senses": ["=", "<="]
  },
  "linking_columns": {
    "rows": [0, 1],
    "cols": [0, 2],
    "values": [1.0, 0.5]
  }
}
```

### Block fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `block_id` | string | yes | Unique block identifier |
| `variable_names` | string[] | yes | Variable names (globally unique across all blocks) |
| `objective` | number[] | yes | `c_i` coefficients (minimize) |
| `bounds` | Bounds[] | yes | Per-variable bounds |
| `constraints` | BlockConstraints | yes | Local `F_i`, `b_i` |
| `linking_columns` | LinkingColumns | yes | Sparse `D_i` matrix |

### `bounds` entry

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lower` | number | `0.0` | Lower bound (inclusive) |
| `upper` | number \| null | `null` | Upper bound; `null` = `+∞` |

### `constraints` object

| Field | Type | Description |
|-------|------|-------------|
| `matrix` | number[][] | Shape `(m_i, n_i)` — coefficient matrix for local constraints |
| `rhs` | number[] | Length `m_i` — right-hand side `b_i` |
| `senses` | string[] | Length `m_i` — each `"="`, `"<="`, or `">="` |

**Constraint**: `len(matrix) == len(rhs) == len(senses)`, and each row has `len(variable_names)` entries.

### `linking_columns` object (sparse COO format)

Encodes the `D_i` matrix — how block `i`'s variables appear in the master linking constraints.

```
D_i[rows[k], cols[k]] = values[k]
```

| Field | Type | Description |
|-------|------|-------------|
| `rows` | int[] | Master constraint index (0-based, into `master.constraint_names`) |
| `cols` | int[] | Variable index within this block (0-based, into `variable_names`) |
| `values` | number[] | Non-zero coefficient |

**Constraint**: `len(rows) == len(cols) == len(values)`. All `rows[k]` must be valid indices into `master.constraint_names`. All `cols[k]` must be valid indices into this block's `variable_names`.

---

## Full Example

Minimal 2-block, 2-linking-constraint problem:

```json
{
  "schema_version": "1.0",
  "metadata": {
    "name": "two_block_example"
  },
  "master": {
    "constraint_names": ["shared_capacity"],
    "rhs": [10.0],
    "senses": ["<="]
  },
  "blocks": [
    {
      "block_id": "block_0",
      "variable_names": ["x0", "x1"],
      "objective": [1.0, 2.0],
      "bounds": [
        {"lower": 0.0, "upper": null},
        {"lower": 0.0, "upper": 5.0}
      ],
      "constraints": {
        "matrix": [[1.0, 1.0]],
        "rhs": [4.0],
        "senses": ["<="]
      },
      "linking_columns": {
        "rows": [0, 0],
        "cols": [0, 1],
        "values": [1.0, 1.0]
      }
    },
    {
      "block_id": "block_1",
      "variable_names": ["y0", "y1"],
      "objective": [3.0, 1.0],
      "bounds": [
        {"lower": 0.0, "upper": null},
        {"lower": 0.0, "upper": null}
      ],
      "constraints": {
        "matrix": [[2.0, 1.0]],
        "rhs": [6.0],
        "senses": ["<="]
      },
      "linking_columns": {
        "rows": [0, 0],
        "cols": [0, 1],
        "values": [1.0, 2.0]
      }
    }
  ]
}
```

---

## Schema Evolution

- `schema_version` is a semver string; only the **major** version gates compatibility.
- `extra="ignore"` on all Pydantic models: unknown fields are silently dropped, so additive v1.x changes are backward-compatible.
- A future `schema_version: "2.0"` would require a `migrate_v1_to_v2()` function gated on the major version number.
- The solver raises `DWSolverInputError` for any unsupported major version.
