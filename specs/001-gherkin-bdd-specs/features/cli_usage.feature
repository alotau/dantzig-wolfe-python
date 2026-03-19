Feature: Command Line Interface — Dantzig-Wolfe Solver
  As a researcher or engineer working with large-scale linear programs,
  I want to invoke the DW solver from the command line with a structured input file,
  So that I can obtain an optimal solution or a clear explanation of why none exists.

  # NOTE: Scenario steps use the form "dwsolver solve FILE" for readability.
  # The actual CLI is a flat command: dwsolver [OPTIONS] FILES...
  # The "solve" token is stripped by the _invoke() helper in test_cli_usage.py
  # so every step works correctly against the real flat entry point.

  Background:
    Given the dwsolver command is available on the PATH

  # ---------------------------------------------------------------------------
  # Successful solve scenarios
  # ---------------------------------------------------------------------------

  Scenario: Solve a valid two-block LP and write a solution file
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json"
    Then the exit code is 0
    And a solution file "simple_two_block.solution.json" is created
    And the solution file contains status "optimal"
    And the solution file contains the optimal objective value

  Scenario: Solve with an explicit output path
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json --output my_result.json"
    Then the exit code is 0
    And a solution file "my_result.json" is created
    And the solution file contains status "optimal"

  Scenario: Solution file contains variable assignments
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json"
    Then the solution file contains a non-empty mapping of variable names to values

  # ---------------------------------------------------------------------------
  # Infeasible and unbounded problems
  # ---------------------------------------------------------------------------

  # Exit code is 0: non-optimal outcomes are valid solver results, not tool failures
  Scenario Outline: Report non-optimal status for an unsolvable problem
    Given a "<status>" LP input file "<input_file>"
    When I run "dwsolver solve <input_file>"
    Then the exit code is 0
    And a solution file "<solution_file>" is created
    And the solution file contains status "<status>"
    And the solution file contains a non-empty diagnostic message
    And the solution file does not contain variable assignments

    Examples:
      | input_file              | solution_file                    | status     |
      | infeasible_problem.json | infeasible_problem.solution.json | infeasible |
      | unbounded_problem.json  | unbounded_problem.solution.json  | unbounded  |

  # ---------------------------------------------------------------------------
  # Input validation and error handling
  # ---------------------------------------------------------------------------

  Scenario: Error on malformed input file
    Given a malformed input file "bad_format.json" that is not a valid problem schema
    When I run "dwsolver solve bad_format.json"
    Then the exit code is non-zero
    And an error message is written to stderr
    And no solution file is created

  Scenario: Error on missing input file
    When I run "dwsolver solve nonexistent_file.json"
    Then the exit code is non-zero
    And an error message is written to stderr mentioning the missing file

  Scenario: Error on unwritable output path
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json --output /nonexistent_dir/out.json"
    Then the exit code is non-zero
    And an error message is written to stderr
    And no solution file is created

  # ---------------------------------------------------------------------------
  # Worker count parameter
  # ---------------------------------------------------------------------------

  Scenario: Solve with an explicit worker count
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json --workers 4"
    Then the exit code is 0
    And the solution file contains status "optimal"
    And the solution file contains the optimal objective value

  Scenario: Results are identical regardless of worker count
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json --workers 1" and record the objective value
    And I run "dwsolver solve simple_two_block.json --workers 8" and record the objective value
    Then both objective values are equal

  # ---------------------------------------------------------------------------
  # Convergence tolerance parameter
  # ---------------------------------------------------------------------------

  Scenario: Solve with a custom convergence tolerance
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json --tolerance 1e-4"
    Then the exit code is 0
    And the solution file contains status "optimal"

  Scenario: Default tolerance of 1e-6 is used when --tolerance is not specified
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json"
    Then the exit code is 0
    And the solution file contains status "optimal"
    And the solution file records the tolerance value 1e-6

  # ---------------------------------------------------------------------------
  # Verbose diagnostic output
  # ---------------------------------------------------------------------------

  Scenario: Verbose output is emitted to stderr when --verbose is passed
    Given a valid block-angular LP input file "simple_two_block.json"
    When I run "dwsolver solve simple_two_block.json --verbose"
    Then the exit code is 0
    And the solution file contains status "optimal"
    And solver diagnostic lines are written to the output