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
