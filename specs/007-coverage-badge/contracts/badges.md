# Contract: Badge Endpoint Schemas

**Feature**: 007-coverage-badge  
**Phase**: 1 — Interface contract

This document defines the data contracts for the two badge endpoint JSON files that CI produces and shields.io consumes. Any change to these schemas must be reflected in both the producer (`scripts/bdd_report.py` / `python-coverage-comment-action`) and the README badge URLs.

---

## 1. Line Coverage Badge Endpoint

**File**: `endpoint.json`  
**Branch**: `python-coverage-comment-action-data`  
**Managed by**: `py-cov-action/python-coverage-comment-action@v3` (not hand-written)  
**Consumed by**: shields.io dynamic badge in README

### Schema (shields.io Endpoint v1)

```json
{
  "schemaVersion": 1,
  "label": "coverage",
  "message": "97%",
  "color": "brightgreen",
  "cacheSeconds": 300
}
```

| Field | Type | Constraints | Description |
|---|---|---|---|
| `schemaVersion` | integer | Must be `1` | shields.io schema version |
| `label` | string | Non-empty | Left-hand badge text |
| `message` | string | Pattern `^\d+%$` | Coverage percentage string |
| `color` | string | One of the colour values below | Badge colour |
| `cacheSeconds` | integer | ≥ 60 | shields.io TTL for caching |

**Colour rules** (applied by coverage action):

| Coverage | Color |
|---|---|
| ≥ 90% | `brightgreen` |
| ≥ 70% | `yellow` |
| < 70% | `red` |

**README badge Markdown**:
```markdown
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/alotau/dantzig-wolfe-python/python-coverage-comment-action-data/endpoint.json)](https://github.com/alotau/dantzig-wolfe-python/actions/workflows/ci.yml)
```

---

## 2. BDD Scenario Completeness Badge Endpoint

**File**: `bdd-badge.json`  
**Branch**: `python-coverage-comment-action-data`  
**Managed by**: `scripts/bdd_report.py` (run in CI after test suite)  
**Consumed by**: shields.io dynamic badge in README

### Schema (shields.io Endpoint v1)

```json
{
  "schemaVersion": 1,
  "label": "BDD scenarios",
  "message": "40 / 40",
  "color": "brightgreen",
  "cacheSeconds": 300
}
```

| Field | Type | Constraints | Description |
|---|---|---|---|
| `schemaVersion` | integer | Must be `1` | shields.io schema version |
| `label` | string | Must be `"BDD scenarios"` | Left-hand badge text |
| `message` | string | Pattern `^\d+ / \d+$` | `"{passed} / {total}"` |
| `color` | string | One of the colour values below | Badge colour |
| `cacheSeconds` | integer | Must be `300` | shields.io TTL |

**Colour rules**:

| Condition | Color |
|---|---|
| `passed == total` (all pass) | `brightgreen` |
| `passed / total >= 0.9` | `yellow` |
| `passed / total < 0.9` | `red` |

**README badge Markdown**:
```markdown
[![BDD Scenarios](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/alotau/dantzig-wolfe-python/python-coverage-comment-action-data/bdd-badge.json)](https://github.com/alotau/dantzig-wolfe-python/actions/workflows/ci.yml)
```

---

## 3. BDD Traceability Report (CI Artefact)

**File**: `bdd-traceability.md`  
**Storage**: Uploaded as GitHub Actions artifact named `bdd-traceability-report` on each `main` branch run  
**Managed by**: `scripts/bdd_report.py`  
**Consumed by**: developers and reviewers via GitHub Actions → Artifacts

### Format

```markdown
# BDD Scenario Traceability Report

Generated: {ISO-8601 timestamp}

| Feature File | Passed | Total | Status |
|---|---|---|---|
| cli_usage.feature | 13 | 13 | ✅ |
| cplex_lp_usage.feature | 18 | 18 | ✅ |
| library_usage.feature | 11 | 11 | ✅ |
| **Total** | **42** | **42** | **✅ All pass** |
```

### Column definitions

| Column | Description |
|---|---|
| `Feature File` | Basename of the `.feature` file |
| `Passed` | Count of pytest test instances that passed (Scenario Outline rows count individually) |
| `Total` | Count of pytest test instances collected (may exceed scenario definitions for Outlines) |
| `Status` | `✅` if `passed == total`, `❌` otherwise |

---

## Versioning

These contracts are internal to the project. Breaking changes (field renames, schema version bumps, message format changes) require updating:
1. `scripts/bdd_report.py` (producer)
2. README badge URLs (if the file path or branch changes)
3. This document
