"""
KOTAK AUDIT SYMBOL DETECTION FIX V3
===================================

Safely patches contains_symbol() inside:

    kotak_live_integration_audit.py

Adds support for:

    - classes
    - functions
    - async functions
    - normal assignments
    - annotated assignments

Example fixed:

    LIVE_QUOTES = {}

The patch location is found using Python AST.
No regex replacement is used.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

AUDIT_FILE = (
    PROJECT_ROOT
    / "kotak_live_integration_audit.py"
)

BACKUP_FILE = (
    PROJECT_ROOT
    / "kotak_live_integration_audit.py.bak"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "fix_kotak_audit_symbol_detection_v3_report.json"
)


# ============================================================
# REPORT
# ============================================================

report = {
    "generated_at": datetime.now().isoformat(),
    "project_root": str(PROJECT_ROOT),
    "audit_file": str(AUDIT_FILE),
    "backup_file": str(BACKUP_FILE),
    "status": "STARTED",
    "changes": [],
    "validation": {},
    "errors": [],
}


def log(message: str) -> None:
    print(message)


def add_error(message: str) -> None:
    report["errors"].append(message)
    log(f"[ERROR] {message}")


def write_report() -> None:

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# START
# ============================================================

log("=" * 70)
log("KOTAK AUDIT SYMBOL DETECTION FIX V3")
log("=" * 70)
log("")


# ============================================================
# CHECK FILE
# ============================================================

if not AUDIT_FILE.is_file():

    add_error(
        "Audit file not found: "
        + str(AUDIT_FILE)
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


log("[PASS] Audit file found:")
log(str(AUDIT_FILE))


# ============================================================
# READ ORIGINAL SOURCE
# ============================================================

try:

    original_source = AUDIT_FILE.read_text(
        encoding="utf-8",
    )

except Exception as exc:

    add_error(
        f"Could not read audit file: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# BACKUP
# ============================================================

try:

    if not BACKUP_FILE.exists():

        BACKUP_FILE.write_text(
            original_source,
            encoding="utf-8",
        )

        log("[CREATED BACKUP]")

        report["changes"].append(
            "Created backup of original audit file"
        )

    else:

        log("[EXISTING BACKUP PRESERVED]")

        report["changes"].append(
            "Existing backup preserved"
        )

except Exception as exc:

    add_error(
        f"Could not create backup: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# PARSE AUDIT FILE
# ============================================================

try:

    tree = ast.parse(
        original_source
    )

except SyntaxError as exc:

    add_error(
        f"Original audit file has syntax error: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


log("[PASS] Original audit AST parsed")


# ============================================================
# FIND contains_symbol()
# ============================================================

target_function = None

for node in tree.body:

    if (
        isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == "contains_symbol"
    ):

        target_function = node

        break


if target_function is None:

    add_error(
        "contains_symbol() function not found"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


start_line = target_function.lineno
end_line = target_function.end_lineno


report["validation"][
    "contains_symbol_found"
] = True


log("[PASS] contains_symbol() located")

log(
    f"       Lines {start_line} to {end_line}"
)


# ============================================================
# NEW contains_symbol FUNCTION
# ============================================================

replacement_function = """
def contains_symbol(
    relative_path: str,
    symbol: str,
) -> bool:

    content = read_file(
        relative_path
    )

    if not content:
        return False

    try:

        tree = ast.parse(
            content
        )

    except SyntaxError:

        return symbol in content

    for node in ast.walk(tree):

        # ----------------------------------------------------
        # CLASS
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.ClassDef,
        ):

            if node.name == symbol:
                return True

        # ----------------------------------------------------
        # NORMAL FUNCTION
        # ----------------------------------------------------

        elif isinstance(
            node,
            ast.FunctionDef,
        ):

            if node.name == symbol:
                return True

        # ----------------------------------------------------
        # ASYNC FUNCTION
        # ----------------------------------------------------

        elif isinstance(
            node,
            ast.AsyncFunctionDef,
        ):

            if node.name == symbol:
                return True

        # ----------------------------------------------------
        # NORMAL VARIABLE ASSIGNMENT
        #
        # Example:
        #
        # LIVE_QUOTES = {}
        # ----------------------------------------------------

        elif isinstance(
            node,
            ast.Assign,
        ):

            for target in node.targets:

                if (
                    isinstance(
                        target,
                        ast.Name,
                    )
                    and target.id == symbol
                ):

                    return True

        # ----------------------------------------------------
        # ANNOTATED VARIABLE ASSIGNMENT
        #
        # Example:
        #
        # LIVE_QUOTES: dict = {}
        # ----------------------------------------------------

        elif isinstance(
            node,
            ast.AnnAssign,
        ):

            if (
                isinstance(
                    node.target,
                    ast.Name,
                )
                and node.target.id == symbol
            ):

                return True

    return False
""".strip()


# ============================================================
# VALIDATE REPLACEMENT FUNCTION ALONE
# ============================================================

try:

    replacement_tree = ast.parse(
        replacement_function
    )

    report["validation"][
        "replacement_function_syntax_valid"
    ] = True

    log(
        "[PASS] Replacement function syntax valid"
    )

except SyntaxError as exc:

    add_error(
        f"Replacement function syntax error: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# REPLACE FUNCTION USING LINE SLICES
# ============================================================

original_lines = original_source.splitlines()

replacement_lines = (
    replacement_function.splitlines()
)


new_lines = []

# Everything before contains_symbol()
new_lines.extend(
    original_lines[
        :start_line - 1
    ]
)

# New function
new_lines.extend(
    replacement_lines
)

# Add blank line after function
new_lines.append("")

# Everything after old function
new_lines.extend(
    original_lines[
        end_line:
    ]
)


new_source = "\n".join(
    new_lines
)

# Ensure final newline
new_source += "\n"


# ============================================================
# VALIDATE COMPLETE PATCHED SOURCE
# ============================================================

try:

    patched_tree = ast.parse(
        new_source
    )

    report["validation"][
        "patched_audit_syntax_valid"
    ] = True

    log(
        "[PASS] Complete patched audit syntax valid"
    )

except SyntaxError as exc:

    add_error(
        f"Patched audit syntax error: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# VERIFY NEW AST CAPABILITIES
# ============================================================

checks = {
    "ast.Assign": "ast.Assign",
    "ast.AnnAssign": "ast.AnnAssign",
    "LIVE_QUOTES": "LIVE_QUOTES",
    "return False": "return False",
}


for check_name, expected_text in checks.items():

    exists = (
        expected_text
        in new_source
    )

    report["validation"][
        check_name
    ] = exists

    if exists:

        log(
            f"[PASS] {check_name} present"
        )

    else:

        add_error(
            f"{check_name} missing from patched source"
        )


if report["errors"]:

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# WRITE PATCH
# ============================================================

try:

    AUDIT_FILE.write_text(
        new_source,
        encoding="utf-8",
    )

    report["changes"].append(
        "Replaced contains_symbol() with "
        "assignment-aware AST detection"
    )

    log(
        "[FIXED] contains_symbol() updated"
    )

except Exception as exc:

    add_error(
        f"Could not write patched audit: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# POST-WRITE VALIDATION
# ============================================================

try:

    written_source = AUDIT_FILE.read_text(
        encoding="utf-8",
    )

    ast.parse(
        written_source
    )

    report["validation"][
        "post_write_syntax_valid"
    ] = True

    log(
        "[PASS] Post-write syntax validation"
    )

except Exception as exc:

    add_error(
        f"Post-write validation failed: {exc}"
    )

    report["status"] = "FAILED"

    write_report()

    raise SystemExit(1)


# ============================================================
# COMPLETE
# ============================================================

if report["errors"]:

    report["status"] = "PARTIAL"

else:

    report["status"] = "SUCCESS"


write_report()


log("")
log("=" * 70)
log("FIX COMPLETE")
log("=" * 70)

log("")

log(
    f"Status: {report['status']}"
)

log("")

log("Changes:")

for change in report["changes"]:

    log(
        f"  - {change}"
    )


log("")

log("Errors:")

if report["errors"]:

    for error in report["errors"]:

        log(
            f"  - {error}"
        )

else:

    log("  0")


log("")

log("Report:")

log(
    str(REPORT_FILE)
)