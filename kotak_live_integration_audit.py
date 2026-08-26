"""
KOTAK LIVE INTEGRATION AUDIT
============================

Audits the actual Kotak live integration architecture.

Checks:

1. Project root detection
2. LIVE_QUOTES
3. update_live_quote
4. TickNormalizer
5. WebsocketManager
6. Kotak broker package
7. KotakNeoClient
8. LiveDataPipeline
9. Pipeline wiring
10. Basic import compatibility

IMPORTANT:
This script automatically finds the repository root instead
of assuming the parent directory.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# PROJECT ROOT DETECTION
# ============================================================

def find_project_root() -> Path:
    """
    Find the directory containing backend/.

    Supports execution from:
        C:\\Users\\Romala\\romala-algo
        C:\\Users\\Romala
        script directory
        nested directories
    """

    candidates = []

    # Current working directory and parents
    cwd = Path.cwd().resolve()

    candidates.append(cwd)
    candidates.extend(cwd.parents)

    # Script location and parents
    script_dir = Path(__file__).resolve().parent

    candidates.append(script_dir)
    candidates.extend(script_dir.parents)

    # Look for direct project root
    for candidate in candidates:

        if (
            (candidate / "backend").is_dir()
            and (candidate / "backend").exists()
        ):
            return candidate

    # Look one level down for common project folder
    for candidate in candidates:

        try:
            for child in candidate.iterdir():

                if not child.is_dir():
                    continue

                if (
                    (child / "backend").is_dir()
                    and (child / "backend").exists()
                ):
                    return child

        except (PermissionError, OSError):
            continue

    raise RuntimeError(
        "Could not find project root containing backend/"
    )


PROJECT_ROOT = find_project_root()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


BACKEND = PROJECT_ROOT / "backend"


# ============================================================
# REPORT
# ============================================================

report = {
    "generated_at": datetime.now().isoformat(),
    "project_root": str(PROJECT_ROOT),
    "summary": {},
    "checks": [],
}


def add_check(
    name: str,
    status: str,
    details: str,
    path: str | None = None,
):

    item = {
        "name": name,
        "status": status,
        "details": details,
    }

    if path:
        item["path"] = path

    report["checks"].append(item)

    print(
        f"[{status}] {name}"
    )

    print(
        f"    {details}"
    )

    if path:
        print(
            f"    Path: {path}"
        )


# ============================================================
# FILE HELPERS
# ============================================================

def file_exists(relative_path: str) -> bool:

    return (
        PROJECT_ROOT / relative_path
    ).is_file()


def read_file(relative_path: str) -> str:

    path = PROJECT_ROOT / relative_path

    try:

        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:

        return ""


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



# ============================================================
# CHECK 1
# PROJECT ROOT
# ============================================================

add_check(
    "Project root",
    "PASS",
    "Repository root detected successfully",
    str(PROJECT_ROOT),
)


# ============================================================
# CHECK 2
# LIVE_QUOTES
# ============================================================

LIVE_QUOTES_FILE = (
    "backend/market/live_quotes.py"
)

if (
    file_exists(LIVE_QUOTES_FILE)
    and contains_symbol(
        LIVE_QUOTES_FILE,
        "LIVE_QUOTES",
    )
):

    add_check(
        "LIVE_QUOTES",
        "PASS",
        "Central quote cache exists",
        LIVE_QUOTES_FILE,
    )

else:

    add_check(
        "LIVE_QUOTES",
        "MISSING",
        "Central quote cache missing",
        LIVE_QUOTES_FILE,
    )


# ============================================================
# CHECK 3
# update_live_quote
# ============================================================

if (
    file_exists(LIVE_QUOTES_FILE)
    and contains_symbol(
        LIVE_QUOTES_FILE,
        "update_live_quote",
    )
):

    add_check(
        "update_live_quote",
        "PASS",
        "Single ownership quote update function exists",
        LIVE_QUOTES_FILE,
    )

else:

    add_check(
        "update_live_quote",
        "MISSING",
        "Single ownership quote update function missing",
        LIVE_QUOTES_FILE,
    )


# ============================================================
# CHECK 4
# TickNormalizer
# ============================================================

TICK_NORMALIZER_FILE = (
    "backend/market/tick_normalizer.py"
)

if (
    file_exists(TICK_NORMALIZER_FILE)
    and contains_symbol(
        TICK_NORMALIZER_FILE,
        "TickNormalizer",
    )
):

    add_check(
        "TickNormalizer",
        "PASS",
        "Canonical broker tick normalization exists",
        TICK_NORMALIZER_FILE,
    )

else:

    add_check(
        "TickNormalizer",
        "MISSING",
        "Canonical broker tick normalization missing",
        TICK_NORMALIZER_FILE,
    )


# ============================================================
# CHECK 5
# WebsocketManager
# ============================================================

WEBSOCKET_MANAGER_FILE = (
    "backend/market/websocket_manager.py"
)

if (
    file_exists(WEBSOCKET_MANAGER_FILE)
    and contains_symbol(
        WEBSOCKET_MANAGER_FILE,
        "WebsocketManager",
    )
):

    add_check(
        "WebsocketManager",
        "PASS",
        "Central websocket pipeline exists",
        WEBSOCKET_MANAGER_FILE,
    )

else:

    add_check(
        "WebsocketManager",
        "MISSING",
        "Existing broker websocket pipeline missing",
        WEBSOCKET_MANAGER_FILE,
    )


# ============================================================
# CHECK 6
# KOTAK BROKER PACKAGE
# ============================================================

KOTAK_DIR = (
    BACKEND
    / "broker"
    / "kotak"
)

kotak_files = []

if KOTAK_DIR.exists():

    kotak_files = list(
        KOTAK_DIR.rglob("*.py")
    )

if kotak_files:

    add_check(
        "Kotak broker module",
        "PASS",
        f"Found {len(kotak_files)} Python file(s)",
        str(KOTAK_DIR.relative_to(PROJECT_ROOT)),
    )

else:

    add_check(
        "Kotak broker module",
        "MISSING",
        "No Kotak Python module found",
        "backend/broker/kotak",
    )


# ============================================================
# CHECK 7
# KotakNeoClient
# ============================================================

KOTAK_CLIENT_FILE = (
    "backend/broker/kotak/kotak_neo_client.py"
)

if (
    file_exists(KOTAK_CLIENT_FILE)
    and contains_symbol(
        KOTAK_CLIENT_FILE,
        "KotakNeoClient",
    )
):

    add_check(
        "KotakNeoClient",
        "PASS",
        "Kotak REST broker client exists",
        KOTAK_CLIENT_FILE,
    )

else:

    add_check(
        "KotakNeoClient",
        "MISSING",
        "No KotakNeoClient implementation found",
        KOTAK_CLIENT_FILE,
    )


# ============================================================
# CHECK 8
# LiveDataPipeline
# ============================================================

LIVE_PIPELINE_FILE = (
    "backend/market/live_data_pipeline.py"
)

if (
    file_exists(LIVE_PIPELINE_FILE)
    and contains_symbol(
        LIVE_PIPELINE_FILE,
        "LiveDataPipeline",
    )
):

    add_check(
        "LiveDataPipeline",
        "PASS",
        "Live data pipeline exists",
        LIVE_PIPELINE_FILE,
    )

else:

    add_check(
        "LiveDataPipeline",
        "MISSING",
        "Live data pipeline missing",
        LIVE_PIPELINE_FILE,
    )


# ============================================================
# CHECK 9
# PIPELINE WIRING
# ============================================================

pipeline_content = read_file(
    LIVE_PIPELINE_FILE
)

required_pipeline_refs = [
    "WebsocketManager",
]

missing_refs = []

for ref in required_pipeline_refs:

    if ref not in pipeline_content:

        missing_refs.append(ref)

if not missing_refs:

    add_check(
        "Pipeline wiring",
        "PASS",
        "LiveDataPipeline references WebsocketManager",
        LIVE_PIPELINE_FILE,
    )

else:

    add_check(
        "Pipeline wiring",
        "PARTIAL",
        (
            "Pipeline missing references: "
            + ", ".join(missing_refs)
        ),
        LIVE_PIPELINE_FILE,
    )


# ============================================================
# CHECK 10
# WEBSOCKET -> NORMALIZER -> CACHE
# ============================================================

manager_content = read_file(
    WEBSOCKET_MANAGER_FILE
)

required_manager_refs = [
    "TickNormalizer",
    "update_live_quote",
]

missing_manager_refs = []

for ref in required_manager_refs:

    if ref not in manager_content:

        missing_manager_refs.append(ref)

if not missing_manager_refs:

    add_check(
        "Tick processing chain",
        "PASS",
        (
            "WebsocketManager -> TickNormalizer "
            "-> LIVE_QUOTES chain exists"
        ),
        WEBSOCKET_MANAGER_FILE,
    )

else:

    add_check(
        "Tick processing chain",
        "PARTIAL",
        (
            "Missing chain components: "
            + ", ".join(missing_manager_refs)
        ),
        WEBSOCKET_MANAGER_FILE,
    )


# ============================================================
# CHECK 11
# BASIC PYTHON IMPORT VALIDATION
# ============================================================

modules_to_check = [
    "backend.market.live_quotes",
    "backend.market.tick_normalizer",
    "backend.market.websocket_manager",
    "backend.market.live_data_pipeline",
    "backend.broker.kotak.kotak_neo_client",
]

import_failures = []

for module_name in modules_to_check:

    try:

        spec = importlib.util.find_spec(
            module_name
        )

        if spec is None:

            import_failures.append(
                f"{module_name}: not found"
            )

    except Exception as exc:

        import_failures.append(
            f"{module_name}: {exc}"
        )

if not import_failures:

    add_check(
        "Module discovery",
        "PASS",
        "All core Kotak live modules are discoverable",
    )

else:

    add_check(
        "Module discovery",
        "PARTIAL",
        "; ".join(import_failures),
    )


# ============================================================
# SUMMARY
# ============================================================

passed = sum(
    1
    for item in report["checks"]
    if item["status"] == "PASS"
)

missing = sum(
    1
    for item in report["checks"]
    if item["status"] == "MISSING"
)

partial = sum(
    1
    for item in report["checks"]
    if item["status"] == "PARTIAL"
)

total = len(
    report["checks"]
)

report["summary"] = {
    "total": total,
    "passed": passed,
    "partial": partial,
    "missing": missing,
}


# ============================================================
# WRITE REPORT
# ============================================================

report_path = (
    PROJECT_ROOT
    / "kotak_live_integration_audit.json"
)

report_path.write_text(
    json.dumps(
        report,
        indent=2,
    ),
    encoding="utf-8",
)


print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

print(
    report["summary"]
)

print()
print("Report written to:")

print(report_path)
