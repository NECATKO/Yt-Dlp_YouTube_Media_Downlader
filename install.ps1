# install.ps1
$ErrorActionPreference = "Stop"

# Konsol ciktilari UTF-8 olsun (PowerShell 5/7 icin)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Has-Command($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
  $machine = [System.Environment]::GetEnvironmentVariable("Path","Machine")
  $user    = [System.Environment]::GetEnvironmentVariable("Path","User")
  $env:Path = "$machine;$user"
}

function Ensure-Winget {
  if (-not (Has-Command "winget")) {
    Write-Host "HATA: winget bulunamadı. Windows App Installer (winget) gerekli." -ForegroundColor Red
    throw "winget missing"
  }
}

function Ensure-WingetPackage([string]$Id) {
  # Kurulu mu kontrol et
  $installed = $false
  try {
    $out = winget list -e --id $Id 2>$null | Out-String
    if ($LASTEXITCODE -eq 0 -and ($out -match [regex]::Escape($Id))) { $installed = $true }
  } catch { $installed = $false }

  if ($installed) {
    Write-Host "Zaten kurulu: $Id"
    return
  }

  Write-Host "Kuruluyor: $Id"
  winget install -e --id $Id --source winget --accept-package-agreements --accept-source-agreements
}

# --- 0) Klasor kontrol ---
if (-not (Test-Path ".\downloader.py")) {
  throw "downloader.py bulunamadı. install.ps1 ile aynı klasorde olmalı."
}

# --- 1) winget ile sistem bagimliliklari ---
Ensure-Winget
Ensure-WingetPackage "Gyan.FFmpeg"
Ensure-WingetPackage "DenoLand.Deno"

# Python yoksa kurmayi dene
Refresh-Path
if (-not (Has-Command "python")) {
  Write-Host "Python bulunamadı. Python kurulumu deneniyor..." -ForegroundColor Yellow
  # Winget'te bazi sistemlerde 3.13/3.12 id'leri degisebiliyor; once 3.13 dene, olmazsa 3.12
  try {
    Ensure-WingetPackage "Python.Python.3.13"
  } catch {
    Ensure-WingetPackage "Python.Python.3.12"
  }
  Refresh-Path
}

if (-not (Has-Command "python")) {
  throw "Python hala bulunamadı. Kurulumdan sonra yeni PowerShell açıp tekrar deneyin."
}

# --- 2) venv olustur ---
if (-not (Test-Path ".\.venv")) {
  Write-Host "Virtualenv oluşturuluyor (.venv)..."
  python -m venv .\.venv
}

# --- 3) venv aktif et ---
$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "venv python bulunamadı: $venvPython"
}

Write-Host "pip guncelleniyor..."
& $venvPython -m pip install --upgrade pip

# --- 4) Python paketleri (yt-dlp) ---
Write-Host "yt-dlp kuruluyor..."
& $venvPython -m pip install "yt-dlp[default]"

Refresh-Path

# --- 5) Surum kontrolleri ---
Write-Host "`n--- Kontroller ---"
try { yt-dlp --version } catch { Write-Host "yt-dlp PATH'te gorunmuyor (venv icinden calisacagiz)." -ForegroundColor Yellow }
try { ffmpeg -version | Select-Object -First 1 } catch { Write-Host "ffmpeg calismadi. Yeni terminal acmak gerekebilir." -ForegroundColor Yellow }
try { deno --version } catch { Write-Host "deno calismadi. Yeni terminal acmak gerekebilir." -ForegroundColor Yellow }

# --- 6) Calistirmak ister misin? (tek tus) ---
Write-Host "`nKurulum tamamlandı. ✓"
$runNow = Read-Host "Şimdi downloader.py çalıştırılsın mı? (E/H)"
if ($runNow -match '^(E|e)$') {
  & $venvPython .\downloader.py
} else {
  Write-Host "Çalıştırmak için: .\.venv\Scripts\python.exe .\downloader.py"
}
