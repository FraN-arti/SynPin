# SynPin Installation Script
# For private repositories - run from a cloned repo directory.
#
# Usage:
#   git clone https://github.com/FraN-arti/SynPin.git
#   cd SynPin
#   .\scripts\install.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SynPin v0.1.0 - Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Configuration ---
$SYNPIN_HOME = Join-Path $env:USERPROFILE ".synpin"
$SOURCE_DIR = Split-Path $PSScriptRoot -Parent

# --- Verify source ---
if (-not (Test-Path "$SOURCE_DIR\core\pyproject.toml")) {
    Write-Host "ERROR: Not a SynPin repository." -ForegroundColor Red
    Write-Host "  Run this script from the cloned SynPin directory." -ForegroundColor Red
    exit 1
}

# --- Helper Functions ---
function Test-Command($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Test-PythonVersion {
    try {
        $version = python --version 2>&1
        if ($version -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            return ($major -gt 3) -or ($major -eq 3 -and $minor -ge 11)
        }
    } catch {}
    return $false
}

# --- Step 1: Check Dependencies ---
Write-Host "[1/5] Checking dependencies..." -ForegroundColor Yellow

# Python
if (-not (Test-PythonVersion)) {
    Write-Host "  ERROR: Python 3.11+ not found." -ForegroundColor Red
    Write-Host "  Install: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
$pythonVersion = python --version 2>&1
Write-Host "  OK: $pythonVersion" -ForegroundColor Green

# uv
if (-not (Test-Command "uv")) {
    Write-Host "  WARNING: uv not found. Installing..." -ForegroundColor Yellow
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex" *> $null
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}
Write-Host "  OK: uv installed" -ForegroundColor Green

# Node.js
if (-not (Test-Command "node")) {
    Write-Host "  ERROR: Node.js not found." -ForegroundColor Red
    Write-Host "  Install: https://nodejs.org/" -ForegroundColor Red
    exit 1
}
$nodeVersion = node --version
Write-Host "  OK: Node.js $nodeVersion" -ForegroundColor Green

# npm
if (-not (Test-Command "npm")) {
    Write-Host "  ERROR: npm not found (included with Node.js)." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: npm found" -ForegroundColor Green

# --- Step 2: Create SynPin Home ---
Write-Host ""
Write-Host "[2/5] Setting up $SYNPIN_HOME..." -ForegroundColor Yellow

if (Test-Path $SYNPIN_HOME) {
    Write-Host "  WARNING: $SYNPIN_HOME already exists." -ForegroundColor Yellow
    $overwrite = Read-Host "  Overwrite? (y/N)"
    if ($overwrite -ne "y") {
        Write-Host "  Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
    Remove-Item -Recurse -Force $SYNPIN_HOME
}

New-Item -ItemType Directory -Path $SYNPIN_HOME -Force | Out-Null
Write-Host "  OK: Created $SYNPIN_HOME" -ForegroundColor Green

# --- Step 3: Copy Repository ---
Write-Host ""
Write-Host "[3/5] Copying SynPin to $SYNPIN_HOME..." -ForegroundColor Yellow

# Copy core, web (without node_modules), wiki, scripts
$exclude = @("node_modules", ".git", ".venv", "__pycache__", "dist", "data", "logs")
Get-ChildItem -Path $SOURCE_DIR -Directory | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination "$SYNPIN_HOME\$($_.Name)" -Recurse -Force
}
Get-ChildItem -Path $SOURCE_DIR -File | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination "$SYNPIN_HOME\$($_.Name)" -Force
}

Write-Host "  OK: Copied" -ForegroundColor Green

# --- Step 4: Install Core Dependencies ---
Write-Host ""
Write-Host "[4/5] Installing Python dependencies..." -ForegroundColor Yellow

$ErrorActionPreference = "Continue"
cmd /c "uv sync --project $SYNPIN_HOME\core --no-dev" 2>&1 | Out-Null
Push-Location "$SYNPIN_HOME\core"
cmd /c "$SYNPIN_HOME\core\.venv\Scripts\python.exe -m pip install -e ." 2>&1 | Out-Null
Pop-Location
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Failed to install Python dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: Core dependencies installed" -ForegroundColor Green

# --- Step 5: Build Web UI ---
Write-Host ""
Write-Host "[5/5] Building Web UI..." -ForegroundColor Yellow

Push-Location "$SYNPIN_HOME\web"
$ErrorActionPreference = "Continue"
cmd /c "npm ci --silent" 2>&1 | Out-Null
cmd /c "npm run build" 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Failed to build Web UI." -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Host "  OK: Web UI built" -ForegroundColor Green

# --- Install CLI ---
Write-Host ""
Write-Host "Installing synpin CLI..." -ForegroundColor Yellow

# Create wrapper script in PATH
$binDir = Join-Path $env:USERPROFILE ".local\bin"
if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

# Add to PATH permanently if not already
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$binDir", "User")
    $env:PATH = "$binDir;$env:PATH"
}

# Create synpin.bat
$synpinBat = '@echo off' + "`n" +
    "set SYNPIN_HOME=$SYNPIN_HOME" + "`n" +
    'set PATH=%SYNPIN_HOME%\core\.venv\Scripts;%PATH%' + "`n" +
    "python -m synpin %*"
$synpinBat | Out-File -FilePath "$binDir\synpin.bat" -Encoding ascii

# Create synpin.ps1
$synpinPs1 = '$env:SYNPIN_HOME = "' + $SYNPIN_HOME + '"' + "`n" +
    '$env:PATH = "' + $SYNPIN_HOME + '\core\.venv\Scripts;" + $env:PATH' + "`n" +
    "python -m synpin @args"
$synpinPs1 | Out-File -FilePath "$binDir\synpin.ps1" -Encoding utf8

Write-Host "  OK: CLI installed to $binDir" -ForegroundColor Green

# --- Done ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SynPin installed successfully!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Restart your terminal (for PATH update)" -ForegroundColor White
Write-Host "    2. Run: synpin setup" -ForegroundColor White
Write-Host "    3. Run: synpin start" -ForegroundColor White
Write-Host ""
Write-Host "  To uninstall: Remove-Item -Recurse `$env:USERPROFILE\.synpin" -ForegroundColor DarkGray
Write-Host ""
