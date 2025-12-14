chcp 65001 > nul
set PYTHONUTF8=1
@echo off
setlocal
title YouTube Downloader - Tek Tik Calistirici

REM --- Bulundugu klasore gec ---
cd /d "%~dp0"

echo ==========================================
echo   YouTube Downloader - Tek Tik Baslatma
echo ==========================================
echo.

REM --- Kurulum kontrolu ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Ilk kurulum yapiliyor...
    echo.
    powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
    if errorlevel 1 (
        echo.
        echo HATA: Kurulum basarisiz oldu.
        echo Lutfen install.ps1 ciktisini kontrol edin.
        pause
        exit /b 1
    )
) else (
    echo [1/2] Kurulum zaten mevcut, atlandi.
)

echo.
echo [2/2] Program baslatiliyor...
echo.

REM --- Programi calistir ---
".venv\Scripts\python.exe" "%~dp0downloader.py"

echo.
echo Program kapandi.
pause
endlocal
