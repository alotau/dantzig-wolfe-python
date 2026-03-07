"""Entry point: python -m benchmarks [OPTIONS]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmarks.models import BenchConfig
from benchmarks.runner import run_benchmark
from benchmarks.table import format_table, save_chart


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m benchmarks",
        description="Dantzig-Wolfe performance benchmark: workers vs. subproblems",
    )
    parser.add_argument(
        "--repeats", type=int, default=1, metavar="N",
        help="Timed runs per cell; minimum is reported (default: 1)",
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0, metavar="SECONDS",
        help="Per-cell wall-clock timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--save-chart", type=Path, default=None, metavar="PATH", dest="save_chart",
        help="Write heatmap+line-chart PNG to this path",
    )
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")

    config = BenchConfig(
        repeats=args.repeats,
        timeout=args.timeout,
        save_chart=args.save_chart,
    )

    try:
        matrix = run_benchmark(config)
    except Exception as exc:
        print(f"Fatal error during benchmark: {exc}", file=sys.stderr)
        sys.exit(2)

    print(format_table(matrix))

    if args.save_chart is not None:
        save_chart(matrix, args.save_chart)


if __name__ == "__main__":
    main()

