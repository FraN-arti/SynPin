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

# Find a Python that has synpin-core available. Plain 'python' on
# PATH often points to a tool venv (Hermes-agent) or a Microsoft
# Store stub that doesn't have our package. We walk PATH plus
# canonical install locations and test each candidate with a real
# 'import synpin' before using it.
function Find-SynPinPython {
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
        "$localApp\Python\python.exe"
        "$localApp\Python\bin\python.exe"
        'C:\Python311\python.exe'
        'C:\Python312\python.exe'
    ) | Where-Object { Test-Path $_ }

    foreach ($py in ($candidates | Select-Object -Unique)) {
        $out = & $py -c "import synpin; print(synpin.__file__)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            return $py
        }
    }
    return $null
}

switch -Regex ($args[0]) {
    '^$|^start$|^dev$' {
        $pythonExe = Find-SynPinPython
        if (-not $pythonExe) {
            # No Python on PATH has synpin-core. Auto-install into
            # the first Python we can find.
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
        } else {
            Write-Host "[dev] using Python: $pythonExe" -ForegroundColor Gray
        }

        # The cmd 'set' in dev.bat is local to that .bat process, so
        # $env:SYNPIN_DEV never reaches here. We set it explicitly
        # so 'synpin dev' knows to use the in-repo config layout
        # (synpin/config/, synpin/data/) instead of the prod
        # ~/.synpin/ one.
        $env:SYNPIN_DEV = "1"

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
