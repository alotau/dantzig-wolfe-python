"""CPLEX LP parser for dwsolver.

Internal module — not part of the public ``dwsolver`` API.

Converts CPLEX LP format files into the ``Problem`` data model used by the
solver.  Only the CPLEX LP subset produced by ``alotau/dwsolver``-style files
is supported (``Minimize``/``Maximize``, ``Subject To``, ``Bounds``,
``Generals``/``Binary``, ``End``; backslash line comments; block comments).
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from pydantic import ValidationError

from dwsolver.models import (
    Block,
    BlockConstraints,
    Bounds,
    DWSolverInputError,
    LinkingColumns,
    Master,
    Problem,
)

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# CPLEX LP variable name: starts with letter or underscore; may contain
# letters, digits, underscores, dots, parentheses, and commas.  This covers
# the four_sea convention ``w(AC8_7,SEA,199)`` as well as ordinary names.
_VARNAME = r"[a-zA-Z_][a-zA-Z0-9_.,()]*"

# Match an optional ±coefficient then a variable name.
# Examples:  "- 2 x1"  "+ y"  "3.5 z"  "w(AC8_7,SEA,199)"
_COEFF_VAR_RE = re.compile(r"([+-]?\s*(?:\d+(?:\.\d+)?)?\s*)(" + _VARNAME + r")")

# Block comment delimiters:  \* ... *\  (used for "constant term = N")
_BLOCK_COMMENT_RE = re.compile(r"\\\*.*?\*\\", re.DOTALL)

# Objective constant term inside a block comment.
_OBJ_CONST_RE = re.compile(r"\\\*\s*constant\s+term\s*=\s*(-?\d+(?:\.\d+)?)\s*\*\\")

# Section headers (case-insensitive; leading whitespace permitted).
_HDR_RE = re.compile(
    r"^[ \t]*(Minimize|Maximize|Subject\s+To|Bounds|Generals|General|Gen"
    r"|Binary|Bin|End)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Map raw (lower-cased) section keywords to canonical keys.
_SECTION_KEY_MAP: dict[str, str] = {
    "minimize": "minimize",
    "maximize": "maximize",
    "bounds": "bounds",
    "generals": "generals",
    "general": "generals",
    "gen": "generals",
    "binary": "generals",  # treated same as generals — ignored
    "bin": "generals",
    "end": "end",
}

# Bounds line patterns — try in this order to avoid partial double-bound matches.
_DOUBLE_BOUND_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*<=\s*(" + _VARNAME + r")\s*<=\s*(-?\d+(?:\.\d+)?)"
)
_FREE_VAR_RE = re.compile(r"(" + _VARNAME + r")\s+free", re.IGNORECASE)
_LOWER_BOUND_RE = re.compile(r"(" + _VARNAME + r")\s*>=\s*(-?\d+(?:\.\d+)?)")
_UPPER_BOUND_RE = re.compile(r"(" + _VARNAME + r")\s*<=\s*(-?\d+(?:\.\d+)?)")

# ---------------------------------------------------------------------------
# Intermediate dataclasses  (internal — not exported)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MasterLP:
    """Parsed representation of a master CPLEX LP file."""

    constraint_names: list[str]
    rhs: list[float]
    senses: list[str]
    objective: dict[str, float]
    row_coefficients: list[dict[str, float]]
    obj_constant: float


@dataclasses.dataclass(frozen=True)
class SubproblemLP:
    """Parsed representation of one subproblem CPLEX LP file."""

    block_id: str
    variable_names: list[str]
    bounds: list[tuple[float, float | None]]
    objective: dict[str, float]
    constraints_matrix: list[list[float]]
    constraints_rhs: list[float]
    constraints_senses: list[str]
    constraints_names: list[str]


@dataclasses.dataclass(frozen=True)
class LinkingSpec:
    """Sparse COO encoding of the linking matrix D_i."""

    rows: list[int]
    cols: list[int]
    values: list[float]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_coeff(raw: str) -> float:
    """Convert a raw coefficient token string to a float.

    Examples: ``""`` → 1.0,  ``"+"`` → 1.0,  ``"-"`` → −1.0,
    ``"- 2"`` → −2.0,  ``"2.5"`` → 2.5.
    """
    s = raw.strip().replace(" ", "")
    if s in ("", "+"):
        return 1.0
    if s == "-":
        return -1.0
    return float(s)


def _clean_text(text: str) -> str:
    """Remove block comments and backslash line comments from CPLEX LP text."""
    # Remove \* ... *\ block comments first (constant term already extracted).
    text = _BLOCK_COMMENT_RE.sub("", text)
    # Remove lines that start with a backslash comment marker.
    lines = [line for line in text.splitlines() if not line.strip().startswith("\\")]
    return "\n".join(lines)


def _split_sections(text: str) -> dict[str, str]:
    """Split cleaned CPLEX LP text into ``{canonical_key: body_text}`` mapping.

    Keys: ``"minimize"``, ``"maximize"``, ``"subject_to"``, ``"bounds"``,
    ``"generals"``, ``"end"``.
    """
    result: dict[str, str] = {}
    matches = list(_HDR_RE.finditer(text))
    for i, m in enumerate(matches):
        kw = m.group(1).strip().lower()
        # Normalize "subject to" / "subject\tto" etc.
        key = "subject_to" if kw.startswith("subject") else _SECTION_KEY_MAP.get(kw, kw)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[key] = text[body_start:body_end]
    return result


def _parse_obj_section(text: str, negate: bool) -> dict[str, float]:
    """Parse objective coefficients from a section body.

    Strips an optional ``label:`` prefix before scanning.
    ``negate=True`` when the section was ``Maximize``.
    """
    clean = text.strip()
    # Strip optional label, e.g. "Delay_Costs:" or "objective:".
    label_m = re.match(r"^(" + _VARNAME + r")\s*:", clean)
    if label_m:
        clean = clean[label_m.end() :]

    obj: dict[str, float] = {}
    for m in _COEFF_VAR_RE.finditer(clean):
        var = m.group(2)
        coeff = _parse_coeff(m.group(1))
        if negate:
            coeff = -coeff
        obj[var] = obj.get(var, 0.0) + coeff
    return obj


def _split_constraint_blocks(section_text: str) -> list[str]:
    """Split a ``Subject To`` section into individual constraint text blobs.

    Splits at every line that begins with ``identifier:``, which is the CPLEX
    LP constraint-name syntax.
    """
    starts = [
        m.start() for m in re.finditer(r"(?m)^[ \t]*(" + _VARNAME + r")[ \t]*:", section_text)
    ]
    if not starts:
        return []
    blocks: list[str] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(section_text)
        blocks.append(section_text[start:end].strip())
    return blocks


def _parse_master_constraints(
    section_text: str,
) -> tuple[list[str], list[str], list[float], list[dict[str, float]]]:
    """Parse master coupling constraints into sparse-dict rows.

    Returns ``(names, senses, rhs, row_coefficients)``.
    """
    names: list[str] = []
    senses: list[str] = []
    rhs: list[float] = []
    row_coefficients: list[dict[str, float]] = []

    for block in _split_constraint_blocks(section_text):
        name_m = re.match(r"^[ \t]*(" + _VARNAME + r")[ \t]*:", block)
        if not name_m:
            continue
        cname = name_m.group(1).strip()
        body = block[name_m.end() :]
        body_flat = body.replace("\n", " ")

        sense_m = re.search(r"(<=|>=|=)\s*(-?\d+(?:\.\d+)?)\s*$", body_flat)
        if not sense_m:
            continue
        sense = sense_m.group(1)
        rhs_val = float(sense_m.group(2))

        expr = body_flat[: body_flat.rfind(sense_m.group(0))]
        row: dict[str, float] = {}
        for vm in _COEFF_VAR_RE.finditer(expr):
            vname = vm.group(2)
            c = _parse_coeff(vm.group(1))
            row[vname] = row.get(vname, 0.0) + c

        names.append(cname)
        senses.append(sense)
        rhs.append(rhs_val)
        row_coefficients.append(row)

    return names, senses, rhs, row_coefficients


def _parse_subproblem_constraints(
    section_text: str, var_names: list[str]
) -> tuple[list[str], list[str], list[float], list[list[float]]]:
    """Parse subproblem constraints into a dense matrix.

    Only variables in ``var_names`` are recorded; other variables appearing in
    the expression (e.g. variables belonging to other blocks in cross-block
    constraints) are silently skipped.

    Returns ``(names, senses, rhs, dense_matrix)``.
    """
    var_index = {name: i for i, name in enumerate(var_names)}
    n_vars = len(var_names)

    names: list[str] = []
    senses: list[str] = []
    rhs: list[float] = []
    matrix: list[list[float]] = []

    for block in _split_constraint_blocks(section_text):
        name_m = re.match(r"^[ \t]*(" + _VARNAME + r")[ \t]*:", block)
        if not name_m:
            continue
        cname = name_m.group(1).strip()
        body = block[name_m.end() :]
        body_flat = body.replace("\n", " ")

        sense_m = re.search(r"(<=|>=|=)\s*(-?\d+(?:\.\d+)?)\s*$", body_flat)
        if not sense_m:
            continue
        sense = sense_m.group(1)
        rhs_val = float(sense_m.group(2))

        expr = body_flat[: body_flat.rfind(sense_m.group(0))]
        row = [0.0] * n_vars
        for vm in _COEFF_VAR_RE.finditer(expr):
            vname = vm.group(2)
            if vname in var_index:
                coeff = _parse_coeff(vm.group(1))
                row[var_index[vname]] += coeff

        names.append(cname)
        senses.append(sense)
        rhs.append(rhs_val)
        matrix.append(row)

    return names, senses, rhs, matrix


def _parse_bounds_section(
    section_text: str,
) -> tuple[list[str], list[tuple[float, float | None]]]:
    """Parse a ``Bounds`` section into ``(variable_names, bounds)`` in file order.

    Supported formats (tried in order to avoid partial matches):
    - Double-sided:  ``0 <= x <= 1``
    - Free:          ``x free``
    - Lower-only:    ``x >= 0``
    - Upper-only:    ``x <= 10``

    Variables appearing on multiple lines use first-occurrence bounds.
    """
    var_names: list[str] = []
    bounds_list: list[tuple[float, float | None]] = []
    seen: set[str] = set()

    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Double-sided: l <= x <= u  (try first to avoid false upper-only match)
        dm = _DOUBLE_BOUND_RE.search(stripped)
        if dm:
            var = dm.group(2)
            if var not in seen:
                seen.add(var)
                var_names.append(var)
                bounds_list.append((float(dm.group(1)), float(dm.group(3))))
            continue

        # Free: x free
        fm = _FREE_VAR_RE.search(stripped)
        if fm:
            var = fm.group(1)
            if var not in seen:
                seen.add(var)
                var_names.append(var)
                bounds_list.append((float("-inf"), None))
            continue

        # Lower-only: x >= l
        lm = _LOWER_BOUND_RE.search(stripped)
        if lm:
            var = lm.group(1)
            if var not in seen:
                seen.add(var)
                var_names.append(var)
                bounds_list.append((float(lm.group(2)), None))
            continue

        # Upper-only: x <= u
        um = _UPPER_BOUND_RE.search(stripped)
        if um:
            var = um.group(1)
            if var not in seen:
                seen.add(var)
                var_names.append(var)
                bounds_list.append((0.0, float(um.group(2))))

    return var_names, bounds_list


# ---------------------------------------------------------------------------
# Public parse functions
# ---------------------------------------------------------------------------


def parse_master(text: str) -> MasterLP:
    """Parse the text of a master CPLEX LP file.

    Args:
        text: Full UTF-8 text of the master ``.lp`` or ``.cplex`` file.

    Returns:
        :class:`MasterLP` dataclass.

    Raises:
        DWSolverInputError: If no ``Subject To`` section is found, or the
            section contains no coupling constraints.
    """
    # Extract objective constant from raw text before comment removal.
    const_m = _OBJ_CONST_RE.search(text)
    obj_constant = float(const_m.group(1)) if const_m else 0.0

    clean = _clean_text(text)
    sections = _split_sections(clean)

    # Parse objective direction and coefficients.
    if "maximize" in sections:
        objective = _parse_obj_section(sections["maximize"], negate=True)
    else:
        objective = _parse_obj_section(sections.get("minimize", ""), negate=False)

    # Validate Subject To section presence.
    if "subject_to" not in sections:
        raise DWSolverInputError(
            "Master file: no 'Subject To' section found — is this a valid CPLEX LP file?"
        )

    names, senses, rhs, row_coefficients = _parse_master_constraints(sections["subject_to"])

    if not names:
        raise DWSolverInputError(
            "Master file: no coupling constraints found in 'Subject To' section"
        )

    return MasterLP(
        constraint_names=names,
        rhs=rhs,
        senses=senses,
        objective=objective,
        row_coefficients=row_coefficients,
        obj_constant=obj_constant,
    )


def parse_subproblem(text: str, block_id: str) -> SubproblemLP:
    """Parse the text of one subproblem CPLEX LP file.

    Args:
        text: Full UTF-8 text of a subproblem ``.lp`` or ``.cplex`` file.
        block_id: Caller-supplied identifier, e.g. ``"block_0"``.

    Returns:
        :class:`SubproblemLP` dataclass.

    Raises:
        DWSolverInputError: If the ``Bounds`` section is absent or declares
            no variables.
    """
    clean = _clean_text(text)
    sections = _split_sections(clean)

    # Validate Bounds section.
    if "bounds" not in sections:
        raise DWSolverInputError(f"Subproblem {block_id!r}: no 'Bounds' section found")

    var_names, bounds_tuples = _parse_bounds_section(sections["bounds"])

    if not var_names:
        raise DWSolverInputError(
            f"Subproblem {block_id!r}: no variables declared in 'Bounds' section"
        )

    # Parse subproblem objective (may be empty / placeholder).
    if "maximize" in sections:
        sub_obj = _parse_obj_section(sections["maximize"], negate=True)
    else:
        sub_obj = _parse_obj_section(sections.get("minimize", ""), negate=False)

    # Parse local constraints (dense matrix over this block's variables only).
    if "subject_to" in sections:
        c_names, c_senses, c_rhs, c_matrix = _parse_subproblem_constraints(
            sections["subject_to"], var_names
        )
    else:
        n_vars = len(var_names)
        c_names, c_senses, c_rhs, c_matrix = [], [], [], []
        _ = n_vars  # unused — empty constraint system is valid

    return SubproblemLP(
        block_id=block_id,
        variable_names=var_names,
        bounds=bounds_tuples,
        objective=sub_obj,
        constraints_matrix=c_matrix,
        constraints_rhs=c_rhs,
        constraints_senses=c_senses,
        constraints_names=c_names,
    )


def infer_linking(master: MasterLP, sub: SubproblemLP) -> LinkingSpec:
    """Build the sparse COO linking matrix for one subproblem.

    Matches variable names from the subproblem's ``Bounds`` section against
    the master's ``Subject To`` constraint expressions.

    Args:
        master: Parsed master.
        sub: Parsed subproblem.

    Returns:
        :class:`LinkingSpec` with COO triplets ``(row_idx, col_idx, coeff)``.
        An empty spec (all lists empty) is valid — the subproblem has no
        variables appearing in the master coupling constraints.
    """
    var_index = {name: i for i, name in enumerate(sub.variable_names)}

    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []

    for row_idx, row_dict in enumerate(master.row_coefficients):
        for var_name, coeff in row_dict.items():
            if var_name in var_index:
                rows.append(row_idx)
                cols.append(var_index[var_name])
                values.append(coeff)

    return LinkingSpec(rows=rows, cols=cols, values=values)


def resolve_block_objective(master: MasterLP, sub: SubproblemLP) -> list[float]:
    """Determine the objective coefficient list for a block.

    Strategy: master-first, subproblem fallback.

    If the master objective contains any non-zero coefficient for at least one
    variable in this block, use the master objective for the full block
    (missing variables default to 0.0).  This handles the common CPLEX LP
    convention where the master file carries the global objective and the
    subproblem files contain a placeholder or partial objective.

    Otherwise (master has zero coefficients for all block variables), fall back
    to the subproblem's own objective section.

    Args:
        master: Parsed master.
        sub: Parsed subproblem.

    Returns:
        ``list[float]`` of length ``len(sub.variable_names)``.
    """
    master_coeffs = [master.objective.get(v, 0.0) for v in sub.variable_names]
    if any(c != 0.0 for c in master_coeffs):
        return master_coeffs

    # Fallback: use the subproblem's own objective.
    return [sub.objective.get(v, 0.0) for v in sub.variable_names]


def assemble_problem(master: MasterLP, subs: list[SubproblemLP]) -> Problem:
    """Assemble a validated ``Problem`` from parsed intermediate objects.

    Args:
        master: Parsed master.
        subs: Parsed subproblems in argument order (determines ``block_id``
            assignment and block index).

    Returns:
        Validated :class:`~dwsolver.models.Problem` instance.

    Raises:
        DWSolverInputError: If ``subs`` is empty, if a variable name appears
            in more than one subproblem, if any master coupling-constraint
            variable is not declared in any subproblem ``Bounds`` section, or
            if Pydantic validation fails.
    """
    if not subs:
        raise DWSolverInputError("At least one subproblem file is required for CPLEX LP format")

    # Check for duplicate variable names across blocks.
    all_vars: dict[str, str] = {}  # var_name → block_id
    for sub in subs:
        for var in sub.variable_names:
            if var in all_vars:
                raise DWSolverInputError(
                    f"Variable {var!r} appears in both {all_vars[var]!r} and {sub.block_id!r}"
                )
            all_vars[var] = sub.block_id

    # Check that every master coupling-constraint variable is owned by a block.
    for row_dict in master.row_coefficients:
        for var in row_dict:
            if var not in all_vars:
                raise DWSolverInputError(
                    f"Variable {var!r} appears in master coupling constraints "
                    f"but is not declared in any subproblem Bounds section"
                )

    # Build Block objects.
    blocks: list[Block] = []
    for i, sub in enumerate(subs):
        obj = resolve_block_objective(master, sub)
        linking = infer_linking(master, sub)

        var_names = list(sub.variable_names)
        bounds = [Bounds(lower=lb, upper=ub) for lb, ub in sub.bounds]
        matrix = [list(row) for row in sub.constraints_matrix]

        # Inject objective constant as a pinned dummy variable into block 0.
        if i == 0 and master.obj_constant != 0.0:
            var_names.append("__objective_constant__")
            obj.append(master.obj_constant)
            bounds.append(Bounds(lower=1.0, upper=1.0))
            matrix = [row + [0.0] for row in matrix]

        blocks.append(
            Block(
                block_id=sub.block_id,
                variable_names=var_names,
                objective=obj,
                bounds=bounds,
                constraints=BlockConstraints(
                    matrix=matrix,
                    rhs=list(sub.constraints_rhs),
                    senses=list(sub.constraints_senses),
                ),
                linking_columns=LinkingColumns(
                    rows=linking.rows,
                    cols=linking.cols,
                    values=linking.values,
                ),
            )
        )

    master_model = Master(
        constraint_names=list(master.constraint_names),
        rhs=list(master.rhs),
        senses=list(master.senses),
    )

    try:
        return Problem(master=master_model, blocks=blocks)
    except ValidationError as exc:
        raise DWSolverInputError(f"Problem assembly failed schema validation: {exc}") from exc


def load_problem_from_lp(master_path: Path, subproblem_paths: list[Path]) -> Problem:
    """Load, parse, and assemble a ``Problem`` from CPLEX LP files.

    Args:
        master_path: Path to the master LP file.
        subproblem_paths: Ordered list of subproblem LP file paths.  Position
            determines ``block_id`` (``"block_0"``, ``"block_1"``, …).

    Returns:
        Validated :class:`~dwsolver.models.Problem`.

    Raises:
        DWSolverInputError: For any file I/O, parse, or assembly error.
    """
    # Read master file.
    try:
        master_text = master_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DWSolverInputError(f"Master file not found: {str(master_path)!r}") from exc
    except OSError as exc:
        raise DWSolverInputError(f"Error reading master file {str(master_path)!r}: {exc}") from exc

    # Read subproblem files.
    sub_texts: list[tuple[str, str]] = []  # (block_id, text)
    for idx, sp in enumerate(subproblem_paths):
        block_id = f"block_{idx}"
        try:
            text = sp.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise DWSolverInputError(f"Subproblem file not found: {str(sp)!r}") from exc
        except OSError as exc:
            raise DWSolverInputError(f"Error reading subproblem file {str(sp)!r}: {exc}") from exc
        sub_texts.append((block_id, text))

    # Parse master and subproblems.
    master = parse_master(master_text)
    subs: list[SubproblemLP] = []
    for block_id, text in sub_texts:
        subs.append(parse_subproblem(text, block_id))

    return assemble_problem(master, subs)
