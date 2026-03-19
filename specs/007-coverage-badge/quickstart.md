# Quickstart: Test Coverage Reporting & Live README Badges

**Feature**: 007-coverage-badge

---

## Running Coverage Locally

After this feature is implemented, running the full test suite will automatically produce a coverage report:

```bash
# Standard test run — coverage included by default
pytest

# Skip coverage for a faster local cycle
pytest --no-cov

# View HTML coverage report in browser (optional, not in addopts)
pytest --cov-report=html && open htmlcov/index.html
```

Sample output:

```
Name                         Stmts   Miss  Cover   Missing
----------------------------------------------------------
src/dwsolver/__init__.py         4      0   100%
src/dwsolver/cli.py             47      3    94%   35, 52, 109
src/dwsolver/lp_parser.py      282     10    96%   ...
src/dwsolver/models.py         170      3    98%   ...
src/dwsolver/solver.py         220     10    95%   ...
src/dwsolver/subproblem.py      51      0   100%
----------------------------------------------------------
TOTAL                          774     26    97%

Coverage failure: total of 97% is below minimum of 90%
```

> The last line only appears if coverage drops below 90%. At 97%, the suite passes normally.

---

## Running the BDD Report Script Locally

```bash
# Run BDD tests and capture JUnit XML, then generate the badge JSON and traceability table
pytest tests/bdd/ --junitxml=.bdd-results.xml --no-cov -q
python scripts/bdd_report.py --junit .bdd-results.xml \
    --features specs/001-gherkin-bdd-specs/features \
    --badge-output bdd-badge.json \
    --report-output bdd-traceability.md

# View the traceability report
cat bdd-traceability.md
```

---

## Badge Setup (One-Time: First CI Run on Main)

The badges in the README are driven by files on the `python-coverage-comment-action-data` branch. This branch is **created automatically** the first time the updated CI pipeline runs on `main`. No manual setup is needed.

After the first successful CI run:
1. The badge branch is created with `endpoint.json` (line coverage) and `bdd-badge.json` (BDD scenarios)
2. The shields.io badge URLs in the README become live and resolve correctly

Until the first CI run completes, the badges will show "invalid" or "unknown" — this is expected.

---

## Verifying the Badges

After merging to `main` and CI completing (~2–5 min):

1. Visit the repository README on GitHub
2. Confirm three badges are visible:
   - **Coverage**: shows `97%` (or current value) in green
   - **BDD Scenarios**: shows `42 / 42` in green  
3. Click either badge → lands on the GitHub Actions CI workflow page for `main`
4. On the CI run page, download the `bdd-traceability-report` artifact to see the per-feature breakdown

---

## Coverage Threshold

The minimum coverage threshold is `90%`, defined in `pyproject.toml`:

```toml
[tool.coverage.report]
fail_under = 90
```

To change it: edit this value and open a PR. The rationale for 90% (vs the current 97%) is to provide regression headroom without failing the build on minor fluctuations.

---

## Developer Setup (Ensuring Coverage Tool Is Available)

Coverage support is part of the standard dev dependency group. No extra steps beyond the normal project setup:

```bash
pip install -e ".[dev]"
```

This installs `pytest-cov` automatically. Running `pytest` will then produce coverage output.
