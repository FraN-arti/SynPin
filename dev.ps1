# SynPin Development launcher (PowerShell).
#
# Starts `synpin dev` with unified Rich-colored output. Unlike the old
# dev.bat, this script:
#   - sets console to UTF-8 so the Vite/Node ANSI escape codes
#     (which dev.bat was emitting as raw [32m[1m... garbage) render
#     as actual color,
#   - enables Windows Terminal VT processing so Rich's ANSI codes
#     render correctly when running in Windows Terminal / modern
#     conhost,
#   - runs synpin dev under python -m so the editable install is
#     picked up regardless of CWD.
#
# Usage:
#   .\dev.ps1           # start dev server (foreground)
#   .\dev.ps1 stop      # stop running dev server
#   .\dev.ps1 doctor    # run prerequisites check
#   .\dev.ps1 help      # show this help

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Try to enable Windows Terminal VT processing so ANSI colors render.
# This is a no-op on Windows Terminal (always VT) and a one-shot
# enable on legacy conhost. We ignore failures because some hosts
# (CI, bare cmd) just don't support it.
try {
    $null = $Host.UI.RawUI.WindowTitle  # ensure RawUI is available
    $signature = @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll")]
public static extern IntPtr GetStdHandle(int nStdHandle);
'@
    $Win32 = Add-Type -MemberDefinition $signature -Name 'Win32' -Namespace 'SynPin' -PassThru
    $handle = $Win32::GetStdHandle(-11)  # STD_OUTPUT_HANDLE
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
    Write-Host "SynPin Development launcher" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1           " -NoNewline
    Write-Host "# start dev server (foreground)" -ForegroundColor Gray
    Write-Host "  .\dev.ps1 stop      " -NoNewline
    Write-Host "# stop running dev server" -ForegroundColor Gray
    Write-Host "  .\dev.ps1 doctor    " -NoNewline
    Write-Host "# run prerequisites check" -ForegroundColor Gray
    Write-Host "  .\dev.ps1 help      " -NoNewline
    Write-Host "# show this help" -ForegroundColor Gray
    Write-Host ""
}

switch -Regex ($args[0]) {
    '^$|^start$|^dev$' {
        # Find a Python interpreter that has synpin-core available.
        # Plain 'python' on PATH often points to a tool venv (e.g.
        # Hermes-agent's venv) that doesn't have our package. Walking
        # through PATH in order would still pick the wrong one, so
        # we test each candidate for the actual import. If none
        # work, fall back to the system Python and auto-install.
        $pythonExe = $null
        $candidates = @()
        foreach ($p in ($env:PATH -split ';')) {
            if ($p -and (Test-Path (Join-Path $p 'python.exe'))) {
                $candidates += (Join-Path $p 'python.exe')
            }
        }
        # Add the canonical Windows install locations that may
        # not be on PATH (install-for-me without admin) to the
        # candidate list. We use a here-string for the path
        # templates and Replace the env var at run time, which
        # sidesteps the PowerShell-5.1 single-quote parsing
        # quirks that were tripping up the parser on backslashes.
        $localApp = $env:LOCALAPPDATA
        $candidates += @(
            "$localApp\Programs\Python\Python311\python.exe"
            "$localApp\Programs\Python\Python312\python.exe"
            "$localApp\Programs\Python\Python313\python.exe"
            "$localApp\Python\python.exe"
            "$localApp\Python\bin\python.exe"
            'C:\Python311\python.exe'
            'C:\Python312\python.exe'
        ) | Where-Object { Test-Path $_ }

        foreach ($py in ($candidates | Select-Object -Unique)) {
            $ok = $false
            try {
                $out = & $py -c "import synpin; print(synpin.__file__)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $out) {
                    $pythonExe = $py
                    Write-Host "[dev] using Python: $py" -ForegroundColor Gray
                    Write-Host "[dev] synpin located at: $out" -ForegroundColor Gray
                    # Warn if this Python is 3.14+ — SynPin has not
                    # been tested on it yet and may fail at startup
                    # (Python 3.14 changed several pathlib internals
                    # that the codebase relies on). See
                    # pyproject.toml for the current bound.
                    try {
                        $verOut = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                        if ($LASTEXITCODE -eq 0 -and $verOut) {
                            $parts = $verOut.Split('.')
                            if ($parts.Length -ge 2) {
                                $pyMaj = [int]$parts[0]
                                $pyMin = [int]$parts[1]
                                if ($pyMaj -ge 3 -and $pyMin -ge 14) {
                                    Write-Host "[dev] WARNING: Python $verOut is not yet supported (max 3.13). If SynPin fails to start, install Python 3.11-3.13." -ForegroundColor Yellow
                                }
                            }
                        }
                    } catch { }
                    break
                }
            } catch { }
        }

        if (-not $pythonExe) {
            # No Python on PATH has synpin-core. Try the one that
            # was used to install the package most recently (look for
            # an editable install under core/.synpin/ in site-packages
            # of any reachable Python).
            Write-Host "[!] synpin-core is not pip-installed in any Python on PATH." -ForegroundColor Yellow
            Write-Host "    Attempting to install into the first Python on PATH..." -ForegroundColor Yellow
            $firstPy = (& where.exe python.exe 2>$null | Select-Object -First 1)
            if (-not $firstPy) { $firstPy = "python" }
            & $firstPy -m pip install -e "$ScriptDir\core" --quiet
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[FAIL] auto-install failed. Run .\install.ps1 first." -ForegroundColor Red
                exit 1
            }
            $pythonExe = $firstPy
            Write-Host "[dev] installed into $pythonExe, continuing." -ForegroundColor Green
        }

        # Suppress the old green "Starting SynPin Development..." echo
        # and let synpin dev's own Rich banner do the talking.
        & $pythonExe -m synpin dev
    }
    '^stop$|^--stop$' {
        Write-Host "Stopping SynPin Dev..." -ForegroundColor Yellow
        & taskkill /F /FI "WINDOWTITLE eq SynPin Dev*" /T 2>$null
        Write-Host "Done." -ForegroundColor Green
    }
    '^doctor$' {
        & python -m synpin doctor
    }
    '^help$|^--help$|^/?$' {
        Show-Help
    }
    default {
        Write-Host "Unknown command: $($args[0])" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
