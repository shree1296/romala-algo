"""
KOTAK LIVE PIPELINE DEEP VALIDATION
===================================

Performs runtime inspection without connecting to Kotak.

Validates:

1. TickNormalizer public API discovery
2. TickNormalizer callable methods
3. WebsocketManager public API discovery
4. LiveDataPipeline public API discovery
5. Source-level import/wiring relationships
6. LIVE_QUOTES runtime ownership
7. Synthetic normalized quote update
8. Duplicate quote-store detection
9. Startup candidate discovery

This script does NOT:
- connect to Kotak
- authenticate
- subscribe to WebSocket
- place orders

Run:

    python kotak_pipeline_deep_validation.py
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

def find_project_root() -> Path:

    candidates = []

    cwd = Path.cwd().resolve()

    candidates.append(cwd)
    candidates.extend(cwd.parents)

    script_dir = Path(__file__).resolve().parent

    candidates.append(script_dir)
    candidates.extend(script_dir.parents)

    for candidate in candidates:

        if (candidate / "backend").is_dir():
            return candidate

    raise RuntimeError(
        "Could not locate project root containing backend/"
    )


PROJECT_ROOT = find_project_root()
BACKEND = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# ============================================================
# REPORT
# ============================================================

report = {
    "generated_at": datetime.now().isoformat(),
    "project_root": str(PROJECT_ROOT),
    "summary": {},
    "checks": [],
    "apis": {},
    "startup_candidates": [],
    "duplicate_quote_files": [],
    "errors": [],
}


def add_check(
    name: str,
    status: str,
    details: str,
):

    report["checks"].append(
        {
            "name": name,
            "status": status,
            "details": details,
        }
    )

    print(f"[{status}] {name}")
    print(f"    {details}")


def add_error(
    name: str,
    exc: Exception,
):

    report["errors"].append(
        {
            "name": name,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    )

    print(f"[ERROR] {name}")
    print(f"    {exc}")


def get_public_methods(
    obj,
):

    methods = []

    for name, member in inspect.getmembers(
        obj,
    ):

        if name.startswith("_"):
            continue

        if callable(member):

            methods.append(name)

    return methods


def read_file(
    path: Path,
) -> str:

    try:

        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:

        return ""


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 70)
print("KOTAK LIVE PIPELINE DEEP VALIDATION")
print("=" * 70)
print()

print(
    f"[INFO] Project root: {PROJECT_ROOT}"
)


# ============================================================
# IMPORT MODULES
# ============================================================

MODULE_NAMES = [
    "backend.market.live_quotes",
    "backend.market.tick_normalizer",
    "backend.market.websocket_manager",
    "backend.market.live_data_pipeline",
    "backend.broker.kotak.kotak_neo_client",
]

modules = {}

for module_name in MODULE_NAMES:

    try:

        module = importlib.import_module(
            module_name
        )

        modules[module_name] = module

        add_check(
            f"Import {module_name}",
            "PASS",
            "Imported successfully",
        )

    except Exception as exc:

        add_error(
            f"Import {module_name}",
            exc,
        )


# ============================================================
# LOAD COMPONENTS
# ============================================================

if not report["errors"]:

    try:

        live_quotes_module = modules[
            "backend.market.live_quotes"
        ]

        normalizer_module = modules[
            "backend.market.tick_normalizer"
        ]

        websocket_module = modules[
            "backend.market.websocket_manager"
        ]

        pipeline_module = modules[
            "backend.market.live_data_pipeline"
        ]

        LIVE_QUOTES = getattr(
            live_quotes_module,
            "LIVE_QUOTES",
        )

        update_live_quote = getattr(
            live_quotes_module,
            "update_live_quote",
        )

        clear_live_quotes = getattr(
            live_quotes_module,
            "clear_live_quotes",
        )

        TickNormalizer = getattr(
            normalizer_module,
            "TickNormalizer",
        )

        WebsocketManager = getattr(
            websocket_module,
            "WebsocketManager",
        )

        LiveDataPipeline = getattr(
            pipeline_module,
            "LiveDataPipeline",
        )

        add_check(
            "Core runtime symbols",
            "PASS",
            (
                "All required live pipeline "
                "components loaded"
            ),
        )

    except Exception as exc:

        add_error(
            "Core runtime symbols",
            exc,
        )


# ============================================================
# TICK NORMALIZER API DISCOVERY
# ============================================================

normalizer = None

if not report["errors"]:

    try:

        normalizer = TickNormalizer()

        methods = get_public_methods(
            normalizer
        )

        report["apis"]["TickNormalizer"] = {
            "methods": methods,
        }

        print()
        print("-" * 70)
        print("TickNormalizer PUBLIC METHODS")
        print("-" * 70)

        if methods:

            for method in methods:
                print(f"  - {method}")

            add_check(
                "TickNormalizer API",
                "PASS",
                (
                    f"Discovered {len(methods)} "
                    "public callable method(s)"
                ),
            )

        else:

            add_check(
                "TickNormalizer API",
                "PARTIAL",
                (
                    "No public callable methods found"
                ),
            )

    except Exception as exc:

        add_error(
            "TickNormalizer API",
            exc,
        )


# ============================================================
# WEBSOCKET MANAGER API DISCOVERY
# ============================================================

if not report["errors"]:

    try:

        manager = WebsocketManager()

        methods = get_public_methods(
            manager
        )

        report["apis"]["WebsocketManager"] = {
            "methods": methods,
        }

        print()
        print("-" * 70)
        print("WebsocketManager PUBLIC METHODS")
        print("-" * 70)

        if methods:

            for method in methods:
                print(f"  - {method}")

            add_check(
                "WebsocketManager API",
                "PASS",
                (
                    f"Discovered {len(methods)} "
                    "public callable method(s)"
                ),
            )

        else:

            add_check(
                "WebsocketManager API",
                "PARTIAL",
                (
                    "No public callable methods found"
                ),
            )

    except Exception as exc:

        add_error(
            "WebsocketManager API",
            exc,
        )


# ============================================================
# LIVE DATA PIPELINE API DISCOVERY
# ============================================================

if not report["errors"]:

    try:

        pipeline = LiveDataPipeline()

        methods = get_public_methods(
            pipeline
        )

        report["apis"]["LiveDataPipeline"] = {
            "methods": methods,
        }

        print()
        print("-" * 70)
        print("LiveDataPipeline PUBLIC METHODS")
        print("-" * 70)

        if methods:

            for method in methods:
                print(f"  - {method}")

            add_check(
                "LiveDataPipeline API",
                "PASS",
                (
                    f"Discovered {len(methods)} "
                    "public callable method(s)"
                ),
            )

        else:

            add_check(
                "LiveDataPipeline API",
                "PARTIAL",
                (
                    "No public callable methods found"
                ),
            )

    except Exception as exc:

        add_error(
            "LiveDataPipeline API",
            exc,
        )


# ============================================================
# LIVE QUOTE RUNTIME VALIDATION
# ============================================================

if not report["errors"]:

    try:

        clear_live_quotes()

        synthetic_normalized_tick = {
            "exchange": "nse_fo",
            "token": "SMOKE_001",
            "symbol": "NIFTY_SMOKE_TEST",
            "ltp": 25000.50,
            "timestamp": datetime.now().isoformat(),
            "source": "smoke_test",
        }

        update_live_quote(
            synthetic_normalized_tick
        )

        expected_key = (
            "nse_fo|SMOKE_001"
        )

        if expected_key not in LIVE_QUOTES:

            raise RuntimeError(
                "Synthetic quote missing from "
                "LIVE_QUOTES"
            )

        cached_quote = LIVE_QUOTES[
            expected_key
        ]

        if (
            cached_quote.get("ltp")
            != 25000.50
        ):

            raise RuntimeError(
                "Cached LTP validation failed"
            )

        add_check(
            "LIVE_QUOTES ownership",
            "PASS",
            (
                "Synthetic normalized tick successfully "
                "stored in central quote cache"
            ),
        )

    except Exception as exc:

        add_error(
            "LIVE_QUOTES ownership",
            exc,
        )


# ============================================================
# SOURCE-LEVEL WIRING VALIDATION
# ============================================================

SOURCE_CHECKS = [
    (
        BACKEND
        / "market"
        / "websocket_manager.py",
        "TickNormalizer",
        "WebsocketManager -> TickNormalizer",
    ),
    (
        BACKEND
        / "market"
        / "websocket_manager.py",
        "update_live_quote",
        "WebsocketManager -> update_live_quote",
    ),
    (
        BACKEND
        / "market"
        / "live_data_pipeline.py",
        "WebsocketManager",
        "LiveDataPipeline -> WebsocketManager",
    ),
]


for file_path, symbol, check_name in SOURCE_CHECKS:

    try:

        content = read_file(
            file_path
        )

        if symbol in content:

            add_check(
                check_name,
                "PASS",
                (
                    f"{symbol} reference found in "
                    f"{file_path.name}"
                ),
            )

        else:

            add_check(
                check_name,
                "PARTIAL",
                (
                    f"{symbol} reference NOT found in "
                    f"{file_path.name}"
                ),
            )

    except Exception as exc:

        add_error(
            check_name,
            exc,
        )


# ============================================================
# DUPLICATE LIVE QUOTE STORE DETECTION
# ============================================================

try:

    quote_files = []

    for path in BACKEND.rglob("*.py"):

        if path.name == "live_quotes.py":

            quote_files.append(
                str(
                    path.relative_to(
                        PROJECT_ROOT
                    )
                )
            )

    report[
        "duplicate_quote_files"
    ] = quote_files

    if len(quote_files) == 1:

        add_check(
            "Single LIVE_QUOTES module",
            "PASS",
            quote_files[0],
        )

    elif len(quote_files) > 1:

        add_check(
            "Single LIVE_QUOTES module",
            "PARTIAL",
            (
                "Multiple live_quotes.py files found: "
                + ", ".join(quote_files)
            ),
        )

    else:

        add_check(
            "Single LIVE_QUOTES module",
            "MISSING",
            "No live_quotes.py found",
        )

except Exception as exc:

    add_error(
        "Single LIVE_QUOTES module",
        exc,
    )


# ============================================================
# STARTUP FILE DISCOVERY
# ============================================================

STARTUP_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "startup.py",
    "run.py",
}

startup_candidates = []

for path in PROJECT_ROOT.rglob("*.py"):

    if ".venv" in path.parts:
        continue

    if "__pycache__" in path.parts:
        continue

    if path.name in STARTUP_NAMES:

        relative_path = str(
            path.relative_to(
                PROJECT_ROOT
            )
        )

        startup_candidates.append(
            relative_path
        )

report[
    "startup_candidates"
] = startup_candidates


print()
print("-" * 70)
print("STARTUP CANDIDATES")
print("-" * 70)

if startup_candidates:

    for candidate in startup_candidates:
        print(f"  - {candidate}")

    add_check(
        "Startup discovery",
        "PASS",
        (
            f"Found {len(startup_candidates)} "
            "startup candidate(s)"
        ),
    )

else:

    add_check(
        "Startup discovery",
        "PARTIAL",
        (
            "No standard startup file name found"
        ),
    )


# ============================================================
# CHECK STARTUP REFERENCES
# ============================================================

pipeline_references = []

for relative_path in startup_candidates:

    path = PROJECT_ROOT / relative_path

    content = read_file(
        path
    )

    references = []

    for symbol in [
        "LiveDataPipeline",
        "WebsocketManager",
        "KotakNeoClient",
    ]:

        if symbol in content:
            references.append(symbol)

    if references:

        pipeline_references.append(
            {
                "file": relative_path,
                "references": references,
            }
        )


report[
    "startup_pipeline_references"
] = pipeline_references


if pipeline_references:

    details = []

    for item in pipeline_references:

        details.append(
            (
                f"{item['file']}: "
                + ", ".join(
                    item["references"]
                )
            )
        )

    add_check(
        "Startup pipeline references",
        "PASS",
        "; ".join(details),
    )

else:

    add_check(
        "Startup pipeline references",
        "PARTIAL",
        (
            "Startup files found but no direct "
            "LiveDataPipeline/WebsocketManager/"
            "KotakNeoClient references detected"
        ),
    )


# ============================================================
# SUMMARY
# ============================================================

passed = sum(
    1
    for item in report["checks"]
    if item["status"] == "PASS"
)

partial = sum(
    1
    for item in report["checks"]
    if item["status"] == "PARTIAL"
)

missing = sum(
    1
    for item in report["checks"]
    if item["status"] == "MISSING"
)

errors = len(
    report["errors"]
)

total = len(
    report["checks"]
)

report["summary"] = {
    "total_checks": total,
    "passed": passed,
    "partial": partial,
    "missing": missing,
    "errors": errors,
}


# ============================================================
# WRITE REPORT
# ============================================================

report_path = (
    PROJECT_ROOT
    / "kotak_pipeline_deep_validation.json"
)

report_path.write_text(
    json.dumps(
        report,
        indent=2,
        default=str,
    ),
    encoding="utf-8",
)


# ============================================================
# FINAL OUTPUT
# ============================================================

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

print(
    json.dumps(
        report["summary"],
        indent=2,
    )
)

print()

if errors == 0 and missing == 0:

    print(
        "RESULT: DEEP VALIDATION COMPLETED"
    )

elif errors == 0:

    print(
        "RESULT: VALIDATION COMPLETED WITH PARTIAL FINDINGS"
    )

else:

    print(
        "RESULT: RUNTIME VALIDATION ISSUES DETECTED"
    )

print()
print("Report written to:")
print(report_path)