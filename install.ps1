# SynPin installer for Windows (PowerShell 5.1+)
#
# Verifies prerequisites, sets up a Python venv, installs the package
# in editable mode, and (if Node.js is present) installs web
# dependencies. Safe to re-run.
#
# Usage:
#   .\install.ps1           # install / verify
#   .\install.ps1 doctor   # run prerequisites check only
#   .\install.ps1 update   # pull latest + reinstall

$ErrorActionPreference = 'Stop'

# Anchor to repo root (where this script lives)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$RequiredPythonMajor = 3
$RequiredPythonMinor = 11
$RequiredNodeMajor = 18

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

function Check-Python {
    Step "Checking Python >= $RequiredPythonMajor.$RequiredPythonMinor"
    try {
        $pyOut = & python --version 2>&1
    } catch {
        Fail "python not found in PATH. Install Python $RequiredPythonMajor.$RequiredPythonMinor+"
        Write-Host "  Download: https://www.python.org/downloads/"
        exit 1
    }
    if ($pyOut -notmatch 'Python (\d+)\.(\d+)\.(\d+)') {
        Fail "Could not parse Python version: $pyOut"
        exit 1
    }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt $RequiredPythonMajor -or ($major -eq $RequiredPythonMajor -and $minor -lt $RequiredPythonMinor)) {
        Fail "Python $pyOut found, need >= $RequiredPythonMajor.$RequiredPythonMinor"
        exit 1
    }
    Ok "Python $pyOut"
}

function Check-Pip {
    Step "Checking pip"
    $pipOut = & python -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "pip not available. Run: python -m ensurepip --upgrade"
        exit 1
    }
    Ok "pip $($pipOut.Split()[1])"
}

function Check-Git {
    Step "Checking git"
    try {
        $gitOut = & git --version 2>&1
        if ($LASTEXITCODE -ne 0) { throw "not in PATH" }
    } catch {
        Fail "git not found. Install from https://git-scm.com/download/win"
        exit 1
    }
    Ok "$gitOut"
}

function Check-Node {
    Step "Checking Node.js >= $RequiredNodeMajor (optional — only needed for the web frontend)"
    try {
        $nodeOut = & node --version 2>&1
        if ($LASTEXITCODE -ne 0) { throw "not in PATH" }
    } catch {
        Warn "Node.js not found. Web frontend won't work without it."
        Warn "  Download from https://nodejs.org/"
        return
    }
    $nodeVersion = $nodeOut -replace '^v', ''
    $nodeMajor = [int]($nodeVersion.Split('.')[0])
    if ($nodeMajor -lt $RequiredNodeMajor) {
        Warn "Node.js $nodeVersion found, recommend >= $RequiredNodeMajor"
    } else {
        Ok "Node.js $nodeVersion"
    }
    try {
        $npmOut = & npm --version 2>&1
        if ($LASTEXITCODE -eq 0) { Ok "npm $npmOut" }
        else { Warn "npm not responding" }
    } catch { Warn "npm not found" }
}

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

function Install-PythonDeps {
    Step "Installing Python dependencies (editable install of synpin-core)"
    & python -m pip install --upgrade pip --quiet
    & python -m pip install -e core/ --quiet
    if ($LASTEXITCODE -ne 0) { Fail "pip install failed"; exit 1 }
    Ok "synpin-core installed (editable)"
}

function Install-WebDeps {
    if (Test-Path "web/node_modules") {
        Step "Web dependencies already installed (web/node_modules exists). Skipping."
        return
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Warn "npm not available — skipping web install. Run 'npm install' in web/ manually."
        return
    }
    Step "Installing web dependencies (npm install in web/)"
    Push-Location web
    & npm install --no-fund --no-audit
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Fail "npm install failed"; exit 1 }
    Ok "web/node_modules installed"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

function Cmd-Doctor {
    Check-Python
    Check-Pip
    Check-Git
    Check-Node
    Ok "All required prerequisites met."
}

function Cmd-Install {
    Step "SynPin Installer"
    Check-Python
    Check-Pip
    Check-Git
    Check-Node
    Install-PythonDeps
    Install-WebDeps
    Step "Done."
    Ok "SynPin installed. Run '.\bin\synpin.cmd start' or '.\bin\synpin.cmd dev' to begin."
}

function Cmd-Update {
    Step "Updating SynPin"
    if (-not (Test-Path .git)) {
        Fail "Not a git repository — cannot update."
        exit 1
    }
    & git pull --rebase --autostash
    if ($LASTEXITCODE -ne 0) { Fail "git pull failed"; exit 1 }
    Install-PythonDeps
    Install-WebDeps
    Ok "Updated."
}

switch ($args[0]) {
    'doctor'  { Cmd-Doctor }
    'update'  { Cmd-Update }
    default   { Cmd-Install }
}
