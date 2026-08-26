# ============================================================================
# ROMALA ALGO - LIVE DATA + KOTAK ROOT CAUSE FORENSIC AUDIT
# READ ONLY - NO SOURCE CODE MODIFICATIONS
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "ROMALA ALGO - ROOT CAUSE FORENSIC AUDIT" -ForegroundColor Cyan
Write-Host "READ ONLY - NO CODE WILL BE MODIFIED" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 0. PROJECT DETECTION
# ============================================================================

Write-Host "=============================================================================="
Write-Host "0. PROJECT DETECTION"
Write-Host "=============================================================================="

$ProjectRoot = Get-Location

Write-Host "[INFO] Project Root: $ProjectRoot"

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "[FAIL] Virtual environment Python not found:" -ForegroundColor Red
    Write-Host "       $Python"
    exit 1
}

Write-Host "[OK] Python: $Python" -ForegroundColor Green

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Section {
    param([string]$Title)

    Write-Host ""
    Write-Host "==============================================================================" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "==============================================================================" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Gray
}

function Mask-Value {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "<EMPTY>"
    }

    if ($Value.Length -le 4) {
        return "*" * $Value.Length
    }

    return $Value.Substring(0, 2) +
        ("*" * ($Value.Length - 4)) +
        $Value.Substring($Value.Length - 2)
}

# ============================================================================
# 1. FILE STRUCTURE
# ============================================================================

Write-Section "1. KOTAK ARCHITECTURE DETECTION"

$ExpectedFiles = @(
    "backend\main.py",
    "backend\kotak_neo\client.py",
    "backend\broker\kotak\kotak_neo_client.py",
    "backend\market\live_quotes.py",
    "backend\market\live_data_pipeline.py",
    "backend\market\websocket_manager.py"
)

foreach ($File in $ExpectedFiles) {

    $Path = Join-Path $ProjectRoot $File

    if (Test-Path $Path) {
        Write-Ok "$File exists"
    }
    else {
        Write-Warn "$File NOT FOUND"
    }
}

# ============================================================================
# 2. FIND ALL KOTAK CLIENT IMPORTS
# ============================================================================

Write-Section "2. FINDING ALL KOTAK CLIENT IMPORTS"

Write-Info "Searching Python source for KotakNeoClient imports..."

Get-ChildItem $ProjectRoot -Recurse -Filter "*.py" |
    Where-Object {
        $_.FullName -notmatch "\\.venv\\" -and
        $_.FullName -notmatch "__pycache__"
    } |
    ForEach-Object {

        $Matches = Select-String `
            -Path $_.FullName `
            -Pattern "KotakNeoClient|backend\.kotak_neo|backend\.broker\.kotak|from.*kotak|import.*kotak" `
            -ErrorAction SilentlyContinue

        foreach ($Match in $Matches) {

            Write-Host ""
            Write-Host "[MATCH] $($_.FullName)" -ForegroundColor Yellow
            Write-Host "        Line $($Match.LineNumber): $($Match.Line.Trim())"
        }
    }

# ============================================================================
# 3. IDENTIFY WHICH CLIENT main.py USES
# ============================================================================

Write-Section "3. ACTIVE BROKER CLIENT USED BY backend/main.py"

$MainFile = Join-Path $ProjectRoot "backend\main.py"

if (Test-Path $MainFile) {

    Write-Info "Searching main.py for Kotak imports..."

    Select-String `
        -Path $MainFile `
        -Pattern "KotakNeoClient|kotak_neo|broker\.kotak|broker_client|auto_login|broker/login" `
        -Context 2,2 |
        ForEach-Object {

            Write-Host ""
            Write-Host "Line $($_.LineNumber):" -ForegroundColor Yellow
            $_.Context.PreContext | ForEach-Object {
                Write-Host "    $_"
            }

            Write-Host ">>> $($_.Line)" -ForegroundColor Green

            $_.Context.PostContext | ForEach-Object {
                Write-Host "    $_"
            }
        }
}
else {
    Write-Fail "backend/main.py not found."
}

# ============================================================================
# 4. CHECK BOTH CLIENTS
# ============================================================================

Write-Section "4. DUPLICATE KOTAK CLIENT ANALYSIS"

$SdkClient = Join-Path $ProjectRoot "backend\kotak_neo\client.py"
$RestClient = Join-Path $ProjectRoot "backend\broker\kotak\kotak_neo_client.py"

if (Test-Path $SdkClient) {

    Write-Host ""
    Write-Info "SDK WRAPPER:"
    Write-Host "backend\kotak_neo\client.py"

    $SdkContent = Get-Content $SdkClient -Raw

    if ($SdkContent -match "from neo_api_client") {
        Write-Ok "Uses neo_api_client SDK"
    }

    if ($SdkContent -match "totp_login") {
        Write-Ok "Contains totp_login()"
    }

    if ($SdkContent -match "totp_validate") {
        Write-Ok "Contains totp_validate()"
    }

    if ($SdkContent -match "auto_login") {
        Write-Ok "Contains auto_login()"
    }
}

if (Test-Path $RestClient) {

    Write-Host ""
    Write-Info "RAW REST CLIENT:"
    Write-Host "backend\broker\kotak\kotak_neo_client.py"

    $RestContent = Get-Content $RestClient -Raw

    if ($RestContent -match "requests") {
        Write-Ok "Uses raw requests HTTP client"
    }

    if ($RestContent -match "auth_token") {
        Write-Ok "Requires externally supplied auth_token"
    }

    if ($RestContent -match "sid") {
        Write-Ok "Requires externally supplied SID"
    }

    Write-Warn "This client does NOT appear to perform Kotak authentication itself."
}

# ============================================================================
# 5. ENVIRONMENT FILE AUDIT
# ============================================================================

Write-Section "5. ENVIRONMENT VARIABLE AUDIT"

$EnvFile = Join-Path $ProjectRoot "backend\.env"

if (-not (Test-Path $EnvFile)) {

    Write-Fail "backend\.env not found."
}
else {

    Write-Ok "Found backend\.env"

    $RequiredVariables = @(
        "KOTAK_CONSUMER_KEY",
        "KOTAK_MOBILE_NUMBER",
        "KOTAK_UCC",
        "KOTAK_MPIN",
        "KOTAK_TOTP",
        "NEO_CONSUMER_KEY"
    )

    $EnvContent = Get-Content $EnvFile

    foreach ($Variable in $RequiredVariables) {

        $Line = $EnvContent |
            Where-Object {
                $_ -match "^\s*$Variable\s*="
            } |
            Select-Object -First 1

        if ($Line) {

            $Value = ($Line -split "=", 2)[1].Trim()

            Write-Host "[ENV] $Variable = $(Mask-Value $Value)"

            if ($Variable -eq "KOTAK_TOTP") {

                Write-Host ""
                Write-Host "[TOTP ANALYSIS]" -ForegroundColor Cyan

                $CleanValue = $Value.Replace(" ", "").Trim()

                if ($CleanValue -match "^\d{6}$") {

                    Write-Ok "KOTAK_TOTP is currently a 6-digit numeric OTP."

                    Write-Warn "A static OTP expires. Auto-login will fail after expiration."
                }
                elseif ($CleanValue -match "^[A-Z2-7]+=*$") {

                    Write-Ok "KOTAK_TOTP appears to be Base32-compatible."

                    Write-Info "Backend should convert this secret into a current 6-digit OTP before calling Kotak."
                }
                else {

                    Write-Fail "KOTAK_TOTP is NOT a valid 6-digit numeric OTP."

                    Write-Warn "It may also be an invalid/malformed Base32 secret."

                    Write-Warn "This matches the Swagger error:"
                    Write-Warn "'Invalid field Totp; must contain only numbers'"
                }
            }
        }
        else {

            Write-Warn "$Variable not present in backend\.env"
        }
    }
}

# ============================================================================
# 6. LOAD DOTENV AND CHECK PYTHON ENV
# ============================================================================

Write-Section "6. PYTHON ENVIRONMENT VISIBILITY"

& $Python -c @"
from pathlib import Path
import os

env_path = Path("backend/.env")

print("ENV_PATH:", env_path.resolve())
print("ENV_EXISTS:", env_path.exists())

try:
    from dotenv import load_dotenv

    load_dotenv(env_path, override=True)

    print("DOTENV: AVAILABLE")

except Exception as exc:

    print("DOTENV_ERROR:", type(exc).__name__, exc)

for name in [
    "KOTAK_CONSUMER_KEY",
    "KOTAK_MOBILE_NUMBER",
    "KOTAK_UCC",
    "KOTAK_MPIN",
    "KOTAK_TOTP",
    "NEO_CONSUMER_KEY",
]:

    value = os.getenv(name)

    if value:
        print(name, "= PRESENT length=", len(value))
    else:
        print(name, "= MISSING")
"@

# ============================================================================
# 7. NEO SDK INSPECTION
# ============================================================================

Write-Section "7. KOTAK NEO SDK METHOD INSPECTION"

& $Python -c @"
import inspect

try:
    from neo_api_client import NeoAPI

    print("NeoAPI:", NeoAPI)
    print()

    for method_name in [
        "totp_login",
        "totp_validate",
        "quotes",
        "positions",
        "holdings",
        "subscribe",
        "logout",
    ]:

        print("-" * 70)

        if hasattr(NeoAPI, method_name):

            method = getattr(NeoAPI, method_name)

            try:
                print(method_name, inspect.signature(method))
            except Exception as exc:
                print(method_name, "SIGNATURE_UNAVAILABLE", exc)

        else:

            print(method_name, "NOT FOUND")

except Exception as exc:

    print("SDK_INSPECTION_FAILED")
    print(type(exc).__name__)
    print(exc)
"@

# ============================================================================
# 8. CHECK LOGIN ENDPOINT IMPLEMENTATION
# ============================================================================

Write-Section "8. /api/broker/login FORENSIC TRACE"

if (Test-Path $MainFile) {

    $Lines = Get-Content $MainFile

    for ($i = 0; $i -lt $Lines.Count; $i++) {

        if (
            $Lines[$i] -match 'api/broker/login' -or
            $Lines[$i] -match 'def.*broker_login'
        ) {

            Write-Host ""
            Write-Host "[LOGIN ENDPOINT FOUND]" -ForegroundColor Yellow

            $Start = [Math]::Max(0, $i - 10)
            $End = [Math]::Min($Lines.Count - 1, $i + 80)

            for ($j = $Start; $j -le $End; $j++) {

                Write-Host ("{0,5}: {1}" -f ($j + 1), $Lines[$j])
            }

            break
        }
    }
}

# ============================================================================
# 9. CHECK TOTP TRANSFORMATION PATH
# ============================================================================

Write-Section "9. TOTP FLOW ANALYSIS"

Write-Info "Searching for every use of TOTP..."

Get-ChildItem $ProjectRoot -Recurse -Filter "*.py" |
    Where-Object {
        $_.FullName -notmatch "\\.venv\\" -and
        $_.FullName -notmatch "__pycache__"
    } |
    ForEach-Object {

        $Matches = Select-String `
            -Path $_.FullName `
            -Pattern "KOTAK_TOTP|totp_login|pyotp|TOTP\(" `
            -ErrorAction SilentlyContinue

        foreach ($Match in $Matches) {

            Write-Host ""
            Write-Host "$($_.FullName):$($Match.LineNumber)" -ForegroundColor Yellow
            Write-Host "    $($Match.Line.Trim())"
        }
    }

# ============================================================================
# 10. RUNNING PYTHON / UVICORN PROCESSES
# ============================================================================

Write-Section "10. RUNNING BACKEND PROCESSES"

$Processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python|uvicorn"
    }

foreach ($Process in $Processes) {

    Write-Host ""
    Write-Host "PID: $($Process.ProcessId)"
    Write-Host "NAME: $($Process.Name)"
    Write-Host "COMMAND:"
    Write-Host $Process.CommandLine
}

# ============================================================================
# 11. PORT CHECK
# ============================================================================

Write-Section "11. PORT 8000 / 5173 CHECK"

foreach ($Port in @(8000, 5173)) {

    Write-Info "Checking port $Port..."

    $Connections = Get-NetTCPConnection `
        -LocalPort $Port `
        -State Listen `
        -ErrorAction SilentlyContinue

    if ($Connections) {

        foreach ($Connection in $Connections) {

            Write-Ok "Port $Port LISTENING"

            Write-Host "PID: $($Connection.OwningProcess)"
        }
    }
    else {

        Write-Fail "Nothing listening on port $Port"
    }
}

# ============================================================================
# 12. API HEALTH
# ============================================================================

Write-Section "12. LIVE API STATUS"

$Endpoints = @(
    "http://127.0.0.1:8000/api/health",
    "http://127.0.0.1:8000/api/broker/status",
    "http://127.0.0.1:8000/api/market-status"
)

foreach ($Endpoint in $Endpoints) {

    Write-Host ""
    Write-Info "GET $Endpoint"

    try {

        $Response = Invoke-RestMethod `
            -Uri $Endpoint `
            -Method GET `
            -TimeoutSec 10

        Write-Ok "Response received"

        $Response |
            ConvertTo-Json -Depth 10
    }
    catch {

        Write-Fail $_.Exception.Message
    }
}

# ============================================================================
# 13. QUOTES ENDPOINT INSPECTION
# ============================================================================

Write-Section "13. /api/quotes ROOT CAUSE INSPECTION"

if (Test-Path $MainFile) {

    $Lines = Get-Content $MainFile

    for ($i = 0; $i -lt $Lines.Count; $i++) {

        if (
            $Lines[$i] -match 'api/quotes'
        ) {

            Write-Host ""
            Write-Host "[QUOTES ENDPOINT FOUND]" -ForegroundColor Yellow

            $Start = [Math]::Max(0, $i - 10)
            $End = [Math]::Min($Lines.Count - 1, $i + 100)

            for ($j = $Start; $j -le $End; $j++) {

                Write-Host ("{0,5}: {1}" -f ($j + 1), $Lines[$j])
            }

            break
        }
    }
}

# ============================================================================
# 14. LIVE DATA PIPELINE IMPORT TEST
# ============================================================================

Write-Section "14. LIVE DATA PIPELINE IMPORT TEST"

& $Python -c @"
import traceback

modules = [
    "backend.market.tick_normalizer",
    "backend.market.live_quotes",
    "backend.market.websocket_manager",
    "backend.market.live_data_pipeline",
]

for module_name in modules:

    print()
    print("=" * 70)
    print("IMPORT:", module_name)
    print("=" * 70)

    try:

        module = __import__(
            module_name,
            fromlist=["*"]
        )

        print("SUCCESS:", module)

    except Exception as exc:

        print("FAILED:", type(exc).__name__, exc)

        traceback.print_exc()
"@

# ============================================================================
# 15. FRONTEND API CONFIGURATION
# ============================================================================

Write-Section "15. FRONTEND API / WEBSOCKET CONFIGURATION"

$FrontendFiles = Get-ChildItem `
    $ProjectRoot `
    -Recurse `
    -Include "*.ts","*.tsx","*.js","*.jsx" |
    Where-Object {
        $_.FullName -notmatch "\\node_modules\\" -and
        $_.FullName -notmatch "\\.venv\\"
    }

foreach ($File in $FrontendFiles) {

    $Matches = Select-String `
        -Path $File.FullName `
        -Pattern "/api/quotes|/api/broker|ws://|WebSocket|VITE_" `
        -ErrorAction SilentlyContinue

    foreach ($Match in $Matches) {

        Write-Host ""
        Write-Host "$($File.FullName):$($Match.LineNumber)" `
            -ForegroundColor Yellow

        Write-Host "    $($Match.Line.Trim())"
    }
}

# ============================================================================
# 16. GIT WORKTREE STATUS
# ============================================================================

Write-Section "16. GIT STATUS"

git status

# ============================================================================
# FINAL
# ============================================================================

Write-Section "FORENSIC AUDIT COMPLETE"

Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host ""
Write-Host "This script DOES NOT modify:"
Write-Host "  - Python files"
Write-Host "  - .env"
Write-Host "  - Git"
Write-Host "  - Kotak credentials"
Write-Host "  - Orders"
Write-Host ""
Write-Host "It only identifies the actual execution path and root causes."
Write-Host ""
Write-Host "=============================================================================="
Write-Host "NEXT: REVIEW THE OUTPUT BEFORE APPLYING ANY FIX" -ForegroundColor Cyan
Write-Host "=============================================================================="