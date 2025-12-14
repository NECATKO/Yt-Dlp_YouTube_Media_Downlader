# install.ps1
$ErrorActionPreference = "Stop"

# Konsol çıktıları UTF-8 olsun (PowerShell 5/7 için)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$MinPythonVersion = [Version]"3.10"

function Has-Command([string]$name) {
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
  if ($LASTEXITCODE -ne 0) {
    throw "winget install başarısız: $Id (exit $LASTEXITCODE)"
  }
}

function Get-PythonInfo {
  param(
    [Parameter(Mandatory=$true)][string]$Command,
    [Parameter(Mandatory=$false)][string[]]$PrefixArgs = @()
  )

  if (-not (Has-Command $Command)) { return $null }

  $json = $null
  try {
    $json = & $Command @PrefixArgs -c "import sys, json; print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), 'executable': sys.executable}))" 2>$null
  } catch {
    return $null
  }

  if (-not $json) { return $null }

  try {
    $obj = $json | ConvertFrom-Json
    return [pscustomobject]@{
      Command = $Command
      PrefixArgs = $PrefixArgs
      Version = [Version]$obj.version
      Executable = [string]$obj.executable
    }
  } catch {
    return $null
  }
}

function Ensure-Python {
  Refresh-Path

  $candidates = @(
    (Get-PythonInfo -Command "py" -PrefixArgs @("-3")),
    (Get-PythonInfo -Command "python" -PrefixArgs @())
  ) | Where-Object { $_ -ne $null }

  $ok = $candidates | Where-Object { $_.Version -ge $MinPythonVersion } | Select-Object -First 1
  if ($ok) {
    Write-Host ("Python bulundu: {0} ({1})" -f $ok.Version, $ok.Executable)
    return $ok
  }

  if ($candidates.Count -gt 0) {
    $found = ($candidates | Sort-Object Version -Descending | Select-Object -First 1)
    Write-Host ("Python bulundu ama sürüm düşük: {0} ({1}). En az {2} gerekli." -f $found.Version, $found.Executable, $MinPythonVersion) -ForegroundColor Yellow
  } else {
    Write-Host "Python bulunamadı. Python kurulumu deneniyor..." -ForegroundColor Yellow
  }

  Ensure-Winget

  $pythonWingetIds = @(
    "Python.Python.3",
    "Python.Python.3.13",
    "Python.Python.3.12",
    "Python.Python.3.11"
  )

  $installed = $false
  foreach ($id in $pythonWingetIds) {
    try {
      Ensure-WingetPackage $id
      $installed = $true
      break
    } catch {
      continue
    }
  }

  if (-not $installed) {
    throw ("Python kurulumu winget ile başarısız oldu. Lütfen Python {0}+ kurup tekrar deneyin." -f $MinPythonVersion)
  }

  Refresh-Path
  $candidates = @(
    (Get-PythonInfo -Command "py" -PrefixArgs @("-3")),
    (Get-PythonInfo -Command "python" -PrefixArgs @())
  ) | Where-Object { $_ -ne $null }

  $ok = $candidates | Where-Object { $_.Version -ge $MinPythonVersion } | Select-Object -First 1
  if (-not $ok) {
    $hint = if (Has-Command "py") { "py -3" } else { "python" }
    throw "Python hala uygun değil. Yeni bir terminal açıp tekrar deneyin ve `"$hint --version`" ile sürümü kontrol edin."
  }

  Write-Host ("Python kuruldu: {0} ({1})" -f $ok.Version, $ok.Executable)
  return $ok
}

# --- 0) Klasör kontrol ---
if (-not (Test-Path ".\downloader.py")) {
  throw "downloader.py bulunamadı. install.ps1 ile aynı klasörde olmalı."
}

# --- 1) winget ile sistem bağımlılıkları ---
Ensure-Winget
Ensure-WingetPackage "Gyan.FFmpeg"
Ensure-WingetPackage "DenoLand.Deno"

$python = Ensure-Python

# --- 2) venv oluştur ---
if (-not (Test-Path ".\.venv")) {
  Write-Host "Virtualenv oluşturuluyor (.venv)..."
  & $python.Command @($python.PrefixArgs) -m venv .\.venv
}

# --- 3) venv python ---
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
try { & $venvPython -m yt_dlp --version } catch { Write-Host "yt-dlp çalışmadı (venv içinde kurulu olmalı)." -ForegroundColor Yellow }
try { ffmpeg -version | Select-Object -First 1 } catch { Write-Host "ffmpeg çalışmadı. Yeni terminal açmak gerekebilir." -ForegroundColor Yellow }
try { deno --version } catch { Write-Host "deno çalışmadı. Yeni terminal açmak gerekebilir." -ForegroundColor Yellow }

# --- 6) Çalıştırmak ister misin? (tek tuş) ---
Write-Host "`nKurulum tamamlandı."
$runNow = Read-Host "Şimdi downloader.py çalıştırılsın mı? (E/H)"
if ($runNow -match '^(E|e)$') {
  & $venvPython .\downloader.py
} else {
  Write-Host "Çalıştırmak için: .\.venv\Scripts\python.exe .\downloader.py"
}
