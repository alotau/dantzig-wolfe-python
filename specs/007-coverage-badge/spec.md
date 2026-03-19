# Feature Specification: Test Coverage Reporting & Live README Badges

**Feature Branch**: `007-coverage-badge`  
**Created**: 2026-03-18  
**Status**: Draft  
**Input**: User description: "Add test coverage reporting with live badges on the main README — including source-code line coverage, Gherkin scenario completeness, and feature-level BDD traceability"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Coverage Report (Priority: P1)

A developer runs the test suite and immediately sees a per-module and overall coverage percentage, including which specific lines are not covered. This gives them instant feedback on test quality without any external dependency.

**Why this priority**: This is the foundational capability — every other story depends on coverage data being measurable. It delivers standalone value and unblocks US2 and US3.

**Independent Test**: Can be fully tested by running the test suite and verifying a coverage report is printed to the terminal. Delivers value as a standalone improvement even if US2 and US3 are never implemented.

**Acceptance Scenarios**:

1. **Given** a developer has checked out the project and installed dev dependencies, **When** they run the standard test command, **Then** a coverage report is printed showing overall coverage % and per-module breakdown
2. **Given** a coverage report has been generated, **When** a developer inspects it, **Then** they can see exactly which lines in each source file are not covered by any test
3. **Given** dev dependencies are installed, **When** a developer installs them fresh from the project configuration, **Then** the coverage tool is included without requiring a separate install step

---

### User Story 2 - Live README Badge (Priority: P2)

A contributor or potential user visits the project repository on GitHub and sees a coverage badge in the README showing the current coverage percentage of the `main` branch. The badge is always up-to-date and updates automatically whenever code is merged to `main`.

**Why this priority**: Provides public visibility into code quality. Builds trust with contributors and users by showing test health at a glance, without requiring them to clone and run the suite themselves.

**Independent Test**: Can be fully tested by merging a change to `main`, visiting the repository README on GitHub, and confirming the badge reflects the new coverage value within a few minutes.

**Acceptance Scenarios**:

1. **Given** code has been merged to `main`, **When** a visitor views the README on GitHub, **Then** a badge displays the current overall coverage percentage
2. **Given** the coverage percentage changes due to new code or new tests, **When** changes are merged to `main`, **Then** the badge updates automatically without any manual action
3. **Given** the coverage reporting service is temporarily unavailable, **When** a visitor views the README, **Then** the badge shows a neutral "unknown" or "pending" state rather than an incorrect value
4. **Given** the badge is rendered, **When** a user clicks it, **Then** they are taken to a detailed coverage breakdown report

---

### User Story 3 - Coverage Regression Guard (Priority: P3)

The CI pipeline detects when a pull request would lower the overall test coverage below the project's defined minimum, and blocks the merge until coverage is restored or the threshold is explicitly reviewed.

**Why this priority**: Prevents gradual coverage decay. Ensures that new features and bug fixes are accompanied by adequate tests. Lower priority because the project already has high coverage (97%) and US1 + US2 are more immediately valuable.

**Independent Test**: Can be fully tested by opening a pull request that adds source lines without corresponding tests and confirming the CI check fails with a clear message about coverage regression.

**Acceptance Scenarios**:

1. **Given** a pull request that decreases overall coverage below the defined minimum, **When** CI runs, **Then** the coverage check step fails with a message indicating the coverage shortfall
2. **Given** a pull request that maintains or improves coverage, **When** CI runs, **Then** the coverage check passes and does not block the merge
3. **Given** the coverage threshold is defined in project configuration, **When** a developer reads it, **Then** they can find and understand the threshold value without searching through CI scripts

---

### User Story 4 - Gherkin Scenario Completeness Badge (Priority: P4)

A visitor to the repository README sees a badge showing that all Gherkin scenarios defined across the project's feature files have matching step implementations and pass. This surfaces BDD test health as a distinct, visible metric separate from source-line coverage.

**Why this priority**: Adds visibility into the health of the BDD layer specifically. Since the project uses pytest-bdd with feature files as a first-class artifact, showing scenario completeness independently signals that the BDD contract is being honoured. Depends on US1's infrastructure being in place.

**Independent Test**: Can be fully tested by pushing to `main` and confirming a badge appears in the README displaying the number of passing BDD scenarios out of the total defined. Delivers standalone value as a BDD health signal.

**Acceptance Scenarios**:

1. **Given** the test suite has run on `main`, **When** a visitor views the README, **Then** a badge displays the count of passing BDD scenarios out of the total defined across all feature files (e.g., "BDD: 31 / 31")
2. **Given** a new BDD scenario is added to a feature file without a step implementation, **When** CI runs, **Then** the scenario completeness count reflects the gap and the overall test run fails (undefined step)
3. **Given** all scenarios are passing, **When** CI completes, **Then** the Gherkin completeness badge shows 100% or full pass status
4. **Given** the badge is rendered in the README, **When** a user reads it, **Then** they can distinguish it from the line coverage badge as a separate measure

---

### User Story 5 - Feature-level BDD Traceability Report (Priority: P5)

A developer or reviewer can inspect a report that shows, for each feature file, how many scenarios passed out of the total defined. This gives a per-feature health view rather than a single aggregate number.

**Why this priority**: Provides the deepest visibility into BDD test quality — identifying which specific features are fully exercised vs. partially. Lower priority as it requires more reporting infrastructure, but completes the traceability story that US4 begins.

**Independent Test**: Can be fully tested by inspecting CI artefacts after a run and verifying a per-feature breakdown is available listing scenario counts per file. Delivers standalone value as a traceability audit tool.

**Acceptance Scenarios**:

1. **Given** CI has completed a test run, **When** a developer accesses the test report artefact, **Then** they can see each feature file listed with its passing and total scenario count
2. **Given** a feature file has all scenarios passing, **When** the report is read, **Then** that feature is shown as fully traced
3. **Given** the per-feature report exists, **When** a user clicks the BDD badge in the README, **Then** they are taken to a view that shows the per-feature breakdown

---

### Edge Cases

- What happens when the coverage reporting service is unavailable during a CI run? The test run itself must still succeed; only the badge upload should fail gracefully without blocking the build.
- What if optional dependencies (e.g., `matplotlib`) cause some lines to always be skipped? Those modules should be excluded from the coverage minimum threshold calculation or the threshold set with this in mind.
- What if coverage drops to exactly the threshold value? That should be treated as passing (threshold is a minimum, not a floor-exclusive value).
- What happens if a developer's local environment doesn't have the coverage tool installed despite the dev configuration listing it? The standard install command for dev dependencies should resolve this automatically.
- What if a `.feature` file has no scenarios at all (e.g., a stub)? It should not contribute to the completeness count in either direction.
- What if the same step definition is shared across multiple feature files? It should count once per scenario that uses it, not once per definition.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST produce a per-module line coverage report showing covered and uncovered lines as part of a standard test run
- **FR-002**: The coverage measurement tool MUST be listed as a standard developer dependency so it is installed automatically when a developer sets up the project
- **FR-003**: The project CI pipeline MUST upload coverage results to an external coverage tracking service after each successful test run on `main`
- **FR-004**: The README MUST include a line coverage badge that dynamically displays the current overall coverage percentage sourced from the external coverage tracking service
- **FR-005**: The line coverage badge MUST reflect the coverage of the `main` branch specifically, not a feature branch or PR
- **FR-006**: The CI pipeline MUST be configured to enforce a minimum overall coverage threshold, failing the build if the threshold is not met
- **FR-007**: The minimum coverage threshold MUST be defined in a single, developer-visible location within the project configuration (not buried inside CI scripts)
- **FR-008**: Coverage reporting MUST remain compatible with the project's existing multi-Python-version test matrix
- **FR-009**: The CI pipeline MUST count the total number of Gherkin scenarios defined across all feature files and the number that pass after each run on `main`
- **FR-010**: The README MUST include a Gherkin completeness badge displaying passing scenarios out of total defined (e.g., "BDD: 31 / 31") that auto-updates on each `main` run
- **FR-011**: The CI pipeline MUST produce a per-feature file breakdown report showing scenario pass/total counts for each `.feature` file after each run on `main`
- **FR-012**: The Gherkin completeness badge MUST link to the per-feature breakdown report so users can drill into feature-level detail
- **FR-013**: All three README badges (line coverage, Gherkin completeness, feature traceability link) MUST be visually grouped together in the README for discoverability

### Key Entities

- **Coverage Report**: The output of a test run that maps each source file to a percentage of lines executed, along with a list of uncovered line numbers
- **Line Coverage Badge**: A dynamically rendered image embedded in the README showing the current overall line coverage percentage, sourced from the external coverage tracking service
- **Coverage Threshold**: A project-level minimum acceptable overall coverage percentage below which a CI run is considered a failure
- **Gherkin Scenario**: A single `Scenario` or `Scenario Outline` entry within a `.feature` file representing one testable behaviour
- **Gherkin Completeness Count**: The ratio of passing Gherkin scenarios to total Gherkin scenarios defined across all feature files (e.g., 31 / 31)
- **Gherkin Completeness Badge**: A dynamically rendered image in the README showing the current passing/total scenario count, updated on each `main` run
- **BDD Traceability Report**: A per-feature file breakdown that lists each feature file with its passing scenario count and total scenario count, produced as a CI artefact

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can view a full per-module line coverage report within 30 seconds of completing a local test run, using only the standard test command
- **SC-002**: The README line coverage badge reflects the most recent `main` branch coverage within 5 minutes of a successful CI run completing
- **SC-003**: The badge accurately reports the coverage percentage to within 1 percentage point of the value computed locally
- **SC-004**: 100% of developers who follow the standard project setup instructions (install dev dependencies) have the coverage tool available without additional steps
- **SC-005**: The CI pipeline fails on any pull request that would lower overall line coverage below the configured minimum threshold
- **SC-006**: The README Gherkin completeness badge reflects the most recent `main` scenario pass/total count within 5 minutes of a successful CI run completing
- **SC-007**: A developer can access a per-feature BDD breakdown report from CI artefacts showing each feature file's scenario counts after any `main` run
- **SC-008**: All three badges in the README render correctly and are visually grouped so a first-time visitor can assess test quality in under 10 seconds

## Assumptions

- The project is hosted on GitHub and has a functioning GitHub Actions CI pipeline (confirmed: `.github/workflows/ci.yml` exists)
- Coverage is measured at the line level (not branch coverage), consistent with current ad-hoc usage
- A free external coverage reporting service compatible with GitHub repositories is available (industry-standard services fit this description)
- The minimum coverage threshold is set at 90%, providing headroom below the current 97% while guarding against significant regressions; this can be raised later
- Coverage for the `benchmarks/` package (which is separate from `src/dwsolver/`) is excluded from the threshold enforcement, as benchmarks are infrastructure, not production code
- The optional `matplotlib` extra is excluded from coverage enforcement since those lines are conditionally skippable
- Gherkin scenario counts are derived from the existing feature files under `specs/001-gherkin-bdd-specs/features/`; all current scenarios are already passing
- A static badge service (e.g., shields.io with a custom endpoint, or a generated SVG committed to the repo) is sufficient for the Gherkin completeness badge, since an external BDD-specific SaaS is not assumed
- The per-feature BDD traceability report is produced as a CI artefact (downloadable file) rather than hosted on an external service, keeping the implementation self-contained
