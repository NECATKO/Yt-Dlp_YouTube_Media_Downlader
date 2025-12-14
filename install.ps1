# install.ps1
$ErrorActionPreference = "Stop"

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

# --- 0) Klasör kontrol ---
if (-not (Test-Path ".\downloader.py")) {
  throw "downloader.py bulunamadı. install.ps1 ile aynı klasörde olmalı."
}

# --- 1) winget ile sistem bağımlılıkları ---
Ensure-Winget
Ensure-WingetPackage "Gyan.FFmpeg"
Ensure-WingetPackage "DenoLand.Deno"

# Python yoksa kurmayı dene
Refresh-Path
if (-not (Has-Command "python")) {
  Write-Host "Python bulunamadı. Python kurulumu deneniyor..." -ForegroundColor Yellow
  # Winget'te bazı sistemlerde 3.13/3.12 id'leri değişebiliyor; önce 3.13 dene, olmazsa 3.12
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

# --- 2) venv oluştur ---
if (-not (Test-Path ".\.venv")) {
  Write-Host "Virtualenv oluşturuluyor (.venv)..."
  python -m venv .\.venv
}

# --- 3) venv aktif et ---
$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "venv python bulunamadı: $venvPython"
}

Write-Host "pip güncelleniyor..."
& $venvPython -m pip install --upgrade pip

# --- 4) Python paketleri (yt-dlp) ---
Write-Host "yt-dlp kuruluyor..."
& $venvPython -m pip install "yt-dlp[default]"

Refresh-Path

# --- 5) Sürüm kontrolleri ---
Write-Host "`n--- Kontroller ---"
try { yt-dlp --version } catch { Write-Host "yt-dlp PATH'te görünmüyor (venv içinden çalışacağız)." -ForegroundColor Yellow }
try { ffmpeg -version | Select-Object -First 1 } catch { Write-Host "ffmpeg çalışmadı. Yeni terminal açmak gerekebilir." -ForegroundColor Yellow }
try { deno --version } catch { Write-Host "deno çalışmadı. Yeni terminal açmak gerekebilir." -ForegroundColor Yellow }

# --- 6) Çalıştırmak ister misin? (tek tuş) ---
Write-Host "`nKurulum tamamlandı. ✅"
$runNow = Read-Host "Şimdi downloader.py çalıştırılsın mı? (E/H)"
if ($runNow -match '^(E|e)$') {
  & $venvPython .\downloader.py
} else {
  Write-Host "Çalıştırmak için: .\.venv\Scripts\python.exe .\downloader.py"
}
