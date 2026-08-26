from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

LIVE_QUOTES_FILE = (
    PROJECT_ROOT
    / "backend"
    / "market"
    / "live_quotes.py"
)

REPORT = {
    "generated_at": datetime.now().isoformat(),
    "project_root": str(PROJECT_ROOT),
    "changes": [],
    "errors": [],
}


def print_status(status: str, message: str):
    print(f"[{status}] {message}")


# ============================================================
# VALIDATE PROJECT
# ============================================================

if not (PROJECT_ROOT / "backend").exists():
    raise RuntimeError(
        f"Invalid project root: {PROJECT_ROOT}"
    )

if not LIVE_QUOTES_FILE.exists():
    raise RuntimeError(
        f"Missing file: {LIVE_QUOTES_FILE}"
    )


# ============================================================
# READ FILE
# ============================================================

source = LIVE_QUOTES_FILE.read_text(
    encoding="utf-8"
)

original_source = source


# ============================================================
# REMOVE EXISTING MODULE-LEVEL LIVE_QUOTES DECLARATION
#
# Handles:
#
# LIVE_QUOTES = {}
# LIVE_QUOTES: Dict[...] = {}
# LIVE_QUOTES: dict = {}
#
# We replace it with the exact canonical form:
#
# LIVE_QUOTES = {}
# ============================================================

lines = source.splitlines()

new_lines = []
live_quotes_replaced = False

for line in lines:

    stripped = line.strip()

    # Match only module-level declarations.
    # Do not remove usages like:
    # LIVE_QUOTES[symbol] = quote
    #
    pattern = r"^LIVE_QUOTES(?:\s*:\s*[^=]+)?\s*=\s*\{\s*\}\s*$"

    if re.match(pattern, stripped):

        if not live_quotes_replaced:

            new_lines.append(
                "LIVE_QUOTES = {}"
            )

            live_quotes_replaced = True

            REPORT["changes"].append(
                "Normalized LIVE_QUOTES to plain assignment"
            )

            print_status(
                "FIXED",
                "LIVE_QUOTES declaration normalized",
            )

        else:

            REPORT["changes"].append(
                "Removed duplicate LIVE_QUOTES declaration"
            )

            print_status(
                "FIXED",
                "Removed duplicate LIVE_QUOTES declaration",
            )

        continue

    new_lines.append(line)


# ============================================================
# IF NO SIMPLE EMPTY-DICT DECLARATION WAS FOUND,
# INSERT A CANONICAL ONE AFTER IMPORTS.
# ============================================================

if not live_quotes_replaced:

    insertion_index = 0

    for index, line in enumerate(new_lines):

        stripped = line.strip()

        if (
            stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped == ""
            or stripped.startswith("#")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
        ):
            insertion_index = index + 1
            continue

        break

    new_lines.insert(
        insertion_index,
        ""
    )

    new_lines.insert(
        insertion_index + 1,
        "# Canonical central live quote cache."
    )

    new_lines.insert(
        insertion_index + 2,
        "LIVE_QUOTES = {}"
    )

    REPORT["changes"].append(
        "Inserted canonical LIVE_QUOTES = {} declaration"
    )

    print_status(
        "FIXED",
        "Inserted canonical LIVE_QUOTES declaration",
    )


# ============================================================
# WRITE FILE
# ============================================================

updated_source = "\n".join(new_lines) + "\n"

try:

    ast.parse(updated_source)

except SyntaxError as exc:

    REPORT["errors"].append(
        f"Generated source failed syntax validation: {exc}"
    )

    print_status(
        "ERROR",
        f"Syntax validation failed: {exc}",
    )

    raise


LIVE_QUOTES_FILE.write_text(
    updated_source,
    encoding="utf-8",
)


# ============================================================
# FINAL SOURCE VALIDATION
# ============================================================

final_source = LIVE_QUOTES_FILE.read_text(
    encoding="utf-8"
)

checks = {
    "plain LIVE_QUOTES assignment":
        bool(
            re.search(
                r"(?m)^LIVE_QUOTES\s*=\s*\{\s*\}\s*$",
                final_source,
            )
        ),

    "update_live_quote function":
        bool(
            re.search(
                r"(?m)^def\s+update_live_quote\s*\(",
                final_source,
            )
        ),
}


print()
print("=" * 70)
print("LIVE_QUOTES AUDIT COMPATIBILITY CHECK")
print("=" * 70)

for name, result in checks.items():

    status = "PASS" if result else "FAIL"

    print_status(
        status,
        name,
    )

    if not result:
        REPORT["errors"].append(
            f"Validation failed: {name}"
        )


# ============================================================
# REPORT
# ============================================================

report_path = (
    PROJECT_ROOT
    / "live_quotes_audit_fix_report.json"
)

REPORT["validation"] = checks

report_path.write_text(
    json.dumps(
        REPORT,
        indent=2,
    ),
    encoding="utf-8",
)


print()
print("=" * 70)
print("LIVE_QUOTES FIX COMPLETE")
print("=" * 70)

print()
print("Changes:")

for change in REPORT["changes"]:
    print(f"  - {change}")

print()
print(f"Errors: {len(REPORT['errors'])}")

print()
print("Report:")
print(report_path)