"""Benchmark table formatter and optional chart output."""

from __future__ import annotations

import sys
from pathlib import Path

from benchmarks.models import BenchMatrix, CellError, CellResult

_COL_W = 9  # width of each worker-count column
_LABEL_W = 3  # width of the subproblem-count label column


def _cell_str(cell: CellResult) -> str:
    """Format a single cell as a right-aligned, fixed-width string."""
    if isinstance(cell.status, CellError):
        return cell.status.value.rjust(_COL_W)
    assert cell.elapsed is not None, "optimal cell must have elapsed time"
    return f"{cell.elapsed:.2f}s".rjust(_COL_W)


def format_table(matrix: BenchMatrix) -> str:
    """Render the BenchMatrix as a formatted text table string.

    Output format:
        Workers →        4         8        12        16        20
        Subproblems
          1         0.12s     0.09s     0.08s     0.08s     0.09s
          ...
         20        12.44s     6.81s     4.92s     3.98s     4.10s

    Non-optimal cells display ERR or TIMEOUT instead of a time value.
    """
    config = matrix.config
    worker_counts = config.worker_counts

    # Header row: "Workers →" centred in (label + first-col) chars, then worker counts
    header = "Workers →".center(_LABEL_W + _COL_W) + "".join(
        str(w).rjust(_COL_W) for w in worker_counts
    )
    lines = [header, "Subproblems"]

    for row_idx, n in enumerate(config.subproblems):
        label = str(n).rjust(_LABEL_W)
        cells_str = "".join(_cell_str(cell) for cell in matrix.cells[row_idx])
        lines.append(label + cells_str)

    lines.append("")  # trailing blank line
    return "\n".join(lines) + "\n"


def save_chart(matrix: BenchMatrix, path: Path) -> None:
    """Save a heatmap and line-chart to *path* as a PNG.

    Requires matplotlib. Prints a warning to stderr if matplotlib is absent.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print(
            "Warning: matplotlib is not installed; --save-chart is a no-op.",
            file=sys.stderr,
        )
        return

    config = matrix.config
    subproblems = list(config.subproblems)
    worker_counts = config.worker_counts
    n_sub = len(subproblems)
    n_wkr = len(worker_counts)

    # Build elapsed matrix (NaN for error/timeout cells)
    data = np.full((n_sub, n_wkr), float("nan"))
    for i, row in enumerate(matrix.cells):
        for j, cell in enumerate(row):
            if not isinstance(cell.status, CellError) and cell.elapsed is not None:
                data[i, j] = cell.elapsed

    fig, (ax_heat, ax_line) = plt.subplots(1, 2, figsize=(14, 6))

    # Heatmap
    im = ax_heat.imshow(data, aspect="auto", origin="upper", cmap="viridis_r")
    fig.colorbar(im, ax=ax_heat, label="Elapsed (s)")
    ax_heat.set_xticks(range(n_wkr))
    ax_heat.set_xticklabels([str(w) for w in worker_counts])
    ax_heat.set_yticks(range(n_sub))
    ax_heat.set_yticklabels([str(n) for n in subproblems])
    ax_heat.set_xlabel("Workers")
    ax_heat.set_ylabel("Subproblems")
    ax_heat.set_title("Solve time heatmap (s)")

    # Line chart
    for j, w in enumerate(worker_counts):
        y = data[:, j]
        ax_line.plot(subproblems, y, marker="o", label=f"workers={w}")
    ax_line.set_xlabel("Subproblems")
    ax_line.set_ylabel("Elapsed (s)")
    ax_line.set_title("Solve time vs. subproblem count")
    ax_line.legend()

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Chart saved to {path}", file=sys.stderr)
