@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM First-time use: run install.ps1 to set up the Python venv, install
REM the synpin-core package in editable mode, and pull web deps. dev.bat
REM assumes that setup has been run; if you see "No module named synpin"
REM at startup, run install.ps1 first.

if /i "%~1"=="stop" goto :stop
if /i "%~1"=="--stop" goto :stop

:run
title SynPin Dev
set SYNPIN_DEV=1
echo.
echo   Starting SynPin Development...
echo.
python -m synpin dev
goto :end

:stop
echo.
echo   Stopping SynPin Dev...
echo.
:: Kill by window title (set in :run)
taskkill /F /FI "WINDOWTITLE eq SynPin Dev*" /T 2>nul
echo   Done.
echo.
timeout /t 1 >nul
goto :end

:end
