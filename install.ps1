# SynPin installer for Windows (PowerShell 5.1+).
#
# Verifies prerequisites, installs the synpin-core Python package in
# editable mode, and (if Node.js is present) installs the web
# frontend's npm dependencies. Safe to re-run.
#
# Usage:
#   .\install.ps1           # install / verify (default)
#   .\install.ps1 doctor   # prerequisites check only, no install
#   .\install.ps1 update   # git pull + reinstall
#
# This script is written for Windows PowerShell 5.1 (the version
# that ships with Windows 10/11). It avoids em-dashes and other
# non-ASCII characters in source-level strings because PS 5.1 reads
# .ps1 files as Windows-1252 by default; PowerShell 7+ would handle
# UTF-8 fine but PS 5.1 silently turns a UTF-8 em-dash into two
# garbage bytes that confuse the parser.

$ErrorActionPreference = 'Stop'

# Anchor to repo root (where this script lives)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$RequiredPythonMajor = 3
$RequiredPythonMinor = 11
$RequiredNodeMajor = 18

# ----------------------------------------------------------------------------
# Output helpers (PS 5.1 doesn't have ??' for null-coalescing, so we use
# function defaults and avoid $PSStyle which only exists in PS 7+).
# ----------------------------------------------------------------------------

# Load the shared SynPin brand colors. colors.ps1 maps each brand
# color to the closest PowerShell-named color (PowerShell 5.1 can't
# take hex codes in Write-Host). Keep that file in sync with
# core/synpin/cli/console.py:synpin_theme.
. (Join-Path $PSScriptRoot 'colors.ps1')

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor $SynPinBrand }
function Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor $SynPinOK }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor $SynPinWarn }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor $SynPinFail }

# ----------------------------------------------------------------------------
# Auto-install helpers
#
# On Windows 11 / Windows 10 (1809+) the system ships with `winget`,
# the official Microsoft package manager. We use it to install Python
# 3.11 and Node.js 20 LTS without the user having to open a browser
# and click through installers. As with install.sh, every privileged
# install is gated behind an interactive y/N prompt unless
# $env:SYNPIN_AUTO_INSTALL is set to '1'.
# ----------------------------------------------------------------------------

$script:WingetAvailable = $null  # lazy-detect on first use

function Test-Winget {
    if ($null -ne $script:WingetAvailable) { return $script:WingetAvailable }
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($null -eq $wingetCmd) {
        $script:WingetAvailable = $false
    } else {
        $script:WingetAvailable = $true
    }
    return $script:WingetAvailable
}

function Offer-Install {
    param(
        [string]$What,           # human-readable name, e.g. "Python 3.11+"
        [string]$WingetId,       # winget package id, e.g. "Python.Python.3.11"
        [string]$WingetExtraArgs = ""  # extra winget flags if needed
    )
    if (-not (Test-Winget)) {
        Warn "Cannot auto-install ${What}: winget not found on this system."
        Warn "  Install manually from the project website, or upgrade Windows 10 to 1809+."
        return $false
    }
    $cmd = "winget install --id $WingetId --accept-package-agreements --accept-source-agreements $WingetExtraArgs"
    Write-Host ""
    Write-Host "  ${What} is missing. The installer can install it via:" -ForegroundColor $SynPinWarn
    Write-Host "    $cmd" -ForegroundColor $SynPinDim
    if ($env:SYNPIN_AUTO_INSTALL -eq "1") {
        Write-Host "    SYNPIN_AUTO_INSTALL=1 set, installing without prompt..." -ForegroundColor $SynPinWarn
        $reply = "y"
    } else {
        $reply = Read-Host "  Install ${What} now? [y/N]"
    }
    if ($reply -notin @("y", "Y", "yes", "Yes", "YES")) {
        Warn "Skipped ${What} install. The script will fail unless you install it manually."
        return $false
    }
    Write-Host "  Running: $cmd" -ForegroundColor $SynPinDim
    & winget install --id $WingetId --accept-package-agreements --accept-source-agreements $WingetExtraArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "${What} install failed (winget exit $LASTEXITCODE). Check the output above."
        return $false
    }
    Ok "${What} installed."
    return $true
}

# ----------------------------------------------------------------------------
# Prerequisite checks
# ----------------------------------------------------------------------------

function Check-Python {
    Step "Checking Python >= $RequiredPythonMajor.$RequiredPythonMinor"
    $pyOut = ""
    try {
        $pyOut = & python --version 2>&1 | Out-String
        $pyOut = $pyOut.Trim()
    } catch {
        # Python missing. Try to install it via winget.
        $ok = Offer-Install -What "Python $RequiredPythonMajor.$RequiredPythonMinor+" -WingetId "Python.Python.3.11"
        if (-not $ok) {
            Fail "python not found in PATH. Install Python $RequiredPythonMajor.$RequiredPythonMinor+"
            Write-Host "  Download: https://www.python.org/downloads/"
            exit 1
        }
        # winget puts python on PATH but the new process may not see it
        # yet. Try once more - if still missing, tell the user to open
        # a fresh PowerShell.
        try {
            $pyOut = & python --version 2>&1 | Out-String
            $pyOut = $pyOut.Trim()
        } catch {
            Fail "python still not on PATH after install. Open a NEW PowerShell window and re-run."
            exit 1
        }
    }
    if ($pyOut -notmatch 'Python (\d+)\.(\d+)\.(\d+)') {
        Fail "Could not parse Python version: $pyOut"
        exit 1
    }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt $RequiredPythonMajor -or ($major -eq $RequiredPythonMajor -and $minor -lt $RequiredPythonMinor)) {
        Fail "Python $pyOut found, need >= $RequiredPythonMajor.$RequiredPythonMinor"
        Write-Host "  Set SYNPIN_AUTO_INSTALL=1 to attempt an automatic upgrade."
        Write-Host "  Or install Python $RequiredPythonMajor.$RequiredPythonMinor+ manually."
        exit 1
    }
    Ok "Python $pyOut"
}

function Check-Pip {
    Step "Checking pip"
    $pipOut = ""
    try {
        $pipOut = & python -m pip --version 2>&1 | Out-String
        $LASTEXITCODE_VALUE = $LASTEXITCODE
    } catch {
        Fail "pip not available. Run: python -m ensurepip --upgrade"
        exit 1
    }
    if ($LASTEXITCODE -ne 0) {
        Fail "pip not available. Run: python -m ensurepip --upgrade"
        exit 1
    }
    Ok "pip $($pipOut.Trim().Split()[1])"
}

function Check-Git {
    Step "Checking git"
    try {
        $gitOut = & git --version 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw "git not in PATH" }
    } catch {
        $ok = Offer-Install -What "git" -WingetId "Git.Git"
        if (-not $ok) {
            Fail "git not found. Install from https://git-scm.com/download/win"
            exit 1
        }
        try {
            $gitOut = & git --version 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw "git still not in PATH" }
        } catch {
            Fail "git installed but not on PATH. Open a NEW PowerShell and re-run."
            exit 1
        }
    }
    Ok "$($gitOut.Trim())"
}

function Check-Node {
    Step "Checking Node.js >= $RequiredNodeMajor (optional, only needed for the web frontend)"
    $nodeOut = ""
    try {
        $nodeOut = & node --version 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw "node not in PATH" }
    } catch {
        $ok = Offer-Install -What "Node.js $RequiredNodeMajor+" -WingetId "OpenJS.NodeJS.LTS"
        if (-not $ok) {
            Warn "Node.js not found. Web frontend won't work without it."
            Warn "  Download from https://nodejs.org/"
            return
        }
        try {
            $nodeOut = & node --version 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw "node still not in PATH" }
        } catch {
            Warn "Node.js installed but not on PATH. Open a NEW PowerShell to use it."
            return
        }
    }
    $nodeVersion = ($nodeOut.Trim() -replace '^v', '')
    $nodeMajor = 0
    if ($nodeVersion -match '^(\d+)\.') {
        $nodeMajor = [int]$Matches[1]
    }
    if ($nodeMajor -lt $RequiredNodeMajor) {
        Warn "Node.js $nodeVersion found, recommend >= $RequiredNodeMajor"
    } else {
        Ok "Node.js $nodeVersion"
    }
    try {
        $npmOut = & npm --version 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            Ok "npm $($npmOut.Trim())"
        } else {
            Warn "npm not responding"
        }
    } catch {
        Warn "npm not found"
    }
}

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

function Install-PythonDeps {
    Step "Installing Python dependencies (editable install of synpin-core)"

    # Use the repo's own .venv, NOT the first 'python' on PATH.
    # Plain 'python' often resolves to a shared venv (Hermes-agent,
    # system Python with prior installs) which would put synpin-core
    # in the wrong place — and would surprise anyone who has multiple
    # tools installed. A dedicated .venv per repo is the standard.
    $scriptDir = Split-Path -Parent $PSCommandPath
    $venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Step "Creating .venv in $scriptDir\.venv"
        & python -m venv (Join-Path $scriptDir ".venv")
        if ($LASTEXITCODE -ne 0) { Fail "venv creation failed"; exit 1 }
    }

    & $venvPython -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed"; exit 1 }
    & $venvPython -m pip install core/ --quiet
    if ($LASTEXITCODE -ne 0) { Fail "pip install -e core/ failed"; exit 1 }
    Ok "synpin-core installed (editable) into $scriptDir\.venv"
}

function Install-WebDeps {
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($null -eq $npmCmd) {
        Warn "npm not available, skipping web install. Run 'npm install' in web/ manually."
        return
    }
    if (Test-Path "web/node_modules") {
        Step "Web dependencies exist - checking for updates..."
    } else {
        Step "Installing web dependencies (npm install in web/)"
    }
    Push-Location web
    & npm install --no-fund --no-audit
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Fail "npm install failed"; exit 1 }
    Ok "web/node_modules installed"

    # Build frontend for production
    Step "Building web frontend (npm run build in web/)"
    Push-Location web
    & npm run build
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Fail "npm run build failed"; exit 1 }
    Ok "web/dist built"

    # Copy dist to ~/.synpin/web/dist/ for production
    Step "Copying web/dist to ~/.synpin/web/dist/"
    $homeDist = Join-Path $env:USERPROFILE ".synpin\web"
    if (-not (Test-Path $homeDist)) { New-Item -ItemType Directory -Path $homeDist -Force | Out-Null }
    $destDist = Join-Path $homeDist "dist"
    if (Test-Path $destDist) { Remove-Item -Recurse -Force $destDist }
    Copy-Item -Path "web\dist" -Destination $destDist -Recurse
    Ok "web/dist installed to ~/.synpin/web/dist/"
}

# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

function Cmd-Doctor {
    Step "SynPin Doctor"
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

    # Ask to remove source repo (everything is in site-packages + ~/.synpin now)
    # Use $PSScriptRoot (always resolves to the script's directory even when
    # called from within a function) instead of $MyInvocation.MyCommand.Path,
    # which is NULL inside Cmd-Install because $MyInvocation refers to the
    # function call site, not the script root.
    $repoDir = $PSScriptRoot
    Step "Installation complete. Source repo: $repoDir"

    # Mark the install as 'prod-style' by writing a sentinel to ~/.synpin.
    # The first 'synpin start' (production server, not 'synpin dev') will
    # see this sentinel + a present source repo and auto-cleanup the
    # repo, since after install it's no longer needed. This replaces the
    # previous manual [y/N] prompt, which was the wrong place — users
    # hit it right after install when they had no idea whether to keep
    # the repo. Defer to runtime when the question is meaningful:
    # 'this prod server is running; do we still need source?' No.
    #
    # If SYNPIN_KEEP_REPO=1 is set at install time, we skip the
    # sentinel — the user has explicitly opted in to keep source.
    if (-not (Test-Path (Join-Path $env:USERPROFILE '.synpin'))) {
        New-Item -ItemType Directory -Path (Join-Path $env:USERPROFILE '.synpin') -Force | Out-Null
    }
    if (-not $env:SYNPIN_KEEP_REPO) {
        Set-Content -Path (Join-Path $env:USERPROFILE '.synpin\.installed_from') -Value $repoDir -Encoding UTF8
        Ok "Marked install source. Will auto-cleanup on first 'synpin start'."
    } else {
        Ok "SYNPIN_KEEP_REPO=1 set: source will not be auto-removed."
    }

    Step "Done."
    Ok "SynPin installed. Run 'synpin start' or 'synpin dev' to begin."

    # ── Add <repo>/bin to user PATH (idempotent) ───────────────────────────
    # The hand-written bin/synpin and bin/synpin.cmd are the canonical
    # launchers. Without them on PATH, typing 'synpin' from anywhere
    # else fails with 'Имя synpin не распознано'. We append the bin dir
    # to the user's PATH (HKCU\Environment) so it persists across new
    # PowerShell sessions. The current session still won't see it —
    # the user must open a new terminal, or use the explicit path
    # printed below.
    $binDir = Join-Path $repoDir 'bin'
    if (Test-Path $binDir) {
        $currentUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $pathEntries = $currentUserPath -split ';' | Where-Object { $_ -and $_ -ne $binDir }
        $pathEntries = @($binDir) + $pathEntries  # bin first so it wins
        $newUserPath = $pathEntries -join ';'
        [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
        Ok "Added $binDir to user PATH (open new terminal to use)"
    }

    Step "Quick start"
    Ok "  Open a NEW PowerShell, then:"
    Ok "    synpin start     # production server (uses $repoDir\.venv)"
    Ok "    synpin dev       # development with live reload"
    Ok "  Or call the launcher explicitly:"
    Ok "    $binDir\synpin.cmd"
}

function Cmd-Update {
    Step "Updating SynPin"
    if (-not (Test-Path .git)) {
        Fail "Not a git repository, cannot update."
        exit 1
    }
    & git pull --rebase --autostash
    if ($LASTEXITCODE -ne 0) { Fail "git pull failed"; exit 1 }
    Install-PythonDeps
    Install-WebDeps
    Ok "Updated."
}

# ----------------------------------------------------------------------------
# Dispatch: use if/elseif rather than `switch` because PS 5.1's
# `switch -Wildcard`/`-Regex` parsing differs from PS 7 and trips over
# the single-quoted labels we want as plain strings. if/elseif on
# $args[0] is portable across both.
# ----------------------------------------------------------------------------

if ($args.Count -eq 0) {
    Cmd-Install
} elseif ($args[0] -eq "doctor") {
    Cmd-Doctor
} elseif ($args[0] -eq "update") {
    Cmd-Update
} else {
    Write-Host "Unknown command: $($args[0])" -ForegroundColor $SynPinFail
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor $SynPinInfo
    Write-Host "  .\install.ps1            install / verify (default)"
    Write-Host "  .\install.ps1 doctor    prerequisites check only"
    Write-Host "  .\install.ps1 update    git pull + reinstall"
    exit 1
}
