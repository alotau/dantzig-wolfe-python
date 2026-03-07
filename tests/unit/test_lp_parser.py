"""Unit tests for lp_parser module — T004 + T012 + T016.

Tests cover:
  T004: parse_master, parse_subproblem, infer_linking, resolve_block_objective
        (including FR-009 Generals/Binary silently-ignored case)
  T012: Problem.from_lp and Problem.from_lp_text (cross-format assertion)
  T016: all DWSolverInputError error paths

The four_sea fixture files in tests/fixtures/four_sea/ are used for
integration-level unit tests (parse real files, validate structure and counts).
"""

from __future__ import annotations

import pytest

from dwsolver.lp_parser import (
    MasterLP,
    SubproblemLP,
    LinkingSpec,
    assemble_problem,
    infer_linking,
    load_problem_from_lp,
    parse_master,
    parse_subproblem,
    resolve_block_objective,
)
from dwsolver.models import DWSolverInputError, Problem

from pathlib import Path

# ---------------------------------------------------------------------------
# Fixture files
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_FOUR_SEA_DIR = _FIXTURES_DIR / "four_sea"

MASTER_CPLEX = _FOUR_SEA_DIR / "master.cplex"
SUBPROB_1 = _FOUR_SEA_DIR / "subprob_1.cplex"
SUBPROB_2 = _FOUR_SEA_DIR / "subprob_2.cplex"
SUBPROB_3 = _FOUR_SEA_DIR / "subprob_3.cplex"
SUBPROB_4 = _FOUR_SEA_DIR / "subprob_4.cplex"

ALL_SUBPROBS = [SUBPROB_1, SUBPROB_2, SUBPROB_3, SUBPROB_4]

# ---------------------------------------------------------------------------
# Minimal synthetic LP text for fast unit tests
# ---------------------------------------------------------------------------

_SIMPLE_MASTER_LP = """\
Minimize
 obj: x1 + 2 x2 + 3 y1 + 4 y2
Subject To
 c1: x1 + y1 <= 10
 c2: x2 + y2 = 5
End
"""

_SIMPLE_SUB1_LP = """\
Minimize
 obj1: x1 + 2 x2
Subject To
 lc1: x1 - x2 >= 0
Bounds
 0 <= x1 <= 5
 0 <= x2 <= 5
End
"""

_SIMPLE_SUB2_LP = """\
Minimize
 obj2: 3 y1 + 4 y2
Subject To
 lc2: y1 + y2 <= 4
Bounds
 0 <= y1 <= 3
 0 <= y2 <= 3
End
"""

# Subproblem with a Generals section (must be silently ignored — FR-009).
_SUB_WITH_GENERALS_LP = """\
Minimize
Subject To
 c1: x1 >= 0
Bounds
 0 <= x1 <= 10
 0 <= x2 <= 10
Generals
 x1 x2
End
"""

# Subproblem with Maximize direction.
_SUB_MAXIMIZE_LP = """\
Maximize
 obj: 3 x1
Subject To
 c1: x1 <= 10
Bounds
 0 <= x1 <= 10
End
"""

# Master with Maximize and constant term.
_MASTER_MAXIMIZE_LP = """\
Maximize
 m_obj: x1 + x2
\\* constant term = 5 *\\
Subject To
 c1: x1 + x2 <= 8
End
"""

# Master with no Subject To section.
_MASTER_NO_SUBJECT_TO = """\
Minimize
 obj: x1
End
"""

# Master with empty Subject To.
_MASTER_EMPTY_SUBJECT_TO = """\
Minimize
 obj: x1
Subject To
End
"""

# Subproblem with no Bounds section.
_SUB_NO_BOUNDS = """\
Minimize
 obj: x1
Subject To
 c1: x1 >= 0
End
"""

# Subproblem with Bounds section but no variables.
_SUB_EMPTY_BOUNDS = """\
Minimize
Subject To
Bounds
End
"""


# ===========================================================================
# T004 — parse_master
# ===========================================================================


class TestParseMaster:
    def test_simple_constraint_count(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert len(master.constraint_names) == 2

    def test_simple_constraint_names(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert master.constraint_names == ["c1", "c2"]

    def test_simple_senses(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert master.senses == ["<=", "="]

    def test_simple_rhs(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert master.rhs == [10.0, 5.0]

    def test_simple_objective_coefficients(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert master.objective == {"x1": 1.0, "x2": 2.0, "y1": 3.0, "y2": 4.0}

    def test_simple_row_coefficients(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert master.row_coefficients[0] == {"x1": 1.0, "y1": 1.0}
        assert master.row_coefficients[1] == {"x2": 1.0, "y2": 1.0}

    def test_no_obj_constant_when_absent(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        assert master.obj_constant == 0.0

    def test_maximize_negates_objective(self) -> None:
        master = parse_master(_MASTER_MAXIMIZE_LP)
        # x1 + x2 → negated → -1.0, -1.0
        assert master.objective["x1"] == pytest.approx(-1.0)
        assert master.objective["x2"] == pytest.approx(-1.0)

    def test_constant_term_extracted(self) -> None:
        master = parse_master(_MASTER_MAXIMIZE_LP)
        assert master.obj_constant == pytest.approx(5.0)

    # --- four_sea ---

    @pytest.mark.slow
    def test_four_sea_constraint_count(self) -> None:
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        assert len(master.constraint_names) == 2

    @pytest.mark.slow
    def test_four_sea_constraint_names(self) -> None:
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        assert "Arrival_Rate(SEA,13)" in master.constraint_names
        assert "Arrival_Rate(SEA,14)" in master.constraint_names

    @pytest.mark.slow
    def test_four_sea_obj_constant(self) -> None:
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        assert master.obj_constant == pytest.approx(160.0)

    @pytest.mark.slow
    def test_four_sea_objective_has_sea_coefficients(self) -> None:
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        # SEA arrival vars have coeff -2.0
        assert master.objective.get("w(AC8_7,SEA,199)") == pytest.approx(-2.0)

    @pytest.mark.slow
    def test_four_sea_objective_has_las_coefficients(self) -> None:
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        # LAS departure vars have coeff +1.0
        assert master.objective.get("w(AC8_7,LAS,20)") == pytest.approx(1.0)


# ===========================================================================
# T004 — parse_subproblem
# ===========================================================================


class TestParseSubproblem:
    def test_simple_variable_names(self) -> None:
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        assert sub.variable_names == ["x1", "x2"]

    def test_simple_bounds(self) -> None:
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        assert sub.bounds == [(0.0, 5.0), (0.0, 5.0)]

    def test_simple_block_id(self) -> None:
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        assert sub.block_id == "block_0"

    def test_simple_constraint_count(self) -> None:
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        assert len(sub.constraints_names) == 1
        assert sub.constraints_names[0] == "lc1"

    def test_simple_constraint_direction_and_sense(self) -> None:
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        assert sub.constraints_senses == [">="]
        assert sub.constraints_rhs == [0.0]

    def test_simple_constraint_matrix_shape(self) -> None:
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        # lc1: x1 - x2 >= 0  → row [1.0, -1.0]
        assert len(sub.constraints_matrix) == 1
        assert sub.constraints_matrix[0] == pytest.approx([1.0, -1.0])

    def test_generals_section_silently_ignored(self) -> None:
        """FR-009: Generals/Binary section must not affect variable list."""
        sub = parse_subproblem(_SUB_WITH_GENERALS_LP, "block_0")
        # Variables still come only from Bounds.
        assert set(sub.variable_names) == {"x1", "x2"}
        # No extra fields or errors.

    def test_maximize_direction_negates_objective(self) -> None:
        sub = parse_subproblem(_SUB_MAXIMIZE_LP, "block_0")
        assert sub.objective.get("x1") == pytest.approx(-3.0)

    def test_free_bounds(self) -> None:
        lp = "Minimize\nSubject To\nBounds\n x1 free\nEnd\n"
        sub = parse_subproblem(lp, "block_0")
        assert sub.bounds[0][0] == float("-inf")
        assert sub.bounds[0][1] is None

    def test_lower_only_bounds(self) -> None:
        lp = "Minimize\nSubject To\nBounds\n x1 >= 2\nEnd\n"
        sub = parse_subproblem(lp, "block_0")
        assert sub.bounds[0] == (2.0, None)

    def test_upper_only_bounds(self) -> None:
        lp = "Minimize\nSubject To\nBounds\n x1 <= 7\nEnd\n"
        sub = parse_subproblem(lp, "block_0")
        assert sub.bounds[0] == (0.0, 7.0)

    # --- four_sea ---

    @pytest.mark.slow
    def test_four_sea_sub1_variable_count(self) -> None:
        sub = parse_subproblem(SUBPROB_1.read_text(encoding="utf-8"), "block_0")
        # 220 variables for block_1 in the reference (AC8_7 + AC7_6 aircraft)
        assert len(sub.variable_names) == 440

    @pytest.mark.slow
    def test_four_sea_sub1_all_bounds_zero_to_one(self) -> None:
        sub = parse_subproblem(SUBPROB_1.read_text(encoding="utf-8"), "block_0")
        assert all(lb == 0.0 and ub == 1.0 for lb, ub in sub.bounds)

    @pytest.mark.slow
    def test_four_sea_sub1_objective_initially_empty_coeff(self) -> None:
        """Subproblem objective has only 1 variable — will be replaced by master."""
        sub = parse_subproblem(SUBPROB_1.read_text(encoding="utf-8"), "block_0")
        # The subproblem's own Minimize has just one var (w(AC8_7,SEA,199):1.0)
        assert sub.objective.get("w(AC8_7,SEA,199)") == pytest.approx(1.0)


# ===========================================================================
# T004 — infer_linking + resolve_block_objective
# ===========================================================================


class TestInferLinking:
    def _master_and_sub(self) -> tuple[MasterLP, SubproblemLP]:
        master = parse_master(_SIMPLE_MASTER_LP)
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        return master, sub

    def test_linking_rows_are_valid_master_indices(self) -> None:
        master, sub = self._master_and_sub()
        linking = infer_linking(master, sub)
        n_constraints = len(master.constraint_names)
        assert all(0 <= r < n_constraints for r in linking.rows)

    def test_linking_cols_are_valid_var_indices(self) -> None:
        master, sub = self._master_and_sub()
        linking = infer_linking(master, sub)
        n_vars = len(sub.variable_names)
        assert all(0 <= c < n_vars for c in linking.cols)

    def test_simple_linking_c1_picks_x1(self) -> None:
        """c1: x1 + y1 <= 10 — sub1 owns x1 (col index 0) at row 0."""
        master, sub = self._master_and_sub()
        linking = infer_linking(master, sub)
        pairs = list(zip(linking.rows, linking.cols, linking.values))
        # x1 belongs to sub1 (block_0); should appear at (row=0, col=0, val=1.0)
        assert (0, 0, 1.0) in pairs

    def test_empty_linking_when_no_overlap(self) -> None:
        """A subproblem with variables that don't appear in master constraints."""
        master = parse_master(_SIMPLE_MASTER_LP)
        # Subproblem with a variable "zz" not in master rows.
        lp = "Minimize\nSubject To\nBounds\n 0 <= zz <= 1\nEnd\n"
        sub = parse_subproblem(lp, "block_zz")
        linking = infer_linking(master, sub)
        assert linking.rows == []
        assert linking.cols == []
        assert linking.values == []

    @pytest.mark.slow
    def test_four_sea_linking_non_empty(self) -> None:
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        sub = parse_subproblem(SUBPROB_1.read_text(encoding="utf-8"), "block_0")
        linking = infer_linking(master, sub)
        assert len(linking.rows) > 0


class TestResolveBlockObjective:
    def test_master_takes_precedence_when_non_zero(self) -> None:
        """Master has non-zero coefficients → use master (not subproblem)."""
        master = parse_master(_SIMPLE_MASTER_LP)
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        obj = resolve_block_objective(master, sub)
        # Master has x1:1.0, x2:2.0 → should match those
        assert len(obj) == len(sub.variable_names)
        idx = sub.variable_names.index("x1")
        assert obj[idx] == pytest.approx(1.0)
        idx2 = sub.variable_names.index("x2")
        assert obj[idx2] == pytest.approx(2.0)

    def test_fallback_to_subproblem_when_master_zero(self) -> None:
        """Master has no objective for this block's vars → use subproblem."""
        master_lp = "Minimize\nSubject To\n c1: x1 <= 5\nEnd\n"
        master = parse_master(master_lp)
        # Sub has x1 + 2 x2 as REAL objective; master doesn't mention x1/x2
        sub_lp = (
            "Minimize\n obj: x1 + 2 x2\nSubject To\nBounds\n"
            " 0 <= x1 <= 1\n 0 <= x2 <= 1\nEnd\n"
        )
        sub = parse_subproblem(sub_lp, "block_0")
        obj = resolve_block_objective(master, sub)
        assert obj[sub.variable_names.index("x1")] == pytest.approx(1.0)
        assert obj[sub.variable_names.index("x2")] == pytest.approx(2.0)

    def test_length_equals_variable_count(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        sub = parse_subproblem(_SIMPLE_SUB1_LP, "block_0")
        obj = resolve_block_objective(master, sub)
        assert len(obj) == len(sub.variable_names)

    @pytest.mark.slow
    def test_four_sea_objective_uses_master(self) -> None:
        """four_sea: master has non-zero coefficients for all block vars."""
        master = parse_master(MASTER_CPLEX.read_text(encoding="utf-8"))
        sub = parse_subproblem(SUBPROB_1.read_text(encoding="utf-8"), "block_0")
        obj = resolve_block_objective(master, sub)
        # AC8_7 SEA vars have coeff -2.0 in master
        idx = sub.variable_names.index("w(AC8_7,SEA,199)")
        assert obj[idx] == pytest.approx(-2.0)


# ===========================================================================
# T016 — DWSolverInputError error paths
# ===========================================================================


class TestErrorPaths:

    # --- parse_master errors ---

    def test_master_no_subject_to(self) -> None:
        with pytest.raises(DWSolverInputError, match="Subject To"):
            parse_master(_MASTER_NO_SUBJECT_TO)

    def test_master_empty_subject_to(self) -> None:
        with pytest.raises(DWSolverInputError, match="no coupling constraints"):
            parse_master(_MASTER_EMPTY_SUBJECT_TO)

    # --- parse_subproblem errors ---

    def test_subproblem_no_bounds(self) -> None:
        with pytest.raises(DWSolverInputError, match="Bounds"):
            parse_subproblem(_SUB_NO_BOUNDS, "block_0")

    def test_subproblem_empty_bounds(self) -> None:
        with pytest.raises(DWSolverInputError, match="no variables"):
            parse_subproblem(_SUB_EMPTY_BOUNDS, "block_0")

    # --- assemble_problem errors ---

    def test_assemble_empty_subs(self) -> None:
        master = parse_master(_SIMPLE_MASTER_LP)
        with pytest.raises(DWSolverInputError, match="subproblem"):
            assemble_problem(master, [])

    def test_assemble_duplicate_variable_across_blocks(self) -> None:
        """Variable appearing in two subproblems raises DWSolverInputError."""
        # Both subs declare x1.
        dup_sub_lp = (
            "Minimize\nSubject To\n c1: x1 >= 0\n"
            "Bounds\n 0 <= x1 <= 5\nEnd\n"
        )
        # Build a master that references x1 in coupling constraints.
        master_lp = "Minimize\n obj: x1\nSubject To\n c1: x1 <= 10\nEnd\n"
        master = parse_master(master_lp)
        sub_a = parse_subproblem(dup_sub_lp, "block_0")
        sub_b = parse_subproblem(dup_sub_lp, "block_1")
        with pytest.raises(DWSolverInputError, match="x1"):
            assemble_problem(master, [sub_a, sub_b])

    def test_assemble_master_var_not_in_any_subproblem(self) -> None:
        """Coupling constraint variable absent from all Bounds raises error."""
        # Master references "phantom_var" in a constraint; no sub declares it.
        master_lp = (
            "Minimize\n obj: phantom_var\n"
            "Subject To\n c1: phantom_var <= 10\nEnd\n"
        )
        sub_lp = (
            "Minimize\nSubject To\n c1: x1 >= 0\n"
            "Bounds\n 0 <= x1 <= 5\nEnd\n"
        )
        master = parse_master(master_lp)
        sub = parse_subproblem(sub_lp, "block_0")
        with pytest.raises(DWSolverInputError, match="phantom_var"):
            assemble_problem(master, [sub])

    # --- load_problem_from_lp errors ---

    def test_missing_master_file(self, tmp_path: Path) -> None:
        with pytest.raises(DWSolverInputError, match="not found"):
            load_problem_from_lp(
                tmp_path / "nonexistent_master.cplex",
                [tmp_path / "nonexistent_sub.cplex"],
            )

    def test_missing_subproblem_file(self, tmp_path: Path) -> None:
        master_file = tmp_path / "master.cplex"
        master_file.write_text(_SIMPLE_MASTER_LP, encoding="utf-8")
        with pytest.raises(DWSolverInputError, match="not found"):
            load_problem_from_lp(
                master_file,
                [tmp_path / "nonexistent_sub.cplex"],
            )

    # --- Full end-to-end assembly ---

    @pytest.mark.slow
    def test_four_sea_assembles_without_error(self) -> None:
        problem = load_problem_from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        assert isinstance(problem, Problem)
        assert len(problem.blocks) == 4

    @pytest.mark.slow
    def test_four_sea_block_variable_counts(self) -> None:
        problem = load_problem_from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        # block_0 gets the __objective_constant__ injected → 440+1=441
        assert len(problem.blocks[0].variable_names) == 441
        for block in problem.blocks[1:]:
            assert len(block.variable_names) == 440

    @pytest.mark.slow
    def test_four_sea_objective_constant_variable_in_block0(self) -> None:
        problem = load_problem_from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        assert "__objective_constant__" in problem.blocks[0].variable_names

    @pytest.mark.slow
    def test_four_sea_objective_constant_coeff_is_160(self) -> None:
        problem = load_problem_from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        idx = problem.blocks[0].variable_names.index("__objective_constant__")
        assert problem.blocks[0].objective[idx] == pytest.approx(160.0)

    @pytest.mark.slow
    def test_four_sea_objective_constant_bounds_pinned(self) -> None:
        problem = load_problem_from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        idx = problem.blocks[0].variable_names.index("__objective_constant__")
        b = problem.blocks[0].bounds[idx]
        assert b.lower == pytest.approx(1.0)
        assert b.upper == pytest.approx(1.0)


# ===========================================================================
# T012 — Problem.from_lp and Problem.from_lp_text
# ===========================================================================


class TestProblemFromLP:
    """Tests for the Problem public factory methods that load CPLEX LP files."""

    def test_from_lp_text_simple_creates_problem(self) -> None:
        problem = Problem.from_lp_text(
            _SIMPLE_MASTER_LP, [_SIMPLE_SUB1_LP, _SIMPLE_SUB2_LP]
        )
        assert isinstance(problem, Problem)
        assert len(problem.blocks) == 2

    def test_from_lp_text_block_ids_are_zero_indexed(self) -> None:
        problem = Problem.from_lp_text(
            _SIMPLE_MASTER_LP, [_SIMPLE_SUB1_LP, _SIMPLE_SUB2_LP]
        )
        assert problem.blocks[0].block_id == "block_0"
        assert problem.blocks[1].block_id == "block_1"

    def test_from_lp_text_master_rhs_transferred(self) -> None:
        problem = Problem.from_lp_text(
            _SIMPLE_MASTER_LP, [_SIMPLE_SUB1_LP, _SIMPLE_SUB2_LP]
        )
        assert problem.master.rhs == [10.0, 5.0]

    def test_from_lp_text_propagates_parse_error(self) -> None:
        from dwsolver.models import DWSolverInputError

        with pytest.raises(DWSolverInputError):
            Problem.from_lp_text(_MASTER_NO_SUBJECT_TO, [_SIMPLE_SUB1_LP])

    def test_from_lp_text_propagates_assembly_error(self) -> None:
        from dwsolver.models import DWSolverInputError

        with pytest.raises(DWSolverInputError):
            Problem.from_lp_text(_SIMPLE_MASTER_LP, [])

    @pytest.mark.slow
    def test_from_lp_creates_four_sea_problem(self) -> None:
        problem = Problem.from_lp(str(MASTER_CPLEX), [str(p) for p in ALL_SUBPROBS])
        assert isinstance(problem, Problem)
        assert len(problem.blocks) == 4

    @pytest.mark.slow
    def test_from_lp_accepts_path_objects(self) -> None:
        problem = Problem.from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        assert isinstance(problem, Problem)

    @pytest.mark.slow
    def test_from_lp_propagates_file_not_found(self, tmp_path: Path) -> None:
        from dwsolver.models import DWSolverInputError

        with pytest.raises(DWSolverInputError, match="not found"):
            Problem.from_lp(tmp_path / "ghost.cplex", [SUBPROB_1])

    @pytest.mark.slow
    def test_cross_format_objective_matches_json(self) -> None:
        """SC-002: LP and JSON inputs must produce the same solve objective.

        abs(lp_obj - json_obj) < 1e-6 for the four_sea reference problem.
        """
        from dwsolver.solver import solve

        _JSON_FIXTURE = _FIXTURES_DIR / "ref_four_sea.json"
        if not _JSON_FIXTURE.exists():
            pytest.skip("ref_four_sea.json not available")

        lp_problem = Problem.from_lp(MASTER_CPLEX, ALL_SUBPROBS)
        json_problem = Problem.from_file(_JSON_FIXTURE)

        lp_result = solve(lp_problem)
        json_result = solve(json_problem)

        assert abs(lp_result.objective - json_result.objective) < 1e-6, (
            f"Objective mismatch: LP={lp_result.objective}, "
            f"JSON={json_result.objective}"
        )
