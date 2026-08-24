#!/usr/bin/env python3
"""Romala Algo — single launcher for backend (FastAPI) + frontend (Vite).

Usage:
    python launch.py            # start both
    python launch.py --backend  # backend only
    python launch.py --frontend # frontend only

Backend runs on http://localhost:8000  (FastAPI / uvicorn)
Frontend runs on http://localhost:5173 (Vite dev server)
"""
from __future__ import annotations

import os
import sys
import signal
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

NEO_CONSUMER_KEY = os.getenv("NEO_CONSUMER_KEY", "59776906-45e5-4253-a05c-e8e6aad1eb9f")


def load_backend_env() -> None:
    """Load backend/.env into os.environ so the Kotak Neo client picks it up."""
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    os.environ.setdefault("NEO_CONSUMER_KEY", NEO_CONSUMER_KEY)


def stream(proc: subprocess.Popen, prefix: str) -> None:
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode(errors="replace").rstrip()
        if line:
            print(f"[{prefix}] {line}", flush=True)


def ensure_python_deps() -> None:
    """Best-effort install of backend Python deps if missing."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except Exception:
        print("[launcher] Installing backend Python dependencies…", flush=True)
        req = BACKEND_DIR / "requirements.txt"
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])

    # Kotak Neo SDK is not on PyPI — install from GitHub
    try:
        import neo_api_client  # noqa: F401
    except Exception:
        print("[launcher] Installing neo_api_client from GitHub…", flush=True)
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git",
        ])


def ensure_node_deps() -> bool:
    """Ensure node_modules exist for the frontend. Returns True if ready."""
    if (FRONTEND_DIR / "node_modules").exists():
        return True
    npm = os.getenv("npm_executable", "npm")
    print("[launcher] Installing frontend Node dependencies…", flush=True)
    try:
        subprocess.check_call([npm, "install"], cwd=str(FRONTEND_DIR))
        return True
    except Exception as e:
        print(f"[launcher] npm install failed: {e}", flush=True)
        return False


def start_backend() -> subprocess.Popen:
    env = os.environ.copy()
    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT),
        "--reload",
    ]
    print(f"[launcher] Starting backend on :{BACKEND_PORT}", flush=True)
    proc = subprocess.Popen(
        cmd, cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    threading.Thread(target=stream, args=(proc, "backend"), daemon=True).start()
    return proc


def start_frontend() -> subprocess.Popen:
    npm = os.getenv("npm_executable", "npm")
    # Prefer npx vite so we don't depend on a global install
    cmd = [npm, "run", "dev", "--", "--port", str(FRONTEND_PORT), "--strictPort"]
    print(f"[launcher] Starting frontend on :{FRONTEND_PORT}", flush=True)
    proc = subprocess.Popen(
        cmd, cwd=str(FRONTEND_DIR), env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    threading.Thread(target=stream, args=(proc, "frontend"), daemon=True).start()
    return proc


def wait_for_http(url: str, timeout: int = 30) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    load_backend_env()
    args = set(sys.argv[1:])
    run_backend = "--frontend" not in args or "--backend" in args or not args
    run_frontend = "--backend" not in args or "--frontend" in args or not args
    # If explicit flags given, honor exactly them
    if "--backend" in args and "--frontend" not in args:
        run_backend, run_frontend = True, False
    elif "--frontend" in args and "--backend" not in args:
        run_backend, run_frontend = False, True
    elif not args:
        run_backend, run_frontend = True, True

    procs: list[subprocess.Popen] = []

    def shutdown(*_: object) -> None:
        print("\n[launcher] Shutting down…", flush=True)
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if run_backend:
        ensure_python_deps()
        procs.append(start_backend())

    if run_frontend:
        if ensure_node_deps():
            procs.append(start_frontend())
        else:
            print("[launcher] Skipping frontend — node deps unavailable", flush=True)

    # Health check
    if run_backend:
        if wait_for_http(f"http://localhost:{BACKEND_PORT}/api/health"):
            print(f"[launcher] Backend health OK on :{BACKEND_PORT}", flush=True)
        else:
            print(f"[launcher] Backend did not become healthy on :{BACKEND_PORT}", flush=True)

    print("[launcher] Both services launched. Ctrl+C to stop.", flush=True)

    while True:
        for p in procs:
            if p.poll() is not None:
                print(f"[launcher] Process exited (pid {p.pid}, code {p.returncode})", flush=True)
                shutdown()
        time.sleep(1)


if __name__ == "__main__":
    main()
