"""Unit tests for benchmarks.generator.make_bench_problem (TDD: written before impl)."""

from __future__ import annotations

import pytest

from dwsolver import Problem, SolveStatus, solve

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_problem(n: int) -> Problem:
    from benchmarks.generator import make_bench_problem

    return make_bench_problem(n)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


def test_make_bench_problem_returns_valid_problem():
    """make_bench_problem(3) returns a Problem without raising."""
    prob = _get_problem(3)
    assert isinstance(prob, Problem)


@pytest.mark.parametrize("n", list(range(1, 21)))
def test_make_bench_problem_block_count(n: int):
    """len(problem.blocks) == n for every valid n."""
    prob = _get_problem(n)
    assert len(prob.blocks) == n


def test_make_bench_problem_identical_blocks():
    """All blocks in an n=5 problem share the same objective coefficients."""
    prob = _get_problem(5)
    objectives = [b.objective for b in prob.blocks]
    for obj in objectives[1:]:
        assert obj == objectives[0]


# ---------------------------------------------------------------------------
# Feasibility (marked slow: these require actual LP solves)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_make_bench_problem_feasibility_n1():
    result = solve(_get_problem(1))
    assert result.status == SolveStatus.OPTIMAL


@pytest.mark.slow
def test_make_bench_problem_feasibility_n5():
    result = solve(_get_problem(5))
    assert result.status == SolveStatus.OPTIMAL


@pytest.mark.slow
def test_make_bench_problem_feasibility_n20():
    result = solve(_get_problem(20))
    assert result.status == SolveStatus.OPTIMAL


# ---------------------------------------------------------------------------
# Reference scaling: obj(n) == n * obj(1)  (up to solver tolerance)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_make_bench_problem_reference_scaling():
    """Objective of n=2 should be 2 × objective of n=1 (symmetric LP)."""
    obj1 = solve(_get_problem(1)).objective
    obj2 = solve(_get_problem(2)).objective
    assert obj1 is not None and obj2 is not None
    assert abs(obj2 - 2 * obj1) < 1e-4


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_make_bench_problem_deterministic():
    """Two calls with the same n return equivalent Problem instances."""
    from benchmarks.generator import make_bench_problem

    p1 = make_bench_problem(4)
    p2 = make_bench_problem(4)
    # Compare via their serialised dict representations
    assert p1.model_dump() == p2.model_dump()


# ---------------------------------------------------------------------------
# Boundary validation
# ---------------------------------------------------------------------------


def test_make_bench_problem_invalid_n_zero():
    from benchmarks.generator import make_bench_problem

    with pytest.raises(ValueError):
        make_bench_problem(0)


def test_make_bench_problem_invalid_n_21():
    from benchmarks.generator import make_bench_problem

    with pytest.raises(ValueError):
        make_bench_problem(21)
