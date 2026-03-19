# Changelog

All notable changes to `dwsolver` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-03-18

First stable release. The solver is feature-complete, numerically verified
against all reference problems, and rigorously tested via TDD with 98%+ coverage.

### Highlights

- **Dantzig-Wolfe decomposition** fully implemented as a self-contained Python
  library and CLI, solving block-angular LPs to optimality.
- **Dual input formats**: JSON schema and CPLEX LP (master + subproblem files).
- **Massively parallel subproblem dispatch** via `concurrent.futures`
  (`ThreadPoolExecutor`), with a configurable `--workers` option.
- **42 BDD acceptance scenarios** written in Gherkin, executed via `pytest-bdd`,
  covering the full solver lifecycle from file load to solution output.
- **98%+ test coverage** enforced in CI, with live coverage and BDD badges in
  the README.

### Added

- `Problem.from_file()` — load from a validated JSON schema file (spec 001)
- `Problem.from_lp()` / `Problem.from_lp_text()` — load from CPLEX LP files;
  auto-detects format by file extension (spec 005)
- `solve()` — Dantzig-Wolfe decomposition entry point returning a `Result` with
  `SolveStatus` (optimal / infeasible / unbounded / iteration limit)
- CLI entry point `dwsolver` with `--output`, `--workers`, `--tolerance`, and
  `--format` options
- `benchmarks/` package — worker-scalability and subproblem-count benchmarks
  using a parametric synthetic LP generator (specs 003, 004)
- BDD feature files under `specs/001-gherkin-bdd-specs/features/` with
  step definitions in `tests/bdd/` (spec 001)
- `bdd_report.py` — generates a `bdd-badge.json` endpoint for shields.io live
  badge tracking BDD scenario pass rate (spec 007)
- CI workflows: full test matrix (Python 3.11–3.13), coverage comment on PRs,
  live `badge.svg` on the data branch, and auto GitHub Release on `v*` tags
- `DWSolverInputError` — unified user-facing exception for all I/O and schema
  validation errors
- Pydantic v2 models (`Problem`, `Master`, `Block`, `Result`) with strict
  cross-field validators (unique block IDs, unique variable names, COO index
  range checks, dimension consistency)
- Pre-push git hooks enforcing `ruff format`, `ruff check`, and `mypy --strict`

### Reference problems verified

| Problem | Source | Status |
|---------|--------|--------|
| Bertsimas & Tsitsiklis (1-block) | textbook | ✓ optimal |
| Bertsimas & Tsitsiklis (2-block) | textbook | ✓ optimal |
| Bertsimas & Tsitsiklis (3-block) | textbook | ✓ optimal |
| Dantzig (1-block) | textbook | ✓ optimal |
| Lasdon | textbook | ✓ optimal |
| Mitchell | web | ✓ optimal |
| Trick | web | ✓ optimal |
| four_sea (4-block, 440 vars/block) | real-world | ✓ optimal |
| eight_sea (8-block, 440 vars/block) | real-world | ✓ optimal |

---

## [0.1.2] — 2026-03-15

- Additional CPLEX LP fixture coverage and CI stabilisation (spec 005, cont.)

## [0.1.1] — 2026-03-15

- CPLEX LP parser edge cases: Generals/Binary sections silently ignored (FR-009),
  Maximize direction, multi-line constraints, objective constant injection (spec 005)

## [0.1.0] — 2026-03-14

- CPLEX LP input format support: `parse_master`, `parse_subproblem`,
  `infer_linking`, `resolve_block_objective`, `assemble_problem`,
  `load_problem_from_lp` (spec 005)
- GitHub Release workflow triggered on `v*` tags

## [0.0.1] — 2026-03-13

- Initial release: core solver, JSON format, BDD specs, synthetic generator,
  and performance benchmarks (specs 001–004)

[1.0.0]: https://github.com/alotau/dantzig-wolfe-python/compare/v0.1.2...v1.0.0
[0.1.2]: https://github.com/alotau/dantzig-wolfe-python/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/alotau/dantzig-wolfe-python/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/alotau/dantzig-wolfe-python/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/alotau/dantzig-wolfe-python/releases/tag/v0.0.1
