"""Unit tests for dwsolver.models — T015.

All tests in this file MUST fail before T012–T014 are implemented.
They validate:
  - Happy paths for all Pydantic v2 models
  - Each error / validation constraint
  - Problem.from_file() with valid, missing, and malformed files
  - SolveStatus string values
  - Result field constraints per status
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from dwsolver.models import (
    Block,
    BlockConstraints,
    Bounds,
    DWSolverInputError,
    LinkingColumns,
    Master,
    Problem,
    Result,
    SolveStatus,
)

# ---------------------------------------------------------------------------
# Helpers — minimal valid building blocks
# ---------------------------------------------------------------------------

VALID_BOUNDS = {"lower": 0.0, "upper": None}
VALID_BOUNDS_FINITE = {"lower": 0.0, "upper": 10.0}

VALID_CONSTRAINTS = {
    "matrix": [[1.0, 1.0]],
    "rhs": [4.0],
    "senses": ["<="],
}

VALID_LINKING = {
    "rows": [0],
    "cols": [0],
    "values": [1.0],
}

VALID_BLOCK = {
    "block_id": "block_0",
    "variable_names": ["x0", "x1"],
    "objective": [1.0, 2.0],
    "bounds": [VALID_BOUNDS, VALID_BOUNDS_FINITE],
    "constraints": VALID_CONSTRAINTS,
    "linking_columns": VALID_LINKING,
}

VALID_MASTER = {
    "constraint_names": ["cap"],
    "rhs": [10.0],
    "senses": ["<="],
}

VALID_PROBLEM_DICT: dict = {
    "schema_version": "1.0",
    "metadata": {"name": "test"},
    "master": VALID_MASTER,
    "blocks": [VALID_BLOCK],
}


def _two_block_problem() -> dict:
    """A valid two-block problem dict (blocks share no variable names)."""
    block1 = {
        "block_id": "block_1",
        "variable_names": ["y0", "y1"],
        "objective": [3.0, 1.0],
        "bounds": [VALID_BOUNDS, VALID_BOUNDS],
        "constraints": {
            "matrix": [[2.0, 1.0]],
            "rhs": [6.0],
            "senses": ["<="],
        },
        "linking_columns": {
            "rows": [0],
            "cols": [1],
            "values": [2.0],
        },
    }
    return {
        "schema_version": "1.0",
        "master": VALID_MASTER,
        "blocks": [VALID_BLOCK, block1],
    }


# ---------------------------------------------------------------------------
# SolveStatus
# ---------------------------------------------------------------------------


class TestSolveStatus:
    def test_string_values(self) -> None:
        assert SolveStatus.OPTIMAL == "optimal"
        assert SolveStatus.INFEASIBLE == "infeasible"
        assert SolveStatus.UNBOUNDED == "unbounded"
        assert SolveStatus.ITERATION_LIMIT == "iteration_limit"

    def test_is_str(self) -> None:
        assert isinstance(SolveStatus.OPTIMAL, str)
        assert isinstance(SolveStatus.INFEASIBLE, str)

    def test_no_error_value(self) -> None:
        """Spec does not define an ERROR value."""
        values = [s.value for s in SolveStatus]
        assert "error" not in values

    def test_all_four_members(self) -> None:
        members = {s.value for s in SolveStatus}
        assert members == {"optimal", "infeasible", "unbounded", "iteration_limit"}


# ---------------------------------------------------------------------------
# DWSolverInputError
# ---------------------------------------------------------------------------


class TestDWSolverInputError:
    def test_is_value_error(self) -> None:
        err = DWSolverInputError("bad input")
        assert isinstance(err, ValueError)

    def test_message_preserved(self) -> None:
        err = DWSolverInputError("something failed")
        assert "something failed" in str(err)


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


class TestBounds:
    def test_defaults(self) -> None:
        b = Bounds()
        assert b.lower == 0.0
        assert b.upper is None

    def test_finite_upper(self) -> None:
        b = Bounds(lower=1.0, upper=5.0)
        assert b.lower == 1.0
        assert b.upper == 5.0

    def test_lower_greater_than_upper_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            Bounds(lower=5.0, upper=3.0)

    def test_equal_bounds_ok(self) -> None:
        b = Bounds(lower=2.0, upper=2.0)
        assert b.lower == b.upper == 2.0

    def test_negative_lower_ok(self) -> None:
        b = Bounds(lower=-10.0, upper=0.0)
        assert b.lower == -10.0

    def test_extra_fields_ignored(self) -> None:
        b = Bounds.model_validate({"lower": 0.0, "upper": None, "extra_field": "ignored"})
        assert not hasattr(b, "extra_field")


# ---------------------------------------------------------------------------
# BlockConstraints
# ---------------------------------------------------------------------------


class TestBlockConstraints:
    def test_valid(self) -> None:
        bc = BlockConstraints.model_validate(VALID_CONSTRAINTS)
        assert len(bc.matrix) == 1
        assert bc.rhs == [4.0]
        assert bc.senses == ["<="]

    def test_all_senses_valid(self) -> None:
        for sense in ("=", "<=", ">="):
            bc = BlockConstraints.model_validate(
                {"matrix": [[1.0]], "rhs": [1.0], "senses": [sense]}
            )
            assert bc.senses[0] == sense

    def test_invalid_sense_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            BlockConstraints.model_validate({"matrix": [[1.0]], "rhs": [1.0], "senses": ["<"]})

    def test_mismatched_rhs_length_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            BlockConstraints.model_validate(
                {"matrix": [[1.0], [2.0]], "rhs": [1.0], "senses": ["<=", "<="]}
            )

    def test_mismatched_senses_length_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            BlockConstraints.model_validate(
                {"matrix": [[1.0]], "rhs": [1.0], "senses": ["<=", ">="]}
            )

    def test_extra_fields_ignored(self) -> None:
        bc = BlockConstraints.model_validate(
            {"matrix": [[1.0]], "rhs": [1.0], "senses": ["="], "unknown": True}
        )
        assert not hasattr(bc, "unknown")


# ---------------------------------------------------------------------------
# LinkingColumns
# ---------------------------------------------------------------------------


class TestLinkingColumns:
    def test_valid(self) -> None:
        lc = LinkingColumns.model_validate(VALID_LINKING)
        assert lc.rows == [0]
        assert lc.cols == [0]
        assert lc.values == [1.0]

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            LinkingColumns.model_validate({"rows": [0, 1], "cols": [0], "values": [1.0]})

    def test_empty_coo_is_valid(self) -> None:
        """A block with no linking is valid (e.g., purely local subproblem)."""
        lc = LinkingColumns.model_validate({"rows": [], "cols": [], "values": []})
        assert lc.rows == []

    def test_extra_fields_ignored(self) -> None:
        lc = LinkingColumns.model_validate({"rows": [0], "cols": [0], "values": [1.0], "meta": "x"})
        assert not hasattr(lc, "meta")


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------


class TestBlock:
    def test_valid(self) -> None:
        b = Block.model_validate(VALID_BLOCK)
        assert b.block_id == "block_0"
        assert len(b.variable_names) == 2

    def test_dimension_mismatch_objective_raises(self) -> None:
        bad = {**VALID_BLOCK, "objective": [1.0]}  # 1 instead of 2
        with pytest.raises((DWSolverInputError, ValidationError)):
            Block.model_validate(bad)

    def test_dimension_mismatch_bounds_raises(self) -> None:
        bad = {**VALID_BLOCK, "bounds": [VALID_BOUNDS]}  # 1 instead of 2
        with pytest.raises((DWSolverInputError, ValidationError)):
            Block.model_validate(bad)

    def test_extra_fields_ignored(self) -> None:
        b = Block.model_validate({**VALID_BLOCK, "unknown_key": 999})
        assert not hasattr(b, "unknown_key")


# ---------------------------------------------------------------------------
# Master
# ---------------------------------------------------------------------------


class TestMaster:
    def test_valid(self) -> None:
        m = Master.model_validate(VALID_MASTER)
        assert m.constraint_names == ["cap"]
        assert m.rhs == [10.0]
        assert m.senses == ["<="]

    def test_all_senses(self) -> None:
        for sense in ("=", "<=", ">="):
            m = Master.model_validate({"constraint_names": ["c"], "rhs": [1.0], "senses": [sense]})
            assert m.senses[0] == sense

    def test_invalid_sense_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            Master.model_validate({"constraint_names": ["c"], "rhs": [1.0], "senses": ["gt"]})

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises((DWSolverInputError, ValidationError)):
            Master.model_validate({"constraint_names": ["c", "d"], "rhs": [1.0], "senses": [">="]})

    def test_senses_length_mismatch_raises(self) -> None:
        # rhs length correct, senses length wrong → triggers the senses check
        with pytest.raises((DWSolverInputError, ValidationError)):
            Master.model_validate({"constraint_names": ["c"], "rhs": [1.0], "senses": ["<=", ">="]})

    def test_extra_fields_ignored(self) -> None:
        m = Master.model_validate({**VALID_MASTER, "extra": True})
        assert not hasattr(m, "extra")


# ---------------------------------------------------------------------------
# Problem — happy paths
# ---------------------------------------------------------------------------


class TestProblemHappy:
    def test_valid_single_block(self) -> None:
        p = Problem.model_validate(VALID_PROBLEM_DICT)
        assert len(p.blocks) == 1
        assert p.schema_version == "1.0"

    def test_valid_two_blocks(self) -> None:
        p = Problem.model_validate(_two_block_problem())
        assert len(p.blocks) == 2

    def test_metadata_defaults_empty(self) -> None:
        d = {**VALID_PROBLEM_DICT}
        del d["metadata"]
        p = Problem.model_validate(d)
        assert p.metadata == {}

    def test_schema_version_1x_ok(self) -> None:
        d = {**VALID_PROBLEM_DICT, "schema_version": "1.5"}
        p = Problem.model_validate(d)
        assert p.schema_version == "1.5"

    def test_extra_fields_ignored(self) -> None:
        p = Problem.model_validate({**VALID_PROBLEM_DICT, "unknown_top": "bye"})
        assert not hasattr(p, "unknown_top")

    def test_problem_is_frozen(self) -> None:
        p = Problem.model_validate(VALID_PROBLEM_DICT)
        with pytest.raises((ValidationError, TypeError)):
            p.schema_version = "2.0"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Problem — validation errors
# ---------------------------------------------------------------------------


class TestProblemValidation:
    def test_no_blocks_raises(self) -> None:
        d = {**VALID_PROBLEM_DICT, "blocks": []}
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)

    def test_duplicate_block_ids_raises(self) -> None:
        block_copy = {**VALID_BLOCK}  # same block_id "block_0"
        d: dict = {
            "schema_version": "1.0",
            "master": VALID_MASTER,
            "blocks": [VALID_BLOCK, block_copy],
        }
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)

    def test_duplicate_variable_names_across_blocks_raises(self) -> None:
        block1 = {
            **VALID_BLOCK,
            "block_id": "block_1",
            # variable_names overlap with VALID_BLOCK ("x0", "x1")
        }
        d = {
            "schema_version": "1.0",
            "master": VALID_MASTER,
            "blocks": [VALID_BLOCK, block1],
        }
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)

    def test_schema_version_2_raises(self) -> None:
        d = {**VALID_PROBLEM_DICT, "schema_version": "2.0"}
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)

    def test_schema_version_non_semver_raises(self) -> None:
        d = {**VALID_PROBLEM_DICT, "schema_version": "v1"}
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)

    def test_linking_row_out_of_range_raises(self) -> None:
        bad_block = {
            **VALID_BLOCK,
            "linking_columns": {
                "rows": [99],  # out of range — master only has 1 constraint (index 0)
                "cols": [0],
                "values": [1.0],
            },
        }
        d = {**VALID_PROBLEM_DICT, "blocks": [bad_block]}
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)

    def test_linking_col_out_of_range_raises(self) -> None:
        bad_block = {
            **VALID_BLOCK,
            "linking_columns": {
                "rows": [0],
                "cols": [99],  # out of range — block only has 2 vars (indices 0-1)
                "values": [1.0],
            },
        }
        d = {**VALID_PROBLEM_DICT, "blocks": [bad_block]}
        with pytest.raises((DWSolverInputError, ValidationError)):
            Problem.model_validate(d)


# ---------------------------------------------------------------------------
# Problem.from_file()
# ---------------------------------------------------------------------------


class TestProblemFromFile:
    def test_valid_file_loads(self, tmp_path: Path) -> None:
        f = tmp_path / "problem.json"
        f.write_text(json.dumps(VALID_PROBLEM_DICT))
        p = Problem.from_file(str(f))
        assert p.schema_version == "1.0"
        assert len(p.blocks) == 1

    def test_from_file_accepts_path_object(self, tmp_path: Path) -> None:
        f = tmp_path / "problem.json"
        f.write_text(json.dumps(VALID_PROBLEM_DICT))
        p = Problem.from_file(f)
        assert isinstance(p, Problem)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DWSolverInputError, match="not found|No such file|missing"):
            Problem.from_file(str(tmp_path / "nonexistent.json"))

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("{not valid json}")
        with pytest.raises(DWSolverInputError):
            Problem.from_file(str(f))

    def test_invalid_schema_raises(self, tmp_path: Path) -> None:
        bad = {"schema_version": "1.0", "master": VALID_MASTER, "blocks": []}
        f = tmp_path / "invalid.json"
        f.write_text(json.dumps(bad))
        with pytest.raises(DWSolverInputError):
            Problem.from_file(str(f))

    def test_fixture_simple_two_block(self) -> None:
        fixture = Path(__file__).parent.parent / "fixtures" / "simple_two_block.json"
        p = Problem.from_file(fixture)
        assert len(p.blocks) == 2

    def test_fixture_infeasible(self) -> None:
        fixture = Path(__file__).parent.parent / "fixtures" / "infeasible_problem.json"
        p = Problem.from_file(fixture)
        assert len(p.blocks) >= 1

    def test_fixture_unbounded(self) -> None:
        fixture = Path(__file__).parent.parent / "fixtures" / "unbounded_problem.json"
        p = Problem.from_file(fixture)
        assert len(p.blocks) >= 1

    def test_oserror_on_read_raises(self, tmp_path: Path) -> None:
        # File must exist so FileNotFoundError is not raised; OSError covers e.g. permission denied
        f = tmp_path / "problem.json"
        f.write_text("{}", encoding="utf-8")
        with (
            patch("pathlib.Path.read_text", side_effect=OSError("permission denied")),
            pytest.raises(DWSolverInputError, match="Error reading"),
        ):
            Problem.from_file(f)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


class TestResult:
    def test_optimal_result(self) -> None:
        r = Result(
            status=SolveStatus.OPTIMAL,
            objective=-9.0,
            variable_values={"x0": 3.0, "x1": 2.0},
            iterations=5,
            tolerance=1e-6,
        )
        assert r.status == SolveStatus.OPTIMAL
        assert r.objective == -9.0
        assert r.variable_values == {"x0": 3.0, "x1": 2.0}
        assert r.iterations == 5
        assert math.isclose(r.tolerance, 1e-6)

    def test_infeasible_result(self) -> None:
        r = Result(
            status=SolveStatus.INFEASIBLE,
            objective=None,
            variable_values={},
            iterations=3,
            tolerance=1e-6,
        )
        assert r.status == SolveStatus.INFEASIBLE
        assert r.objective is None
        assert r.variable_values == {}

    def test_unbounded_result(self) -> None:
        r = Result(
            status=SolveStatus.UNBOUNDED,
            objective=None,
            variable_values={},
            iterations=1,
            tolerance=1e-6,
        )
        assert r.status == SolveStatus.UNBOUNDED

    def test_iteration_limit_result(self) -> None:
        r = Result(
            status=SolveStatus.ITERATION_LIMIT,
            objective=-5.0,
            variable_values={"x0": 1.0},
            iterations=1000,
            tolerance=1e-6,
        )
        assert r.status == SolveStatus.ITERATION_LIMIT
        assert r.objective == -5.0
        assert r.variable_values != {}

    def test_solver_info_default_empty(self) -> None:
        r = Result(
            status=SolveStatus.OPTIMAL,
            objective=0.0,
            variable_values={},
            iterations=0,
            tolerance=1e-6,
        )
        assert r.solver_info == {}

    def test_solver_info_populated(self) -> None:
        r = Result(
            status=SolveStatus.OPTIMAL,
            objective=0.0,
            variable_values={},
            iterations=1,
            tolerance=1e-6,
            solver_info={"wall_time": 0.42},
        )
        assert r.solver_info["wall_time"] == 0.42

    def test_status_is_str(self) -> None:
        r = Result(
            status=SolveStatus.OPTIMAL,
            objective=1.0,
            variable_values={},
            iterations=1,
            tolerance=1e-6,
        )
        assert isinstance(r.status, str)
        assert r.status == "optimal"
