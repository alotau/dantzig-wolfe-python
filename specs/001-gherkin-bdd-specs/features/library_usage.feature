Feature: Python Library Interface — Dantzig-Wolfe Solver
  As a developer building an application that requires large-scale LP optimization,
  I want to import the dwsolver package and call it programmatically,
  So that I can integrate the solver into automated workflows without using the CLI.

  # ---------------------------------------------------------------------------
  # Successful solve scenarios
  # ---------------------------------------------------------------------------

  Scenario: Solve a valid two-block problem and obtain an optimal result
    Given a Problem object with a valid two-block block-angular structure
    When I call solver.solve(problem)
    Then the result status is "optimal"
    And the result contains an objective value
    And result.variable_values is a non-empty mapping of variable names to numeric values

  Scenario: Solve is stateless across multiple calls
    Given a Problem object "problem_a" and a different Problem object "problem_b"
    When I call solver.solve(problem_a) and then solver.solve(problem_b)
    Then each call returns an independent Result with no shared state

  # ---------------------------------------------------------------------------
  # Worker count parameter
  # ---------------------------------------------------------------------------

  Scenario: Results are identical regardless of worker count
    Given a Problem object with a valid two-block block-angular structure
    When I call solver.solve(problem, workers=1) and record the objective value
    And I call solver.solve(problem, workers=8) and record the objective value
    Then both objective values are equal

  # ---------------------------------------------------------------------------
  # Convergence tolerance parameter
  # ---------------------------------------------------------------------------

  Scenario: Solve with a custom convergence tolerance
    Given a Problem object with a valid two-block block-angular structure
    When I call solver.solve(problem, tolerance=1e-4)
    Then the result status is "optimal"
    And the result contains an objective value

  Scenario: Default tolerance of 1e-6 is used when tolerance is not specified
    Given a Problem object with a valid two-block block-angular structure
    When I call solver.solve(problem)
    Then result.tolerance is 1e-6

  # ---------------------------------------------------------------------------
  # Non-optimal outcomes
  # ---------------------------------------------------------------------------

  Scenario Outline: Return non-optimal status for an unsolvable problem
    Given a Problem object describing a "<status>" LP
    When I call solver.solve(problem)
    Then the result status is "<status>"
    And result.variable_values is empty

    Examples:
      | status     |
      | infeasible |
      | unbounded  |

  # ---------------------------------------------------------------------------
  # Iteration limit — partial result
  # ---------------------------------------------------------------------------

  Scenario: Return best feasible solution when iteration limit is reached
    Given a Problem object and a Solver configured with a very low iteration limit
    When I call solver.solve(problem) and the limit is reached before convergence
    Then the result status is "iteration_limit"
    And result.variable_values is a non-empty mapping of variable names to numeric values
    And the result contains an objective value for the incumbent solution
    And the result contains a non-empty diagnostic message

  # ---------------------------------------------------------------------------
  # Input validation and error handling
  # ---------------------------------------------------------------------------

  Scenario: Raise DWSolverInputError for a problem missing required fields
    Given a Problem object that is missing a required structural field
    When I call solver.solve(problem)
    Then a DWSolverInputError is raised
    And the exception message identifies the missing or invalid field

  Scenario: DWSolverInputError is importable from the top-level package
    When I import "DWSolverInputError" from "dwsolver"
    Then the import succeeds without error

  # ---------------------------------------------------------------------------
  # Loading problems from files
  # ---------------------------------------------------------------------------

  Scenario: Load a problem from a valid input file using the library
    Given a valid block-angular LP input file "simple_two_block.json"
    When I call Problem.from_file("simple_two_block.json")
    Then a Problem object is returned with the correct number of blocks
    And I can pass it directly to solver.solve(problem)
