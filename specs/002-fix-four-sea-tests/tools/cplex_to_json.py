#!/usr/bin/env python3
"""CPLEX → dwsolver JSON fixture converter for the four_sea example.

Fetches five LP files from alotau/dwsolver on GitHub and converts them to a
single dwsolver JSON schema v1.0 problem file.

Usage:
    python specs/002-fix-four-sea-tests/tools/cplex_to_json.py \\
        --output tests/fixtures/ref_four_sea.json

Block assignments (from research.md):
    block_1 → subprob_1.cplex → AC8_7 / AC7_6
    block_2 → subprob_2.cplex → AC6_5 / AC5_4
    block_3 → subprob_3.cplex → AC4_3 / AC3_2
    block_4 → subprob_4.cplex → AC2_1 / AC1_0

dwsolver schema v1.0 reference (src/dwsolver/models.py):
    Problem  → schema_version, metadata, master: Master, blocks: list[Block]
    Master   → constraint_names: list[str], rhs: list[float], senses: list[str]
               senses must be one of {"=", "<=", ">="}
    Block    → block_id, variable_names, objective: list[float],
               bounds: list[Bounds], constraints: BlockConstraints,
               linking_columns: LinkingColumns
    Bounds   → {"lower": float, "upper": float | None}
    BlockConstraints → matrix: list[list[float]] (DENSE), rhs, senses
    LinkingColumns   → rows: list[int], cols: list[int], values: list[float]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from urllib.request import urlopen

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CPLEX_BASE_URL = "https://raw.githubusercontent.com/alotau/dwsolver/master/examples/four_sea/"

SUBPROB_FILES = [
    ("block_1", "subprob_1.cplex"),
    ("block_2", "subprob_2.cplex"),
    ("block_3", "subprob_3.cplex"),
    ("block_4", "subprob_4.cplex"),
]

# Regex: optional sign + optional coefficient + variable name w(...)
# Handles: "w(x)", "+ w(x)", "- w(x)", "2 w(x)", "- 2 w(x)", "+ 2.5 w(x)"
_COEFF_VAR = re.compile(r"([+-]?\s*(?:\d+(?:\.\d+)?)?\s*)w\(([^)]+)\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_url(url: str) -> str:
    """Fetch and return UTF-8 text content from *url*."""
    with urlopen(url) as resp:
        return resp.read().decode("utf-8")


def fetch_cplex(base_url: str, filename: str) -> str:
    """Fetch a CPLEX LP file from *base_url/filename*."""
    return fetch_url(base_url.rstrip("/") + "/" + filename)


def _parse_coeff(raw: str) -> float:
    """Convert a raw token coefficient string to float.

    Examples: ''→1.0, '+'→1.0, '-'→-1.0, '- 2'→-2.0, '2'→2.0
    """
    s = raw.strip().replace(" ", "")
    if s in ("", "+"):
        return 1.0
    if s == "-":
        return -1.0
    return float(s)


def _extract_section(text: str, header_pat: str, stop_pats: list[str]) -> str:
    """Extract the text body of a CPLEX LP section (case-insensitive).

    Wraps *header_pat* in a non-capturing group so that alternation (|)
    inside it does not break the capture group for the body.
    """
    stops = "|".join(stop_pats)
    pat = re.compile(
        r"(?:" + header_pat + r")\s+(.*?)(?=" + stops + r"|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pat.search(text)
    return m.group(1) or "" if m else ""


def _split_constraint_blocks(section_text: str) -> list[str]:
    """Split a Subject To section into individual constraint text blocks.

    Splits at every line that starts with an identifier followed by ':'.
    """
    # Find positions of constraint name lines: identifier(possibly with parens):
    starts = [m.start() for m in re.finditer(r"(?m)^\s*\w[\w,.()\s]*?:", section_text)]
    if not starts:
        return []
    blocks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(section_text)
        blocks.append(section_text[start:end].strip())
    return blocks


# ---------------------------------------------------------------------------
# Master CPLEX parser
# ---------------------------------------------------------------------------


def parse_master(text: str) -> dict:
    """Parse master.cplex and return master problem data.

    Returns:
        constraint_names: list[str]   — coupling constraint names
        rhs:              list[float] — right-hand side values
        senses:           list[str]   — "<=" or ">=" or "="
        master_obj:       dict[str, float] — {var_name: coeff} for all vars
        master_rows:      list[dict[str, float]] — per-constraint sparse dicts
    """
    # ------- Minimize section → master_obj -------
    min_text = _extract_section(
        text,
        r"Minimize",
        [r"Subject\s+To", r"Bounds"],
    )
    master_obj: dict[str, float] = {}
    for m in _COEFF_VAR.finditer(min_text):
        var = f"w({m.group(2)})"
        master_obj[var] = _parse_coeff(m.group(1))

    # ------- Subject To section → constraints -------
    subj_text = _extract_section(
        text,
        r"Subject\s+To",
        [r"Bounds", r"Generals", r"End\b"],
    )

    constraint_names: list[str] = []
    rhs_list: list[float] = []
    senses_list: list[str] = []
    master_rows: list[dict[str, float]] = []

    for block in _split_constraint_blocks(subj_text):
        # Extract constraint name (text before first ':')
        name_m = re.match(r"^\s*(\S[^:]*?)\s*:", block)
        if not name_m:
            continue
        cname = name_m.group(1).strip()
        body = block[name_m.end() :]

        # Find sense and RHS (last occurrence of sense+number)
        sense_m = re.search(r"(<=|>=|=)\s*(-?\d+(?:\.\d+)?)\s*$", body.replace("\n", " "))
        if not sense_m:
            continue
        sense = sense_m.group(1)
        rhs_val = float(sense_m.group(2))

        # Parse variable coefficients from expression part
        expr = body[: body.rfind(sense_m.group(0))]
        row: dict[str, float] = {}
        for vm in _COEFF_VAR.finditer(expr):
            vname = f"w({vm.group(2)})"
            row[vname] = _parse_coeff(vm.group(1))

        constraint_names.append(cname)
        rhs_list.append(rhs_val)
        senses_list.append(sense)
        master_rows.append(row)

    return {
        "constraint_names": constraint_names,
        "rhs": rhs_list,
        "senses": senses_list,
        "master_obj": master_obj,
        "master_rows": master_rows,
    }


# ---------------------------------------------------------------------------
# Subproblem parsers
# ---------------------------------------------------------------------------


def parse_subproblem_vars(text: str, block_id: str, master_obj: dict) -> dict:
    """Parse variable declarations, bounds, and objective for one block.

    Variables are read from the Bounds section (``0 <= w(...) <= 1`` lines).
    Objective coefficients come from *master_obj*; the subproblem MINIMIZE
    section contains only a dummy placeholder and is intentionally ignored.

    Returns:
        block_id:       str
        variable_names: list[str]  — sorted alphabetically for determinism
        var_index:      dict[str, int]
        objective:      list[float]
        bounds:         list[dict]  — [{"lower": 0.0, "upper": 1.0}, ...]
    """
    bounds_text = _extract_section(
        text,
        r"Bounds",
        [r"Generals", r"End\b"],
    )

    variable_names: list[str] = []
    for bm in re.finditer(r"0\s*<=\s*w\(([^)]+)\)\s*<=\s*1", bounds_text):
        variable_names.append(f"w({bm.group(1)})")

    variable_names.sort()
    var_index = {name: i for i, name in enumerate(variable_names)}
    objective = [master_obj.get(name, 0.0) for name in variable_names]
    bounds = [{"lower": 0.0, "upper": 1.0} for _ in variable_names]

    return {
        "block_id": block_id,
        "variable_names": variable_names,
        "var_index": var_index,
        "objective": objective,
        "bounds": bounds,
    }


def parse_subproblem_constraints(text: str, var_index: dict) -> dict:
    """Parse Temporality and Sector_Time constraints from a subproblem file.

    Each constraint has the form:
        NAME: VAR_A - VAR_B [<=|>=] 0

    Builds a dense constraint matrix (rows × len(var_index)) with +1 on the
    LHS variable and -1 on the subtracted variable.

    Returns:
        names:  list[str]
        senses: list[str]          — "<=" (Sector_Time) or ">=" (Temporality)
        rhs:    list[float]        — all 0.0
        matrix: list[list[float]]  — dense, one row per constraint
    """
    subj_text = _extract_section(
        text,
        r"Subject\s+To",
        [r"Bounds", r"Generals", r"End\b"],
    )

    names: list[str] = []
    senses: list[str] = []
    rhs: list[float] = []
    matrix: list[list[float]] = []
    n_vars = len(var_index)

    for block in _split_constraint_blocks(subj_text):
        name_m = re.match(r"^\s*(\S[^:]*?)\s*:", block)
        if not name_m:
            continue
        cname = name_m.group(1).strip()
        body = block[name_m.end() :]

        sense_m = re.search(r"(<=|>=|=)\s*(-?\d+(?:\.\d+)?)\s*$", body.replace("\n", " "))
        if not sense_m:
            continue
        sense = sense_m.group(1)
        rhs_val = float(sense_m.group(2))

        expr = body[: body.rfind(sense_m.group(0))]
        row = [0.0] * n_vars
        for vm in _COEFF_VAR.finditer(expr):
            vname = f"w({vm.group(2)})"
            if vname in var_index:
                row[var_index[vname]] = _parse_coeff(vm.group(1))

        names.append(cname)
        senses.append(sense)
        rhs.append(rhs_val)
        matrix.append(row)

    return {"names": names, "senses": senses, "rhs": rhs, "matrix": matrix}


# ---------------------------------------------------------------------------
# Linking columns
# ---------------------------------------------------------------------------


def build_linking_columns(master_rows: list[dict], var_index: dict) -> dict:
    """Build sparse COO linking matrix D_i for one block.

    Iterates over all master constraint rows and emits a COO triplet for each
    master variable that belongs to this block's var_index.

    Args:
        master_rows: list of per-constraint sparse dicts {var_name: coeff}
        var_index:   block's {var_name: col_idx}

    Returns:
        rows:   list[int]
        cols:   list[int]
        values: list[float]
    """
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []

    for row_idx, row_dict in enumerate(master_rows):
        for var_name, coeff in row_dict.items():
            if var_name in var_index:
                rows.append(row_idx)
                cols.append(var_index[var_name])
                values.append(coeff)

    return {"rows": rows, "cols": cols, "values": values}


# ---------------------------------------------------------------------------
# Problem assembler
# ---------------------------------------------------------------------------


def assemble_problem(master_data: dict, block_data_list: list[dict]) -> dict:
    """Assemble the top-level dwsolver JSON schema v1.0 problem dict.

    Strips internal working keys (master_obj, master_rows, var_index) and
    builds the final serialisable structure.
    """
    master_dict = {
        "constraint_names": master_data["constraint_names"],
        "rhs": master_data["rhs"],
        "senses": master_data["senses"],
    }

    blocks_list = []
    for bd in block_data_list:
        blocks_list.append(
            {
                "block_id": bd["block_id"],
                "variable_names": bd["variable_names"],
                "objective": bd["objective"],
                "bounds": bd["bounds"],
                "constraints": {
                    "matrix": bd["constraints"]["matrix"],
                    "rhs": bd["constraints"]["rhs"],
                    "senses": bd["constraints"]["senses"],
                },
                "linking_columns": bd["linking_columns"],
            }
        )

    return {
        "schema_version": "1.0",
        "metadata": {
            "source": "four_sea (LAS→SEA, 8 aircraft)",
            "generated_by": "specs/002-fix-four-sea-tests/tools/cplex_to_json.py",
        },
        "master": master_dict,
        "blocks": blocks_list,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI args, fetch CPLEX files, convert, and write JSON fixture."""
    parser = argparse.ArgumentParser(
        description="Convert four_sea CPLEX LP files to dwsolver JSON fixture."
    )
    parser.add_argument("--output", required=True, help="Output path for the JSON fixture")
    parser.add_argument(
        "--cplex-base-url",
        default=CPLEX_BASE_URL,
        help="Base URL for CPLEX files (default: alotau/dwsolver on GitHub)",
    )
    args = parser.parse_args()

    print(f"Fetching master.cplex from {args.cplex_base_url} ...")
    master_text = fetch_cplex(args.cplex_base_url, "master.cplex")
    print("Parsing master.cplex ...")
    master_data = parse_master(master_text)
    n_master = len(master_data["constraint_names"])
    n_obj_vars = len(master_data["master_obj"])
    print(f"  {n_master} coupling constraints, {n_obj_vars} objective variables")

    block_data_list: list[dict] = []
    total_vars = 0
    total_constraints = 0

    for block_id, filename in SUBPROB_FILES:
        print(f"Fetching {filename} ...")
        subprob_text = fetch_cplex(args.cplex_base_url, filename)

        print(f"  Parsing variables for {block_id} ...")
        var_data = parse_subproblem_vars(subprob_text, block_id, master_data["master_obj"])
        var_index = var_data["var_index"]

        print(f"  Parsing constraints for {block_id} ...")
        constraint_data = parse_subproblem_constraints(subprob_text, var_index)

        print(f"  Building linking columns for {block_id} ...")
        lc = build_linking_columns(master_data["master_rows"], var_index)

        block_data_list.append(
            {
                "block_id": block_id,
                "variable_names": var_data["variable_names"],
                "objective": var_data["objective"],
                "bounds": var_data["bounds"],
                "constraints": {
                    "matrix": constraint_data["matrix"],
                    "rhs": constraint_data["rhs"],
                    "senses": constraint_data["senses"],
                },
                "linking_columns": lc,
            }
        )

        n_vars = len(var_data["variable_names"])
        n_c = len(constraint_data["rhs"])
        n_lc = len(lc["rows"])
        total_vars += n_vars
        total_constraints += n_c
        print(f"  {block_id}: {n_vars} vars, {n_c} constraints, {n_lc} linking entries")

    # -------------------------------------------------------------------
    # Inject the +160 objective constant (master.cplex comment:
    # "\* constant term = 160 *\").  The solver returns variable-part
    # objective only; adding a dummy variable fixed at 1.0 with
    # objective coefficient 160 ensures the solver reports objective 12.0
    # instead of -148.0 at optimality.  Placed in block_1 only; D-W
    # includes it in every master column from block_1 (sum lambda^1 = 1).
    # -------------------------------------------------------------------
    b0 = block_data_list[0]
    b0["variable_names"].append("__objective_constant__")
    b0["objective"].append(160.0)
    b0["bounds"].append({"lower": 1.0, "upper": 1.0})
    for row in b0["constraints"]["matrix"]:
        row.append(0.0)
    print(f"  Injected +160 objective constant into {b0['block_id']}")

    print("Assembling problem ...")
    problem = assemble_problem(master_data, block_data_list)

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing to {out_path} ...")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(problem, f, sort_keys=True, indent=2)

    print(
        f"Written: {out_path}  "
        f"({len(block_data_list)} blocks, {total_vars} vars, "
        f"{total_constraints} constraints)"
    )


if __name__ == "__main__":
    main()
