# update.ps1 - transactional updater for the Windows portable app
#
#   powershell -File update.ps1            update if a newer release exists
#   powershell -File update.ps1 -CheckOnly only say whether one exists
#   powershell -File update.ps1 -Quiet     what Run.bat does at every launch: silent unless it
#                                          acts, and it never blocks the launch (exits 0)
#
# The app package is replaced as one transaction, like update.sh does on Linux/macOS:
#   1. the release ZIP is downloaded and unpacked into a private folder inside this one,
#   2. the new package is checked (expected files, a version that matches the release and is
#      newer than the installed one, and that it imports) WITHOUT touching the install,
#   3. every file to replace is first copied next to its place, and only when all copies
#      exist is each old file moved into a backup folder and the new one moved in,
#   4. app_version.txt is written last, so it never names a version that was not installed,
#   5. any failure moves every old file back and leaves the previous version running.
# The previous version stays in .previous-version\ afterwards. An update killed half way is
# undone the next time this script starts.
#
# Never touched: config.json, logs, archives, runtime, cache, downloads, .venv.
# Not replaced: Run.bat. It is the running script's own launcher: cmd.exe reads a batch
# file while it executes, so swapping it underneath the launch could derail it. It rarely
# changes; when a release does change it, copy it over by hand.
# The runtime components (Python, ffmpeg, Deno) are verified separately by install.ps1
# against runtime.lock; this script only verifies the app package.
param(
  [string]$Owner = "NECATKO",
  [string]$Repo  = "Yt-Dlp_YouTube_Media_Downlader",
  [string]$AssetName = "YtDlpDownloader-Portable.zip",
  [string]$ApiUrl = "",
  [switch]$Quiet,
  [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
# Windows PowerShell 5.1 may default to TLS 1.0, which GitHub rejects.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir
if (-not $ApiUrl) { $ApiUrl = "https://api.github.com/repos/$Owner/$Repo/releases/latest" }

$VersionFile = Join-Path $AppDir "app_version.txt"
$LockPath    = Join-Path $AppDir ".update.lock"
$Journal     = Join-Path $AppDir ".update-in-progress"
$PreviousDir = Join-Path $AppDir ".previous-version"

# What an update replaces. Everything else in this folder belongs to the user.
$ReplaceItems  = @("ytdlp_app", "downloader.py", "pyproject.toml", "runtime.lock", "run.sh", "install.sh", "update.sh", "install.ps1", "update.ps1", "README.md", "LICENSE")
$RequiredFiles = @("ytdlp_app\__init__.py", "ytdlp_app\_version.py", "downloader.py", "pyproject.toml", "runtime.lock")

function Say([string]$Message, [string]$Color = "Gray") {
  if (-not $Quiet) { Write-Host $Message -ForegroundColor $Color }
}
function Warn([string]$Message) { Write-Host $Message -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "ERROR: $Message" -ForegroundColor Red }

# --- versions ---------------------------------------------------------------

function ConvertTo-Version([string]$Text) {
  # "v1.2.3-rc.1+build" -> @{ Core = @(1,2,3); Pre = @("rc","1") }, or $null when unparseable.
  $m = [regex]::Match($Text.Trim(), '^[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$')
  if (-not $m.Success) { return $null }
  $core = @($m.Groups[1].Value.Split('.') | ForEach-Object { [System.Numerics.BigInteger]::Parse($_) })
  $pre = @()
  if ($m.Groups[2].Success) { $pre = @($m.Groups[2].Value.Split('.')) }
  return [pscustomobject]@{ Core = $core; Pre = $pre }
}

function Compare-Version([string]$A, [string]$B) {
  # -1, 0 or 1, by semantic versioning: 0.10.0 > 0.9.0, 1.0.0 > 1.0.0-rc1.
  $x = ConvertTo-Version $A
  $y = ConvertTo-Version $B
  $n = [Math]::Max($x.Core.Count, $y.Core.Count)
  for ($i = 0; $i -lt $n; $i++) {
    $p = if ($i -lt $x.Core.Count) { $x.Core[$i] } else { [System.Numerics.BigInteger]::Zero }
    $q = if ($i -lt $y.Core.Count) { $y.Core[$i] } else { [System.Numerics.BigInteger]::Zero }
    if ($p -gt $q) { return 1 }
    if ($p -lt $q) { return -1 }
  }
  if ($x.Pre.Count -eq 0 -and $y.Pre.Count -eq 0) { return 0 }
  if ($x.Pre.Count -eq 0) { return 1 }    # a release outranks its pre-releases
  if ($y.Pre.Count -eq 0) { return -1 }
  $m = [Math]::Max($x.Pre.Count, $y.Pre.Count)
  for ($i = 0; $i -lt $m; $i++) {
    if ($i -ge $x.Pre.Count) { return -1 }  # fewer identifiers is lower
    if ($i -ge $y.Pre.Count) { return 1 }
    $p = $x.Pre[$i]; $q = $y.Pre[$i]
    $pNum = $p -match '^\d+$'; $qNum = $q -match '^\d+$'
    if ($pNum -and $qNum) {
      $pv = [System.Numerics.BigInteger]::Parse($p); $qv = [System.Numerics.BigInteger]::Parse($q)
      if ($pv -gt $qv) { return 1 }
      if ($pv -lt $qv) { return -1 }
    } elseif ($pNum) { return -1 }          # numbers sort before words
    elseif ($qNum) { return 1 }
    else {
      $c = [string]::CompareOrdinal($p, $q)
      if ($c -gt 0) { return 1 }
      if ($c -lt 0) { return -1 }
    }
  }
  return 0
}

function Get-LocalVersion {
  if (Test-Path $VersionFile) { return (Get-Content $VersionFile -Raw).Trim() }
  return "unknown"
}

# --- one update at a time ----------------------------------------------------
# The lock is a file held open with no sharing: a second run cannot open it while the first
# lives, and a file left by a killed run opens fine (Windows released the handle with it).

$script:LockStream = $null
function Enter-Lock {
  try {
    $script:LockStream = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    return $true
  } catch {
    return $false
  }
}
function Exit-Lock {
  if ($script:LockStream) {
    $script:LockStream.Dispose()
    $script:LockStream = $null
    Remove-Item $LockPath -Force -ErrorAction SilentlyContinue
  }
}

# --- undoing what an interrupted or failed update moved ------------------------

function Restore-FromBackup([string]$Backup) {
  $ok = $true
  foreach ($entry in Get-ChildItem -LiteralPath $Backup -Force) {
    $target = Join-Path $AppDir $entry.Name
    try {
      if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
      Move-Item -LiteralPath $entry.FullName -Destination $target -Force
    } catch {
      $ok = $false
    }
  }
  return $ok
}

function Restore-Interrupted {
  if (-not (Test-Path $Journal)) { return $true }
  $backup = (Get-Content $Journal -Raw).Trim()
  if ($backup -and (Test-Path -LiteralPath $backup)) {
    Warn "A previous update was interrupted; restoring the previous version..."
    if (-not (Restore-FromBackup $backup)) {
      Fail "Could not restore everything; the files are in $backup"
      return $false
    }
    Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $Journal -Force -ErrorAction SilentlyContinue
  Get-ChildItem -Path $AppDir -Directory -Force -Filter ".update-new-*" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  Say "The previous version was restored." "Green"
  return $true
}

# --- unpacking (with a guard against entries that climb out of the folder) -----

function Expand-Release([string]$Zip, [string]$Destination) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $root = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
  $archive = [System.IO.Compression.ZipFile]::OpenRead($Zip)
  try {
    foreach ($entry in $archive.Entries) {
      $relative = $entry.FullName.Replace('/', '\')
      $full = [System.IO.Path]::GetFullPath((Join-Path $Destination $relative))
      if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "The package contains an entry outside its folder: $($entry.FullName)"
      }
      if ($relative.EndsWith('\')) {
        New-Item -ItemType Directory -Force -Path $full | Out-Null
      } else {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $full) | Out-Null
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $full, $true)
      }
    }
  } finally {
    $archive.Dispose()
  }
}

function Find-PackageRoot([string]$Base) {
  if (Test-Path (Join-Path $Base "downloader.py")) { return $Base }
  foreach ($dir in Get-ChildItem -LiteralPath $Base -Directory) {
    if (Test-Path (Join-Path $dir.FullName "downloader.py")) { return $dir.FullName }
  }
  return $null
}

# --- verifying a package before anything changes --------------------------------

function Get-PackageVersion([string]$Root) {
  $text = Get-Content (Join-Path $Root "ytdlp_app\_version.py") -Raw
  $m = [regex]::Match($text, '(?m)^__version__\s*=\s*["'']([^"'']*)["'']')
  if ($m.Success) { return $m.Groups[1].Value }
  return $null
}

function Test-Package([string]$Root, [string]$Tag, [string]$Current) {
  foreach ($file in $RequiredFiles) {
    if (-not (Test-Path (Join-Path $Root $file))) {
      Fail "The downloaded package is incomplete: $file is missing."
      return $false
    }
  }
  $version = Get-PackageVersion $Root
  if (-not $version -or ($version.TrimStart('v','V') -ne $Tag.TrimStart('v','V'))) {
    Fail "The package says it is version '$version', not the release $Tag."
    return $false
  }
  $versionFile = Join-Path $Root "app_version.txt"
  if ((Test-Path $versionFile) -and ((Get-Content $versionFile -Raw).Trim() -ne $Tag)) {
    Fail "app_version.txt in the package does not match the release $Tag."
    return $false
  }
  if ((Compare-Version $Tag $Current) -ne 1) {
    Fail "Release $Tag is not newer than the installed $Current; not installing it."
    return $false
  }
  $python = Join-Path $AppDir "runtime\python\python.exe"
  if (Test-Path $python) {
    Push-Location $Root
    try {
      $env:PYTHONDONTWRITEBYTECODE = "1"
      $env:PYTHONNOUSERSITE = "1"
      & $python -s -c "import sys; sys.path.insert(0, '.'); import ytdlp_app, ytdlp_app.app" 2>&1 | Out-Null
      $started = ($LASTEXITCODE -eq 0)
    } finally {
      Pop-Location
    }
    if (-not $started) {
      Fail "The new package does not start under the bundled Python; keeping the installed version."
      return $false
    }
  } else {
    Warn "The bundled Python is not installed yet; skipping the start-up check of the new package."
  }
  return $true
}

# --- the transaction --------------------------------------------------------------

function Install-Package([string]$Root, [string]$Tag) {
  $stamp = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $PID
  $backup  = Join-Path $AppDir ".update-backup-$stamp"
  $staging = Join-Path $AppDir ".update-new-$stamp"
  New-Item -ItemType Directory -Force -Path $backup, $staging | Out-Null
  # From here on a crash is recoverable: the journal says where the old files are.
  Set-Content -Path $Journal -Value $backup -Encoding UTF8 -NoNewline

  $abort = {
    param([string]$Reason)
    Fail $Reason
    Warn "Rolling back to the previous version..."
    if (-not (Restore-FromBackup $backup)) { Fail "Rollback was incomplete; the old files are in $backup" }
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $Journal -Force -ErrorAction SilentlyContinue
    if (-not (Get-ChildItem -LiteralPath $backup -Force -ErrorAction SilentlyContinue)) {
      Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
    }
  }

  try {
    # 1) Copy every new file next to its place. Nothing of the install changes yet.
    foreach ($item in $ReplaceItems) {
      $source = Join-Path $Root $item
      if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $staging $item) -Recurse -Force
      }
    }
  } catch {
    & $abort "Could not copy the new files: $($_.Exception.Message)"
    return $false
  }

  try {
    # 2) Swap: old -> backup, new -> place. Each step is a rename.
    foreach ($item in $ReplaceItems) {
      $new = Join-Path $staging $item
      if (-not (Test-Path -LiteralPath $new)) { continue }
      $current = Join-Path $AppDir $item
      if (Test-Path -LiteralPath $current) {
        Move-Item -LiteralPath $current -Destination (Join-Path $backup $item) -Force
      }
      Move-Item -LiteralPath $new -Destination $current -Force
    }
    # 3) The version last, so it only ever names what is really installed.
    if (Test-Path $VersionFile) {
      Move-Item -LiteralPath $VersionFile -Destination (Join-Path $backup "app_version.txt") -Force
    }
    $temp = "$VersionFile.new"
    Set-Content -Path $temp -Value $Tag -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $VersionFile -Force
  } catch {
    & $abort "Could not install the new files: $($_.Exception.Message)"
    return $false
  }

  # 4) The installed copy must start too.
  $python = Join-Path $AppDir "runtime\python\python.exe"
  if (Test-Path $python) {
    $env:PYTHONNOUSERSITE = "1"
    & $python -s -c "import ytdlp_app, ytdlp_app.app" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      & $abort "The installed package does not start."
      return $false
    }
  }

  # Commit: the journal goes away, the old version becomes .previous-version.
  Remove-Item $Journal -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $PreviousDir -Recurse -Force -ErrorAction SilentlyContinue
  try { Move-Item -LiteralPath $backup -Destination $PreviousDir -Force }
  catch { Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue }
  Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
  return $true
}

function Install-Release($Release, [string]$Tag, [string]$Current) {
  $asset = $Release.assets | Where-Object { $_.name -eq $AssetName } | Select-Object -First 1
  if (-not $asset) {
    Fail "Release $Tag has no $AssetName asset; nothing was changed."
    return $false
  }
  $shaAsset = $Release.assets | Where-Object { $_.name -eq "$AssetName.sha256" } | Select-Object -First 1

  # A private work folder inside this one: same volume (renames stay atomic), unique per run.
  $work = Join-Path $AppDir (".update-work-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
  New-Item -ItemType Directory -Force -Path $work | Out-Null
  try {
    $zip = Join-Path $work "release.zip"
    $unpacked = Join-Path $work "unpacked"
    New-Item -ItemType Directory -Force -Path $unpacked | Out-Null

    Say "Downloading $Tag..." "Cyan"
    try {
      Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -UseBasicParsing -TimeoutSec 600
    } catch {
      Fail "The download failed; nothing was changed. ($($_.Exception.Message))"
      return $false
    }

    # The checksum the release publishes, when it publishes one. Without it the package is
    # only checked structurally; the runtime components are pinned separately.
    if ($shaAsset) {
      try {
        $expected = ((Invoke-WebRequest -Uri $shaAsset.browser_download_url -UseBasicParsing -TimeoutSec 30).Content -split '\s+')[0].Trim().ToLower()
      } catch {
        $expected = ""
      }
      $actual = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLower()
      if (-not $expected -or $expected -ne $actual) {
        Fail "The download does not match the published SHA-256 checksum; it was discarded."
        return $false
      }
      Say "Checksum verified." "Green"
    } else {
      Say "This release publishes no checksum; the package is verified structurally only." "Yellow"
    }

    try {
      Expand-Release $zip $unpacked
    } catch {
      Fail "The package could not be unpacked; nothing was changed. ($($_.Exception.Message))"
      return $false
    }
    $root = Find-PackageRoot $unpacked
    if (-not $root) {
      Fail "The package has an unexpected layout (no downloader.py); nothing was changed."
      return $false
    }
    if (-not (Test-Package $root $Tag $Current)) { return $false }

    Say "Installing..." "Yellow"
    if (-not (Install-Package $root $Tag)) { return $false }
    Say "Updated to $Tag. The previous version is kept in .previous-version\" "Green"
    return $true
  } finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
  }
}

# --- main ---------------------------------------------------------------------------

$exitCode = 0
if (-not (Enter-Lock)) {
  if (-not $Quiet) { Fail "Another update is already running (lock: $LockPath)."; exit 1 }
  exit 0
}
try {
  if (-not (Restore-Interrupted)) {
    if (-not $Quiet) { exit 1 } else { exit 0 }
  }

  $local = Get-LocalVersion
  if (-not (ConvertTo-Version $local)) {
    if (-not $Quiet) { Fail "Cannot read the installed version (app_version.txt says '$local')."; exit 1 }
    exit 0
  }

  # Offline (or GitHub unreachable) is normal and must never get in the way of starting.
  try {
    $release = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "User-Agent" = "YtDlpDownloader-Updater" } -TimeoutSec 15
  } catch {
    Say "Update check could not run (internet/API). Continuing..." "Yellow"
    exit 0
  }
  $tag = [string]$release.tag_name
  if ([string]::IsNullOrWhiteSpace($tag) -or -not (ConvertTo-Version $tag)) { exit 0 }

  if ((Compare-Version $tag $local) -ne 1) {
    Say "Already up to date: $local" "Green"
    exit 0
  }
  if ($CheckOnly) {
    Write-Host "Update available: $local -> $tag" -ForegroundColor Yellow
    exit 0
  }

  Say "New version found: $local -> $tag" "Cyan"
  if (-not (Install-Release $release $tag $local)) {
    if ($Quiet) { Warn "The update was not installed; continuing with $local."; exit 0 }
    exit 1
  }
  exit 0
} finally {
  Exit-Lock
}
