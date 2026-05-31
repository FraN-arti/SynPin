# SynPin Installation Script
# Usage: iex (irm https://raw.githubusercontent.com/<user>/synpin/main/scripts/install.ps1)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  🚀 SynPin v0.1.0 — Installation         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# --- Configuration ---
$SYNPIN_HOME = Join-Path $env:USERPROFILE ".synpin"
$REPO_URL = "https://github.com/<user>/synpin.git"
$BRANCH = "main"

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
Write-Host "[1/6] Checking dependencies..." -ForegroundColor Yellow

# Python
if (-not (Test-PythonVersion)) {
    Write-Host "  ❌ Python 3.11+ not found." -ForegroundColor Red
    Write-Host "     Install: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
$pythonVersion = python --version 2>&1
Write-Host "  ✅ $pythonVersion" -ForegroundColor Green

# uv
if (-not (Test-Command "uv")) {
    Write-Host "  ⚠️  uv not found. Installing..." -ForegroundColor Yellow
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}
Write-Host "  ✅ uv installed" -ForegroundColor Green

# Node.js
if (-not (Test-Command "node")) {
    Write-Host "  ❌ Node.js not found." -ForegroundColor Red
    Write-Host "     Install: https://nodejs.org/" -ForegroundColor Red
    exit 1
}
$nodeVersion = node --version
Write-Host "  ✅ Node.js $nodeVersion" -ForegroundColor Green

# npm
if (-not (Test-Command "npm")) {
    Write-Host "  ❌ npm not found (included with Node.js)." -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ npm found" -ForegroundColor Green

# --- Step 2: Create SynPin Home ---
Write-Host ""
Write-Host "[2/6] Setting up $SYNPIN_HOME..." -ForegroundColor Yellow

if (Test-Path $SYNPIN_HOME) {
    Write-Host "  ⚠️  $SYNPIN_HOME already exists." -ForegroundColor Yellow
    $overwrite = Read-Host "  Overwrite? (y/N)"
    if ($overwrite -ne "y") {
        Write-Host "  Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
    Remove-Item -Recurse -Force $SYNPIN_HOME
}

New-Item -ItemType Directory -Path $SYNPIN_HOME -Force | Out-Null
Write-Host "  ✅ Created $SYNPIN_HOME" -ForegroundColor Green

# --- Step 3: Clone Repository ---
Write-Host ""
Write-Host "[3/6] Downloading SynPin..." -ForegroundColor Yellow

if (Test-Command "git") {
    git clone --depth 1 --branch $BRANCH $REPO_URL "$SYNPIN_HOME\repo" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ Failed to clone repository." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ⚠️  git not found. Using direct download..." -ForegroundColor Yellow
    $zipUrl = "https://github.com/<user>/synpin/archive/refs/heads/$BRANCH.zip"
    $zipPath = "$env:TEMP\synpin.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $SYNPIN_HOME -Force
    Move-Item "$SYNPIN_HOME\synpin-$BRANCH" "$SYNPIN_HOME\repo" -Force
    Remove-Item $zipPath -Force
}

Write-Host "  ✅ Downloaded" -ForegroundColor Green

# --- Step 4: Install Core Dependencies ---
Write-Host ""
Write-Host "[4/6] Installing Python dependencies..." -ForegroundColor Yellow

$env:PATH = "$SYNPIN_HOME\repo\core\.venv\Scripts;$env:PATH"
uv sync --project "$SYNPIN_HOME\repo\core" --no-dev 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Failed to install Python dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Core dependencies installed" -ForegroundColor Green

# --- Step 5: Build Web UI ---
Write-Host ""
Write-Host "[5/6] Building Web UI..." -ForegroundColor Yellow

Push-Location "$SYNPIN_HOME\repo\web"
npm ci --silent 2>&1 | Out-Null
npm run build 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Failed to build Web UI." -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Host "  ✅ Web UI built" -ForegroundColor Green

# --- Step 6: Install CLI ---
Write-Host ""
Write-Host "[6/6] Installing synpin CLI..." -ForegroundColor Yellow

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
$synpinBat = @"
@echo off
set SYNPIN_HOME=$SYNPIN_HOME
set PATH=%SYNPIN_HOME%\repo\core\.venv\Scripts;%PATH%
python -m synpin %*
"@
$synpinBat | Out-File -FilePath "$binDir\synpin.bat" -Encoding ascii

# Create synpin.ps1
$synpinPs1 = @"
`$env:SYNPIN_HOME = "$SYNPIN_HOME"
`$env:PATH = "$SYNPIN_HOME\repo\core\.venv\Scripts;" + `$env:PATH
python -m synpin @args
"@
$synpinPs1 | Out-File -FilePath "$binDir\synpin.ps1" -Encoding utf8

Write-Host "  ✅ CLI installed to $binDir" -ForegroundColor Green

# --- Done ---
Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  ✅  SynPin installed successfully!      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Restart your terminal (for PATH update)" -ForegroundColor White
Write-Host "    2. Run: synpin setup" -ForegroundColor White
Write-Host "    3. Run: synpin start" -ForegroundColor White
Write-Host ""
