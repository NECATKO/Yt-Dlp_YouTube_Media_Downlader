@echo off
REM Ensure console and Python output uses UTF-8
chcp 65001 > nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title YouTube Downloader - One Click Launcher

REM --- Move to this directory ---
cd /d "%~dp0"

REM --- Silent update check ---
powershell -ExecutionPolicy Bypass -File "%~dp0update.ps1" -Quiet

echo ==========================================
echo   YouTube Downloader - One Click Launch
echo ==========================================
echo.

REM --- Install check ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Running first-time setup...
    echo.
    powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
    if errorlevel 1 (
        echo.
        echo ERROR: Setup failed.
        echo Please review install.ps1 output.
        pause
        exit /b 1
    )
) else (
    echo [1/2] Setup already present, skipping.
)

echo.
echo [2/2] Starting app...
echo.

REM --- Run program ---
".venv\Scripts\python.exe" "%~dp0downloader.py"

echo.
echo Application closed.
pause
endlocal
