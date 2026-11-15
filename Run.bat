@echo off
REM Ensure console and Python output uses UTF-8
chcp 65001 > nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM Ignore packages from the user's own Python profile: the app must only see
REM what is inside runtime\python.
set PYTHONNOUSERSITE=1
title YouTube Downloader - One Click Launcher

REM --- Move to this directory ---
cd /d "%~dp0"

echo ==========================================
echo   YouTube Downloader - One Click Launch
echo ==========================================
echo.

REM --- Portable runtime (first run downloads it into .\runtime) ---
if not exist "runtime\python\python.exe" (
    echo [1/2] First-time setup: downloading the portable runtime into this folder...
    echo       ^(Python, yt-dlp, ffmpeg, Deno - nothing is installed on the system^)
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
) else (
    echo [1/2] Checking the portable runtime...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Quiet
)
if errorlevel 1 (
    if not exist "runtime\python\python.exe" (
        echo.
        echo ERROR: Setup failed. Check your internet connection and the output above.
        pause
        exit /b 1
    )
    REM Already set up once: an offline launch must still work.
    echo.
    echo WARNING: The runtime check did not finish; continuing with what is installed.
)

echo.
echo [2/2] Starting app...
echo.

REM --- Run program ---
"runtime\python\python.exe" -s "%~dp0downloader.py" %*
set "APP_RC=%ERRORLEVEL%"

REM A double-click (no arguments) keeps the window open to read the output; a command
REM line run (downloader.py audit ...) must not wait, and passes the app's exit code on.
if "%~1"=="" (
    echo.
    echo Application closed.
    pause
)
endlocal & exit /b %APP_RC%
