import os
import sys
import subprocess
import importlib.util
import traceback
import socket
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"


# ============================================================
# DISPLAY HELPERS
# ============================================================

def header(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def section(title):
    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


# ============================================================
# 1. PYTHON ENVIRONMENT
# ============================================================

def check_python():
    header("1. PYTHON ENVIRONMENT")

    print("Executable:")
    print(sys.executable)

    print()
    print("Version:")
    print(sys.version)

    print()
    print("Python prefix:")
    print(sys.prefix)

    print()
    print("Base prefix:")
    print(sys.base_prefix)

    print()
    print("Virtual environment:")

    virtual_env = os.environ.get("VIRTUAL_ENV")

    if virtual_env:
        print(f"[OK] {virtual_env}")
    else:
        if sys.prefix != sys.base_prefix:
            print(f"[OK] Virtual environment detected: {sys.prefix}")
        else:
            print("[WARNING] Virtual environment does not appear active")


# ============================================================
# 2. PROJECT STRUCTURE
# ============================================================

def check_structure():
    header("2. PROJECT STRUCTURE")

    if not ROOT.exists():
        print("[ERROR] Project root does not exist")
        return False

    print(f"Project root: {ROOT}")

    if not BACKEND.exists():
        print("[ERROR] backend directory missing")
        return False

    print(f"Backend: {BACKEND}")

    print()

    for path in sorted(BACKEND.rglob("*")):

        if "__pycache__" in path.parts:
            continue

        relative = path.relative_to(ROOT)

        if path.is_dir():
            print(f"DIR  {relative}")
        else:
            print(f"FILE {relative}")

    return True


# ============================================================
# 3. PYTHON PACKAGES
# ============================================================

def check_packages():
    header("3. REQUIRED PYTHON PACKAGES")

    packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "neo_api_client",
    ]

    all_ok = True

    for package in packages:

        try:

            spec = importlib.util.find_spec(package)

            if spec:
                print(f"[OK]      {package}")
            else:
                print(f"[MISSING] {package}")
                all_ok = False

        except Exception as exc:

            print(f"[ERROR] {package}: {exc}")
            all_ok = False

    return all_ok


# ============================================================
# 4. KOTAK NEO SDK
# ============================================================

def check_kotak_sdk():
    header("4. KOTAK NEO SDK")

    try:

        from neo_api_client import NeoAPI

        print("[OK] neo_api_client import works")
        print(f"[OK] NeoAPI class: {NeoAPI}")

        return True

    except Exception as exc:

        print("[FAILED] neo_api_client import")

        print(f"Error type: {type(exc).__name__}")
        print(f"Error: {exc}")

        traceback.print_exc()

        return False


# ============================================================
# 5. KOTAK DIRECTORY CHECK
# ============================================================

def fix_kotak_directory():
    header("5. KOTAK NEO DIRECTORY CHECK")

    expected = BACKEND / "kotak_neo"
    alternative = BACKEND / "kotek_neo"

    print("Expected:")
    print(expected)

    print()
    print("Alternative:")
    print(alternative)

    # Correct directory already exists
    if expected.exists():

        print()
        print("[OK] backend/kotak_neo exists")

        return True

    # Misspelled directory exists
    if alternative.exists():

        print()
        print("[ROOT CAUSE FOUND]")

        print("main.py expects:")
        print("    kotak_neo")

        print("Actual directory:")
        print("    kotek_neo")

        print()
        print("Applying safe fix...")

        try:

            alternative.rename(expected)

            print()
            print("[FIXED]")
            print("Renamed:")
            print("    backend/kotek_neo")
            print("to:")
            print("    backend/kotak_neo")

            return True

        except Exception as exc:

            print()
            print("[ERROR] Could not rename directory")
            print(exc)

            return False

    print()
    print("[ERROR] Neither kotak_neo nor kotek_neo exists")

    return False


# ============================================================
# 6. FIND PYTHON MODULE MISMATCHES
# ============================================================

def detect_python_module_mismatches():

    header("6. PYTHON MODULE FILE CHECK")

    problems = []

    source_files = list(BACKEND.rglob("*.py"))

    for source in source_files:

        if "__pycache__" in source.parts:
            continue

        try:

            content = source.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        except Exception:
            continue

        for line in content.splitlines():

            line = line.strip()

            # Example:
            #
            # from strategies.engine import ...
            #
            if line.startswith("from ") and " import " in line:

                module = line.split(
                    "from ",
                    1
                )[1].split(
                    " import ",
                    1
                )[0].strip()

                parts = module.split(".")

                if len(parts) < 2:
                    continue

                package_dir = BACKEND.joinpath(*parts[:-1])

                module_name = parts[-1]

                expected_py = (
                    package_dir /
                    f"{module_name}.py"
                )

                possible_txt = (
                    package_dir /
                    f"{module_name}.txt"
                )

                if (
                    not expected_py.exists()
                    and possible_txt.exists()
                ):

                    print()
                    print("[MODULE MISMATCH]")

                    print(
                        f"Source  : {source.relative_to(ROOT)}"
                    )

                    print(
                        f"Import  : {module}"
                    )

                    print(
                        f"Expected: {expected_py.relative_to(ROOT)}"
                    )

                    print(
                        f"Found   : {possible_txt.relative_to(ROOT)}"
                    )

                    problems.append(
                        (
                            possible_txt,
                            expected_py
                        )
                    )

    # Remove duplicates
    unique = []

    for problem in problems:

        if problem not in unique:
            unique.append(problem)

    if not unique:

        print("[OK] No obvious module filename mismatches")

    return unique


# ============================================================
# 7. SAFELY FIX PYTHON MODULE MISMATCHES
# ============================================================

def inspect_and_fix_modules():

    header("7. FIX PYTHON MODULE MISMATCHES")

    problems = detect_python_module_mismatches()

    if not problems:

        print("[OK] Nothing to fix")

        return True

    all_fixed = True

    for source_file, expected_file in problems:

        print()
        print("Candidate:")
        print(
            f"  {source_file.relative_to(ROOT)}"
        )

        print()
        print("Potential destination:")
        print(
            f"  {expected_file.relative_to(ROOT)}"
        )

        try:

            content = source_file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        except Exception as exc:

            print(
                f"[ERROR] Cannot read file: {exc}"
            )

            all_fixed = False
            continue

        # Indicators that the TXT file actually contains
        # Python source code.

        python_indicators = [
            "def ",
            "class ",
            "import ",
            "from ",
            "return ",
            "async ",
            "await ",
            "if __name__",
        ]

        score = sum(
            1
            for indicator in python_indicators
            if indicator in content
        )

        print()
        print(
            f"Python-content score: {score}"
        )

        if score >= 2:

            print(
                "[CONFIRMED] File appears to contain Python code."
            )

            if expected_file.exists():

                print(
                    "[WARNING] Destination already exists."
                )

                print(
                    "[SKIPPED] No overwrite performed."
                )

                continue

            try:

                source_file.rename(expected_file)

                print()
                print("[FIXED]")

                print(
                    f"{source_file.name} -> "
                    f"{expected_file.name}"
                )

            except Exception as exc:

                print()
                print("[ERROR] Rename failed")
                print(exc)

                all_fixed = False

        else:

            print()
            print(
                "[WARNING] File does not strongly look like Python."
            )

            print(
                "[SKIPPED] Automatic rename not performed."
            )

            all_fixed = False

    return all_fixed


# ============================================================
# 8. MAIN.PY IMPORT INSPECTION
# ============================================================

def inspect_main_imports():

    header("8. MAIN.PY IMPORTS")

    main_file = BACKEND / "main.py"

    if not main_file.exists():

        print("[ERROR] backend/main.py missing")

        return False

    try:

        content = main_file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception as exc:

        print("[ERROR] Cannot read main.py")
        print(exc)

        return False

    for line in content.splitlines():

        stripped = line.strip()

        if (
            stripped.startswith("from ")
            or
            stripped.startswith("import ")
        ):

            print(stripped)

    return True


# ============================================================
# 9. BACKEND IMPORT TEST
# ============================================================

def test_backend_import():

    header("9. BACKEND IMPORT TEST")

    # Make sure project root is importable.
    root_string = str(ROOT)

    if root_string not in sys.path:

        sys.path.insert(
            0,
            root_string
        )

    try:

        # Remove cached module if this script is rerun
        # in the same Python process.

        if "backend.main" in sys.modules:

            del sys.modules["backend.main"]

        import backend.main

        print(
            "[SUCCESS] backend.main imported"
        )

        app = getattr(
            backend.main,
            "app",
            None
        )

        if app is not None:

            print(
                "[SUCCESS] FastAPI app found"
            )

            print(app)

            return True

        print(
            "[ERROR] FastAPI app variable 'app' not found"
        )

        return False

    except Exception as exc:

        print()
        print(
            "[FAILED] backend.main import"
        )

        print(
            f"Error type: {type(exc).__name__}"
        )

        print(
            f"Error: {exc}"
        )

        print()
        print("FULL TRACEBACK")
        print("-" * 70)

        traceback.print_exc()

        return False


# ============================================================
# 10. NODE.JS / NPM
# ============================================================

def run_command(command):

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False
        )

        return result

    except FileNotFoundError:

        return None

    except Exception as exc:

        print(
            f"[ERROR] Could not execute {command}: {exc}"
        )

        return None


def check_node():

    header("10. NODE.JS / NPM")

    node = run_command(
        ["node.exe", "--version"]
    )

    if node is not None and node.returncode == 0:

        print(
            f"[OK] Node.js: {node.stdout.strip()}"
        )

    else:

        print(
            "[MISSING] Node.js"
        )

        print(
            "Python could not execute node.exe"
        )

    # Windows npm normally resolves to npm.cmd.
    npm = run_command(
        ["npm.cmd", "--version"]
    )

    if npm is not None and npm.returncode == 0:

        print(
            f"[OK] npm: {npm.stdout.strip()}"
        )

    else:

        print(
            "[MISSING] npm.cmd"
        )

        print()
        print(
            "Checking common Node.js locations..."
        )

        candidates = [

            Path(
                r"C:\Program Files\nodejs\npm.cmd"
            ),

            Path(
                r"C:\Program Files\nodejs\node.exe"
            ),

            Path(
                os.environ.get(
                    "APPDATA",
                    ""
                )
            ) / "npm" / "npm.cmd",

        ]

        for candidate in candidates:

            if candidate.exists():

                print(
                    f"[FOUND] {candidate}"
                )

            else:

                print(
                    f"[NOT FOUND] {candidate}"
                )


# ============================================================
# 11. FRONTEND CHECK
# ============================================================

def check_frontend():

    header("11. FRONTEND CHECK")

    package_files = list(
        ROOT.rglob("package.json")
    )

    # Ignore node_modules
    package_files = [
        p
        for p in package_files
        if "node_modules" not in p.parts
    ]

    if not package_files:

        print(
            "[WARNING] No package.json found"
        )

        return False

    print(
        f"Found {len(package_files)} package.json file(s):"
    )

    frontend_ok = True

    for package_json in package_files:

        print()
        print(
            f"[FOUND] {package_json.relative_to(ROOT)}"
        )

        node_modules = (
            package_json.parent /
            "node_modules"
        )

        if node_modules.exists():

            print(
                "[OK] node_modules exists"
            )

        else:

            print(
                "[WARNING] node_modules missing"
            )

            frontend_ok = False

    return frontend_ok


# ============================================================
# 12. PORT 8000 CHECK
# ============================================================

def check_port_8000():

    header("12. PORT 8000 CHECK")

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    sock.settimeout(1)

    try:

        result = sock.connect_ex(
            ("127.0.0.1", 8000)
        )

        if result == 0:

            print(
                "[WARNING] Port 8000 is already in use"
            )

            print(
                "A server may already be running."
            )

            return False

        print(
            "[OK] Port 8000 is available"
        )

        return True

    except Exception as exc:

        print(
            "[ERROR] Could not check port 8000"
        )

        print(exc)

        return False

    finally:

        sock.close()


# ============================================================
# 13. REQUIREMENTS.TXT
# ============================================================

def check_requirements():

    header("13. REQUIREMENTS.TXT")

    requirements = BACKEND / "requirements.txt"

    if not requirements.exists():

        print(
            "[ERROR] backend/requirements.txt missing"
        )

        return False

    print(
        f"[OK] Found {requirements}"
    )

    print()
    print("Contents:")

    try:

        print(
            requirements.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        print(
            f"[ERROR] Could not read requirements.txt: {exc}"
        )

        return False

    return True


# ============================================================
# 14. QUICK UVICORN CONFIG CHECK
# ============================================================

def check_uvicorn_config():

    header("14. UVICORN CONFIGURATION")

    print(
        "Recommended command:"
    )

    print()

    print(
        "python -m uvicorn "
        "backend.main:app "
        "--reload "
        "--port 8000"
    )

    print()

    print(
        "[INFO] This debugger does not start Uvicorn."
    )

    print(
        "[INFO] It only validates that backend.main imports."
    )


# ============================================================
# FINAL DIAGNOSIS
# ============================================================

def final_diagnosis(
    backend_ok,
    node_ok=None,
    frontend_ok=None,
    port_ok=None
):

    header("FINAL DIAGNOSIS")

    if backend_ok:

        print(
            "[SUCCESS] Backend import/startup structure is OK."
        )

        print()
        print(
            "FastAPI application was successfully loaded."
        )

        print()
        print(
            "Start the backend with:"
        )

        print()

        print(
            "python -m uvicorn "
            "backend.main:app "
            "--reload "
            "--port 8000"
        )

    else:

        print(
            "[FAILED] Backend still has an import/startup problem."
        )

        print()
        print(
            "Review the traceback in section 9."
        )

    print()

    if node_ok:

        print(
            "[OK] Node.js/npm available."
        )

    else:

        print(
            "[WARNING] Node.js/npm requires attention."
        )

    print()

    if frontend_ok:

        print(
            "[OK] Frontend dependencies appear available."
        )

    else:

        print(
            "[WARNING] Frontend dependencies are missing "
            "or package.json could not be validated."
        )

    print()

    if port_ok:

        print(
            "[OK] Port 8000 is available."
        )

    else:

        print(
            "[WARNING] Port 8000 is already occupied."
        )

    print()

    print("=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    header(
        "ROMALA ALGO - PYTHON DEBUG & FIX TOOL"
    )

    print(
        "Running from:"
    )

    print(ROOT)

    # --------------------------------------------------------
    # Python
    # --------------------------------------------------------

    check_python()

    # --------------------------------------------------------
    # Project
    # --------------------------------------------------------

    structure_ok = check_structure()

    if not structure_ok:

        print()
        print(
            "[FATAL] Project structure invalid."
        )

        return

    # --------------------------------------------------------
    # Requirements
    # --------------------------------------------------------

    check_requirements()

    # --------------------------------------------------------
    # Packages
    # --------------------------------------------------------

    check_packages()

    # --------------------------------------------------------
    # Kotak SDK
    # --------------------------------------------------------

    check_kotak_sdk()

    # --------------------------------------------------------
    # Kotak directory
    # --------------------------------------------------------

    fix_kotak_directory()

    # --------------------------------------------------------
    # Main imports
    # --------------------------------------------------------

    inspect_main_imports()

    # --------------------------------------------------------
    # Python module mismatches
    # --------------------------------------------------------

    inspect_and_fix_modules()

    # --------------------------------------------------------
    # Backend import
    # --------------------------------------------------------

    backend_ok = test_backend_import()

    # --------------------------------------------------------
    # Node/npm
    # --------------------------------------------------------

    node_result = run_command(
        ["node.exe", "--version"]
    )

    npm_result = run_command(
        ["npm.cmd", "--version"]
    )

    node_ok = (
        node_result is not None
        and node_result.returncode == 0
    )

    npm_ok = (
        npm_result is not None
        and npm_result.returncode == 0
    )

    check_node()

    node_ok = node_ok and npm_ok

    # --------------------------------------------------------
    # Frontend
    # --------------------------------------------------------

    frontend_ok = check_frontend()

    # --------------------------------------------------------
    # Port
    # --------------------------------------------------------

    port_ok = check_port_8000()

    # --------------------------------------------------------
    # Uvicorn
    # --------------------------------------------------------

    check_uvicorn_config()

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    final_diagnosis(
        backend_ok=backend_ok,
        node_ok=node_ok,
        frontend_ok=frontend_ok,
        port_ok=port_ok
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()