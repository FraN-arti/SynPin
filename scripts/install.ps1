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
    $env:PATH = "$env:USERPROFILE/.local/bin;$env:PATH"
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

# --- Step 3: Clone Repository ---
Write-Host ""
Write-Host "[3/5] Cloning SynPin..." -ForegroundColor Yellow

$repoDir = Join-Path $SYNPIN_HOME "repo"
if (Test-Path (Join-Path $repoDir ".git")) {
    Push-Location $repoDir
    git pull --ff-only 2>&1 | Out-Null
    Pop-Location
    Write-Host "  OK: Repository updated" -ForegroundColor Green
} else {
    if (Test-Path $repoDir) {
        Remove-Item -Recurse -Force $repoDir
    }
    $oldEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    git clone --depth 1 https://github.com/FraN-arti/SynPin.git $repoDir 2>&1 | Out-Null
    $gitExit = $LASTEXITCODE
    $ErrorActionPreference = $oldEA
    if ($gitExit -ne 0) {
        Write-Host "  ERROR: Failed to clone repository." -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: Repository cloned" -ForegroundColor Green
}

# --- Step 4: Install Core Dependencies ---
Write-Host ""
Write-Host "[4/5] Installing Python dependencies..." -ForegroundColor Yellow

$CORE_DIR = Join-Path $repoDir "core"
$oldEA = $ErrorActionPreference
$ErrorActionPreference = "Continue"
uv sync --project $CORE_DIR --no-dev 2>&1 | Out-Null
$uvExit = $LASTEXITCODE
$venvPython = Join-Path $CORE_DIR ".venv/Scripts/python.exe"
& "uv" pip install -e $CORE_DIR --python $venvPython 2>&1 | Out-Null
$ErrorActionPreference = $oldEA

if ($uvExit -ne 0) {
    Write-Host "  ERROR: Failed to install Python dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: Core dependencies installed" -ForegroundColor Green

# --- Step 5: Build Web UI ---
Write-Host ""
Write-Host "[5/5] Building Web UI..." -ForegroundColor Yellow

$WEB_DIR = Join-Path $repoDir "web"
Push-Location $WEB_DIR
$oldEA = $ErrorActionPreference
$ErrorActionPreference = "Continue"
npm ci --silent 2>&1 | Out-Null
npm run build 2>&1 | Out-Null
$npmExit = $LASTEXITCODE
$ErrorActionPreference = $oldEA
Pop-Location

if ($npmExit -ne 0) {
    Write-Host "  ERROR: Failed to build Web UI." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: Web UI built" -ForegroundColor Green

# --- Install CLI ---
Write-Host ""
Write-Host "Installing synpin CLI..." -ForegroundColor Yellow

$binDir = Join-Path $env:USERPROFILE ".local/bin"
if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$binDir", "User")
    $env:PATH = "$binDir;$env:PATH"
}

# Create synpin.bat
$repoRel = "repo"
$batLines = @(
    "@echo off",
    "setlocal",
    "set SYNPIN_PYTHON=$SYNPIN_HOME\$repoRel\core\.venv\Scripts\python.exe",
    "if exist ""%SYNPIN_PYTHON%"" (",
    "    ""%SYNPIN_PYTHON%"" -m synpin %*",
    ") else (",
    "    echo ERROR: SynPin venv not found.",
    "    echo Run install.ps1 to reinstall.",
    "    pause",
    ")",
    "endlocal"
)
$batLines -join "`r`n" | Out-File -FilePath "$binDir/synpin.bat" -Encoding ascii

# Create synpin.ps1
$ps1Lines = @(
    '$env:SYNPIN_HOME = "' + $SYNPIN_HOME + '"',
    '$synpinPython = Join-Path $env:SYNPIN_HOME "' + $repoRel + '\core\.venv\Scripts\python.exe"',
    'if (Test-Path $synpinPython) {',
    '    & $synpinPython -m synpin @args',
    '} else {',
    '    Write-Host "ERROR: SynPin venv not found." -ForegroundColor Red',
    '    Write-Host "Run install.ps1 to reinstall." -ForegroundColor Red',
    '}',
)
$ps1Lines -join "`r`n" | Out-File -FilePath "$binDir/synpin.ps1" -Encoding utf8

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
Write-Host "  To uninstall: Remove-Item -Recurse `$env:USERPROFILE/.synpin" -ForegroundColor DarkGray
Write-Host ""
