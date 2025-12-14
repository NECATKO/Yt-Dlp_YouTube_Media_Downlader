# update.ps1
param(
  [string]$Owner = "NECATKO",
  [string]$Repo  = "Yt-Dlp_YouTube_Media_Downlader",
  [string]$AssetName = "YtDlpDownloader-Portable.zip",
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

# Keep user data intact: config/logs/archives and .venv are preserved
$Preserve = @("config.json", "logs", "archives", ".venv")
$VersionFile = Join-Path $AppDir "app_version.txt"

function Get-LocalVersion {
  if (Test-Path $VersionFile) { return (Get-Content $VersionFile -Raw).Trim() }
  return "v0.0.0"
}

function Save-LocalVersion([string]$v) {
  Set-Content -Path $VersionFile -Value $v -Encoding UTF8
}

$local = Get-LocalVersion

# GitHub API (latest release)
# Note: GitHub expects a User-Agent on some requests
$api = "https://api.github.com/repos/$Owner/$Repo/releases/latest"
$headers = @{ "User-Agent" = "YtDlpDownloader-Updater" }

try {
  $rel = Invoke-RestMethod -Uri $api -Headers $headers -TimeoutSec 15
} catch {
  if (-not $Quiet) { Write-Host "Update check could not run (internet/API). Continuing..." -ForegroundColor Yellow }
  exit 0
}

$tag = [string]$rel.tag_name
if ([string]::IsNullOrWhiteSpace($tag)) { exit 0 }

if ($tag -eq $local) {
  if (-not $Quiet) { Write-Host "Already up to date: $local" -ForegroundColor Green }
  exit 0
}

# Find asset
$asset = $rel.assets | Where-Object { $_.name -eq $AssetName } | Select-Object -First 1
if (-not $asset) {
  if (-not $Quiet) { Write-Host "Release found ($tag) but asset missing: $AssetName. Continuing..." -ForegroundColor Yellow }
  exit 0
}

$dl = $asset.browser_download_url
$tmpRoot = Join-Path $env:TEMP "YtDlpDownloaderUpdate"
$tmpZip  = Join-Path $tmpRoot $AssetName
$tmpOut  = Join-Path $tmpRoot "unzipped"

New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
if (Test-Path $tmpOut) { Remove-Item $tmpOut -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tmpOut | Out-Null

if (-not $Quiet) { Write-Host "New version found: $local -> $tag" -ForegroundColor Cyan }

Invoke-WebRequest -Uri $dl -OutFile $tmpZip -UseBasicParsing -TimeoutSec 60

# Unzip
Expand-Archive -Path $tmpZip -DestinationPath $tmpOut -Force

# If ZIP contains a single folder, treat it as root
$items = Get-ChildItem $tmpOut
$srcRoot = $tmpOut
if ($items.Count -eq 1 -and $items[0].PSIsContainer) { $srcRoot = $items[0].FullName }

# Copy (skip preserved items)
$srcItems = Get-ChildItem $srcRoot -Force
foreach ($it in $srcItems) {
  if ($Preserve -contains $it.Name) { continue }
  # If Run.bat might be in use, you can also choose to preserve it:
  # if ($it.Name -ieq "Run.bat") { continue }

  $dest = Join-Path $AppDir $it.Name
  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }

  Copy-Item -Path $it.FullName -Destination $dest -Recurse -Force
}

Save-LocalVersion $tag
if (-not $Quiet) { Write-Host "Update completed: $tag" -ForegroundColor Green }
exit 0
