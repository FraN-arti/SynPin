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
echo   Stopping SynPin Dev...
echo.
:: Kill by window title (set in :run)
taskkill /F /FI "WINDOWTITLE eq SynPin Dev*" /T 2>nul
echo   Done.
echo.
timeout /t 1 >nul
goto :end

:end
