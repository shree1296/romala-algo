#!/usr/bin/env python3
"""
Romala Algo - Full Stack Launcher

Starts:
    Backend  -> FastAPI / Uvicorn -> http://localhost:8000
    Frontend -> Vite             -> http://localhost:5173

Usage:

    python launch.py
        Start both backend and frontend

    python launch.py --backend
        Start backend only

    python launch.py --frontend
        Start frontend only

    python launch.py --debug
        Start both with extra diagnostics

Requirements:
    Python virtual environment should be activated.

The launcher automatically:
    - Detects Python
    - Detects Node.js/npm
    - Installs missing Python dependencies
    - Installs missing frontend dependencies
    - Starts FastAPI
    - Starts Vite
    - Performs health checks
    - Stops both processes with Ctrl+C
"""

from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional


# ============================================================================
# PATHS
# ============================================================================

ROOT = Path(__file__).resolve().parent

BACKEND_DIR = ROOT / "backend"

REQUIREMENTS_FILE = BACKEND_DIR / "requirements.txt"

BACKEND_MAIN = BACKEND_DIR / "main.py"

BACKEND_PACKAGE = BACKEND_DIR / "__init__.py"

# Frontend is currently expected at project root.
# package.json must therefore exist here.
FRONTEND_DIR = ROOT

PACKAGE_JSON = FRONTEND_DIR / "package.json"

NODE_MODULES = FRONTEND_DIR / "node_modules"


# ============================================================================
# PORTS
# ============================================================================

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000

FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173


# ============================================================================
# GLOBAL PROCESS STORAGE
# ============================================================================

processes: list[subprocess.Popen] = []

shutdown_requested = False


# ============================================================================
# DISPLAY HELPERS
# ============================================================================

def header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def info(message: str) -> None:
    print(f"[launcher] {message}", flush=True)


def success(message: str) -> None:
    print(f"[launcher] [OK] {message}", flush=True)


def warning(message: str) -> None:
    print(f"[launcher] [WARNING] {message}", flush=True)


def error(message: str) -> None:
    print(f"[launcher] [ERROR] {message}", flush=True)


# ============================================================================
# ENVIRONMENT
# ============================================================================

def setup_environment() -> None:
    """
    Configure environment variables so imports work consistently.
    """

    # Ensure project root is available to Python.
    root_string = str(ROOT)

    python_path = os.environ.get("PYTHONPATH", "")

    paths = python_path.split(os.pathsep) if python_path else []

    if root_string not in paths:
        paths.insert(0, root_string)

    os.environ["PYTHONPATH"] = os.pathsep.join(paths)

    # Backend can also be imported directly if needed.
    backend_string = str(BACKEND_DIR)

    if backend_string not in paths:
        paths.insert(0, backend_string)

    os.environ["PYTHONPATH"] = os.pathsep.join(paths)

    # Helpful for unbuffered logs.
    os.environ["PYTHONUNBUFFERED"] = "1"


# ============================================================================
# LOAD .ENV
# ============================================================================

def load_backend_env() -> None:
    """
    Load backend/.env into os.environ.

    Existing environment variables always win.
    """

    env_file = BACKEND_DIR / ".env"

    if not env_file.exists():
        info("backend/.env not found; continuing with existing environment.")
        return

    info(f"Loading environment from {env_file}")

    try:
        for raw_line in env_file.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines():

            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            key = key.strip()
            value = value.strip()

            # Remove optional surrounding quotes.
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in ("'", '"')
            ):
                value = value[1:-1]

            if key:
                os.environ.setdefault(key, value)

        success("Backend .env loaded.")

    except Exception as exc:
        warning(f"Could not load backend/.env: {exc}")


# ============================================================================
# EXECUTABLE DETECTION
# ============================================================================

def find_executable(name: str) -> Optional[str]:
    """
    Find an executable in PATH.

    Windows requires special handling for npm because the actual
    executable is normally npm.cmd.
    """

    # First attempt standard PATH lookup.
    result = shutil.which(name)

    if result:
        return result

    if os.name == "nt":

        candidates = []

        if name.lower() == "npm":
            candidates.extend(
                [
                    "npm.cmd",
                    "npm.exe",
                ]
            )

        elif name.lower() == "node":
            candidates.extend(
                [
                    "node.exe",
                ]
            )

        elif name.lower() == "npx":
            candidates.extend(
                [
                    "npx.cmd",
                    "npx.exe",
                ]
            )

        for candidate in candidates:
            result = shutil.which(candidate)

            if result:
                return result

    return None


def find_node() -> Optional[str]:
    return find_executable("node")


def find_npm() -> Optional[str]:
    return find_executable("npm")


# ============================================================================
# PYTHON CHECK
# ============================================================================

def check_python() -> bool:
    header("PYTHON")

    info(f"Python executable: {sys.executable}")
    info(f"Python version: {sys.version.split()[0]}")

    if hasattr(sys, "prefix"):
        info(f"Python prefix: {sys.prefix}")

    virtual_env = os.environ.get("VIRTUAL_ENV")

    if virtual_env:
        success(f"Virtual environment: {virtual_env}")
    else:
        warning(
            "VIRTUAL_ENV is not set. "
            "The launcher will still use the current Python executable."
        )

    if not BACKEND_DIR.exists():
        error(f"Backend directory does not exist: {BACKEND_DIR}")
        return False

    if not BACKEND_MAIN.exists():
        error(f"backend/main.py does not exist: {BACKEND_MAIN}")
        return False

    success("Python/backend structure detected.")

    return True


# ============================================================================
# PYTHON DEPENDENCIES
# ============================================================================

def python_package_available(module_name: str) -> bool:
    """
    Test whether a Python package/module can be imported.
    """

    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def pip_install(arguments: list[str]) -> bool:
    """
    Install packages using the exact Python interpreter running this launcher.
    """

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        *arguments,
    ]

    info("Running:")
    info(" ".join(f'"{x}"' if " " in x else x for x in command))

    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            check=False,
        )

        return result.returncode == 0

    except Exception as exc:
        error(f"pip execution failed: {exc}")
        return False


def ensure_python_dependencies() -> bool:
    header("PYTHON DEPENDENCIES")

    required_modules = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "neo_api_client",
    ]

    missing = []

    for module in required_modules:

        if python_package_available(module):
            success(f"{module}")
        else:
            missing.append(module)
            warning(f"{module} is missing.")

    if not missing:
        success("All required Python modules are installed.")
        return True

    if not REQUIREMENTS_FILE.exists():
        error(f"Missing requirements file: {REQUIREMENTS_FILE}")
        return False

    info("Installing backend requirements...")

    if not pip_install(["-r", str(REQUIREMENTS_FILE)]):
        error("Python dependency installation failed.")
        return False

    # Verify again.
    failed = []

    for module in required_modules:

        if python_package_available(module):
            success(f"{module} import verified")
        else:
            failed.append(module)

    if failed:
        error(
            "The following Python modules are still unavailable: "
            + ", ".join(failed)
        )
        return False

    success("Python dependencies are ready.")

    return True


# ============================================================================
# KOTAK NEO CHECK
# ============================================================================

def check_kotak_neo() -> bool:
    header("KOTAK NEO SDK")

    try:
        from neo_api_client import NeoAPI

        success("neo_api_client imported.")
        success(f"NeoAPI class: {NeoAPI}")

        return True

    except Exception as exc:
        error(f"neo_api_client import failed: {exc}")
        return False


# ============================================================================
# PROJECT STRUCTURE CHECK
# ============================================================================

def check_project_structure() -> bool:
    header("PROJECT STRUCTURE")

    required_paths = [
        BACKEND_DIR,
        BACKEND_MAIN,
        BACKEND_PACKAGE,
        BACKEND_DIR / "kotak_neo",
        BACKEND_DIR / "kotak_neo" / "__init__.py",
        BACKEND_DIR / "kotak_neo" / "client.py",
        BACKEND_DIR / "indicators",
        BACKEND_DIR / "indicators" / "engine.py",
        BACKEND_DIR / "strategies",
        BACKEND_DIR / "strategies" / "engine.py",
    ]

    ok = True

    for path in required_paths:

        if path.exists():
            success(str(path.relative_to(ROOT)))
        else:
            error(f"Missing: {path.relative_to(ROOT)}")
            ok = False

    # Detect old typo if it still exists.
    old_directory = BACKEND_DIR / "kotek_neo"

    if old_directory.exists():

        warning(
            "Found old directory name backend/kotek_neo."
        )

        new_directory = BACKEND_DIR / "kotak_neo"

        if not new_directory.exists():

            try:
                old_directory.rename(new_directory)

                success(
                    "Renamed backend/kotek_neo -> backend/kotak_neo"
                )

            except Exception as exc:
                error(f"Could not rename old Kotak directory: {exc}")
                ok = False

    return ok


# ============================================================================
# BACKEND IMPORT TEST
# ============================================================================

def test_backend_import() -> bool:
    header("BACKEND IMPORT TEST")

    # Make absolutely sure root is available.
    root_string = str(ROOT)

    if root_string not in sys.path:
        sys.path.insert(0, root_string)

    backend_string = str(BACKEND_DIR)

    if backend_string not in sys.path:
        sys.path.insert(0, backend_string)

    try:

        import backend.main as backend_main

        success("backend.main imported successfully.")

        app = getattr(backend_main, "app", None)

        if app is None:
            error("FastAPI variable 'app' was not found.")
            return False

        success("FastAPI app found.")
        success(f"App object: {app}")

        return True

    except Exception as exc:

        error(
            f"backend.main import failed: "
            f"{type(exc).__name__}: {exc}"
        )

        import traceback

        traceback.print_exc()

        return False


# ============================================================================
# NODE / NPM CHECK
# ============================================================================

def check_node() -> tuple[Optional[str], Optional[str]]:
    header("NODE.JS / NPM")

    node = find_node()
    npm = find_npm()

    if node:

        try:
            result = subprocess.run(
                [node, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                success(f"Node.js: {result.stdout.strip()}")
            else:
                warning("Node.js executable found but --version failed.")

        except Exception as exc:
            warning(f"Node.js version check failed: {exc}")

    else:
        error(
            "Node.js was not found in PATH."
        )

    if npm:

        try:
            result = subprocess.run(
                [npm, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                success(f"npm: {result.stdout.strip()}")
            else:
                warning("npm executable found but --version failed.")

        except Exception as exc:
            warning(f"npm version check failed: {exc}")

    else:
        error(
            "npm was not found in PATH."
        )

    return node, npm


# ============================================================================
# FRONTEND CHECK
# ============================================================================

def check_frontend() -> bool:
    header("FRONTEND")

    if not PACKAGE_JSON.exists():

        error(
            f"package.json was not found in {FRONTEND_DIR}"
        )

        info(
            "If your frontend is in another directory, "
            "change FRONTEND_DIR in launch.py."
        )

        return False

    success(f"package.json found: {PACKAGE_JSON}")

    if NODE_MODULES.exists():
        success("node_modules exists.")
    else:
        warning("node_modules does not exist.")

    return True


# ============================================================================
# FRONTEND DEPENDENCIES
# ============================================================================

def ensure_node_dependencies(npm: Optional[str]) -> bool:
    header("FRONTEND DEPENDENCIES")

    if not PACKAGE_JSON.exists():
        error(
            f"Cannot install frontend dependencies because "
            f"{PACKAGE_JSON} does not exist."
        )
        return False

    if not npm:
        error("npm executable is unavailable.")
        return False

    # Check whether node_modules exists.
    if NODE_MODULES.exists():

        success("node_modules already exists.")

        return True

    info("Installing frontend dependencies...")
    info(f"Working directory: {FRONTEND_DIR}")

    command = [
        npm,
        "install",
    ]

    try:

        result = subprocess.run(
            command,
            cwd=str(FRONTEND_DIR),
            env=os.environ.copy(),
            check=False,
        )

        if result.returncode != 0:

            error(
                f"npm install failed with exit code "
                f"{result.returncode}"
            )

            return False

        if not NODE_MODULES.exists():

            warning(
                "npm install completed but node_modules "
                "was not detected."
            )

            return False

        success("Frontend dependencies installed.")

        return True

    except FileNotFoundError:

        error(
            "Windows could not execute npm."
        )

        error(
            f"Resolved npm path was: {npm}"
        )

        return False

    except Exception as exc:

        error(f"npm install failed: {exc}")

        return False


# ============================================================================
# PROCESS OUTPUT
# ============================================================================

def stream_process(
    process: subprocess.Popen,
    prefix: str,
) -> None:

    if process.stdout is None:
        return

    try:

        for raw_line in process.stdout:

            if isinstance(raw_line, bytes):
                line = raw_line.decode(
                    "utf-8",
                    errors="replace",
                )
            else:
                line = str(raw_line)

            line = line.rstrip()

            if line:
                print(
                    f"[{prefix}] {line}",
                    flush=True,
                )

    except Exception as exc:

        if not shutdown_requested:
            warning(
                f"{prefix} output stream stopped: {exc}"
            )


# ============================================================================
# WINDOWS PROCESS FLAGS
# ============================================================================

def get_creationflags() -> int:

    if os.name != "nt":
        return 0

    # CREATE_NEW_PROCESS_GROUP
    return getattr(
        subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        0,
    )


# ============================================================================
# START BACKEND
# ============================================================================

def start_backend() -> Optional[subprocess.Popen]:
    header("STARTING BACKEND")

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
    ]

    info(
        "Backend command: "
        + " ".join(command)
    )

    env = os.environ.copy()

    env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(
        BACKEND_DIR
    )

    try:

        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=get_creationflags(),
        )

        processes.append(process)

        threading.Thread(
            target=stream_process,
            args=(process, "backend"),
            daemon=True,
        ).start()

        success(
            f"Backend process started. PID={process.pid}"
        )

        return process

    except Exception as exc:

        error(
            f"Could not start backend: {exc}"
        )

        return None


# ============================================================================
# START FRONTEND
# ============================================================================

def start_frontend(
    npm: Optional[str],
) -> Optional[subprocess.Popen]:

    header("STARTING FRONTEND")

    if not npm:

        error("npm executable not available.")

        return None

    command = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        FRONTEND_HOST,
        "--port",
        str(FRONTEND_PORT),
        "--strictPort",
    ]

    info(
        "Frontend command: "
        + " ".join(command)
    )

    env = os.environ.copy()

    try:

        process = subprocess.Popen(
            command,
            cwd=str(FRONTEND_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=get_creationflags(),
        )

        processes.append(process)

        threading.Thread(
            target=stream_process,
            args=(process, "frontend"),
            daemon=True,
        ).start()

        success(
            f"Frontend process started. PID={process.pid}"
        )

        return process

    except FileNotFoundError as exc:

        error(
            f"Windows could not execute npm: {exc}"
        )

        return None

    except Exception as exc:

        error(
            f"Could not start frontend: {exc}"
        )

        return None


# ============================================================================
# HTTP CHECK
# ============================================================================

def wait_for_http(
    url: str,
    timeout: int = 30,
) -> bool:

    deadline = time.time() + timeout

    while time.time() < deadline:

        try:

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "RomalaAlgoLauncher/1.0"
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=2,
            ) as response:

                if 200 <= response.status < 500:
                    return True

        except Exception:
            pass

        time.sleep(0.5)

    return False


# ============================================================================
# BACKEND HEALTH
# ============================================================================

def check_backend_health() -> bool:

    header("BACKEND HEALTH CHECK")

    url = (
        f"http://{BACKEND_HOST}:"
        f"{BACKEND_PORT}/api/health"
    )

    info(f"Checking {url}")

    if not wait_for_http(url, timeout=30):

        error(
            "Backend did not become healthy."
        )

        return False

    success(
        f"Backend health OK on port {BACKEND_PORT}"
    )

    # Optional market-status check.
    try:

        url = (
            f"http://{BACKEND_HOST}:"
            f"{BACKEND_PORT}/api/market-status"
        )

        with urllib.request.urlopen(
            url,
            timeout=5,
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        info(
            "Market status: "
            f"{data.get('status', '?')} "
            f"(IST {data.get('ist_time', '?')})"
        )

    except Exception as exc:

        warning(
            f"Market-status check failed: {exc}"
        )

    # Optional broker check.
    try:

        url = (
            f"http://{BACKEND_HOST}:"
            f"{BACKEND_PORT}/api/broker/status"
        )

        with urllib.request.urlopen(
            url,
            timeout=5,
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        info(
            "Broker status: "
            f"{data.get('status', '?')} - "
            f"{data.get('message', '')}"
        )

    except Exception as exc:

        warning(
            f"Broker-status check failed: {exc}"
        )

    return True


# ============================================================================
# FRONTEND HEALTH
# ============================================================================

def check_frontend_health() -> bool:

    header("FRONTEND HEALTH CHECK")

    url = (
        f"http://{FRONTEND_HOST}:"
        f"{FRONTEND_PORT}"
    )

    info(f"Checking {url}")

    if not wait_for_http(url, timeout=40):

        error(
            "Frontend did not become ready."
        )

        return False

    success(
        f"Frontend ready on port {FRONTEND_PORT}"
    )

    return True


# ============================================================================
# PROCESS STATUS
# ============================================================================

def show_process_status() -> None:

    header("PROCESS STATUS")

    if not processes:

        warning("No child processes are running.")

        return

    for process in processes:

        code = process.poll()

        if code is None:
            success(
                f"PID {process.pid} is running."
            )
        else:
            warning(
                f"PID {process.pid} exited with code {code}."
            )


# ============================================================================
# SHUTDOWN
# ============================================================================

def terminate_process(
    process: subprocess.Popen,
    name: str,
) -> None:

    if process.poll() is not None:
        return

    info(
        f"Stopping {name} process "
        f"(PID {process.pid})..."
    )

    try:

        process.terminate()

    except Exception as exc:

        warning(
            f"Could not terminate {name}: {exc}"
        )

    try:

        process.wait(timeout=5)

        success(
            f"{name} stopped."
        )

        return

    except subprocess.TimeoutExpired:

        warning(
            f"{name} did not stop gracefully."
        )

    try:

        process.kill()

        process.wait(timeout=3)

        success(
            f"{name} killed."
        )

    except Exception as exc:

        warning(
            f"Could not kill {name}: {exc}"
        )


def shutdown(
    *_: object,
) -> None:

    global shutdown_requested

    if shutdown_requested:
        return

    shutdown_requested = True

    print()

    header("SHUTDOWN")

    # Copy list because process output threads may still be active.
    current_processes = list(processes)

    # Usually the last process is frontend.
    for process in reversed(current_processes):

        name = "process"

        if process.pid:
            name = f"process PID {process.pid}"

        terminate_process(
            process,
            name,
        )

    processes.clear()

    print()
    success("Romala Algo launcher stopped.")

    raise SystemExit(0)


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    header("ROMALA ALGO FULL STACK LAUNCHER")

    info(f"Project root: {ROOT}")
    info(f"Backend: {BACKEND_DIR}")
    info(f"Frontend: {FRONTEND_DIR}")

    # ------------------------------------------------------------------------
    # Parse arguments
    # ------------------------------------------------------------------------

    arguments = set(sys.argv[1:])

    valid_arguments = {
        "--backend",
        "--frontend",
        "--debug",
    }

    unknown = arguments - valid_arguments

    if unknown:

        error(
            "Unknown arguments: "
            + ", ".join(sorted(unknown))
        )

        print()
        print("Usage:")
        print("  python launch.py")
        print("  python launch.py --backend")
        print("  python launch.py --frontend")
        print("  python launch.py --debug")

        return

    # Default = both.
    run_backend = True
    run_frontend = True

    if "--backend" in arguments and "--frontend" not in arguments:

        run_backend = True
        run_frontend = False

    elif "--frontend" in arguments and "--backend" not in arguments:

        run_backend = False
        run_frontend = True

    # ------------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------------

    setup_environment()

    load_backend_env()

    # ------------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------------

    try:
        signal.signal(
            signal.SIGINT,
            shutdown,
        )

        signal.signal(
            signal.SIGTERM,
            shutdown,
        )

    except Exception as exc:

        warning(
            f"Signal handler setup failed: {exc}"
        )

    # ------------------------------------------------------------------------
    # Python
    # ------------------------------------------------------------------------

    if run_backend:

        if not check_python():

            error(
                "Python/backend validation failed."
            )

            return

        if not check_project_structure():

            error(
                "Backend project structure validation failed."
            )

            return

        if not ensure_python_dependencies():

            error(
                "Python dependency validation failed."
            )

            return

        if not check_kotak_neo():

            error(
                "Kotak Neo SDK validation failed."
            )

            return

        if not test_backend_import():

            error(
                "Backend import test failed."
            )

            error(
                "Fix backend import errors before starting."
            )

            return

    # ------------------------------------------------------------------------
    # Node
    # ------------------------------------------------------------------------

    npm: Optional[str] = None

    if run_frontend:

        frontend_ok = check_frontend()

        if not frontend_ok:

            error(
                "Frontend validation failed."
            )

            return

        _, npm = check_node()

        if not npm:

            error(
                "npm is required to launch the frontend."
            )

            return

        if not ensure_node_dependencies(npm):

            error(
                "Frontend dependency installation failed."
            )

            return

    # ------------------------------------------------------------------------
    # Start backend
    # ------------------------------------------------------------------------

    backend_process: Optional[subprocess.Popen] = None

    if run_backend:

        backend_process = start_backend()

        if backend_process is None:

            error(
                "Backend could not be started."
            )

            shutdown()

            return

    # ------------------------------------------------------------------------
    # Start frontend
    # ------------------------------------------------------------------------

    frontend_process: Optional[subprocess.Popen] = None

    if run_frontend:

        frontend_process = start_frontend(npm)

        if frontend_process is None:

            error(
                "Frontend could not be started."
            )

            shutdown()

            return

    # ------------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------------

    backend_healthy = True
    frontend_healthy = True

    if run_backend:

        backend_healthy = check_backend_health()

    if run_frontend:

        frontend_healthy = check_frontend_health()

    # ------------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------------

    header("FINAL STATUS")

    if run_backend:

        if backend_healthy:
            success(
                f"Backend: http://localhost:{BACKEND_PORT}"
            )
        else:
            error("Backend: NOT HEALTHY")

    if run_frontend:

        if frontend_healthy:
            success(
                f"Frontend: http://localhost:{FRONTEND_PORT}"
            )
        else:
            error("Frontend: NOT READY")

    show_process_status()

    if (
        (not run_backend or backend_healthy)
        and
        (not run_frontend or frontend_healthy)
    ):

        print()

        success(
            "Romala Algo full stack is running."
        )

        if run_backend:
            print(
                f"  Backend : http://localhost:{BACKEND_PORT}",
                flush=True,
            )

            print(
                f"  Swagger : http://localhost:{BACKEND_PORT}/docs",
                flush=True,
            )

        if run_frontend:
            print(
                f"  Frontend: http://localhost:{FRONTEND_PORT}",
                flush=True,
            )

        print()
        info("Press Ctrl+C to stop all services.")

    else:

        warning(
            "One or more services failed their health check."
        )

        info(
            "The launcher will continue so you can inspect the logs."
        )

    # ------------------------------------------------------------------------
    # Keep launcher alive
    # ------------------------------------------------------------------------

    try:

        while True:

            time.sleep(1)

            for process in list(processes):

                exit_code = process.poll()

                if exit_code is None:
                    continue

                # Don't immediately kill everything during intentional shutdown.
                if shutdown_requested:
                    return

                error(
                    f"Child process PID {process.pid} "
                    f"exited with code {exit_code}."
                )

                # If either service dies, stop the remaining service.
                shutdown()

    except KeyboardInterrupt:

        shutdown()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()