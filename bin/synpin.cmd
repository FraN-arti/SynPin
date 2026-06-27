@echo off
REM SynPin CLI launcher (Windows).
REM
REM Resolves the repo root and invokes `python -m synpin <args>`.
REM Use this from anywhere on the system once bin/ is on the PATH.

setlocal
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

REM Prefer the repo's own .venv (created by install.ps1 alongside
REM dev.ps1 / install.ps1 at the repo root). Fall back to a legacy
REM location under core/.venv for older installs, then system python.
set "PYTHON="

REM 1. Repo-root .venv (current install.ps1 convention)
if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"
)

REM 2. Legacy core/.venv (kept for backward compatibility)
if not defined PYTHON if exist "%REPO_ROOT%\core\.venv\Scripts\python.exe" (
    set "PYTHON=%REPO_ROOT%\core\.venv\Scripts\python.exe"
)

REM 3. System python as last resort
if not defined PYTHON (
    where python >nul 2>&1
    if errorlevel 1 (
        echo synpin: python not found in PATH. Run .\install.ps1 first. 1>&2
        exit /b 1
    )
    set "PYTHON=python"
)

cd /d "%REPO_ROOT%\core"
"%PYTHON%" -m synpin %*
endlocal
