# dwsolver-vibes Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-03

## Active Technologies
- Python 3.11+ + `numpy>=1.24` (new), `highspy` (existing dev dep), `dwsolver` (this project) (003-generate-synthetic-block)
- N/A — generator runs entirely in memory; optional `--output` flag writes JSON (003-generate-synthetic-block)
- Python 3.11 + `dwsolver` (library under test), `highspy`, `pydantic >= 2`, (004-perf-benchmark)
- N/A — no persistent state; results printed to stdou (004-perf-benchmark)
- Python 3.11 + click, pydantic>=2, highspy — all existing; no new runtime deps (005-cplex-lp-input)
- File I/O via `pathlib.Path`; `.lp` and `.cplex` files read as UTF-8 tex (005-cplex-lp-input)

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
- 005-cplex-lp-input: Added Python 3.11 + click, pydantic>=2, highspy — all existing; no new runtime deps
- 004-perf-benchmark: Added Python 3.11 + `dwsolver` (library under test), `highspy`, `pydantic >= 2`,
- 003-generate-synthetic-block: Added Python 3.11+ + `numpy>=1.24` (new), `highspy` (existing dev dep), `dwsolver` (this project)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
