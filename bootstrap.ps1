# SynPin bootstrap installer (PowerShell).
#
# Single-command installer for Windows PowerShell. Forwards to
# the in-repo install.ps1 after cloning into the user's home.
# One folder, no hidden runtime directories outside of it.
#
# Usage:
#   irm https://raw.githubusercontent.com/FraN-arti/SynPin/main/install | iex
#
# (The bootstrap script is also available as bootstrap.ps1;
#  both run on Windows. The plain `install` POSIX variant
#  detects Windows via uname and forwards here.)

$ErrorActionPreference = 'Stop'

$DefaultRepo = 'https://github.com/FraN-arti/SynPin.git'
$DefaultBranch = 'main'

$Repo = if ($env:SYNPIN_INSTALL_REPO) { $env:SYNPIN_INSTALL_REPO } else { $DefaultRepo }
$Branch = if ($env:SYNPIN_BRANCH) { $env:SYNPIN_BRANCH } else { $DefaultBranch }

$HomeDir = if ($env:SYNPIN_HOME) { $env:SYNPIN_HOME } else { $env:USERPROFILE }
$InstallDir = Join-Path $HomeDir 'synpin'

# ── Output helpers (rich-colored brand) ───────────────────────────────

function Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Magenta
}
function Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "    [!!] $msg" -ForegroundColor Yellow }
function Info([string]$msg) { Write-Host "    [..] $msg" -ForegroundColor Cyan }

# ── Step 0: announce ──────────────────────────────────────────────────

Step 'SynPin installer'
Info "Target: $InstallDir"
Info "Repo: $Repo @ $Branch"

# ── Step 1: clone ─────────────────────────────────────────────────────

if (Test-Path (Join-Path $InstallDir '.git')) {
    Warn "Existing SynPin repository detected; updating instead."
    Set-Location $InstallDir
    try { git fetch --depth=1 origin $Branch 2>$null } catch {}
    try { git checkout $Branch 2>$null } catch {}
    try { git pull --ff-only origin $Branch 2>$null } catch {}
} else {
    if (Test-Path $InstallDir) {
        Warn "Directory $InstallDir exists but isn't a git repo; backing up."
        Rename-Item -Path $InstallDir -NewName "$InstallDir.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')" -Force
    }
    Info "Cloning SynPin to $InstallDir"
    try {
        & git clone --depth=1 --branch $Branch $Repo $InstallDir 2>&1 | Out-Null
    } catch {
        Warn "Branch '$Branch' not found; cloning default branch."
        & git clone --depth=1 $Repo $InstallDir
        Set-Location $InstallDir
        try { git checkout $Branch 2>$null } catch {}
    }
}

Set-Location $InstallDir

# ── Step 2: run native installer ──────────────────────────────────────

Step 'Running Windows installer'
& powershell -NoProfile -ExecutionPolicy Bypass -File "./install.ps1" @args

# ── Step 3: next steps ────────────────────────────────────────────────

$BinDir = Join-Path $InstallDir 'bin'

Step 'Done'
Write-Host ""
Write-Host "SynPin installed at: $InstallDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To start the server:" -ForegroundColor Cyan
Write-Host "    cd $InstallDir"
Write-Host "    synpin start"
Write-Host ""
Write-Host "  To access the UI: http://localhost:2088" -ForegroundColor Cyan
Write-Host ""
Write-Host "  If 'synpin' isn't recognised: open a new PowerShell window" -ForegroundColor Yellow
Write-Host "  (PATH was updated for this user; new sessions only)."
Write-Host ""

Ok 'SynPin ready.'
