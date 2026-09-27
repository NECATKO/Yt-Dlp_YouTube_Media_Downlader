# install.ps1 - sets up the portable runtime in .\runtime
#
# Nothing is installed system-wide: no winget, no administrator rights, no PATH
# changes. Everything lands next to this script, so the folder can be moved or
# copied to a USB stick afterwards.
#
#   runtime\python   relocatable Python (python-build-standalone), with yt-dlp
#   runtime\ffmpeg   ffmpeg + ffprobe
#   runtime\deno     Deno, for YouTube's JavaScript challenges
#
# Every download is checked against the sha256 pinned in runtime.lock.
# Safe to run repeatedly: it only fetches what is missing or re-pinned.
param([switch]$Quiet)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
# Invoke-WebRequest is many times slower on Windows PowerShell 5.1 when it
# draws its progress bar.
$ProgressPreference = "SilentlyContinue"
# Windows PowerShell 5.1 may default to TLS 1.0, which GitHub rejects.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

$RuntimeDir = Join-Path $AppDir "runtime"
$PythonDir = Join-Path $RuntimeDir "python"
$PythonExe = Join-Path $PythonDir "python.exe"
# Records which runtime.lock pin the unpacked Python came from.
$PythonMarker = Join-Path $PythonDir ".lock-sha256"

function Say([string]$Message, [string]$Color = "Gray") {
  if (-not $Quiet) { Write-Host $Message -ForegroundColor $Color }
}

function Get-PlatformKey {
  # A 32-bit PowerShell on 64-bit Windows reports x86 here, the real
  # architecture in PROCESSOR_ARCHITEW6432.
  $arch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
  if ($arch -eq "AMD64") { return "windows-x86_64" }
  throw "The portable runtime needs 64-bit (x64) Windows; this machine reports '$arch'."
}

function Get-LockEntry([string]$Component, [string]$Platform) {
  foreach ($line in Get-Content (Join-Path $AppDir "runtime.lock")) {
    $text = $line.Trim()
    if ($text -eq "" -or $text.StartsWith("#")) { continue }
    $fields = $text -split "\s+"
    if ($fields.Count -eq 4 -and $fields[0] -eq $Component -and $fields[1] -eq $Platform) {
      return [pscustomobject]@{ Sha256 = $fields[2].ToLower(); Url = $fields[3] }
    }
  }
  throw "runtime.lock has no $Component build for $Platform"
}

function Install-Python($Entry) {
  $tar = Join-Path $env:SystemRoot "System32\tar.exe"
  if (-not (Test-Path $tar)) {
    throw "tar.exe was not found. Windows 10 version 1803 or newer is required."
  }

  $downloads = Join-Path $RuntimeDir "downloads"
  New-Item -ItemType Directory -Force -Path $downloads | Out-Null
  $archive = Join-Path $downloads ($Entry.Url.Split("/")[-1])
  $partial = "$archive.part"

  Write-Host "Downloading Python ($($Entry.Url.Split('/')[-1]))..." -ForegroundColor Cyan
  try {
    Invoke-WebRequest -Uri $Entry.Url -OutFile $partial -UseBasicParsing -TimeoutSec 600
  } catch {
    Remove-Item $partial -Force -ErrorAction SilentlyContinue
    throw "Python download failed: $($_.Exception.Message)"
  }

  $actual = (Get-FileHash -Path $partial -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $Entry.Sha256) {
    Remove-Item $partial -Force -ErrorAction SilentlyContinue
    throw "Checksum mismatch for Python: expected $($Entry.Sha256), got $actual. The file was discarded."
  }
  Move-Item -Force $partial $archive

  # Unpack beside the old copy and swap at the end, so an interrupted run
  # never leaves a half-unpacked Python behind.
  $staging = Join-Path $RuntimeDir "python-staging"
  if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $staging | Out-Null
  & $tar -xzf $archive -C $staging
  if ($LASTEXITCODE -ne 0) { throw "Could not unpack $archive (tar exit $LASTEXITCODE)." }
  $unpacked = Join-Path $staging "python"
  if (-not (Test-Path (Join-Path $unpacked "python.exe"))) { throw "Unexpected archive layout: $archive" }

  if (Test-Path $PythonDir) { Remove-Item $PythonDir -Recurse -Force }
  Move-Item $unpacked $PythonDir
  Remove-Item $staging -Recurse -Force
  Remove-Item $archive -Force
  Set-Content -Path $PythonMarker -Value $Entry.Sha256 -Encoding ASCII -NoNewline
  Write-Host "Python installed: $PythonExe" -ForegroundColor Green
}

# --- 0) Sanity check ---
if (-not (Test-Path (Join-Path $AppDir "downloader.py"))) {
  throw "downloader.py not found. install.ps1 must be run from the program folder."
}

# --- 1) Python ---
$entry = Get-LockEntry "python" (Get-PlatformKey)
$current = if (Test-Path $PythonMarker) { (Get-Content $PythonMarker -Raw).Trim() } else { "" }
if ((Test-Path $PythonExe) -and ($current -eq $entry.Sha256)) {
  Say "Python is up to date."
} else {
  Install-Python $entry
}

# --- 2) yt-dlp, ffmpeg, Deno (and the weekly yt-dlp update) ---
$env:PYTHONNOUSERSITE = "1"
& $PythonExe -s -m ytdlp_app.portable ensure
if ($LASTEXITCODE -ne 0) { throw "Setting up the portable runtime failed (exit $LASTEXITCODE)." }

Say "Portable runtime ready." "Green"
