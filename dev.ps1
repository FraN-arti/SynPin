# SynPin Development launcher (PowerShell).
#
# Starts `synpin dev` with unified Rich-colored output. This script:
#   - sets console to UTF-8 so the Vite/Node ANSI escape codes
#     render as actual color (they were appearing as raw [32m...
#     garbage in dev.bat's output),
#   - enables Windows Terminal VT processing so Rich's ANSI codes
#     render correctly when running in Windows Terminal / modern
#     conhost,
#   - runs synpin dev under python -m so the editable install is
#     picked up regardless of CWD,
#   - actively picks the right Python: walks PATH plus a list of
#     canonical install locations, testing each for an actual
#     'import synpin' so the first Hermes-venv or Microsoft Store
#     stub on PATH doesn't get picked.
#
# Usage:
#   .\dev.ps1           # start dev server (foreground)
#   .\dev.ps1 stop      # stop running dev server
#   .\dev.ps1 doctor    # run prerequisites check
#   .\dev.ps1 help      # show this help

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Clear PYTHONPATH so the parent environment (e.g. Hermes Agent's
# terminal) doesn't leak its own site-packages into our .venv. The
# .venv has its own self-contained site-packages; an external
# PYTHONPATH pointing at another tool's venv causes hard-to-debug
# import failures (mismatched compiled extensions like
# pydantic_core._pydantic_core).
if ($env:PYTHONPATH) {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
}

# Load the shared SynPin brand colors. colors.ps1 maps each brand
# color to the closest PowerShell-named color (PowerShell 5.1 can't
# take hex codes in Write-Host). Keep that file in sync with
# core/synpin/cli/console.py:synpin_theme.
. (Join-Path $PSScriptRoot 'colors.ps1')

# Try to enable Windows Terminal VT processing so ANSI colors render.
# This is a no-op on Windows Terminal (always VT) and a one-shot
# enable on legacy conhost. We ignore failures because some hosts
# (CI, bare cmd) just don't support it.
try {
    $null = $Host.UI.RawUI.WindowTitle
    $signature = @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll")]
public static extern IntPtr GetStdHandle(int nStdHandle);
'@
    $Win32 = Add-Type -MemberDefinition $signature -Name 'Win32' -Namespace 'SynPin' -PassThru
    $handle = $Win32::GetStdHandle(-11)
    $mode = 0
    if ($Win32::GetConsoleMode($handle, [ref]$mode)) {
        $ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        $newMode = $mode -bor $ENABLE_VIRTUAL_TERMINAL_PROCESSING
        $null = $Win32::SetConsoleMode($handle, $newMode)
    }
} catch {
    # Best-effort; on hosts that don't support it we just live with raw text.
}

# Anchor to repo root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Show-Help {
    Write-Host ""
    Write-Host "SynPin Development launcher" -ForegroundColor $SynPinBrand
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor $SynPinInfo
    Write-Host "  .\dev.ps1           " -NoNewline
    Write-Host "# start dev server (foreground)" -ForegroundColor $SynPinDim
    Write-Host "  .\dev.ps1 stop      " -NoNewline
    Write-Host "# stop running dev server" -ForegroundColor $SynPinDim
    Write-Host "  .\dev.ps1 doctor    " -NoNewline
    Write-Host "# run prerequisites check" -ForegroundColor $SynPinDim
    Write-Host "  .\dev.ps1 help      " -NoNewline
    Write-Host "# show this help" -ForegroundColor $SynPinDim
    Write-Host ""
}

# Find a Python that has synpin-core available. We prefer the repo's
# own .venv first — that's where install.ps1 puts it, and it's where
# editable installs point back at the dev repo's source. Only fall back
# to walking PATH if .venv doesn't exist or doesn't have synpin-core.
function Find-SynPinPython {
    $candidates = @()
    # Highest priority: the repo's own .venv (created by install.ps1 or
    # by the auto-install path below). We use $PSScriptRoot here — same
    # trick we used in install.ps1: $MyInvocation.MyCommand.Path is NULL
    # inside a function because $MyInvocation refers to the call site,
    # not the script root. $PSScriptRoot resolves correctly regardless.
    $scriptDir = $PSScriptRoot
    $venvCandidate = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (Test-Path $venvCandidate) { $candidates += $venvCandidate }
    # Fall back to PATH and canonical install locations.
    foreach ($p in ($env:PATH -split ';')) {
        if ($p -and (Test-Path (Join-Path $p 'python.exe'))) {
            $candidates += (Join-Path $p 'python.exe')
        }
    }
    $localApp = $env:LOCALAPPDATA
    $candidates += @(
        "$localApp\Programs\Python\Python311\python.exe"
        "$localApp\Programs\Python\Python312\python.exe"
        "$localApp\Programs\Python\Python313\python.exe"
        "$localApp\Programs\Python\Python314\python.exe"
        "$localApp\Python\python.exe"
        "$localApp\Python\bin\python.exe"
        'C:\Python311\python.exe'
        'C:\Python312\python.exe'
        'C:\Python313\python.exe'
        'C:\Python314\python.exe'
    ) | Where-Object { Test-Path $_ }

    foreach ($py in ($candidates | Select-Object -Unique)) {
        # Skip Hermes Agent venv (no pip, belongs to another tool)
        if ($py -match 'hermes') { continue }
        # Skip Windows Store stub (launches Store, not a real Python)
        if ($py -match 'WindowsApps') { continue }
        $out = & $py -c "import synpin; print(synpin.__file__)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            # Reject site-packages installs — they point at a copy, not
            # the repo. Without this filter, any shared venv (Hermes,
            # system Python that previously saw synpin-core) gets picked
            # over the repo's own .venv and _project_root() breaks.
            if ($out -match '[\\/](site-packages|Lib)[\\/]synpin[\\/]__init__\.py$') {
                Write-Host "[dev] skipping shared-venv install: $py" -ForegroundColor $SynPinDim
                continue
            }
            return $py
        }
    }
    return $null
}

# Find a usable Python (has pip, not Hermes venv, not Store stub)
# for auto-install when synpin-core isn't found yet.
function Find-UsablePython {
    $candidates = @()
    foreach ($p in ($env:PATH -split ';')) {
        if ($p -and (Test-Path (Join-Path $p 'python.exe'))) {
            $candidates += (Join-Path $p 'python.exe')
        }
    }
    $localApp = $env:LOCALAPPDATA
    $candidates += @(
        "$localApp\Programs\Python\Python311\python.exe"
        "$localApp\Programs\Python\Python312\python.exe"
        "$localApp\Programs\Python\Python313\python.exe"
        "$localApp\Programs\Python\Python314\python.exe"
        "$localApp\Python\python.exe"
        "$localApp\Python\bin\python.exe"
        'C:\Python311\python.exe'
        'C:\Python312\python.exe'
        'C:\Python313\python.exe'
        'C:\Python314\python.exe'
    ) | Where-Object { Test-Path $_ }

    foreach ($py in ($candidates | Select-Object -Unique)) {
        if ($py -match 'hermes') { continue }
        if ($py -match 'WindowsApps') { continue }
        $null = & $py -m pip --version 2>$null
        if ($LASTEXITCODE -eq 0) { return $py }
    }
    return $null
}

switch -Regex ($args[0]) {
    '^$|^start$|^dev$' {
        $pythonExe = Find-SynPinPython
        if (-not $pythonExe) {
            # No Python on PATH has synpin-core. Auto-install into
            # the first USABLE Python we can find (skip Hermes venv
            # and Store stub — they have no pip).
            Write-Host "[!] synpin-core is not pip-installed in any Python on PATH." -ForegroundColor $SynPinInfo
            Write-Host "    Attempting to install into the first usable Python..." -ForegroundColor $SynPinInfo
            $firstPy = Find-UsablePython
            if (-not $firstPy) {
                Write-Host "[FAIL] No usable Python found. Run .\install.ps1 first." -ForegroundColor $SynPinFail
                exit 1
            }
            & $firstPy -m pip install -e "$ScriptDir\core" --quiet
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[FAIL] auto-install failed. Run .\install.ps1 first." -ForegroundColor $SynPinFail
                exit 1
            }
            $pythonExe = $firstPy
            Write-Host "[dev] installed into $pythonExe, continuing." -ForegroundColor $SynPinOK
        } else {
            Write-Host "[dev] using Python: $pythonExe" -ForegroundColor $SynPinDim
        }

        # Version check: read VERSION file (single source of truth),
        # sync into pyproject.toml + package.json, then reinstall.
        try {
            $versionFile = Join-Path $ScriptDir "VERSION"
            if (Test-Path $versionFile) {
                $target = (Get-Content $versionFile -Raw).Trim()
                # Sync pyproject.toml version from VERSION
                $tomlPath = Join-Path $ScriptDir "core\pyproject.toml"
                if (Test-Path $tomlPath) {
                    $tomlContent = Get-Content $tomlPath -Raw
                    $newToml = $tomlContent -replace 'version\s*=\s*"[^"]*"', "version = `"$target`""
                    if ($newToml -ne $tomlContent) {
                        [System.IO.File]::WriteAllText($tomlPath, $newToml, [System.Text.UTF8Encoding]::new($false))
                        Write-Host "[dev] synced pyproject.toml -> $target" -ForegroundColor $SynPinDim
                    }
                }
                $installed = & $pythonExe -c "from importlib.metadata import version; print(version('synpin-core'))" 2>$null
                if ($installed -ne $target) {
                    Write-Host "[dev] version mismatch: installed=$installed, target=$target" -ForegroundColor $SynPinInfo
                    Write-Host "[dev] reinstalling synpin-core $target ..." -ForegroundColor $SynPinInfo
                    & $pythonExe -m pip install -e "$ScriptDir\core" --quiet 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "[dev] synpin-core $target installed." -ForegroundColor $SynPinOK
                    } else {
                        Write-Host "[dev] reinstall failed, continuing with $installed." -ForegroundColor $SynPinAccent
                    }
                }
                # Sync package.json versions from VERSION
                foreach ($pkg in @("package.json", "web\package.json")) {
                    $pkgPath = Join-Path $ScriptDir $pkg
                    if (Test-Path $pkgPath) {
                        $content = Get-Content $pkgPath -Raw
                        $newContent = $content -replace '"version"\s*:\s*"[^"]*"', "`"version`": `"$target`""
                        if ($newContent -ne $content) {
                            [System.IO.File]::WriteAllText($pkgPath, $newContent, [System.Text.UTF8Encoding]::new($false))
                            Write-Host "[dev] synced $pkg -> $target" -ForegroundColor $SynPinDim
                        }
                    }
                }
            }
        } catch {
            # Best-effort; don't block startup if version check fails
        }

        # The cmd 'set' in dev.bat is local to that .bat process, so
        # $env:SYNPIN_DEV never reaches here. We set it explicitly
        # so 'synpin dev' knows to use the in-repo config layout
        # (synpin/config/, synpin/data/) instead of the prod
        # ~/.synpin/ one.
        $env:SYNPIN_DEV = "1"
        # WIZARD_S is a user-controlled production variable. It is
        # NOT set automatically here — users set it in their shell
        # (export WIZARD_S=1; ./dev.ps1) or in their deployment
        # config (systemd unit, pm2 ecosystem, .env, etc). The dev
        # batch file does not touch it.
        # See: core/synpin/api/setup_router.py — reads os.environ['WIZARD_S']

        & $pythonExe -m synpin dev
    }
    '^stop$|^--stop$' {
        Write-Host "Stopping SynPin Dev..." -ForegroundColor $SynPinInfo
        # Kill uvicorn and node processes on known ports (2088, 2099)
        # without /T to avoid killing the batch file itself
        $ports = @(2088, 2099)
        foreach ($port in $ports) {
            $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
                     Where-Object { $_.OwningProcess -gt 0 }
            foreach ($conn in $conns) {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host "Done." -ForegroundColor $SynPinOK
    }
    '^doctor$' {
        $py = Find-UsablePython
        if (-not $py) {
            Write-Host "[FAIL] No usable Python found. Run .\install.ps1 first." -ForegroundColor $SynPinFail
            exit 1
        }
        & $py -m synpin doctor
    }
    '^help$|^--help$|^/?$' {
        Show-Help
    }
    default {
        Write-Host "Unknown command: $($args[0])" -ForegroundColor $SynPinFail
        Show-Help
        exit 1
    }
}
