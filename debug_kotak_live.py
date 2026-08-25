from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pyotp
from dotenv import load_dotenv


# =============================================================================
# ROMALA ALGO — KOTAK NEO TOTP + AUTHENTICATION DIAGNOSTIC
#
# SAFETY:
# - Read-only authentication diagnostics
# - No orders
# - No modify orders
# - No cancel orders
# - No portfolio changes
# =============================================================================


print("=" * 80)
print("ROMALA ALGO — KOTAK NEO TOTP + AUTHENTICATION DIAGNOSTIC")
print("=" * 80)


# =============================================================================
# PROJECT PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
ENV_FILE = BACKEND_ROOT / ".env"

print(f"[INFO] Python      : {sys.executable}")
print(f"[INFO] Project     : {PROJECT_ROOT}")
print(f"[INFO] Backend     : {BACKEND_ROOT}")
print(f"[INFO] Environment : {ENV_FILE}")


# =============================================================================
# LOAD ENVIRONMENT
# =============================================================================

if not ENV_FILE.exists():
    raise RuntimeError(
        f"Environment file not found:\n{ENV_FILE}"
    )

print(f"[INFO] Loading environment: {ENV_FILE}")

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)


# =============================================================================
# ENVIRONMENT HELPERS
# =============================================================================

def get_required_env(*names: str) -> str:
    """
    Return the first configured environment variable.

    Raises a clear error if none exist.
    """

    for name in names:
        value = os.getenv(name)

        if value is not None:
            value = value.strip()

            if value:
                return value

    raise RuntimeError(
        "Missing required environment variable. "
        f"Expected one of: {', '.join(names)}"
    )


def mask(value: str, left: int = 3, right: int = 3) -> str:
    """
    Safely mask secrets.
    """

    if not value:
        return "<EMPTY>"

    if len(value) <= left + right:
        return "*" * len(value)

    return (
        value[:left]
        + "*" * max(4, len(value) - left - right)
        + value[-right:]
    )


# =============================================================================
# LOAD KOTAK CONFIGURATION
# =============================================================================

CONSUMER_KEY = get_required_env(
    "KOTAK_CONSUMER_KEY",
    "KOTAK_API_KEY",
    "NEO_CONSUMER_KEY",
)

MOBILE_NUMBER = get_required_env(
    "KOTAK_MOBILE_NUMBER",
    "KOTAK_MOBILE",
    "NEO_MOBILE_NUMBER",
)

UCC = get_required_env(
    "KOTAK_UCC",
    "NEO_UCC",
)

MPIN = get_required_env(
    "KOTAK_MPIN",
    "NEO_MPIN",
)

TOTP_VALUE = get_required_env(
    "KOTAK_TOTP",
    "NEO_TOTP",
    "KOTAK_TOTP_SECRET",
)


print()
print("=" * 80)
print("KOTAK CONFIGURATION")
print("=" * 80)

print(f"[OK] Consumer Key : {mask(CONSUMER_KEY)}")
print(f"[OK] Mobile       : {mask(MOBILE_NUMBER, 2, 2)}")
print(f"[OK] UCC          : {mask(UCC, 2, 2)}")
print(f"[OK] MPIN         : {mask(MPIN, 2, 2)}")
print(f"[OK] TOTP         : {mask(TOTP_VALUE, 2, 2)}")


# =============================================================================
# TOTP FORMAT DIAGNOSTICS
# =============================================================================

def diagnose_totp(value: str) -> dict:
    """
    Safely diagnose a TOTP value.

    Supported input:

    1. Current 6-digit OTP:
       123456

    2. Base32 TOTP secret:
       JBSWY3DPEHPK3PXP

    3. otpauth URI:
       otpauth://totp/Example?secret=JBSWY3DPEHPK3PXP
    """

    result = {
        "original_length": 0,
        "input_type": None,
        "normalized_length": 0,
        "valid": False,
        "secret": None,
        "reason": None,
    }

    raw = (value or "").strip()

    result["original_length"] = len(raw)

    if not raw:
        result["reason"] = "TOTP value is empty."
        return result

    # -------------------------------------------------------------------------
    # CASE 1 — CURRENT 6 DIGIT OTP
    # -------------------------------------------------------------------------

    if re.fullmatch(r"\d{6}", raw):
        result["input_type"] = "LIVE_OTP"
        result["normalized_length"] = 6
        result["valid"] = True
        result["secret"] = raw
        result["reason"] = (
            "Input is already a 6-digit current OTP."
        )

        return result

    # -------------------------------------------------------------------------
    # CASE 2 — OTpauth URI
    # -------------------------------------------------------------------------

    if raw.lower().startswith("otpauth://"):
        result["input_type"] = "OTPAUTH_URI"

        try:
            parsed = urlparse(raw)
            params = parse_qs(parsed.query)

            secret_values = params.get("secret", [])

            if not secret_values:
                result["reason"] = (
                    "otpauth URI does not contain a secret parameter."
                )

                return result

            raw = secret_values[0].strip()

        except Exception as exc:
            result["reason"] = (
                f"Unable to parse otpauth URI: {exc}"
            )

            return result

    # -------------------------------------------------------------------------
    # NORMALIZE SECRET
    # -------------------------------------------------------------------------

    normalized = raw

    # Remove spaces
    normalized = normalized.replace(" ", "")

    # Remove hyphens
    normalized = normalized.replace("-", "")

    # Remove quotes
    normalized = normalized.replace('"', "")
    normalized = normalized.replace("'", "")

    # Remove common accidental prefixes
    for prefix in (
        "SECRET:",
        "SECRET=",
        "TOTP:",
        "TOTP=",
        "KOTAK_TOTP=",
        "KOTAK_TOTP:",
    ):
        if normalized.upper().startswith(prefix):
            normalized = normalized[len(prefix):]

    normalized = normalized.strip().upper()

    # Remove Base32 padding temporarily
    normalized_without_padding = normalized.rstrip("=")

    result["normalized_length"] = len(
        normalized_without_padding
    )

    if result["input_type"] is None:
        result["input_type"] = "BASE32_SECRET"

    # -------------------------------------------------------------------------
    # BASE32 CHARACTER VALIDATION
    #
    # Valid characters:
    # A-Z
    # 2-7
    # Optional =
    # -------------------------------------------------------------------------

    if not re.fullmatch(
        r"[A-Z2-7]+",
        normalized_without_padding,
    ):
        invalid_chars = sorted(
            set(
                ch
                for ch in normalized_without_padding
                if ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
            )
        )

        result["reason"] = (
            "Value contains characters that are not valid "
            "in a Base32 TOTP secret. "
            f"Invalid characters detected: "
            f"{''.join(invalid_chars) if invalid_chars else '<unknown>'}"
        )

        return result

    # -------------------------------------------------------------------------
    # BASE32 DECODE VALIDATION
    # -------------------------------------------------------------------------

    try:

        padded = normalized_without_padding

        missing_padding = (
            -len(padded)
        ) % 8

        padded += "=" * missing_padding

        base64.b32decode(
            padded,
            casefold=True,
        )

    except Exception as exc:

        result["reason"] = (
            f"Base32 validation failed: {exc}"
        )

        return result

    # -------------------------------------------------------------------------
    # PYOTP VALIDATION
    # -------------------------------------------------------------------------

    try:

        totp = pyotp.TOTP(
            normalized_without_padding
        )

        generated = totp.now()

        if not re.fullmatch(
            r"\d{6}",
            generated,
        ):
            result["reason"] = (
                "pyotp generated an unexpected OTP format."
            )

            return result

    except Exception as exc:

        result["reason"] = (
            f"pyotp rejected the TOTP secret: {exc}"
        )

        return result

    result["valid"] = True
    result["secret"] = normalized_without_padding
    result["reason"] = (
        "Valid Base32 TOTP secret."
    )

    return result


# =============================================================================
# STEP 1 — DIAGNOSE TOTP
# =============================================================================

print()
print("=" * 80)
print("STEP 1 — TOTP FORMAT DIAGNOSTIC")
print("=" * 80)


diagnosis = diagnose_totp(TOTP_VALUE)

print(
    f"[INFO] Original length   : "
    f"{diagnosis['original_length']}"
)

print(
    f"[INFO] Input type        : "
    f"{diagnosis['input_type']}"
)

print(
    f"[INFO] Normalized length : "
    f"{diagnosis['normalized_length']}"
)

print(
    f"[INFO] Diagnosis         : "
    f"{diagnosis['reason']}"
)


if not diagnosis["valid"]:

    print()
    print("[FAIL] KOTAK_TOTP FORMAT IS INVALID")

    print()
    print("Your backend/.env must contain ONE of these formats:")

    print()
    print("OPTION 1 — CURRENT 6-DIGIT OTP")
    print("KOTAK_TOTP=123456")

    print()
    print("OPTION 2 — BASE32 AUTHENTICATOR SECRET")
    print("KOTAK_TOTP=JBSWY3DPEHPK3PXP")

    print()
    print("OPTION 3 — OTPAUTH URI")
    print(
        "KOTAK_TOTP="
        "otpauth://totp/Kotak?secret=JBSWY3DPEHPK3PXP"
    )

    print()
    print("[IMPORTANT]")
    print(
        "Do NOT put a redacted value such as "
        "RE********TP into the .env file."
    )

    print(
        "The actual unmasked TOTP secret or current "
        "6-digit OTP must be present."
    )

    print()
    print(
        "[STOP] Kotak authentication will not be attempted."
    )

    raise SystemExit(1)


# =============================================================================
# RESOLVE CURRENT OTP
# =============================================================================

print()
print("=" * 80)
print("STEP 2 — RESOLVE CURRENT TOTP")
print("=" * 80)


if diagnosis["input_type"] == "LIVE_OTP":

    CURRENT_TOTP = diagnosis["secret"]

    print(
        "[INFO] Using provided current 6-digit OTP."
    )

else:

    secret = diagnosis["secret"]

    totp_generator = pyotp.TOTP(secret)

    CURRENT_TOTP = totp_generator.now()

    remaining = (
        totp_generator.interval
        - (
            __import__("time").time()
            % totp_generator.interval
        )
    )

    print(
        "[PASS] Generated current OTP from Base32 secret."
    )

    print(
        f"[INFO] OTP preview: "
        f"{CURRENT_TOTP[:2]}****"
    )

    print(
        f"[INFO] Approx seconds before refresh: "
        f"{int(remaining)}"
    )


# =============================================================================
# IMPORT KOTAK SDK
# =============================================================================

print()
print("=" * 80)
print("STEP 3 — IMPORT KOTAK NEO SDK")
print("=" * 80)


try:

    import neo_api_client
    from neo_api_client import NeoAPI

    print("[PASS] neo_api_client imported.")

    print(
        "[INFO] SDK version: "
        f"{getattr(neo_api_client, '__version__', 'not exposed')}"
    )

except Exception as exc:

    print("[FAIL] Unable to import neo_api_client.")
    print(f"[ERROR] {exc}")

    raise SystemExit(1)


# =============================================================================
# CREATE CLIENT
# =============================================================================

print()
print("=" * 80)
print("STEP 4 — CREATE NEOAPI CLIENT")
print("=" * 80)


try:

    neo = NeoAPI(
        consumer_key=CONSUMER_KEY,
        environment="prod",
    )

    print("[PASS] NeoAPI client created.")

except Exception as exc:

    print("[FAIL] NeoAPI client creation failed.")
    print(f"[ERROR] {exc}")

    raise SystemExit(1)


# =============================================================================
# NORMALIZE MOBILE NUMBER
# =============================================================================

mobile_number = (
    MOBILE_NUMBER
    .replace(" ", "")
    .replace("-", "")
)

if mobile_number.startswith("+91"):
    pass

elif mobile_number.startswith("91") and len(mobile_number) == 12:
    mobile_number = "+" + mobile_number

elif len(mobile_number) == 10:
    mobile_number = "+91" + mobile_number

print()
print(
    f"[INFO] Normalized mobile: "
    f"{mask(mobile_number, 3, 2)}"
)


# =============================================================================
# STEP 5 — TOTP LOGIN
# =============================================================================

print()
print("=" * 80)
print("STEP 5 — KOTAK TOTP LOGIN")
print("=" * 80)


try:

    login_response = neo.totp_login(
        mobile_number=mobile_number,
        ucc=UCC.strip(),
        totp=CURRENT_TOTP,
    )

    print(
        f"[INFO] Response type: "
        f"{type(login_response).__name__}"
    )

    print(
        f"[INFO] Response: "
        f"{login_response}"
    )

    if not isinstance(login_response, dict):

        raise RuntimeError(
            "Unexpected TOTP login response type."
        )

    if login_response.get("error"):

        raise RuntimeError(
            "Kotak TOTP login rejected: "
            f"{login_response.get('error')}"
        )

    print(
        "[PASS] TOTP login returned without an error."
    )

except Exception as exc:

    print()
    print("[FAIL] KOTAK TOTP LOGIN FAILED")
    print(f"[ERROR] {exc}")

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)


# =============================================================================
# STEP 6 — MPIN VALIDATION
# =============================================================================

print()
print("=" * 80)
print("STEP 6 — KOTAK MPIN VALIDATION")
print("=" * 80)


try:

    validation_response = neo.totp_validate(
        mpin=MPIN.strip(),
    )

    print(
        f"[INFO] Response type: "
        f"{type(validation_response).__name__}"
    )

    print(
        f"[INFO] Response: "
        f"{validation_response}"
    )

    if not isinstance(validation_response, dict):

        raise RuntimeError(
            "Unexpected MPIN validation response type."
        )

    if validation_response.get("error"):

        raise RuntimeError(
            "Kotak MPIN validation rejected: "
            f"{validation_response.get('error')}"
        )

    print(
        "[PASS] MPIN validation returned without an error."
    )

except Exception as exc:

    print()
    print("[FAIL] KOTAK MPIN VALIDATION FAILED")
    print(f"[ERROR] {exc}")

    try:
        neo.logout()
    except Exception:
        pass

    raise SystemExit(1)


# =============================================================================
# FINAL AUTHENTICATION RESULT
# =============================================================================

print()
print("=" * 80)
print("AUTHENTICATION RESULT")
print("=" * 80)

print("[PASS] TOTP format validated.")
print("[PASS] TOTP login completed.")
print("[PASS] MPIN validation completed.")

print()
print(
    "[NEXT STEP] Authentication boundary passed."
)

print(
    "[NEXT STEP] The next debugger can test "
    "quotes() and SFeed WebSocket."
)

print()
print(
    "[SAFETY] No order API was called."
)
print(
    "[SAFETY] No order was placed, modified, or cancelled."
)


# =============================================================================
# CLEAN LOGOUT
# =============================================================================

print()
print("=" * 80)
print("CLEANUP")
print("=" * 80)

try:

    neo.logout()

    print("[PASS] logout() completed.")

except Exception as exc:

    print(
        f"[WARNING] logout() failed: {exc}"
    )