"""Benchmark data model types — BenchConfig, CellResult, BenchMatrix, CellError."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dwsolver import SolveStatus


class CellError(Enum):
    """Non-solve terminal states for a benchmark cell."""

    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class CellResult:
    """Outcome of a single (n_blocks, workers) benchmark cell."""

    n_blocks: int
    workers: int
    elapsed: float | None
    status: SolveStatus | CellError
    iterations: int | None


@dataclass
class BenchConfig:
    """Runtime configuration for a benchmark run, populated from CLI flags."""

    subproblems: range = field(default_factory=lambda: range(1, 21))
    worker_counts: list[int] = field(default_factory=lambda: [4, 8, 12, 16, 20])
    repeats: int = 1
    timeout: float = 120.0
    save_chart: Path | None = None


@dataclass
class BenchMatrix:
    """The full result matrix: one row per subproblem count, one column per worker count."""

    cells: list[list[CellResult]]
    config: BenchConfig

    def __post_init__(self) -> None:
        n_sub = len(self.config.subproblems)
        n_wkr = len(self.config.worker_counts)
        if len(self.cells) != n_sub:
            raise AssertionError(
                f"BenchMatrix row count mismatch: expected {n_sub}, got {len(self.cells)}"
            )
        for i, row in enumerate(self.cells):
            if len(row) != n_wkr:
                raise AssertionError(
                    f"BenchMatrix row {i} column count mismatch: expected {n_wkr}, got {len(row)}"
                )
