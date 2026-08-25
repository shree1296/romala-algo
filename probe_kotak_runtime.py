from __future__ import annotations

import ast
import asyncio
import getpass
import inspect
import os
import re
import shutil
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("[FAIL] python-dotenv is not installed.")
    print("Run: pip install python-dotenv")
    raise SystemExit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
ENV_FILE = BACKEND_ROOT / ".env"

BACKUP_ROOT = PROJECT_ROOT / "_kotak_v3_backups"

MODIFY_FILES = True

print("=" * 88)
print("ROMALA ALGO — KOTAK NEO SDK V3 AUTHENTICATION + RUNTIME REPAIR")
print("=" * 88)

print(f"[INFO] Python       : {sys.executable}")
print(f"[INFO] Project      : {PROJECT_ROOT}")
print(f"[INFO] Backend      : {BACKEND_ROOT}")
print(f"[INFO] Environment  : {ENV_FILE}")
print()


# =============================================================================
# HELPERS
# =============================================================================

def mask(value: str, left: int = 3, right: int = 3) -> str:
    value = str(value or "")

    if not value:
        return "<EMPTY>"

    if len(value) <= left + right:
        return "*" * len(value)

    return value[:left] + ("*" * max(4, len(value) - left - right)) + value[-right:]


def get_env(*names: str, required: bool = True) -> str | None:
    for name in names:
        value = os.getenv(name)

        if value and value.strip():
            return value.strip()

    if required:
        raise RuntimeError(
            "Missing required environment variable. Expected one of: "
            + ", ".join(names)
        )

    return None


def is_current_totp(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", value or ""))


def safe_backup(path: Path) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    relative = path.relative_to(PROJECT_ROOT)

    destination = (
        BACKUP_ROOT
        / timestamp
        / relative
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(
        path,
        destination
    )

    return destination


# =============================================================================
# ENVIRONMENT
# =============================================================================

print("=" * 88)
print("STEP 1 — LOAD ENVIRONMENT")
print("=" * 88)

if not BACKEND_ROOT.exists():
    print(f"[FAIL] Backend directory not found: {BACKEND_ROOT}")
    raise SystemExit(1)

print("[PASS] Backend directory found.")

if not ENV_FILE.exists():
    print(f"[FAIL] .env file not found: {ENV_FILE}")
    raise SystemExit(1)

print(f"[PASS] Loading environment: {ENV_FILE}")

load_dotenv(
    ENV_FILE,
    override=True
)

try:
    CONSUMER_KEY = get_env(
        "KOTAK_CONSUMER_KEY",
        "KOTAK_API_KEY",
        "NEO_CONSUMER_KEY"
    )

    MOBILE_NUMBER = get_env(
        "KOTAK_MOBILE_NUMBER",
        "KOTAK_MOBILE",
        "NEO_MOBILE_NUMBER"
    )

    UCC = get_env(
        "KOTAK_UCC",
        "KOTAK_CLIENT_CODE",
        "NEO_UCC"
    )

    MPIN = get_env(
        "KOTAK_MPIN",
        "NEO_MPIN"
    )

except Exception as exc:
    print(f"[FAIL] Environment configuration error: {exc}")
    raise SystemExit(1)

print()
print("[PASS] Consumer Key :", mask(CONSUMER_KEY))
print("[PASS] Mobile       :", mask(MOBILE_NUMBER, 2, 2))
print("[PASS] UCC          :", mask(UCC, 2, 2))
print("[PASS] MPIN         :", mask(MPIN, 2, 2))


# =============================================================================
# TOTP INPUT
# =============================================================================

print()
print("=" * 88)
print("STEP 2 — ENTER CURRENT TOTP")
print("=" * 88)

print()
print("[IMPORTANT]")
print("Enter the CURRENT 6-digit code shown by your authenticator.")
print("Do NOT enter:")
print("  - a redacted value")
print("  - RE********TP")
print("  - a placeholder")
print("  - a stale code")
print()
print("The code is requested at runtime and is NOT written to .env.")
print()

CURRENT_TOTP = getpass.getpass(
    "Current Kotak Authenticator TOTP: "
).strip()

if not is_current_totp(CURRENT_TOTP):
    print()
    print("[FAIL] Invalid TOTP format.")
    print("[INFO] Expected exactly 6 digits.")
    raise SystemExit(1)

print("[PASS] Valid 6-digit TOTP format received.")


# =============================================================================
# SDK IMPORT
# =============================================================================

print()
print("=" * 88)
print("STEP 3 — IMPORT KOTAK NEO SDK")
print("=" * 88)

try:
    import neo_api_client
    from neo_api_client import NeoAPI

except Exception as exc:
    print("[FAIL] Could not import neo_api_client.")
    print(f"[ERROR] {exc}")
    raise SystemExit(1)

sdk_version = getattr(
    neo_api_client,
    "__version__",
    "UNKNOWN"
)

print("[PASS] neo_api_client imported.")
print(f"[INFO] SDK version: {sdk_version}")

print()
print("[INFO] NeoAPI constructor:")
print(inspect.signature(NeoAPI))


# =============================================================================
# REPOSITORY LEGACY API SCAN
# =============================================================================

print()
print("=" * 88)
print("STEP 4 — SCAN BACKEND FOR LEGACY KOTAK SDK CALLS")
print("=" * 88)

LEGACY_PATTERNS = {
    "session_init": re.compile(
        r"\.\s*session_init\s*\("
    ),

    "legacy_callback_subscribe": re.compile(
        r"\.\s*subscribe\s*\("
    ),

    "legacy_callback_unsubscribe": re.compile(
        r"\.\s*un_subscribe\s*\("
    ),
}

matches = []

for path in BACKEND_ROOT.rglob("*.py"):

    try:
        source = path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        source = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    lines = source.splitlines()

    for index, line in enumerate(
        lines,
        start=1
    ):
        for name, pattern in LEGACY_PATTERNS.items():

            if pattern.search(line):

                matches.append(
                    {
                        "type": name,
                        "file": path,
                        "line": index,
                        "source": line.strip()
                    }
                )

if not matches:

    print("[PASS] No known legacy Kotak SDK patterns found.")

else:

    print(
        f"[WARNING] Found {len(matches)} "
        f"legacy SDK reference(s)."
    )

    for item in matches:

        relative = item["file"].relative_to(
            PROJECT_ROOT
        )

        print()
        print(
            f"[FOUND] {item['type']}"
        )

        print(
            f"  File : {relative}"
        )

        print(
            f"  Line : {item['line']}"
        )

        print(
            f"  Code : {item['source']}"
        )


# =============================================================================
# SAFE session_init REPAIR
# =============================================================================

print()
print("=" * 88)
print("STEP 5 — SAFE session_init() REPAIR")
print("=" * 88)

print()
print(
    "[INFO] Only standalone calls such as "
    "'neo.session_init()' will be removed automatically."
)

print(
    "[INFO] Complex expressions or assigned return values "
    "will NOT be modified."
)

repaired_files = []
manual_review = []

for path in BACKEND_ROOT.rglob("*.py"):

    try:
        source = path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        source = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    original_source = source
    lines = source.splitlines(
        keepends=True
    )

    changed = False
    output = []

    for line_number, line in enumerate(
        lines,
        start=1
    ):

        stripped = line.strip()

        standalone_match = re.fullmatch(
            r"(?P<indent>\s*)"
            r"(?P<object>[A-Za-z_][A-Za-z0-9_]*)"
            r"\.session_init\(\)\s*"
            r"(?:#.*)?"
            r"(?:\r?\n)?",
            line
        )

        if standalone_match:

            indent = standalone_match.group(
                "indent"
            )

            object_name = standalone_match.group(
                "object"
            )

            output.append(
                indent
                + "# Removed legacy Kotak SDK v2 "
                + f"session_init() call for {object_name}.\n"
            )

            output.append(
                indent
                + "# SDK v3 authentication begins with "
                + "totp_login() followed by totp_validate().\n"
            )

            changed = True

            print(
                "[SAFE REPAIR] "
                f"{path.relative_to(PROJECT_ROOT)}"
                f":{line_number}"
            )

            continue

        if ".session_init(" in line:

            manual_review.append(
                (
                    path,
                    line_number,
                    line.strip()
                )
            )

        output.append(line)

    if changed:

        if MODIFY_FILES:

            backup = safe_backup(path)

            path.write_text(
                "".join(output),
                encoding="utf-8"
            )

            print(
                f"[PASS] Backup created: "
                f"{backup.relative_to(PROJECT_ROOT)}"
            )

            print(
                f"[PASS] Repaired: "
                f"{path.relative_to(PROJECT_ROOT)}"
            )

            repaired_files.append(path)

        else:

            print(
                "[INFO] Dry run only — no file modified."
            )

if not repaired_files:

    print(
        "[INFO] No standalone session_init() calls required repair."
    )

if manual_review:

    print()
    print(
        "[WARNING] Complex session_init references require review."
    )

    for path, line_number, code in manual_review:

        print()
        print(
            f"  {path.relative_to(PROJECT_ROOT)}"
            f":{line_number}"
        )

        print(
            f"    {code}"
        )

else:

    print(
        "[PASS] No complex session_init usage found."
    )


# =============================================================================
# PYTHON SYNTAX VALIDATION
# =============================================================================

print()
print("=" * 88)
print("STEP 6 — VALIDATE MODIFIED PYTHON FILES")
print("=" * 88)

syntax_failures = []

for path in repaired_files:

    try:

        source = path.read_text(
            encoding="utf-8"
        )

        ast.parse(
            source,
            filename=str(path)
        )

        print(
            f"[PASS] Syntax valid: "
            f"{path.relative_to(PROJECT_ROOT)}"
        )

    except Exception as exc:

        syntax_failures.append(
            (
                path,
                exc
            )
        )

        print(
            f"[FAIL] Syntax error: "
            f"{path.relative_to(PROJECT_ROOT)}"
        )

        print(
            f"[ERROR] {exc}"
        )

if syntax_failures:

    print()
    print(
        "[CRITICAL] Syntax failures detected after repair."
    )

    raise SystemExit(1)


# =============================================================================
# CREATE SDK CLIENT
# =============================================================================

print()
print("=" * 88)
print("STEP 7 — CREATE KOTAK NEO V3 CLIENT")
print("=" * 88)

try:

    neo = NeoAPI(
        consumer_key=CONSUMER_KEY,
        environment="prod"
    )

    print("[PASS] NeoAPI client created.")

except Exception as exc:

    print("[FAIL] NeoAPI creation failed.")
    print(f"[ERROR] {exc}")

    raise SystemExit(1)


# =============================================================================
# TOTP LOGIN
# =============================================================================

print()
print("=" * 88)
print("STEP 8 — TOTP LOGIN")
print("=" * 88)

mobile_number = MOBILE_NUMBER.strip()

if not mobile_number.startswith("+"):

    mobile_number = "+91" + mobile_number

try:

    login_response = neo.totp_login(
        mobile_number=mobile_number,
        ucc=UCC.strip(),
        totp=CURRENT_TOTP
    )

except Exception as exc:

    print("[FAIL] totp_login() raised an exception.")
    print(f"[ERROR] {type(exc).__name__}: {exc}")

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

print(
    f"[INFO] Response type: "
    f"{type(login_response).__name__}"
)

if not isinstance(login_response, dict):

    print("[FAIL] Unexpected TOTP login response.")
    print(login_response)

    raise SystemExit(1)

if login_response.get("error"):

    print("[FAIL] Kotak rejected TOTP login.")
    print(f"[ERROR RESPONSE] {login_response['error']}")

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

login_data = login_response.get(
    "data",
    {}
)

login_status = login_data.get(
    "status"
)

print(
    f"[INFO] Login status: "
    f"{login_status}"
)

if str(login_status).lower() != "success":

    print("[FAIL] TOTP login did not succeed.")
    print(f"[RESPONSE] {login_response}")

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

print("[PASS] TOTP login succeeded.")


# =============================================================================
# MPIN VALIDATION
# =============================================================================

print()
print("=" * 88)
print("STEP 9 — MPIN VALIDATION")
print("=" * 88)

try:

    validation_response = neo.totp_validate(
        mpin=MPIN.strip()
    )

except Exception as exc:

    print("[FAIL] totp_validate() raised an exception.")
    print(f"[ERROR] {type(exc).__name__}: {exc}")

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

print(
    f"[INFO] Response type: "
    f"{type(validation_response).__name__}"
)

if not isinstance(validation_response, dict):

    print("[FAIL] Unexpected MPIN validation response.")
    print(validation_response)

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

if validation_response.get("error"):

    print("[FAIL] Kotak rejected MPIN validation.")
    print(
        f"[ERROR RESPONSE] "
        f"{validation_response['error']}"
    )

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

validation_data = validation_response.get(
    "data",
    {}
)

validation_status = validation_data.get(
    "status"
)

print(
    f"[INFO] Validation status: "
    f"{validation_status}"
)

if str(validation_status).lower() != "success":

    print(
        "[FAIL] MPIN validation did not succeed."
    )

    print(
        f"[RESPONSE] "
        f"{validation_response}"
    )

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)

print(
    "[PASS] MPIN validation succeeded."
)

print()

for field in (
    "ucc",
    "greetingName",
    "baseUrl",
    "dataCenter",
    "kType",
):

    value = validation_data.get(field)

    if value:

        if field in (
            "baseUrl",
        ):
            print(
                f"[INFO] {field}: available"
            )
        else:
            print(
                f"[INFO] {field}: {value}"
            )


# =============================================================================
# QUOTE CONTRACT INSPECTION
# =============================================================================

print()
print("=" * 88)
print("STEP 10 — AUTHENTICATED REST CONTRACT")
print("=" * 88)

try:

    print(
        "[INFO] quotes signature:"
    )

    print(
        inspect.signature(
            neo.quotes
        )
    )

    print(
        "[PASS] Authenticated NeoAPI object is available."
    )

except Exception as exc:

    print(
        "[WARNING] Could not inspect quotes contract."
    )

    print(
        f"[ERROR] {exc}"
    )


# =============================================================================
# MODERN SFEED WEBSOCKET PROBE
# =============================================================================

print()
print("=" * 88)
print("STEP 11 — MODERN SFEED WEBSOCKET PROBE")
print("=" * 88)

print()
print(
    "[INFO] SDK v3 uses async SFeed WebSocket."
)

print(
    "[INFO] This probe creates the authenticated WebSocket object."
)

print(
    "[INFO] It does NOT place, modify, or cancel orders."
)


async def websocket_probe():

    try:

        websocket = neo.create_websocket()

        print(
            "[PASS] create_websocket() returned:"
        )

        print(
            f"       {type(websocket).__module__}."
            f"{type(websocket).__name__}"
        )

        has_async_context = (
            hasattr(
                websocket,
                "__aenter__"
            )
            and hasattr(
                websocket,
                "__aexit__"
            )
        )

        has_async_iterator = (
            hasattr(
                websocket,
                "__aiter__"
            )
        )

        print(
            f"[INFO] Async context manager: "
            f"{has_async_context}"
        )

        print(
            f"[INFO] Async iterator: "
            f"{has_async_iterator}"
        )

        return True

    except Exception as exc:

        print(
            "[FAIL] create_websocket() failed."
        )

        print(
            f"[ERROR] {type(exc).__name__}: {exc}"
        )

        return False


try:

    websocket_ok = asyncio.run(
        websocket_probe()
    )

except Exception as exc:

    print(
        "[FAIL] WebSocket probe runtime failure."
    )

    print(
        f"[ERROR] {type(exc).__name__}: {exc}"
    )

    websocket_ok = False


# =============================================================================
# LOGOUT
# =============================================================================

print()
print("=" * 88)
print("STEP 12 — CLEAN LOGOUT")
print("=" * 88)

try:

    neo.logout()

    print("[PASS] Logout completed.")

except Exception as exc:

    print(
        "[WARNING] Logout raised:"
    )

    print(
        f"[WARNING] {type(exc).__name__}: {exc}"
    )


# =============================================================================
# FINAL RESULT
# =============================================================================

print()
print("=" * 88)
print("FINAL RESULT")
print("=" * 88)

print(
    f"Legacy files repaired : "
    f"{len(repaired_files)}"
)

print(
    f"WebSocket object      : "
    f"{'PASS' if websocket_ok else 'FAIL'}"
)

if websocket_ok:

    print()
    print(
        "[PASS] Kotak Neo v3 authentication and "
        "WebSocket object creation succeeded."
    )

    print()
    print(
        "[NEXT STEP] Start the Romala Algo backend and test:"
    )

    print()

    print(
        "POST http://localhost:8000/api/broker/login"
    )

    print()

    print(
        "[IMPORTANT] The backend login implementation must use:"
    )

    print(
        "1. NeoAPI(consumer_key=...)"
    )

    print(
        "2. totp_login(...)"
    )

    print(
        "3. totp_validate(...)"
    )

    print(
        "4. No session_init()"
    )

    print(
        "5. Modern async SFeed integration"
    )

else:

    print()
    print(
        "[STOP] Do not assume streaming is fixed yet."
    )

    print(
        "Authentication or WebSocket creation still requires investigation."
    )

print()
print("=" * 88)