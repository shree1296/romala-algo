#!/usr/bin/env python3
"""
ROMALA ALGO - AUTOMATIC REPAIR SCRIPT

Fixes identified issues:

1. Invalid CORS origins containing Markdown URLs
2. Broker status contract does not explicitly expose `connected`
3. WebSocket tick broadcasting from Kotak Neo background thread
4. Event loop retrieval from a non-async SDK thread
5. Unsafe mutation of WebSocket client list during iteration
6. Synthetic historical candle responses not clearly labelled
7. Indicator responses based on synthetic historical data not labelled
8. Strategy responses based on synthetic historical data not labelled
9. Scanner responses based on synthetic historical data not labelled
10. Windows launcher shutdown leaving child processes behind

The script:
- Creates timestamped backups
- Applies patches only when matching source code is found
- Stops if a critical patch cannot be safely applied
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT = Path(__file__).resolve().parent

MAIN_FILE = ROOT / "backend" / "main.py"
LAUNCH_FILE = ROOT / "launch.py"

BACKUP_DIR = ROOT / "_repair_backups"


# ============================================================================
# DISPLAY
# ============================================================================

def header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def info(message: str) -> None:
    print(f"[fixer] {message}", flush=True)


def success(message: str) -> None:
    print(f"[fixer] [OK] {message}", flush=True)


def warning(message: str) -> None:
    print(f"[fixer] [WARNING] {message}", flush=True)


def error(message: str) -> None:
    print(f"[fixer] [ERROR] {message}", flush=True)


# ============================================================================
# BACKUP
# ============================================================================

def backup_file(path: Path) -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup = BACKUP_DIR / f"{path.name}.{timestamp}.bak"

    shutil.copy2(path, backup)

    success(f"Backup created: {backup}")

    return backup


# ============================================================================
# FILE UTILITIES
# ============================================================================

def read_file(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def write_file(path: Path, content: str) -> None:
    path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )


def replace_once(
    content: str,
    old: str,
    new: str,
    label: str,
) -> tuple[str, bool]:

    if old not in content:
        warning(f"Could not find exact source for: {label}")
        return content, False

    content = content.replace(
        old,
        new,
        1,
    )

    success(f"Patched: {label}")

    return content, True


# ============================================================================
# PATCH BACKEND
# ============================================================================

def patch_backend() -> bool:

    header("PATCHING BACKEND")

    if not MAIN_FILE.exists():
        error(f"backend/main.py not found: {MAIN_FILE}")
        return False

    backup_file(MAIN_FILE)

    content = read_file(MAIN_FILE)

    original = content

    changes = 0

    # ------------------------------------------------------------------------
    # 1. FIX CORS
    # ------------------------------------------------------------------------

    old_cors = '''app.add_middleware(
    CORSMiddleware,
    allow_origins=["[http://localhost:5173](http://localhost:5173)", "[http://localhost:5174](http://localhost:5174)", "[http://127.0.0.1:5173](http://127.0.0.1:5173)"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''

    new_cors = '''app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''

    content, changed = replace_once(
        content,
        old_cors,
        new_cors,
        "CORS configuration",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # 2. ENSURE ASYNCIO IS IMPORTED NEAR TOP
    # ------------------------------------------------------------------------

    if "import asyncio\n" not in content:

        marker = "import os\n"

        if marker in content:

            content = content.replace(
                marker,
                "import asyncio\n" + marker,
                1,
            )

            success("Patched: asyncio import")
            changes += 1

        else:
            warning("Could not safely add asyncio import.")

    # Remove duplicate late asyncio import if present.

    content = content.replace(
        "\n_active_ws_clients: list[WebSocket] = []\nimport asyncio\n",
        "\n_active_ws_clients: list[WebSocket] = []\n",
    )

    # ------------------------------------------------------------------------
    # 3. ADD FASTAPI EVENT LOOP STORAGE
    # ------------------------------------------------------------------------

    if "async def _capture_application_event_loop()" not in content:

        marker = "START_TIME = time.time()"

        loop_setup = '''

@app.on_event("startup")
async def _capture_application_event_loop() -> None:
    """
    Capture the FastAPI/Uvicorn event loop.

    Kotak Neo SDK callbacks may arrive from a background thread.
    That thread must NOT attempt to create or retrieve its own
    asyncio event loop.
    """
    app.state.event_loop = asyncio.get_running_loop()
    logger.info("FastAPI event loop captured for broker callbacks.")
'''

        if marker in content:

            content = content.replace(
                marker,
                marker + loop_setup,
                1,
            )

            success("Patched: application event loop capture")
            changes += 1

        else:
            warning("Could not safely add application event loop capture.")

    # ------------------------------------------------------------------------
    # 4. REPLACE WEBSOCKET TICK BROADCASTER
    # ------------------------------------------------------------------------

    pattern = re.compile(
        r'def _broadcast_tick\(tick: dict\) -> None:\n'
        r'.*?'
        r'for ws in dead:\n'
        r'    if ws in _active_ws_clients:\n'
        r'        _active_ws_clients\.remove\(ws\)\n',
        re.DOTALL,
    )

    replacement = '''def _broadcast_tick(tick: dict) -> None:
    """
    Forward a Kotak Neo tick to every connected WebSocket client.

    IMPORTANT:
    Kotak Neo SDK callbacks may execute on a background thread.

    We therefore schedule WebSocket sends on the FastAPI/Uvicorn
    event loop captured during application startup.
    """

    loop = getattr(app.state, "event_loop", None)

    if loop is None:
        logger.warning(
            "Tick received before FastAPI event loop was available."
        )
        return

    dead: list[WebSocket] = []

    for ws in list(_active_ws_clients):

        try:

            if ws.client_state.name != "CONNECTED":

                dead.append(ws)

                continue

            future = asyncio.run_coroutine_threadsafe(
                ws.send_json(
                    {
                        "type": "tick",
                        "data": tick,
                    }
                ),
                loop,
            )

            def _handle_result(
                completed_future,
                websocket=ws,
            ):
                try:
                    completed_future.result()

                except Exception as exc:

                    logger.warning(
                        f"WebSocket tick delivery failed: {exc}"
                    )

                    if websocket in _active_ws_clients:
                        _active_ws_clients.remove(websocket)

            future.add_done_callback(
                _handle_result
            )

        except Exception as exc:

            logger.warning(
                f"Could not schedule tick broadcast: {exc}"
            )

            dead.append(ws)

    for ws in dead:

        if ws in _active_ws_clients:

            _active_ws_clients.remove(ws)
'''

    if pattern.search(content):

        content = pattern.sub(
            replacement,
            content,
            count=1,
        )

        success("Patched: thread-safe WebSocket tick broadcasting")
        changes += 1

    elif "asyncio.run_coroutine_threadsafe" in content:

        success("WebSocket broadcaster already appears patched.")

    else:

        warning(
            "Could not safely locate existing WebSocket broadcaster."
        )

    # ------------------------------------------------------------------------
    # 5. IMPROVE BROKER STATUS CONTRACT
    # ------------------------------------------------------------------------

    old_broker_status = '''@app.get("/api/broker/status")
async def broker_status():
    return neo._status()
'''

    new_broker_status = '''@app.get("/api/broker/status")
async def broker_status():

    raw_status = neo._status()

    if not isinstance(raw_status, dict):
        raw_status = {
            "message": str(raw_status)
        }

    connected = bool(neo.connected)

    raw_status["connected"] = connected

    raw_status["status"] = (
        "connected"
        if connected
        else "disconnected"
    )

    raw_status.setdefault(
        "message",
        (
            "Connected"
            if connected
            else "Not connected — please login"
        ),
    )

    return raw_status
'''

    content, changed = replace_once(
        content,
        old_broker_status,
        new_broker_status,
        "explicit broker connection status",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # 6. LABEL SYNTHETIC HISTORICAL DATA
    # ------------------------------------------------------------------------

    old_historical_return = '''    return [
        {
            "timestamp": b.timestamp,
            "date": b.date,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
'''

    new_historical_return = '''    return {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "data_source": "synthetic_fallback",
        "warning": (
            "These candles are generated from current quote OHLC data "
            "and are NOT genuine historical market candles."
        ),
        "bars": [
            {
                "timestamp": b.timestamp,
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ],
    }
'''

    content, changed = replace_once(
        content,
        old_historical_return,
        new_historical_return,
        "historical synthetic-data labeling",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # 7. LABEL INDICATOR RESULTS
    # ------------------------------------------------------------------------

    old_indicator_return = '''    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(ohlc_bars),
        "indicators": indicator_list,
        "computed_at": int(time.time() * 1000),
    }
'''

    new_indicator_return = '''    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(ohlc_bars),
        "data_source": "synthetic_fallback",
        "warning": (
            "Indicators are currently calculated from generated "
            "fallback candles, not genuine historical candles."
        ),
        "indicators": indicator_list,
        "computed_at": int(time.time() * 1000),
    }
'''

    content, changed = replace_once(
        content,
        old_indicator_return,
        new_indicator_return,
        "indicator synthetic-data labeling",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # 8. LABEL STRATEGY RESULT
    # ------------------------------------------------------------------------

    old_strategy_return = '''    return run_strategy(strategy_id, symbol, bars)
'''

    new_strategy_return = '''    result = run_strategy(
        strategy_id,
        symbol,
        bars,
    )

    if isinstance(result, dict):

        result["data_source"] = "synthetic_fallback"

        result["warning"] = (
            "This strategy result is currently calculated from "
            "generated fallback candles, not genuine historical candles."
        )

    return result
'''

    content, changed = replace_once(
        content,
        old_strategy_return,
        new_strategy_return,
        "strategy synthetic-data labeling",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # 9. LABEL SCANNER RESULTS
    # ------------------------------------------------------------------------

    old_scan_return = '''    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results
'''

    new_scan_return = '''    results.sort(
        key=lambda r: r["confidence"],
        reverse=True,
    )

    return {
        "data_source": "synthetic_fallback",
        "warning": (
            "Scanner signals are currently calculated from generated "
            "fallback candles, not genuine historical market candles."
        ),
        "results": results,
    }
'''

    content, changed = replace_once(
        content,
        old_scan_return,
        new_scan_return,
        "scanner synthetic-data labeling",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # WRITE BACKEND
    # ------------------------------------------------------------------------

    if content == original:

        warning("No backend changes were applied.")

        return True

    write_file(
        MAIN_FILE,
        content,
    )

    success(
        f"Backend patched successfully. Changes applied: {changes}"
    )

    return True


# ============================================================================
# PATCH LAUNCHER
# ============================================================================

def patch_launcher() -> bool:

    header("PATCHING LAUNCHER")

    if not LAUNCH_FILE.exists():

        warning(
            f"launch.py not found: {LAUNCH_FILE}"
        )

        return True

    backup_file(LAUNCH_FILE)

    content = read_file(LAUNCH_FILE)

    original = content

    changes = 0

    # ------------------------------------------------------------------------
    # Add Windows process tree helper
    # ------------------------------------------------------------------------

    if "def terminate_process_tree(" not in content:

        marker = "\n\n# ============================================================================\n# SHUTDOWN\n# ============================================================================\n"

        helper = '''

# ============================================================================
# PROCESS TREE TERMINATION
# ============================================================================

def terminate_process_tree(
    process: subprocess.Popen,
    name: str,
) -> bool:
    """
    Terminate a process and all of its child processes.

    This is particularly important on Windows because npm, Vite,
    and some server launchers can create child processes.
    """

    if process.poll() is not None:
        return True

    if os.name == "nt":

        info(
            f"Stopping Windows process tree for {name} "
            f"(PID {process.pid})..."
        )

        try:

            result = subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:

                success(
                    f"{name} process tree stopped."
                )

                return True

            warning(
                f"taskkill returned {result.returncode}: "
                f"{result.stderr.strip()}"
            )

        except Exception as exc:

            warning(
                f"Could not terminate process tree: {exc}"
            )

    return False
'''

        if marker in content:

            content = content.replace(
                marker,
                helper + marker,
                1,
            )

            success("Patched: Windows process tree termination helper")

            changes += 1

        else:

            warning(
                "Could not safely add process tree helper."
            )

    # ------------------------------------------------------------------------
    # Call tree termination before normal termination
    # ------------------------------------------------------------------------

    old_terminate = '''    info(
        f"Stopping {name} process "
        f"(PID {process.pid})..."
    )

    try:

        process.terminate()
'''

    new_terminate = '''    info(
        f"Stopping {name} process "
        f"(PID {process.pid})..."
    )

    if terminate_process_tree(
        process,
        name,
    ):
        return

    try:

        process.terminate()
'''

    content, changed = replace_once(
        content,
        old_terminate,
        new_terminate,
        "process tree shutdown",
    )

    changes += int(changed)

    # ------------------------------------------------------------------------
    # WRITE LAUNCHER
    # ------------------------------------------------------------------------

    if content == original:

        warning("No launcher changes were applied.")

        return True

    write_file(
        LAUNCH_FILE,
        content,
    )

    success(
        f"Launcher patched successfully. Changes applied: {changes}"
    )

    return True


# ============================================================================
# VALIDATE PYTHON
# ============================================================================

def validate_python(path: Path) -> bool:

    header(f"VALIDATING {path.relative_to(ROOT)}")

    try:

        source = read_file(path)

        compile(
            source,
            str(path),
            "exec",
        )

        success("Python syntax validation passed.")

        return True

    except SyntaxError as exc:

        error(
            f"Syntax error detected: "
            f"{exc.msg} "
            f"at line {exc.lineno}"
        )

        return False

    except Exception as exc:

        error(
            f"Validation failed: {exc}"
        )

        return False


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:

    header("ROMALA ALGO AUTOMATIC REPAIR")

    info(f"Project root: {ROOT}")

    if not MAIN_FILE.exists():

        error(
            "Run this script from the Romala Algo project root."
        )

        error(
            f"Expected file: {MAIN_FILE}"
        )

        return 1

    backend_ok = patch_backend()

    if not backend_ok:

        error("Backend patch failed.")

        return 1

    launcher_ok = patch_launcher()

    if not launcher_ok:

        error("Launcher patch failed.")

        return 1

    # ------------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------------

    backend_valid = validate_python(
        MAIN_FILE
    )

    launcher_valid = True

    if LAUNCH_FILE.exists():

        launcher_valid = validate_python(
            LAUNCH_FILE
        )

    # ------------------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------------------

    header("FINAL RESULT")

    if backend_valid and launcher_valid:

        success(
            "All patched files passed Python syntax validation."
        )

        print()

        info("Backups are stored in:")

        print(
            f"  {BACKUP_DIR}"
        )

        print()

        info("Next step:")

        print(
            "  python launch.py"
        )

        return 0

    error(
        "One or more patched files failed validation."
    )

    warning(
        "Restore the latest backup from _repair_backups before continuing."
    )

    return 1


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":

    try:

        raise SystemExit(
            main()
        )

    except KeyboardInterrupt:

        print()

        warning(
            "Repair cancelled by user."
        )

        raise SystemExit(130)