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
        # Make sure the editable install is in place. We don't fail hard
        # if pip install fails (user might intentionally run without it),
        # but we warn.
        $installed = $false
        try {
            $pipShow = & python -m pip show synpin-core 2>&1
            if ($LASTEXITCODE -eq 0 -and $pipShow -match 'Name:\s*synpin-core') {
                $installed = $true
            }
        } catch { }

        if (-not $installed) {
            Write-Host "[!] synpin-core is not pip-installed in editable mode." -ForegroundColor Yellow
            Write-Host "    Run .\install.ps1 once to set this up. Attempting to continue anyway..." -ForegroundColor Yellow
            Write-Host ""
        }

        # Suppress the old green "Starting SynPin Development..." echo and
        # let synpin dev's own Rich banner do the talking.
        & python -m synpin dev
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
