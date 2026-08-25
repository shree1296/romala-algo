"""
ROMALA ALGO — KOTAK NEO ENVIRONMENT SETUP

Creates:
    backend/.env

SAFETY:
    - Does not contact Kotak
    - Does not authenticate
    - Does not place orders
    - Does not start WebSocket
    - Does not overwrite an existing .env unless explicitly allowed
"""

from __future__ import annotations

from pathlib import Path


# =============================================================================
# PROJECT PATH
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"

print("=" * 80)
print("ROMALA ALGO — KOTAK NEO ENVIRONMENT SETUP")
print("=" * 80)

print(f"[INFO] Project root : {PROJECT_ROOT}")
print(f"[INFO] Backend root : {BACKEND_DIR}")
print(f"[INFO] Target file  : {ENV_FILE}")


# =============================================================================
# VALIDATE PROJECT
# =============================================================================

if not BACKEND_DIR.exists():
    raise RuntimeError(
        f"Backend directory not found: {BACKEND_DIR}"
    )

print("[PASS] Backend directory found.")


# =============================================================================
# DO NOT OVERWRITE EXISTING ENV
# =============================================================================

if ENV_FILE.exists():

    print()
    print("[WARNING] .env already exists.")
    print(f"[INFO] Existing file preserved: {ENV_FILE}")
    print()
    print("No changes were made.")

else:

    ENV_CONTENT = """# =============================================================================
# ROMALA ALGO — KOTAK NEO CONFIGURATION
# =============================================================================
#
# Replace every placeholder with your real credential.
#
# IMPORTANT:
# - Do NOT commit this file to GitHub.
# - Add backend/.env to .gitignore.
# - Never print or log these values.
#
# =============================================================================


# -----------------------------------------------------------------------------
# KOTAK NEO AUTHENTICATION
# -----------------------------------------------------------------------------

KOTAK_CONSUMER_KEY=REPLACE_WITH_YOUR_KOTAK_CONSUMER_KEY

KOTAK_MOBILE_NUMBER=REPLACE_WITH_YOUR_MOBILE_NUMBER

KOTAK_UCC=REPLACE_WITH_YOUR_KOTAK_UCC

KOTAK_MPIN=REPLACE_WITH_YOUR_KOTAK_MPIN


# -----------------------------------------------------------------------------
# KOTAK TOTP
# -----------------------------------------------------------------------------
#
# Use a CURRENT valid TOTP when running the standalone debugger.
#
# This value may expire depending on your authentication flow.
#

KOTAK_TOTP=REPLACE_WITH_CURRENT_KOTAK_TOTP


# -----------------------------------------------------------------------------
# KOTAK NEO ENVIRONMENT
# -----------------------------------------------------------------------------

KOTAK_ENVIRONMENT=prod


# -----------------------------------------------------------------------------
# READ-ONLY MARKET DATA TEST
# -----------------------------------------------------------------------------
#
# IMPORTANT:
# Do not guess this payload.
#
# Replace this only after confirming the exact instrument structure required
# by your installed neo_api_client SDK.
#
# Expected type:
#
# JSON LIST
#
# Example placeholder:
#
# [
#   {
#       "exchange_segment": "nse_cm",
#       "instrument_token": "REPLACE_WITH_VERIFIED_TOKEN"
#   }
# ]
#

KOTAK_TEST_INSTRUMENTS=[]


# =============================================================================
# END
# =============================================================================
"""

    ENV_FILE.write_text(
        ENV_CONTENT,
        encoding="utf-8",
    )

    print()
    print("[PASS] Created .env successfully.")


# =============================================================================
# ENSURE GITIGNORE
# =============================================================================

GITIGNORE_FILE = PROJECT_ROOT / ".gitignore"

GITIGNORE_ENTRY = "backend/.env"

print()
print("=" * 80)
print("GIT SAFETY CHECK")
print("=" * 80)

if GITIGNORE_FILE.exists():

    content = GITIGNORE_FILE.read_text(
        encoding="utf-8",
    )

    entries = {
        line.strip()
        for line in content.splitlines()
    }

    if GITIGNORE_ENTRY not in entries:

        with GITIGNORE_FILE.open(
            "a",
            encoding="utf-8",
        ) as file:

            if content and not content.endswith("\n"):
                file.write("\n")

            file.write(
                "\n# Local Kotak Neo credentials\n"
            )

            file.write(
                f"{GITIGNORE_ENTRY}\n"
            )

        print(
            f"[PASS] Added {GITIGNORE_ENTRY} to .gitignore"
        )

    else:

        print(
            f"[PASS] {GITIGNORE_ENTRY} already protected."
        )

else:

    GITIGNORE_FILE.write_text(
        "# Local Kotak Neo credentials\n"
        "backend/.env\n",
        encoding="utf-8",
    )

    print("[PASS] Created .gitignore.")


# =============================================================================
# FINAL
# =============================================================================

print()
print("=" * 80)
print("SETUP COMPLETE")
print("=" * 80)

print()
print("Edit this file:")
print(ENV_FILE)

print()
print("Replace these placeholders:")
print("  KOTAK_CONSUMER_KEY")
print("  KOTAK_MOBILE_NUMBER")
print("  KOTAK_UCC")
print("  KOTAK_MPIN")
print("  KOTAK_TOTP")

print()
print("Then run:")
print()
print("    python debug_kotak_live.py")

print()
print("[IMPORTANT] backend/.env is configured to be ignored by Git.")
print("[IMPORTANT] No Kotak API call was made.")
print("[IMPORTANT] No trading operation was performed.")