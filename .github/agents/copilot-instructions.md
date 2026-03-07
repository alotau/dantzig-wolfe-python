# dwsolver-vibes Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-03

## Active Technologies
- Python 3.11+ + `numpy>=1.24` (new), `highspy` (existing dev dep), `dwsolver` (this project) (003-generate-synthetic-block)
- N/A — generator runs entirely in memory; optional `--output` flag writes JSON (003-generate-synthetic-block)

- Python 3.11+ + `highspy` (HiGHS LP solver), `concurrent.futures` (stdlib), `click` (CLI), `pytest` + BDD runner (testing), `ruff` (lint/format), `mypy` (type checking) (001-gherkin-bdd-specs)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 003-generate-synthetic-block: Added Python 3.11+ + `numpy>=1.24` (new), `highspy` (existing dev dep), `dwsolver` (this project)
- 002-fix-four-sea-tests: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]
- 002-fix-four-sea-tests: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
