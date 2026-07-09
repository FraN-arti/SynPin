@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if /i "%~1"=="" goto :run
if /i "%~1"=="stop" goto :stop
if /i "%~1"=="--stop" goto :stop
if /i "%~1"=="doctor" goto :doctor
if /i "%~1"=="help" goto :help
if /i "%~1"=="/?" goto :help

:run
title SynPin Dev
set SYNPIN_DEV=1
rem WIZARD_S=1 forces the setup wizard visible. Optional. Unset or 0 = auto-detect (show wizard only if providers are missing).
if not defined WIZARD_S set WIZARD_S=1
echo.
echo   Starting SynPin Development...
echo   WIZARD_S=%WIZARD_S%
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
exit /b %ERRORLEVEL%

:stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" stop
exit /b %ERRORLEVEL%

:doctor
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" doctor
exit /b %ERRORLEVEL%

:help
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" help
exit /b %ERRORLEVEL%
