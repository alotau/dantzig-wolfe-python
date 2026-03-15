Feature: CLI — CPLEX LP Input Format
  As a researcher or engineer who has a Dantzig-Wolfe LP expressed as CPLEX LP files,
  I want to invoke the solver from the command line with a master file and subproblem files,
  So that I can obtain the same solution output as the JSON workflow.

  Background:
    Given the dwsolver command is available on the PATH

  # ---------------------------------------------------------------------------
  # US1: CLI solve using CPLEX LP files
  # ---------------------------------------------------------------------------

  Scenario: Solve four_sea with CPLEX LP files produces objective 12.0
    Given the four_sea CPLEX LP fixtures are available
    When I run "dwsolver four_sea/master.cplex four_sea/subprob_1.cplex four_sea/subprob_2.cplex four_sea/subprob_3.cplex four_sea/subprob_4.cplex"
    Then the exit code is 0
    And a solution file "master.solution.json" is created
    And the solution file contains status "optimal"
    And the solution file objective is approximately 12.0

  Scenario: JSON workflow is unchanged after this feature
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver simple_two_block.json"
    Then the exit code is 0
    And a solution file "simple_two_block.solution.json" is created
    And the solution file contains status "optimal"

  Scenario: .cplex extension is detected as LP format
    Given the four_sea CPLEX LP fixtures are available
    When I run "dwsolver four_sea/master.cplex four_sea/subprob_1.cplex four_sea/subprob_2.cplex four_sea/subprob_3.cplex four_sea/subprob_4.cplex"
    Then the exit code is 0
    And the solution file objective is approximately 12.0

  Scenario: --format lp overrides extension auto-detection
    Given the four_sea CPLEX LP fixtures are available
    When I run "dwsolver --format lp four_sea/master.cplex four_sea/subprob_1.cplex four_sea/subprob_2.cplex four_sea/subprob_3.cplex four_sea/subprob_4.cplex"
    Then the exit code is 0
    And the solution file objective is approximately 12.0

  Scenario: --output flag works with LP mode
    Given the four_sea CPLEX LP fixtures are available
    When I run "dwsolver four_sea/master.cplex four_sea/subprob_1.cplex four_sea/subprob_2.cplex four_sea/subprob_3.cplex four_sea/subprob_4.cplex --output four_sea_result.json"
    Then the exit code is 0
    And a solution file "four_sea_result.json" is created
    And the solution file contains status "optimal"

  # ---------------------------------------------------------------------------
  # US3: Error diagnostics (CLI-visible errors)
  # ---------------------------------------------------------------------------

  Scenario: Error when LP file does not exist
    When I run "dwsolver nonexistent_master.cplex nonexistent_sub.cplex"
    Then the exit code is non-zero
    And an error message is written to stderr

  Scenario: Error when only one LP file provided with no format override
    When I run "dwsolver four_sea/master.cplex"
    Then the exit code is non-zero
    And an error message is written to stderr

  Scenario: Error on unknown --format value
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver --format xyz simple_two_block.json"
    Then the exit code is non-zero
    And an error message is written to stderr

  # ---------------------------------------------------------------------------
  # US2: Library API for CPLEX LP problems
  # ---------------------------------------------------------------------------

  Scenario: Problem.from_lp returns a validated Problem object
    Given the four_sea CPLEX LP fixtures are available
    When I call Problem.from_lp with the four_sea master and subproblem files
    Then a Problem object with 4 blocks is returned

  Scenario: Problem.from_lp_text returns a Problem from in-memory strings
    When I call Problem.from_lp_text with a simple two-block LP
    Then a Problem object with 2 blocks is returned

  Scenario: Block IDs are assigned in subproblem argument order
    When I call Problem.from_lp_text with a simple two-block LP
    Then the Problem block 0 has id "block_0"
    And the Problem block 1 has id "block_1"

  Scenario: Solving a Problem loaded via from_lp returns an optimal result
    Given the four_sea CPLEX LP fixtures are available
    When I call Problem.from_lp with the four_sea master and subproblem files
    And I solve the loaded LP problem
    Then the LP solve status is "optimal"
    And the LP solve objective is approximately 12.0

  Scenario: Cross-format: objectives from from_lp and from_file agree within 1e-6
    Given the four_sea CPLEX LP fixtures are available
    When I solve the four_sea problem via from_lp and via from_file
    Then the two solve objectives agree within 1e-6

  Scenario: Problem.from_lp raises DWSolverInputError for a missing master file
    When I call Problem.from_lp with a nonexistent master path
    Then a DWSolverInputError is raised from the LP loader

  # ---------------------------------------------------------------------------
  # US3: Additional error handling (library API paths)
  # ---------------------------------------------------------------------------

  Scenario: Error when master Subject To section contains no constraints
    When I call Problem.from_lp_text with a master that has an empty Subject To
    Then a DWSolverInputError is raised from the LP loader

  Scenario: Error when subproblem Bounds section declares no variables
    When I call Problem.from_lp_text with a subproblem that has an empty Bounds section
    Then a DWSolverInputError is raised from the LP loader

  Scenario: Error when a variable appears in two subproblem Bounds sections
    When I call Problem.from_lp_text with two subproblems that share a variable name
    Then a DWSolverInputError is raised from the LP loader

  Scenario: Error when master constraint references a variable not in any subproblem
    When I call Problem.from_lp_text with a master referencing an undeclared variable
    Then a DWSolverInputError is raised from the LP loader
