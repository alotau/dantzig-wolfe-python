"""Unit tests for scripts/bdd_report.py — written RED before implementation (T008).

Tests cover:
  (a) Feature file regex parsing returns correct scenario count per file.
  (b) JUnit XML parsed for pass/fail counts per test file.
  (c) bdd-badge.json output matches the shields.io endpoint schema from contracts/badges.md.
  (d) bdd-traceability.md output matches the table format from contracts/badges.md.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path
from textwrap import dedent

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load scripts/bdd_report.py without making scripts/ a package.
# FileNotFoundError here (RED phase) is intentional until T009 creates the file.
# ---------------------------------------------------------------------------
_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "bdd_report.py"
_spec = importlib.util.spec_from_file_location("bdd_report", _SCRIPT_PATH)
bdd_report = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["bdd_report"] = bdd_report
_spec.loader.exec_module(bdd_report)  # type: ignore[union-attr]


# ===========================================================================
# (a) Feature file scenario counting
# ===========================================================================


def test_count_scenarios_simple(tmp_path: Path) -> None:
    """Counts Scenario: lines in a minimal feature file."""
    (tmp_path / "simple.feature").write_text(
        dedent("""\
            Feature: Simple
              Scenario: First
                Given something
              Scenario: Second
                Given something else
        """)
    )
    assert bdd_report.count_scenarios_in_file(tmp_path / "simple.feature") == 2


def test_count_scenarios_with_outline(tmp_path: Path) -> None:
    """Scenario Outline: counts as one definition (not expanded)."""
    (tmp_path / "outline.feature").write_text(
        dedent("""\
            Feature: Outline
              Scenario Outline: Parameterised
                Given <x>
              Examples:
                | x |
                | a |
                | b |
              Scenario: Plain
                Given something
        """)
    )
    assert bdd_report.count_scenarios_in_file(tmp_path / "outline.feature") == 2


def test_count_scenarios_empty_feature(tmp_path: Path) -> None:
    """A feature file with no scenarios returns 0."""
    (tmp_path / "empty.feature").write_text("Feature: Empty\n  Background:\n    Given setup\n")
    assert bdd_report.count_scenarios_in_file(tmp_path / "empty.feature") == 0


def test_count_scenarios_in_dir(tmp_path: Path) -> None:
    """count_scenarios_in_dir returns a dict keyed by feature file basename."""
    (tmp_path / "a.feature").write_text("Feature: A\n  Scenario: S1\n    Given g\n")
    (tmp_path / "b.feature").write_text(
        "Feature: B\n  Scenario: S1\n    Given g\n  Scenario: S2\n    Given g\n"
    )
    result = bdd_report.count_scenarios_in_dir(tmp_path)
    assert result == {"a.feature": 1, "b.feature": 2}


def test_count_scenarios_in_dir_ignores_non_feature_files(tmp_path: Path) -> None:
    """Non-.feature files in the directory are ignored."""
    (tmp_path / "notes.txt").write_text("Scenario: not a real scenario\n")
    (tmp_path / "real.feature").write_text("Feature: R\n  Scenario: S\n    Given g\n")
    result = bdd_report.count_scenarios_in_dir(tmp_path)
    assert list(result.keys()) == ["real.feature"]


# ===========================================================================
# (b) JUnit XML parsing
# ===========================================================================

_JUNIT_ALL_PASS = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite tests="3">
    <testcase classname="tests.bdd.steps.test_cli_usage" name="test_one" />
    <testcase classname="tests.bdd.steps.test_cli_usage" name="test_two" />
    <testcase classname="tests.bdd.steps.test_library_usage" name="test_three" />
  </testsuite>
</testsuites>
"""

_JUNIT_WITH_FAILURE = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite tests="3">
    <testcase classname="tests.bdd.steps.test_cli_usage" name="test_one" />
    <testcase classname="tests.bdd.steps.test_cli_usage" name="test_two">
      <failure message="AssertionError">long traceback here</failure>
    </testcase>
    <testcase classname="tests.bdd.steps.test_library_usage" name="test_three" />
  </testsuite>
</testsuites>
"""

_JUNIT_WITH_ERROR = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite tests="2">
    <testcase classname="tests.bdd.steps.test_cplex_lp_usage" name="test_one">
      <error message="RuntimeError">details</error>
    </testcase>
    <testcase classname="tests.bdd.steps.test_cplex_lp_usage" name="test_two" />
  </testsuite>
</testsuites>
"""


def test_parse_junit_xml_all_passing(tmp_path: Path) -> None:
    """All passing tests produce (total, total) for each feature stem."""
    p = tmp_path / "results.xml"
    p.write_text(_JUNIT_ALL_PASS)
    result = bdd_report.parse_junit_xml(p)
    assert result == {"cli_usage": (2, 2), "library_usage": (1, 1)}


def test_parse_junit_xml_with_failure(tmp_path: Path) -> None:
    """Tests with <failure> children reduce the passed count."""
    p = tmp_path / "results.xml"
    p.write_text(_JUNIT_WITH_FAILURE)
    result = bdd_report.parse_junit_xml(p)
    assert result == {"cli_usage": (1, 2), "library_usage": (1, 1)}


def test_parse_junit_xml_with_error(tmp_path: Path) -> None:
    """Tests with <error> children are also counted as not-passed."""
    p = tmp_path / "results.xml"
    p.write_text(_JUNIT_WITH_ERROR)
    result = bdd_report.parse_junit_xml(p)
    assert result == {"cplex_lp_usage": (1, 2)}


def test_parse_junit_xml_classname_stripping(tmp_path: Path) -> None:
    """The 'test_' prefix is stripped from the last classname segment."""
    p = tmp_path / "results.xml"
    p.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite tests="1">'
        '<testcase classname="tests.bdd.steps.test_my_feature" name="t" />'
        "</testsuite></testsuites>"
    )
    result = bdd_report.parse_junit_xml(p)
    assert "my_feature" in result


# ===========================================================================
# (c) Badge JSON schema (contracts/badges.md §2)
# ===========================================================================


def test_build_badge_json_all_pass() -> None:
    """All scenarios passing → brightgreen, message '42 / 42'."""
    badge = bdd_report.build_badge_json(42, 42)
    assert badge["schemaVersion"] == 1
    assert badge["label"] == "BDD scenarios"
    assert badge["message"] == "42 / 42"
    assert badge["color"] == "brightgreen"
    assert badge["cacheSeconds"] == 300


def test_build_badge_json_partial_above_90() -> None:
    """≥90% but not 100% → yellow."""
    badge = bdd_report.build_badge_json(38, 42)  # 90.5%
    assert badge["color"] == "yellow"
    assert badge["message"] == "38 / 42"


def test_build_badge_json_partial_below_90() -> None:
    """<90% → red."""
    badge = bdd_report.build_badge_json(37, 42)  # 88.1%
    assert badge["color"] == "red"


def test_build_badge_json_message_pattern() -> None:
    """Message matches the contract regex '^\\d+ / \\d+$'."""
    badge = bdd_report.build_badge_json(10, 20)
    assert re.match(r"^\d+ / \d+$", badge["message"])


def test_write_badge_json_creates_valid_file(tmp_path: Path) -> None:
    """write_badge_json writes a file that loads as valid JSON with correct fields."""
    path = tmp_path / "bdd-badge.json"
    bdd_report.write_badge_json(path, 42, 42)
    data = json.loads(path.read_text())
    assert data["schemaVersion"] == 1
    assert data["label"] == "BDD scenarios"
    assert re.match(r"^\d+ / \d+$", data["message"])
    assert data["color"] in ("brightgreen", "yellow", "red")
    assert data["cacheSeconds"] == 300


# ===========================================================================
# (d) Traceability report format (contracts/badges.md §3)
# ===========================================================================


def test_build_traceability_report_heading(tmp_path: Path) -> None:
    """Report contains the required H1 heading."""
    rows = [("cli_usage.feature", 13, 13)]
    report = bdd_report.build_traceability_report(rows, "2024-01-01T00:00:00")
    assert "# BDD Scenario Traceability Report" in report


def test_build_traceability_report_timestamp(tmp_path: Path) -> None:
    """Report contains the supplied timestamp."""
    rows = [("cli_usage.feature", 13, 13)]
    ts = "2024-06-15T10:30:00"
    report = bdd_report.build_traceability_report(rows, ts)
    assert ts in report


def test_build_traceability_report_columns(tmp_path: Path) -> None:
    """Report contains the Feature File, Passed, Total, Status column headers."""
    rows = [("cli_usage.feature", 13, 13)]
    report = bdd_report.build_traceability_report(rows, "2024-01-01T00:00:00")
    assert "Feature File" in report
    assert "Passed" in report
    assert "Total" in report
    assert "Status" in report


def test_build_traceability_report_rows(tmp_path: Path) -> None:
    """Each feature file appears in the table with its correct counts."""
    rows = [
        ("cli_usage.feature", 13, 13),
        ("cplex_lp_usage.feature", 18, 18),
        ("library_usage.feature", 11, 11),
    ]
    report = bdd_report.build_traceability_report(rows, "2024-01-01T00:00:00")
    assert "cli_usage.feature" in report
    assert "cplex_lp_usage.feature" in report
    assert "library_usage.feature" in report
    # All-pass rows get ✅
    assert report.count("✅") >= 3


def test_build_traceability_report_totals_row(tmp_path: Path) -> None:
    """The last row shows bold totals and an overall status."""
    rows = [
        ("cli_usage.feature", 13, 13),
        ("cplex_lp_usage.feature", 18, 18),
        ("library_usage.feature", 11, 11),
    ]
    report = bdd_report.build_traceability_report(rows, "2024-01-01T00:00:00")
    assert "42" in report  # total passed and total scenarios
    assert "Total" in report


def test_build_traceability_report_failure_row(tmp_path: Path) -> None:
    """A failing feature file row shows ❌."""
    rows = [("cli_usage.feature", 10, 13)]
    report = bdd_report.build_traceability_report(rows, "2024-01-01T00:00:00")
    assert "❌" in report


# ===========================================================================
# Integration: main() end-to-end
# ===========================================================================


def test_main_creates_badge_and_report(tmp_path: Path) -> None:
    """main() reads JUnit XML + features dir and writes both output files."""
    features_dir = tmp_path / "features"
    features_dir.mkdir()
    (features_dir / "example.feature").write_text("Feature: Ex\n  Scenario: S1\n    Given g\n")

    junit_xml = tmp_path / "results.xml"
    junit_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite tests="1">'
        '<testcase classname="tests.bdd.steps.test_example" name="test_s1" />'
        "</testsuite></testsuites>"
    )

    badge_out = tmp_path / "bdd-badge.json"
    report_out = tmp_path / "bdd-traceability.md"

    bdd_report.main(
        [
            "--junit",
            str(junit_xml),
            "--features",
            str(features_dir),
            "--badge-output",
            str(badge_out),
            "--report-output",
            str(report_out),
        ]
    )

    assert badge_out.exists(), "bdd-badge.json was not written"
    assert report_out.exists(), "bdd-traceability.md was not written"

    data = json.loads(badge_out.read_text())
    assert data["schemaVersion"] == 1
    assert data["label"] == "BDD scenarios"

    md = report_out.read_text()
    assert "# BDD Scenario Traceability Report" in md
    assert "example.feature" in md


def test_main_exits_nonzero_on_failing_scenarios(tmp_path: Path) -> None:
    """main() exits with code 1 when any scenario fails."""
    features_dir = tmp_path / "features"
    features_dir.mkdir()
    (features_dir / "example.feature").write_text(
        "Feature: Ex\n  Scenario: S1\n    Given g\n  Scenario: S2\n    Given g\n"
    )

    junit_xml = tmp_path / "results.xml"
    junit_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite tests="2">'
        '<testcase classname="tests.bdd.steps.test_example" name="test_s1" />'
        '<testcase classname="tests.bdd.steps.test_example" name="test_s2">'
        "<failure>oops</failure>"
        "</testcase>"
        "</testsuite></testsuites>"
    )

    badge_out = tmp_path / "bdd-badge.json"
    report_out = tmp_path / "bdd-traceability.md"

    with pytest.raises(SystemExit) as exc_info:
        bdd_report.main(
            [
                "--junit",
                str(junit_xml),
                "--features",
                str(features_dir),
                "--badge-output",
                str(badge_out),
                "--report-output",
                str(report_out),
            ]
        )
    assert exc_info.value.code == 1
