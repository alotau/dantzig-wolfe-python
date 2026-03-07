"""Unit tests for tests.synthetic — cross-validation of D-W decomposition vs HiGHS.

Covers:
  - test_cross_validate_single: seed=42 single cross-validation (US1 scenario 3)
  - test_cli_smoke: CLI entry point produces valid JSON + finite objective (SC-006)
  - test_determinism: same seed gives bit-for-bit identical output (US1 scenario 2)
  - TestSC002Synthetic: 12-seed parametrized cross-validation suite (US2)
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from dwsolver.models import Problem, SolveStatus
from dwsolver.solver import solve
from tests.synthetic import (
    CROSS_VALIDATION_ABS_TOL,
    SYNTHETIC_CASES,
    SyntheticCase,
    generate_problem,
)

# ---------------------------------------------------------------------------
# US1 — single cross-validation (T007)
# ---------------------------------------------------------------------------


def test_cross_validate_single() -> None:
    """seed=42: DW objective matches HiGHS reference within CROSS_VALIDATION_ABS_TOL."""
    gp = generate_problem(seed=42)

    assert gp.problem is not None
    assert math.isfinite(gp.reference_objective)

    result = solve(gp.problem)

    assert result.status == SolveStatus.OPTIMAL, (
        f"dwsolver returned status {result.status!r} for seed=42"
    )
    assert result.objective is not None
    assert abs(result.objective - gp.reference_objective) < CROSS_VALIDATION_ABS_TOL, (
        f"Objective mismatch: DW={result.objective:.8f}, "
        f"HiGHS={gp.reference_objective:.8f}, "
        f"diff={abs(result.objective - gp.reference_objective):.2e}, "
        f"tol={CROSS_VALIDATION_ABS_TOL:.2e}"
    )


# ---------------------------------------------------------------------------
# US1 — CLI smoke-test (T006a) — SC-006
# ---------------------------------------------------------------------------


def test_cli_smoke(tmp_path: Path) -> None:
    """CLI exits 0, writes valid dwsolver JSON, prints a finite float to stdout."""
    out_file = tmp_path / "out.json"
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "synthetic.py"),
                "--seed",
                "42",
                "--output",
                str(out_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"CLI smoke test timed out after {exc.timeout} seconds; "
            f"stdout: {exc.stdout!r}; stderr: {exc.stderr!r}"
        )
    assert proc.returncode == 0, f"CLI exited {proc.returncode}; stderr: {proc.stderr!r}"

    # stdout must contain a parseable finite float
    stdout_line = proc.stdout.strip()
    assert stdout_line, "CLI produced no stdout"
    obj_val = float(stdout_line)
    assert math.isfinite(obj_val), f"CLI printed non-finite value: {stdout_line!r}"

    # output file must be a valid Problem JSON
    assert out_file.exists(), "CLI did not write output file"
    Problem.model_validate_json(out_file.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# US1 — determinism (T007a) — US1 scenario 2
# ---------------------------------------------------------------------------


def test_determinism() -> None:
    """Same seed produces bit-for-bit identical Problem and reference objective."""
    gp1 = generate_problem(seed=1)
    gp2 = generate_problem(seed=1)

    assert gp1.reference_objective == gp2.reference_objective, (
        f"Determinism failure: {gp1.reference_objective} != {gp2.reference_objective}"
    )
    assert gp1.problem.model_dump() == gp2.problem.model_dump(), (
        "Determinism failure: same seed produced different Problem structure"
    )


# ---------------------------------------------------------------------------
# US2 — parametrized 12-seed cross-validation suite (T009)
# ---------------------------------------------------------------------------


class TestSC002Synthetic:
    """SC-002: 12-seed parametrized cross-validation suite.

    Each test ID is the SyntheticCase.label (e.g. "seed=6-4blk-5var-4mc").
    """

    @pytest.mark.parametrize("case", SYNTHETIC_CASES, ids=[c.label for c in SYNTHETIC_CASES])
    def test_cross_validate(self, case: SyntheticCase) -> None:
        """DW objective matches HiGHS reference within CROSS_VALIDATION_ABS_TOL for each seed."""
        gp = generate_problem(
            seed=case.seed,
            num_blocks=case.num_blocks,
            vars_per_block=case.vars_per_block,
            local_constraints=case.local_constraints,
            master_constraints=case.master_constraints,
        )

        assert math.isfinite(gp.reference_objective)

        result = solve(gp.problem)

        assert result.status == SolveStatus.OPTIMAL, (
            f"[{case.label}] dwsolver returned {result.status!r}"
        )
        assert result.objective is not None
        assert abs(result.objective - gp.reference_objective) < CROSS_VALIDATION_ABS_TOL, (
            f"[{case.label}] Objective mismatch: "
            f"DW={result.objective:.8f}, HiGHS={gp.reference_objective:.8f}, "
            f"diff={abs(result.objective - gp.reference_objective):.2e}"
        )
