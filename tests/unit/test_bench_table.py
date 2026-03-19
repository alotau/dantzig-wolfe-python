"""Unit tests for benchmarks.table.format_table (TDD: written before impl)."""

from __future__ import annotations

import re

import pytest
from benchmarks.models import BenchConfig, BenchMatrix, CellError, CellResult
from dwsolver import SolveStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_optimal_matrix() -> BenchMatrix:
    config = BenchConfig()
    cells = [
        [
            CellResult(
                n_blocks=n,
                workers=w,
                elapsed=0.12,
                status=SolveStatus.OPTIMAL,
                iterations=5,
            )
            for w in config.worker_counts
        ]
        for n in config.subproblems
    ]
    return BenchMatrix(cells=cells, config=config)


def _make_matrix_with_error(err_type: CellError) -> BenchMatrix:
    mat = _make_optimal_matrix()
    mat.cells[0][0] = CellResult(
        n_blocks=1,
        workers=4,
        elapsed=None,
        status=err_type,
        iterations=None,
    )
    return mat


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_format_table_returns_string():
    from benchmarks.table import format_table

    result = format_table(_make_optimal_matrix())
    assert isinstance(result, str)


def test_format_table_header_contains_worker_counts():
    from benchmarks.table import format_table

    result = format_table(_make_optimal_matrix())
    header_line = next(line for line in result.splitlines() if "Workers" in line)
    for w in [4, 8, 12, 16, 20]:
        assert str(w) in header_line


def test_format_table_has_20_data_rows():
    from benchmarks.table import format_table

    result = format_table(_make_optimal_matrix())
    lines = result.splitlines()
    data_rows = [
        line
        for line in lines
        if line and line[0].isspace() and line.strip() and line.strip()[0].isdigit()
    ]
    assert len(data_rows) == 20


def test_format_table_optimal_cell_matches_pattern():
    """All 100 cells in an all-optimal matrix match the time pattern."""
    from benchmarks.table import format_table

    result = format_table(_make_optimal_matrix())
    matches = re.findall(r"\d+\.\d{2}s", result)
    assert len(matches) == 100


def test_format_table_err_cell_displayed():
    from benchmarks.table import format_table

    result = format_table(_make_matrix_with_error(CellError.ERROR))
    assert "ERR" in result


def test_format_table_timeout_cell_displayed():
    from benchmarks.table import format_table

    result = format_table(_make_matrix_with_error(CellError.TIMEOUT))
    assert "TIMEOUT" in result


def test_format_table_all_optimal_no_err_tokens():
    from benchmarks.table import format_table

    result = format_table(_make_optimal_matrix())
    assert "ERR" not in result
    assert "TIMEOUT" not in result


# ---------------------------------------------------------------------------
# T002 — save_chart produces a PNG when matplotlib is installed
# ---------------------------------------------------------------------------


def test_save_chart_writes_png_when_matplotlib_installed(tmp_path):
    """save_chart() must create a PNG file at the given path.

    Requires the optional [charts] extras group (``pip install dwsolver[charts]``).
    This test is intentionally skipped when matplotlib is absent.
    """
    pytest.importorskip("matplotlib", reason="requires dwsolver[charts]")

    from benchmarks.table import save_chart

    output_png = tmp_path / "bench.png"
    save_chart(_make_optimal_matrix(), output_png)

    assert output_png.exists(), "save_chart() did not create a PNG file"
    assert output_png.stat().st_size > 0, "PNG file is empty"
