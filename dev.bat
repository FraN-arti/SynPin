@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if /i "%~1"=="stop" goto :stop
if /i "%~1"=="--stop" goto :stop

:run
title SynPin Dev
echo.
echo   Starting SynPin Development...
echo.
python core\dev_server.py
goto :end

:stop
echo.
echo   Stopping SynPin...
echo.
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /I "PID"') do (
    taskkill /F /PID %%a /T 2>nul
)
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" /FO LIST ^| findstr /I "PID"') do (
    taskkill /F /PID %%a /T 2>nul
)
echo   Done.
echo.
timeout /t 1 >nul
goto :end

:end
