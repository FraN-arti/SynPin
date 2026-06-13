@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM First-time use: run install.ps1 to set up the Python venv, install
REM the synpin-core package in editable mode, and pull web deps. dev.bat
REM assumes that setup has been run; if you see "No module named synpin"
REM at startup, run install.ps1 first.
REM
REM This .bat is a thin wrapper around dev.ps1. We use PowerShell
REM because it supports ANSI VT processing natively (cmd does not),
REM which is what Vite/Rich output needs to render in color instead of
REM emitting raw [32m[1mVITE[22m... escape sequences. If you prefer to skip
REM the .bat and call dev.ps1 directly, that works too.

if /i "%~1"=="stop" goto :stop
if /i "%~1"=="--stop" goto :stop
if /i "%~1"=="doctor" goto :doctor
if /i "%~1"=="help" goto :help
if /i "%~1"=="/?" goto :help

:run
title SynPin Dev
set SYNPIN_DEV=1
echo.
echo   Starting SynPin Development...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
goto :end

:stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" stop
goto :end

:doctor
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" doctor
goto :end

:help
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" help
goto :end

:end
