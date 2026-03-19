# Data Model: Test Coverage Reporting & Live README Badges

**Feature**: 007-coverage-badge  
**Phase**: 1 — Design artefact

---

## Entities

### 1. `CoverageReport`

Produced by `pytest-cov` after each full test run. Contains line-level execution data for every module in `src/dwsolver/`.

| Field | Type | Description |
|---|---|---|
| `overall_pct` | `float` | Overall line coverage percentage (0–100) across all measured modules |
| `modules` | `list[ModuleCoverage]` | Per-module breakdown |
| `xml_path` | `path` | Location of machine-readable XML export (`coverage.xml`) |
| `fail_under` | `int` | Minimum threshold; report is in a "failing" state if `overall_pct < fail_under` |

### 1a. `ModuleCoverage`

One entry per source file inside `src/dwsolver/`.

| Field | Type | Description |
|---|---|---|
| `module_name` | `str` | Dotted module name (e.g., `dwsolver.solver`) |
| `statements` | `int` | Total executable statement count |
| `missed` | `int` | Statements not executed by any test |
| `coverage_pct` | `float` | `(statements - missed) / statements × 100` |
| `missing_lines` | `list[int]` | Line numbers not covered |

---

### 2. `LineCoverageBadge`

A shields.io-compatible endpoint JSON file stored on the `python-coverage-comment-action-data` branch. Consumed by shields.io to render a dynamic badge in the README.

| Field | Type | Description |
|---|---|---|
| `schemaVersion` | `int` | Always `1` (shields.io endpoint schema) |
| `label` | `str` | Badge left-hand text (e.g., `"coverage"`) |
| `message` | `str` | Badge right-hand text (e.g., `"97%"`) |
| `color` | `str` | Badge colour driven by coverage value: `brightgreen` ≥ 90%, `yellow` ≥ 70%, `red` < 70% |
| `cacheSeconds` | `int` | shields.io cache TTL; `300` (5 min) |

**Managed by**: `python-coverage-comment-action`  
**Storage location**: `python-coverage-comment-action-data` branch → `endpoint.json`

---

### 3. `GherkinScenarioCount`

The total and passing counts of Gherkin scenarios across all `.feature` files. Computed by `scripts/bdd_report.py`.

| Field | Type | Description |
|---|---|---|
| `total` | `int` | Total `Scenario:` + `Scenario Outline:` definitions across all feature files |
| `passed` | `int` | Scenarios whose corresponding pytest test case passed in the most recent run |
| `failed` | `int` | Scenarios whose corresponding pytest test case failed |
| `per_feature` | `list[FeatureScenarioCount]` | Per-feature-file breakdown |

### 3a. `FeatureScenarioCount`

One entry per `.feature` file.

| Field | Type | Description |
|---|---|---|
| `feature_file` | `str` | Filename (e.g., `cli_usage.feature`) |
| `total` | `int` | Scenario count in this feature file |
| `passed` | `int` | Number passing in the most recent run |
| `failed` | `int` | Number failing |
| `status` | `str` | `"✅"` if all pass, `"❌"` if any fail |

---

### 4. `BDDBadgeEndpoint`

A shields.io-compatible endpoint JSON file committed to the `python-coverage-comment-action-data` branch. Rendered as the Gherkin completeness badge in the README.

| Field | Type | Description |
|---|---|---|
| `schemaVersion` | `int` | Always `1` |
| `label` | `str` | `"BDD scenarios"` |
| `message` | `str` | `"{passed} / {total}"` (e.g., `"40 / 40"`) |
| `color` | `str` | `brightgreen` if all pass, `yellow` if any fail, `red` if > 10% fail |
| `cacheSeconds` | `int` | `300` |

**Managed by**: `scripts/bdd_report.py`  
**Storage location**: `python-coverage-comment-action-data` branch → `bdd-badge.json`

---

### 5. `BDDTraceabilityReport`

A Markdown-formatted table summarising scenario pass/fail counts per feature file. Uploaded as a GitHub Actions artifact after each `main` branch CI run.

| Field | Type | Description |
|---|---|---|
| `generated_at` | `str` | ISO-8601 timestamp of the CI run |
| `rows` | `list[FeatureScenarioCount]` | One row per feature file |
| `total_row` | `FeatureScenarioCount` | Aggregate totals row |
| `artifact_name` | `str` | `"bdd-traceability-report"` (GitHub Actions artifact name) |

---

## Entity Relationships

```
CoverageReport
  └── ModuleCoverage[*]   (one per source module)
  └── LineCoverageBadge   (derived; managed by coverage action → endpoint.json)

GherkinScenarioCount
  └── FeatureScenarioCount[*]  (one per .feature file)
  └── BDDBadgeEndpoint         (derived; written by bdd_report.py → bdd-badge.json)
  └── BDDTraceabilityReport    (derived; written by bdd_report.py → bdd-traceability.md)
```

---

## State Transitions: Coverage & BDD Badge Lifecycle

```
[Code changed on feature branch]
  → Developer runs pytest locally
    → CoverageReport produced (terminal + coverage.xml)
    → .bdd-results.xml produced (JUnit XML)

[PR merged to main]
  → CI runs full test suite
    → CoverageReport produced → coverage-comment-action uploads → LineCoverageBadge updated on data branch
    → .bdd-results.xml produced → bdd_report.py runs → BDDBadgeEndpoint + BDDTraceabilityReport written
      → BDDBadgeEndpoint committed to data branch → shields.io badge auto-updates
      → BDDTraceabilityReport uploaded as GitHub Actions artifact

[Visitor views README on GitHub]
  → shields.io fetches LineCoverageBadge endpoint.json (TTL 5 min)
  → shields.io fetches BDDBadgeEndpoint bdd-badge.json (TTL 5 min)
  → Badges render with current values
```
