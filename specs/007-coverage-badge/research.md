# Research: Test Coverage Reporting & Live README Badges

**Feature**: 007-coverage-badge  
**Phase**: 0 — Unknowns resolved before design

---

## Decision 1: External Coverage Reporting Service

**Decision**: Use `py-cov-action/python-coverage-comment-action@v3` — a GitHub Action that runs entirely on GitHub infrastructure with no external SaaS dependency.

**Rationale**:
- Stores coverage badge SVG and a shields.io-compatible `endpoint.json` on a dedicated `python-coverage-comment-action-data` branch inside the project's own repository
- Dynamic badge URL reads directly from that branch via GitHub raw content — no external account or token beyond `${{ github.token }}`
- Posts per-file coverage diff comments on PRs automatically
- No vendor lock-in, no free-tier rate limits, no account management
- Actively maintained open-source project (well-adopted Python ecosystem tool)

**Alternatives considered**:
- **Codecov** — excellent UI and PR comments, but requires routing coverage data through an external service; free for public repos but adds an external dependency and account management overhead
- **Coveralls** — similar trade-offs to Codecov; slightly simpler but less feature-rich

**Badge URL format** (after data branch is created):
```
https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/{owner}/{repo}/python-coverage-comment-action-data/endpoint.json
```

---

## Decision 2: pytest-cov Configuration & Threshold Enforcement

**Decision**: Add `pytest-cov` to the `dev` extras in `pyproject.toml`, configure coverage via `[tool.coverage.run]` and `[tool.coverage.report]` sections, and use `--cov-fail-under` enforced through `[tool.coverage.report] fail_under = 90`.

**Rationale**:
- `fail_under` in `[tool.coverage.report]` means CI automatically fails if coverage drops below 90% — no CI script change needed for threshold enforcement
- `source = ["dwsolver"]` scopes measurement to the library package only (excludes `benchmarks/`, scripts, tests themselves)
- `show_missing = true` prints uncovered line numbers in the terminal report by default
- XML report (`coverage.xml`) is required by `python-coverage-comment-action` and other badge tools
- `--cov` added to `addopts` in `[tool.pytest.ini_options]` so that `pytest` always produces coverage; developers can pass `--no-cov` to skip it for speed

**pyproject.toml additions**:
```toml
[tool.coverage.run]
source = ["dwsolver"]
omit = ["*/benchmarks/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 90
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "\\.\\.\\.",
]
```

**pytest `addopts`** (append to existing `[tool.pytest.ini_options]`):
```toml
addopts = "--cov=dwsolver --cov-report=term-missing --cov-report=xml:coverage.xml"
```

---

## Decision 3: BDD Scenario Counting Strategy

**Decision**: Use a custom Python script (`scripts/bdd_report.py`) that:
1. Parses `.feature` files with `re` to count `Scenario:` and `Scenario Outline:` definitions — this gives the **total scenario count**
2. Parses a JUnit XML report (`--junitxml=.bdd-results.xml` from pytest) to count passing vs failing scenarios per feature file — by mapping test file names back to feature file names
3. Writes two outputs: a shields.io endpoint JSON (`bdd-badge.json`) and a Markdown traceability table (`bdd-traceability.md`)

**Rationale**:
- No new runtime dependencies — `xml.etree.ElementTree` and `re` are stdlib
- JUnit XML is already a supported pytest output format; adding `--junitxml` to the BDD test run is trivial
- The test file → feature file mapping is deterministic: `tests/bdd/steps/test_cli_usage.py` corresponds to `cli_usage.feature` (filename convention already established in the project)
- Parsing feature files directly for totals is simpler and doesn't depend on test runtime state

**Alternatives considered**:
- **`pytest-html`** — produces human-readable HTML but not machine-parseable for badge generation; adds a dependency
- **Allure** — overkill for this project; requires allure-pytest plugin + separate allure CLI to render; heavy dependency
- **pytest-bdd native JSON** — pytest-bdd does not have a built-in JSON reporter; JUnit XML is the standard pytest output

**Current scenario counts** (as of 2026-03-18):

| Feature file | Scenarios defined | Test instances at runtime |
|---|---|---|
| `cli_usage.feature` | 12 | 13 (Scenario Outline × 2) |
| `cplex_lp_usage.feature` | 18 | 18 |
| `library_usage.feature` | 10 | 11 (Scenario Outline × 2) |
| **Total** | **40** | **42** |

---

## Decision 4: BDD Badge Storage & README Integration

**Decision**: Store the BDD badge endpoint JSON on the same `python-coverage-comment-action-data` branch as the coverage badge. In CI, after the coverage action runs, a subsequent step commits `bdd-badge.json` to that branch.

**Rationale**:
- Reuses the branch and git operations already established by the coverage action
- Single branch for all test quality badge data — easier to reason about and maintain
- Shields.io reads the JSON from GitHub raw URL — no additional hosting required
- Committing to the data branch from CI is safe: this branch is never merged to `main` and only ever used as a badge data store

**BDD badge JSON schema** (shields.io endpoint format):
```json
{
  "schemaVersion": 1,
  "label": "BDD scenarios",
  "message": "40 / 40",
  "color": "brightgreen",
  "cacheSeconds": 300
}
```

**Color rules**: `brightgreen` if all pass, `yellow` if any fail, `red` if > 10% fail.

**README badge URL**:
```
https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/{owner}/{repo}/python-coverage-comment-action-data/bdd-badge.json
```

---

## Decision 5: BDD Traceability Report Format

**Decision**: The traceability report is generated as a Markdown table (`bdd-traceability.md`) and uploaded as a GitHub Actions artifact (downloadable from the CI run). The BDD badge in the README links to the GitHub Actions CI run for the `main` branch rather than to a hosted report.

**Rationale**:
- Uploading a Markdown file as a CI artifact is zero-dependency (uses `actions/upload-artifact`)
- Linking the badge to the GitHub Actions page for `main` is simpler than hosting an HTML report and is immediately useful — clicking the badge takes you to the CI run where the artifact is downloadable
- Avoids committing a generated HTML file to the repo on every CI run

**Traceability table format**:
```markdown
| Feature File | Scenarios Passed | Scenarios Total | Status |
|---|---|---|---|
| cli_usage.feature | 13 | 13 | ✅ |
| cplex_lp_usage.feature | 18 | 18 | ✅ |
| library_usage.feature | 11 | 11 | ✅ |
| **Total** | **42** | **42** | **✅ All pass** |
```

---

## Summary: All NEEDS CLARIFICATION Resolved

| Unknown | Resolution |
|---|---|
| Which coverage service to use? | `python-coverage-comment-action` — self-hosted on GitHub |
| Where is the coverage badge URL? | `python-coverage-comment-action-data` branch, via shields.io endpoint |
| How to enforce threshold? | `[tool.coverage.report] fail_under = 90` in pyproject.toml |
| How to count BDD scenarios? | Custom `scripts/bdd_report.py` — feature file regex + JUnit XML parsing |
| Where to store BDD badge JSON? | `python-coverage-comment-action-data` branch alongside coverage badge |
| What format for BDD traceability? | Markdown table uploaded as GitHub Actions artifact |
| Does BDD test coverage count toward the 97%? | Yes — already included; BDD steps exercise `src/dwsolver/` the same as unit tests |
