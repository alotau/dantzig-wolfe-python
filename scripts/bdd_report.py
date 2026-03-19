#!/usr/bin/env python3
"""BDD scenario completeness reporter.

Reads Gherkin feature files (to count scenario definitions) and a JUnit XML
report (to count passed / total runtime instances), then writes:

  - A shields.io Endpoint v1 badge JSON file (e.g. bdd-badge.json)
  - A Markdown traceability table (e.g. bdd-traceability.md)

Usage
-----
    python scripts/bdd_report.py \\
        --junit .bdd-results.xml \\
        --features specs/001-gherkin-bdd-specs/features \\
        --badge-output bdd-badge.json \\
        --report-output bdd-traceability.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Feature file parsing
# ---------------------------------------------------------------------------

_SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:", re.MULTILINE)


def count_scenarios_in_file(path: Path) -> int:
    """Return the number of Scenario / Scenario Outline definitions in *path*."""
    return len(_SCENARIO_RE.findall(path.read_text(encoding="utf-8")))


def count_scenarios_in_dir(features_dir: Path) -> dict[str, int]:
    """Return ``{basename: count}`` for every ``.feature`` file in *features_dir*."""
    return {f.name: count_scenarios_in_file(f) for f in sorted(features_dir.glob("*.feature"))}


# ---------------------------------------------------------------------------
# JUnit XML parsing
# ---------------------------------------------------------------------------

# classname pattern: tests.bdd.steps.test_<feature_stem>
_CLASSNAME_RE = re.compile(r"test_([^.]+)$")


def _feature_stem_from_classname(classname: str) -> str:
    """Extract the feature file stem from a pytest-bdd classname.

    Example: ``"tests.bdd.steps.test_cli_usage"`` → ``"cli_usage"``
    """
    m = _CLASSNAME_RE.search(classname)
    if m:
        return m.group(1)
    # Fallback: strip leading 'test_' from last segment
    segment = classname.rsplit(".", 1)[-1]
    return segment[5:] if segment.startswith("test_") else segment


def parse_junit_xml(junit_path: Path) -> dict[str, tuple[int, int]]:
    """Parse a JUnit XML file and return ``{feature_stem: (passed, total)}``.

    A test case is considered *passed* when it has no ``<failure>`` or
    ``<error>`` child elements.
    """
    tree = ET.parse(junit_path)  # noqa: S314 — local file, not network input
    root = tree.getroot()

    # Support both <testsuite> at root and <testsuites><testsuite> nesting.
    testcases = root.findall(".//testcase")

    counts: dict[str, list[int]] = {}  # stem → [passed, total]
    for tc in testcases:
        classname = tc.get("classname", "")
        if not classname:
            continue
        stem = _feature_stem_from_classname(classname)
        if stem not in counts:
            counts[stem] = [0, 0]
        counts[stem][1] += 1  # total
        if tc.find("failure") is None and tc.find("error") is None:
            counts[stem][0] += 1  # passed

    return {stem: (vals[0], vals[1]) for stem, vals in counts.items()}


# ---------------------------------------------------------------------------
# Badge JSON
# ---------------------------------------------------------------------------


def build_badge_json(passed: int, total: int) -> dict[str, object]:
    """Build a shields.io Endpoint v1 badge dict for BDD scenario completeness.

    Colour rules (from contracts/badges.md):
      * passed == total  → brightgreen
      * passed/total ≥ 0.9 → yellow
      * otherwise → red
    """
    if total == 0 or passed == total:
        color = "brightgreen"
    elif passed / total >= 0.9:
        color = "yellow"
    else:
        color = "red"

    return {
        "schemaVersion": 1,
        "label": "BDD scenarios",
        "message": f"{passed} / {total}",
        "color": color,
        "cacheSeconds": 300,
    }


def write_badge_json(path: Path, passed: int, total: int) -> None:
    """Serialise the badge dict to *path* as pretty-printed JSON."""
    path.write_text(
        json.dumps(build_badge_json(passed, total), indent=2) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Traceability report
# ---------------------------------------------------------------------------


def build_traceability_report(
    rows: list[tuple[str, int, int]],
    timestamp: str,
) -> str:
    """Build the Markdown traceability table.

    Parameters
    ----------
    rows:
        List of ``(feature_file_basename, passed, total)`` tuples.
    timestamp:
        ISO-8601 string embedded in the report header.
    """
    total_passed = sum(r[1] for r in rows)
    total_total = sum(r[2] for r in rows)
    all_pass = total_passed == total_total

    lines: list[str] = [
        "# BDD Scenario Traceability Report",
        "",
        f"Generated: {timestamp}",
        "",
        "| Feature File | Passed | Total | Status |",
        "|---|---|---|---|",
    ]

    for feature_file, passed, total in rows:
        status = "✅" if passed == total else "❌"
        lines.append(f"| {feature_file} | {passed} | {total} | {status} |")

    overall_status = "**✅ All pass**" if all_pass else "**❌ Failures present**"
    lines.append(f"| **Total** | **{total_passed}** | **{total_total}** | {overall_status} |")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(args: list[str] | None = None) -> None:
    """Parse arguments and produce the badge JSON + traceability report."""
    parser = argparse.ArgumentParser(
        description="Generate BDD scenario completeness badge and traceability report."
    )
    parser.add_argument(
        "--junit",
        required=True,
        type=Path,
        metavar="FILE",
        help="Path to the JUnit XML produced by pytest --junitxml.",
    )
    parser.add_argument(
        "--features",
        required=True,
        type=Path,
        metavar="DIR",
        help="Directory containing .feature files.",
    )
    parser.add_argument(
        "--badge-output",
        required=True,
        type=Path,
        metavar="FILE",
        help="Output path for the shields.io badge JSON (e.g. bdd-badge.json).",
    )
    parser.add_argument(
        "--report-output",
        required=True,
        type=Path,
        metavar="FILE",
        help="Output path for the Markdown traceability report.",
    )
    parsed = parser.parse_args(args)

    junit_results = parse_junit_xml(parsed.junit)

    # Build rows: one per feature file found in features_dir.
    # If a feature has no JUnit entry, report (0, 0) to surface missing coverage.
    feature_definitions = count_scenarios_in_dir(parsed.features)
    rows: list[tuple[str, int, int]] = []
    for basename in sorted(feature_definitions):
        stem = Path(basename).stem
        passed, total = junit_results.get(stem, (0, 0))
        rows.append((basename, passed, total))

    total_passed = sum(r[1] for r in rows)
    total_total = sum(r[2] for r in rows)

    write_badge_json(parsed.badge_output, total_passed, total_total)

    timestamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
    report = build_traceability_report(rows, timestamp)
    parsed.report_output.write_text(report, encoding="utf-8")

    if total_passed < total_total:
        sys.exit(1)


if __name__ == "__main__":
    main()
