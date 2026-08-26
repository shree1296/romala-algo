# ============================================================================
# ROMALA ALGO - KOTAK NEO LOGIN DEBUG + AUTO FIX
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=============================================================================="
Write-Host "ROMALA ALGO - KOTAK NEO LOGIN DEBUG + AUTO FIX"
Write-Host "=============================================================================="
Write-Host ""

# ============================================================================
# 1. PROJECT DETECTION
# ============================================================================

Write-Host "=============================================================================="
Write-Host "1. PROJECT DETECTION"
Write-Host "=============================================================================="

$ProjectRoot = Get-Location
$BackendPath = Join-Path $ProjectRoot "backend"
$MainFile = Join-Path $BackendPath "main.py"
$ClientFile = Join-Path $BackendPath "kotak_neo\client.py"
$EnvFile = Join-Path $BackendPath ".env"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "[INFO] Project root: $ProjectRoot"

foreach ($Path in @($BackendPath, $MainFile, $ClientFile)) {
    if (Test-Path $Path) {
        Write-Host "[OK] $Path"
    }
    else {
        Write-Host "[FAIL] Missing: $Path"
        exit 1
    }
}

# ============================================================================
# 2. PYTHON ENVIRONMENT
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "2. PYTHON ENVIRONMENT"
Write-Host "=============================================================================="

if (-not (Test-Path $VenvPython)) {
    Write-Host "[FAIL] Virtual environment Python not found:"
    Write-Host "       $VenvPython"
    exit 1
}

Write-Host "[OK] Python: $VenvPython"

& $VenvPython --version

# ============================================================================
# 3. ENVIRONMENT FILE
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "3. ENVIRONMENT FILE"
Write-Host "=============================================================================="

if (-not (Test-Path $EnvFile)) {
    Write-Host "[FAIL] backend\.env not found."
    exit 1
}

Write-Host "[OK] Found: $EnvFile"
Write-Host "[INFO] Loading environment variables..."

Get-Content $EnvFile | ForEach-Object {

    $Line = $_.Trim()

    if (
        $Line -and
        -not $Line.StartsWith("#") -and
        $Line.Contains("=")
    ) {
        $Parts = $Line.Split("=", 2)

        $Name = $Parts[0].Trim()
        $Value = $Parts[1].Trim()

        if (
            ($Value.StartsWith('"') -and $Value.EndsWith('"')) -or
            ($Value.StartsWith("'") -and $Value.EndsWith("'"))
        ) {
            $Value = $Value.Substring(1, $Value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable(
            $Name,
            $Value,
            "Process"
        )
    }
}

Write-Host "[OK] .env loaded into current PowerShell process"

# ============================================================================
# 4. KOTAK CREDENTIAL VALIDATION
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "4. KOTAK CREDENTIAL VALIDATION"
Write-Host "=============================================================================="

$RequiredVars = @(
    "KOTAK_CONSUMER_KEY",
    "KOTAK_MOBILE_NUMBER",
    "KOTAK_UCC",
    "KOTAK_MPIN",
    "KOTAK_TOTP"
)

$MissingVars = @()

foreach ($Name in $RequiredVars) {

    $Value = [Environment]::GetEnvironmentVariable(
        $Name,
        "Process"
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {

        Write-Host "[FAIL] $Name is missing"
        $MissingVars += $Name
    }
    else {

        if ($Value.Length -le 4) {
            $Masked = "****"
        }
        else {
            $Masked = $Value.Substring(0, 2) +
                      ("*" * ($Value.Length - 4)) +
                      $Value.Substring($Value.Length - 2)
        }

        Write-Host "[OK] $Name = $Masked"
    }
}

if ($MissingVars.Count -gt 0) {

    Write-Host ""
    Write-Host "[FAIL] Missing required Kotak credentials."
    Write-Host ""
    exit 1
}

# ============================================================================
# 5. KOTAK NEO SDK IMPORT TEST
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "5. KOTAK NEO SDK IMPORT"
Write-Host "=============================================================================="

$SdkTest = @'
import sys

try:
    from neo_api_client import NeoAPI

    print("SUCCESS")
    print("NeoAPI:", NeoAPI)
    sys.exit(0)

except Exception as e:
    print("FAILED")
    print(type(e).__name__ + ":", str(e))
    sys.exit(1)
'@

$SdkTest | & $VenvPython -

if ($LASTEXITCODE -ne 0) {

    Write-Host "[FAIL] neo_api_client import failed."
    Write-Host ""
    Write-Host "[INFO] Checking installed packages..."

    & $VenvPython -m pip list | Select-String "neo|kotak"

    Write-Host ""
    Write-Host "[IMPORTANT]"
    Write-Host "Do NOT run: pip install neo-api-client"
    Write-Host "Your SDK may already be installed under a different distribution name."
    Write-Host ""

    exit 1
}

Write-Host "[OK] neo_api_client is working."

# ============================================================================
# 6. CHECK SDK LOCATION
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "6. KOTAK SDK LOCATION"
Write-Host "=============================================================================="

$SdkLocation = @'
import neo_api_client
print(neo_api_client.__file__)
'@

$SdkLocation | & $VenvPython -

# ============================================================================
# 7. TEST BACKEND CLIENT IMPORT
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "7. BACKEND KOTAK CLIENT IMPORT"
Write-Host "=============================================================================="

$ClientTest = @"
import sys
sys.path.insert(0, r'$ProjectRoot')

try:
    from backend.kotak_neo.client import KotakNeoClient

    neo = KotakNeoClient()

    print("SUCCESS")
    print("Client:", type(neo))
    print("Connected:", neo.connected)

except Exception as e:
    import traceback

    print("FAILED")
    traceback.print_exc()
    sys.exit(1)
"@

$ClientTest | & $VenvPython -

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] backend.kotak_neo.client import failed."
    exit 1
}

Write-Host "[OK] Backend KotakNeoClient imported successfully."

# ============================================================================
# 8. CHECK main.py LOGIN REQUEST
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "8. CHECKING LOGIN REQUEST MODEL"
Write-Host "=============================================================================="

$MainContent = Get-Content $MainFile -Raw

if ($MainContent -match "ucc:\s*str") {
    Write-Host "[OK] LoginRequest contains UCC."
}
else {
    Write-Host "[WARN] LoginRequest does not appear to contain UCC."
}

if ($MainContent -match '"ucc":\s*req\.ucc') {
    Write-Host "[OK] UCC is forwarded from API request."
}
else {
    Write-Host "[WARN] UCC forwarding may be missing."
}

# ============================================================================
# 9. CHECK ENV FALLBACK
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "9. CHECKING ENVIRONMENT CREDENTIAL FALLBACK"
Write-Host "=============================================================================="

$ClientContent = Get-Content $ClientFile -Raw

$ExpectedEnvVars = @(
    "KOTAK_CONSUMER_KEY",
    "KOTAK_MOBILE_NUMBER",
    "KOTAK_UCC",
    "KOTAK_MPIN",
    "KOTAK_TOTP"
)

foreach ($VarName in $ExpectedEnvVars) {

    if ($ClientContent -match $VarName) {
        Write-Host "[OK] $VarName referenced in client.py"
    }
    else {
        Write-Host "[WARN] $VarName not found in client.py"
    }
}

# ============================================================================
# 10. DIRECT AUTO LOGIN TEST
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "10. DIRECT KOTAK AUTO LOGIN TEST"
Write-Host "=============================================================================="

Write-Host "[INFO] Testing auto_login()..."
Write-Host "[INFO] No order will be placed."
Write-Host ""

$LoginTest = @"
import os
import sys
import traceback

sys.path.insert(0, r'$ProjectRoot')

try:
    from backend.kotak_neo.client import KotakNeoClient

    neo = KotakNeoClient()

    result = neo.auto_login()

    print()
    print("LOGIN_SUCCESS")
    print(result)
    print("CONNECTED:", neo.connected)

except Exception as e:

    print()
    print("LOGIN_FAILED")
    print("ERROR_TYPE:", type(e).__name__)
    print("ERROR:", str(e))
    print()
    traceback.print_exc()

    sys.exit(1)
"@

$LoginTest | & $VenvPython -

$LoginExitCode = $LASTEXITCODE

# ============================================================================
# 11. FINAL REPORT
# ============================================================================

Write-Host ""
Write-Host "=============================================================================="
Write-Host "FINAL REPORT"
Write-Host "=============================================================================="

if ($LoginExitCode -eq 0) {

    Write-Host ""
    Write-Host "[OK] Kotak Neo login test completed successfully."
    Write-Host ""
    Write-Host "Your next step:"
    Write-Host ""
    Write-Host "    python launch.py"
    Write-Host ""
    Write-Host "Then verify:"
    Write-Host ""
    Write-Host "    http://localhost:8000/api/broker/status"
    Write-Host ""
}
else {

    Write-Host ""
    Write-Host "[FAIL] Kotak Neo login failed."
    Write-Host ""
    Write-Host "The SDK import itself may still be working."
    Write-Host "Review the LOGIN_FAILED error above."
    Write-Host ""
    Write-Host "Common causes:"
    Write-Host "  1. Consumer key is invalid."
    Write-Host "  2. Mobile number format is incorrect."
    Write-Host "  3. UCC is incorrect."
    Write-Host "  4. MPIN is incorrect."
    Write-Host "  5. TOTP expired."
    Write-Host "  6. TOTP secret is invalid."
    Write-Host "  7. Kotak SDK authentication contract differs."
    Write-Host ""
}

Write-Host "=============================================================================="
Write-Host "DEBUG COMPLETE"
Write-Host "=============================================================================="