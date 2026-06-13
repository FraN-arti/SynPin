@echo off
REM SynPin CLI launcher (Windows).
REM
REM Resolves the repo root and invokes `python -m synpin <args>`.
REM Use this from anywhere on the system once bin/ is on the PATH.

setlocal
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

REM Anchor to core/ where the synpin package lives
set "CORE_DIR=%REPO_ROOT%\core"

REM Prefer project-local venv if it exists; otherwise system python
if exist "%CORE_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON=%CORE_DIR%\.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo synpin: python not found in PATH. Run .\install.ps1 first. 1>&2
        exit /b 1
    )
    set "PYTHON=python"
)

cd /d "%CORE_DIR%"
"%PYTHON%" -m synpin %*
endlocal
