# install.ps1
$ErrorActionPreference = "Stop"

# Keep console output UTF-8 for PowerShell 5/7
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$MinPythonVersion = [Version]"3.11"

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
    Write-Host "ERROR: winget not found. Windows App Installer (winget) is required." -ForegroundColor Red
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
    Write-Host "Already installed: $Id"
    return
  }

  Write-Host "Installing: $Id"
  winget install -e --id $Id --source winget --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    throw "winget install failed: $Id (exit $LASTEXITCODE)"
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
    Write-Host ("Python found: {0} ({1})" -f $ok.Version, $ok.Executable)
    return $ok
  }

  if ($candidates.Count -gt 0) {
    $found = ($candidates | Sort-Object Version -Descending | Select-Object -First 1)
    Write-Host ("Python detected but too old: {0} ({1}). {2}+ is required." -f $found.Version, $found.Executable, $MinPythonVersion) -ForegroundColor Yellow
  } else {
    Write-Host "Python not found. Attempting installation via winget..." -ForegroundColor Yellow
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
    throw ("Python installation via winget failed. Please install Python {0}+ and try again." -f $MinPythonVersion)
  }

  Refresh-Path
  $candidates = @(
    (Get-PythonInfo -Command "py" -PrefixArgs @("-3")),
    (Get-PythonInfo -Command "python" -PrefixArgs @())
  ) | Where-Object { $_ -ne $null }

  $ok = $candidates | Where-Object { $_.Version -ge $MinPythonVersion } | Select-Object -First 1
  if (-not $ok) {
    $hint = if (Has-Command "py") { "py -3" } else { "python" }
    throw "Python is still not usable. Open a new terminal and verify with `"$hint --version`"."
  }

  Write-Host ("Python installed: {0} ({1})" -f $ok.Version, $ok.Executable)
  return $ok
}

# --- 0) Sanity check ---
if (-not (Test-Path ".\downloader.py")) {
  throw "downloader.py not found. install.ps1 must be run from the project folder."
}

# --- 1) winget system dependencies ---
Ensure-Winget
Ensure-WingetPackage "Gyan.FFmpeg"
Ensure-WingetPackage "DenoLand.Deno"

$python = Ensure-Python

# --- 2) Create venv ---
if (-not (Test-Path ".\.venv")) {
  Write-Host "Creating virtualenv (.venv)..."
  & $python.Command @($python.PrefixArgs) -m venv .\.venv
}

# --- 3) venv python ---
$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "venv python not found: $venvPython"
}

Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip

# --- 4) Python packages (yt-dlp) ---
Write-Host "Installing yt-dlp..."
& $venvPython -m pip install "yt-dlp[default]"

Refresh-Path

# --- 5) Version checks ---
Write-Host "`n--- Verification ---"
try { & $venvPython -m yt_dlp --version } catch { Write-Host "yt-dlp did not run (it should be installed inside .venv)." -ForegroundColor Yellow }
try { ffmpeg -version | Select-Object -First 1 } catch { Write-Host "ffmpeg did not run. You may need a new terminal." -ForegroundColor Yellow }
try { deno --version } catch { Write-Host "deno did not run. You may need a new terminal." -ForegroundColor Yellow }

# --- 6) Offer to launch ---
Write-Host "`nSetup completed."
$runNow = Read-Host "Launch downloader.py now? (Y/N)"
if ($runNow -match '^(Y|y)$') {
  & $venvPython .\downloader.py
} else {
  Write-Host "Run manually with: .\.venv\Scripts\python.exe .\downloader.py"
}
