# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

From the 2026-10-02 review (`degerlendirme-raporlari/2026-10-02/`, local). The roadmap is in `docs/superpowers/plans/2026-10-02-review-roadmap.md`.

### Fixed — archive evidence
- **The archive check counted a deleted video as present** when its folder, info JSON or thumbnail was left behind, and an MP3 of the same video hid a missing MP4 record (B02). Only a finished media file of the archive's mode is evidence now: folders, side files, `.part`/`.temp` files, unmerged format streams (`.f137.mp4`) and another mode's file are not. A record whose recorded file is gone is *missing* (repairable); an old record without a recorded path and without a matching media file stays *cannot be checked* and is never repaired on a guess. The archive check and the download result use the same rule (`evidence.py`).
- **Giving the same single video again said "already in the archive" although its file had been deleted** (B04). The video id is taken from the URL and its recorded (or moved) file is checked: a deleted one is reported as missing with a pointer to the archive tools, and an id yt-dlp left unarchived at exit code 0 is a failure. Records whose file cannot be checked (no recorded path, or another site's single item, or a channel's `/live`) are shown on their own line instead of as "already in the archive".
- **Moving the program folder made every recorded download look missing** (B05). Files inside the program folder are now recorded in the manifest relative to it (the manifest gains a `# ytdlp_app download manifest v2` header); files in an outside download folder keep their absolute path. Existing manifests are read as before and new lines may be appended to them.

### Fixed — installing and updating
- **A rollback that failed threw away its own way back** (B01). When putting the old files back failed too, both updaters deleted the update journal, so the next run had nothing to recover and the app was left half replaced. The journal and the backup now stay until every old file is back; running the updater again finishes the restore (restored files leave the backup, so a retry only moves what is still missing). Files a release added are recorded in the journal before they appear and removed by a rollback. A journal written by 0.4.0 is still recovered. While the journal exists, `run.sh` and `Run.bat` do not start the app: they say where the previous version is and how to restore it (`run.sh` still never runs the updater itself).
- **`bash update.sh` reported a failed yt-dlp update as a success** (B10). It now checks the result, says the installed yt-dlp is unchanged and exits with 1. The `.venv` upgrade keeps the app's extras (`yt-dlp[default,curl-cffi]`; a bare `yt-dlp` upgrade dropped curl-cffi, which YouTube subtitles need). `python -m ytdlp_app.portable update-ytdlp` fails when pip fails; the weekly upgrade at launch still carries on with the installed copy.
- **macOS: the Python Homebrew had just installed was not used** (B11). `install.sh` checked only `python3`, which `brew install python@3.12` does not change. It now takes the first Python 3.11+ among `python3.14` … `python3.11` and `python3` (compared by Python, so 4.0 passes), and otherwise `$(brew --prefix python@3.12)/bin/python3.12` by path; the `.venv` is made with that interpreter. Checked with stand-ins following Homebrew's layout, not on a real Mac.
- **`update.ps1` started by hand updated without asking** (B12), although the README said it asks. It now shows the new version and asks; anything but *y*, or no answer, keeps the installed version. `-Quiet` (what `Run.bat` runs) and `-CheckOnly` are unchanged.
- **`Run.bat` always waited for a key** (B13), so `Run.bat audit ...` blocked scripts. It now waits only when started without arguments and returns the app's exit code explicitly.
- `update.ps1` and `Run.bat` are now tested under the real Windows PowerShell 5.1 and cmd.exe (`tests/windows.py`: on Windows, or from WSL through its interop). The Windows CI job requires them (`YTDLP_REQUIRE_WINDOWS_SCRIPTS`).

### Fixed — the app
- **The exit code forgot an earlier failure** (B16). A failed download followed by an empty URL, or by a later clean download and *exit*, ended the session with 0. The exit code now describes the whole session: 0 when everything went well, 1 when any download failed or left items undone, 130 when cancelled.
- **Menus crashed on input such as `²`** (B15), which `str.isdigit()` accepts and `int()` does not, and on numbers too long to convert; at the first language question that stopped the app from starting. Such input is now an ordinary invalid choice. A config with `"retries": "²"` no longer crashes the settings load either.
- **Panels overflowed with CJK titles and emoji** (B14): widths counted characters, not screen columns (a 40-column CJK panel was 76 columns wide). Widths are now counted in cells (wide characters 2, combining marks 0) with the standard library, wrapping and title shortening never split a mark from its letter, and below 20 columns panels and menus are printed as plain lines.
- **The settings menu saved a proxy or speed limit the next start would throw away** (B09). The menu now applies the config loader's rules (one shared check per field), says why a value is unusable and asks again. The download entry no longer promises "retries", which it never asked for.
- **WAV failed with the default cover setting** (B03): yt-dlp cannot embed a cover in WAV, so the item was never archived and every retry failed. With WAV the cover is saved as a `.jpg` beside the file, and the app says so. Every audio format is now downloaded with the default cover settings in the engine contract.
- **The minimum yt-dlp did not have the options the app passes** (B06). 2025.03.21 answers `no such option: --js-runtimes`; the minimum is now 2025.11.12 (pyproject and the portable runtime ask for the same string, so the portable runtime upgrades once). The option is spelled `--js-runtimes`. An older yt-dlp on the PATH is reported before a download starts. The engine contract passed on 2025.11.12.

## [0.4.0] - 2026-09-30

Pre-release hardening, from the 2026-09-30 application review (`degerlendirme-raporlari/`). Where a fix concerns what yt-dlp or ffmpeg does with a file or the download archive, it is checked against the real yt-dlp and ffmpeg on generated media (offline), and the regression tests fail when the fix is taken out.

### Upgrading from 0.3.x
Nothing has to be done by hand. Saved default output templates are migrated (a copy of the old `config.json` is kept as `config.json.v1.bak` on the first save), existing archives keep working, and files downloaded earlier keep their names. Items recorded as done by older versions in error are not repaired automatically: run `downloader.py audit` to see which can be proven missing. `run.sh` does not update by itself; use `bash update.sh`.

### Fixed — data integrity
- **Two videos with the same title shared one file.** The default templates were title-only, so the second video found the first one's file, was skipped as "already downloaded" and still written to the download archive. Every default template now carries the video id (`%(title).150B [%(id)s].%(ext)s`; playlists keep the position as a prefix, for ordering only). Saved settings that are still exactly the old defaults are migrated (see *config_version* below); a template you wrote yourself is left alone, and reported when it lacks `%(id)s`.
- **A failed conversion, merge or embedding step was recorded as done.** `--ignore-errors` makes yt-dlp count a failed post-processing step as success and archive the item, and the compatibility profile's second stage then skipped it because of that record. It is replaced by `--no-abort-on-error` (a failed *download* still moves on to the next playlist item; a failed *post-processing step* leaves the item unarchived). Stage 2 now really reprocesses what stage 1 could not finish, and a clean stage 2 cannot hide an unresolved stage 1.
- **A missing HLS/DASH fragment produced a video with a hole and a success.** `--abort-on-unavailable-fragments` is now passed in every mode, so after the retries the item fails and is retried next run.
- **A subtitle or thumbnail that exists but could not be saved was archived as complete.** In archive mode the new `ArchiveComplete` plugin stops such an item before the video is downloaded, so it is not archived and the next run tries it again. A video that has no subtitles or thumbnail is complete without them, and a 404 on the best thumbnail does not matter while a lesser one arrived.
- **The compatibility MP4 profile did not guarantee its codecs.** `--recode-video mp4` goes by the container, so an `.mp4` holding AV1 was reported "already in the target format" and kept. The new `Mp4Compat` plugin probes the result with ffprobe: H.264 + AAC in MP4 is left untouched (no re-encode), a wrong audio codec is converted with the video copied, everything else is converted, and the converted file is probed again and must satisfy the contract or the item fails.
- **The MKV choices did not always produce MKV.** `--merge-output-format mkv` only acts when streams are merged, so a single combined MP4 stayed MP4. Quality/MKV and archive mode now also remux (`--remux-video mkv`, a stream copy); metadata, chapters, thumbnail and subtitles are kept.
- **The archive file name could climb out of `archives/`** (`?list=/../../x`), and two channels' `/videos` tabs shared one archive named `videos`. Names are built from a sanitised id (a token that had to change carries a hash so different ids never collide), checked to stay inside the archives folder, and a channel is keyed by its real channel id in every mode. An archive kept under the channel's handle by older versions is still used until an id-keyed one exists.
- **`/@handle/live`, `/live/<id>` and look-alike paths (`/clip/…`, `/channelfoo`) were classified as playlists or channels**, and another site's URL could be turned into a YouTube watch URL. Classification is now by path segment and YouTube host only; other sites are a single item.

### Fixed — processes
- **Cancelling or failing while a download ran left processes behind.** `run_cmd_tee` returned 130 on Ctrl+C without stopping the child, and never stopped ffmpeg (a grandchild) on any path. Every command now runs in its own process group and is stopped, reaped and its pipes closed on every way out (Ctrl+C, ban, a full disk during a log write, a broken console, any exception): SIGINT, then SIGTERM, then SIGKILL, with a final sweep of the group. Windows uses `CTRL_BREAK` then `taskkill /T /F`; that branch could not be run here and is unit-tested only.
- **A hung metadata call froze the app.** Listings and skip probes now have time limits on the whole request (30 and 3 minutes) and a 30 s network read time-out; downloads have no overall limit. The speed test has a hard 8 s budget (a blocked read used to be able to exceed it).
- **The skip report went on after Ctrl+C or a ban** (it turned the cancellation into explanatory text and probed the next item). It now stops at once.

### Fixed — updating
- **A failed update could delete the working package** (`update.sh` removed `ytdlp_app` before checking the new one; `update.ps1` deleted then copied). Both updaters are now transactions: the package is unpacked in a private temporary folder, verified without touching the install (files, version equals the tag and is newer, imports), copied next to its place, swapped by renames with the old files kept in a backup, `app_version.txt` written last, everything rolled back on any failure, and an update killed half way undone at the next start. A lock keeps two updates from running at once. Versions are compared as semantic versions, so `0.10.0` is newer than `0.9.0` and a downgrade is never installed. `unzip` is no longer required (the bundled Python, `python3` or `bsdtar` work) and its absence is reported before anything is downloaded.
- **Runtime components were replaced by delete-then-move.** They are now renamed aside and swapped in (`portable.py`, `install.sh`, `install.ps1`); an interrupted swap is recovered on the next launch.
- `run.sh`, `install.sh` and `update.sh` are executable (`100755`); the README says `bash run.sh` because a ZIP download loses the bit.

### Fixed — settings, files and privacy
- **Bad hand edits crashed the app** (`"audio": null`, `"retries": 5`, `"inf"` waits…). Every section and field is type- and range-checked; a bad one is reported by name and replaced by its default. NaN, infinity, negative numbers, unknown audio formats, unusable proxies and templates that could leave the download folder are rejected. Retries accept a whole number or `infinite`.
- **A failed save could truncate `config.json`, and the settings menu kept edits that were never saved.** Config and runtime state are written atomically (temporary file + rename); a failed save puts the running settings back to what is on disk; an unreadable config is kept as `config.json.corrupt-<time>` before defaults are used.
- **The listing, the skip probes and the speed test ignored the proxy.** All yt-dlp calls now share one network context (proxy, JS runtime, time-out, pacing).
- **A user's own yt-dlp config could change what a download does.** Every call passes `--ignore-config`; the new setting `allow_external_config` (off by default) opts back in.
- **Proxy credentials appeared in the console, the settings screen and the logs.** They are masked everywhere something is shown or logged; only the arguments that really run keep them.
- **The estimate under-counted audio conversion space** (it added the largest *output*, which is smaller than the source for a low-bit-rate MP3) and **treated "unlimited" as 2160p**. Audio now adds the largest source stream; "unlimited" has its own 8K row.
- **The archive wait was labelled "at least" but was the average.** Both the minimum and the expected time are shown.

### Added
- **Archive check and repair** (`a` at the URL prompt, or `downloader.py audit [--repair] [--forget ID…] [--forget-all] --archive NAME [--apply]`): compares every archive with the files on disk using the new manifest (`archives/<name>.files.tsv`, written for every finished item) or `[id]` in a file or folder name. Records whose file is proven gone can be removed so the next run downloads them again; records that cannot be checked are reported, never repaired on a guess. Every change is a preview until `--apply` (or a confirmation), makes a backup in `archives/backups/` first and is atomic. Older archives are not "repaired" by the fixes above; this is how they are checked.
- **Results judged by what was left behind** (`outcome.py`): completed, already present, failed, missing (recorded but the file is gone), banned and cancelled are counted, and the success, *finished with problems* and *nothing was downloaded* messages come from that model instead of a single exit code. After a partly failed run, exiting returns exit code 1. `planning.py` (folders, templates, archive names) is split out of `session.py`, which now takes the `UI` protocol.
- **Settings:** `download.allow_external_config`, `download.speed_test` (switch the speed test off), `config_version` (schema 2; an older file is migrated in memory, a copy is kept as `config.json.v1.bak` on the first save).
- **Terminal behaviour:** colour only on a terminal (`NO_COLOR`, `FORCE_COLOR`, `TERM=dumb` respected), panels and menus wrap to the terminal width, Turkish text uses the natural characters (output that a legacy console cannot encode is replaced instead of raising), and the audio format you chose is named in the mode menu, summary and messages instead of "MP3".
- **What changing the target means** is now stated: the archive records ids, not folders, resolutions or formats, so items already in it are skipped after such a change; the README and a note after a run say how to download them again.
- `run.sh` and `Run.bat` forward their arguments to the app. Update behaviour stays as it was and is now documented per platform: `Run.bat` checks quietly at launch (`YTDLP_NO_AUTO_UPDATE=1` skips it), `run.sh` does not check; on Linux/macOS updating is `bash update.sh` on request. The release now also publishes `YtDlpDownloader-Portable.zip.sha256`, which the updaters verify when present.
- The engine tests (`tests/test_engine_contract.py`) run the real yt-dlp and ffmpeg on generated media through `--load-info-json` and local files, offline; they skip themselves without ffmpeg. `tests/test_update_sh.py` runs the real `update.sh` against a disposable install with file:// releases.

### Changed
- `--ignore-errors` is gone from the regular modes (see above); the default retry policy is otherwise unchanged.
- MP3 archive files keep the `mp3` name whichever audio format is chosen (documented).
- `Run.bat` is not replaced by the auto-update (cmd.exe reads a batch file while it runs); copy it by hand when a release changes it.
- Not verified in the environment this was developed in: anything on **Windows** (the PowerShell updater and installer, the Windows process-tree stop, `Run.bat`) and **macOS**, and a real YouTube download.

**Earlier changes that were unreleased before this hardening pass (disk-space estimate, archive mode, portable runtime):**


### Added
- **Size estimate, disk check and resolution limit.** Before a playlist or channel download (MP4, MP3 and archive) the app reads the listing once and shows a high-side size estimate for 1080p, 1440p and 2160p from each video's duration and a typical bit rate (no per-video request), checks free disk space (*Continue anyway / Cancel*, never blocked) and, using a short speed test against `speed.cloudflare.com`, estimates the download time. Archive mode also shows the minimum time the waits between videos take. A resolution limit (1080p, 1440p, 2160p or unlimited) is asked after the estimate for MP4 and archive downloads, also for single videos, and can be saved as the new default; it is applied to every video format selector, including the fallback. The compatibility MP4 profile stays at 1080p. New settings `settings.video.max_height` (default `null`) and `settings.archive.max_height` (default `1080`), editable from the settings menu.
- **Fully portable on Windows and Linux.** The first launch downloads a relocatable Python, ffmpeg and Deno into `runtime/` inside the program folder and installs yt-dlp into that Python. Nothing is installed system-wide, no administrator rights or sudo are needed, and the folder keeps working after being moved or copied to another machine or a USB stick.
  - Every download is verified against the SHA-256 pinned in the new `runtime.lock`; a changed pin replaces just that component on the next launch.
  - yt-dlp is upgraded automatically once a week at launch (failures are non-fatal, so offline launches work); `python -m ytdlp_app.portable update-ytdlp` upgrades it on demand and `status` shows what is installed.
  - yt-dlp's and Deno's caches are kept in `cache/` instead of the user profile.
  - New installs download into `downloads/` next to the program, and any folder inside the program folder is stored relative in `config.json`, so it follows the folder.
- **Archive mode** — a third option next to MP4 and MP3, for preserving a channel that may be deleted. For every video it keeps the video (up to 1080p by default, merged into MKV with chapters and metadata), the description, the info JSON, the thumbnail, and uploaded plus auto-generated Turkish/English subtitles converted to SRT, each video in its own folder under `<Videos>/yt-dlp/<channel>/`.
  - Only subtitles that exist on YouTube are kept. YouTube machine-translates every auto-generated subtitle on request, and `--sub-langs tr.*` on an English video would otherwise also fetch that Turkish translation; a bundled yt-dlp plugin (`ytdlp_app/plugins`) drops those entries before anything is downloaded. These translations were also the first requests YouTube rate limited.
  - The original auto-generated subtitle is fetched once per language. YouTube lists it twice, as `en` and `en-orig` with the same URL, which cost an extra subtitle request per video; only `en` is kept.
  - A channel URL (`/@handle`, `/channel/UC…`, `/c/…`, `/user/…`, or one of its tabs) is archived whole: yt-dlp's nested Videos/Shorts/Live playlists are all downloaded, and the playlist-or-video question is skipped.
  - The download archive is `archives/channel_<channel_id>_archive.txt`, keyed by the real channel id (read from the flat listing that also feeds the size estimate), so every URL form of a channel resumes the same archive.
  - Paced to stay under YouTube's limits: `--sleep-requests 1.5`, `--sleep-interval 15`, `--max-sleep-interval 45`, `--sleep-subtitles 5`, and 10 retries instead of infinite. The waits are editable from the settings menu (*Archive mode waits*) and stored under `settings.archive` in `config.json`; the speed limit and proxy still apply.
  - **Ban guard**: when yt-dlp reports HTTP 429 or YouTube's "Sign in to confirm you're not a bot", the download is stopped at once, the event is logged as `[BAN-GUARD]`, and the user is told to wait a few hours and enter the same URL again to resume. The same check covers the channel listing.
  - Archive mode lists a channel or playlist once (a single video sends no listing request), sends no skip-probe requests, and does not pass `--ignore-errors`, so an item whose subtitles or thumbnail failed is retried on the next run instead of being recorded as done.
- **In-app settings menu**: type `s` at the URL prompt (or pick *Settings* after a download) to change the interface language, the download folders, the proxy, the speed limit, the parallel fragment count, the audio format and quality, and the subtitle options. Every change is written to `config.json` immediately, and a language switch applies without a restart.
- Advanced settings are now honored at runtime. They live under the `"settings"` key of `config.json`; a config written before this change has no such key and keeps the previous defaults exactly, so nothing changes until you opt in. See `settings.example.json` for the full shape.
- The URL prompt validates its input and asks again instead of passing anything straight to yt-dlp — most concretely, a URL starting with `-` is no longer read as a command-line flag.
- Startup banner showing the application name and version.
- Test coverage for `CommandBuilder`, the skip-reason prober, and the settings menu, none of which had any.

### Fixed
- A bare channel URL is now listed as its videos: yt-dlp returns the Videos, Shorts and Live tabs as nested playlists, and the flat listing used to count the tabs instead of the videos (which also made the MP4 skip report wrong for channels).
- **YouTube subtitles could not be downloaded at all.** yt-dlp requests every YouTube subtitle with browser impersonation, which needs the optional `curl_cffi` package that was never installed; YouTube answered those requests with HTTP 429. yt-dlp is now installed as `yt-dlp[default,curl-cffi]`, existing portable installs pick it up on their next launch, and archive mode warns up front when it is missing instead of reporting a ban.
- **yt-dlp was reported missing on machines without a global copy.** The launchers start the `.venv` Python directly, which does not put `.venv`'s `yt-dlp` on PATH, while the app looked yt-dlp up on PATH. yt-dlp now runs as `python -m yt_dlp` from the app's own interpreter.
- **The skip report was entirely in English**, even in Turkish, despite the translations for it already existing. All fifteen messages now go through the translation layer, as do the command banner and the success, cancellation, and failure lines.
- `analyze_log_for_error` now recognizes copyright takedowns, which it previously reported with the generic "video unavailable" message.
- **`./run.sh` failed with "Permission denied" in a fresh clone.** `run.sh`, `install.sh` and `update.sh` were committed without the executable bit; they are now executable.

### Changed
- `install.ps1` / `install.sh` no longer use winget or apt/dnf/pacman on Windows and Linux; they set up the portable runtime instead. macOS keeps the Homebrew + `.venv` installation. The updaters now also preserve `runtime/`, `cache/` and `downloads/`.
- Existing installs keep their configured download folders. Their `.venv` and winget-installed Python/ffmpeg/Deno are no longer used and can be removed.
- `AppSettings` gains an `archive` section and `OutputSettings` an `archive_template`. Configs without them load the defaults, so no migration is needed. MP4 and MP3 commands are unchanged.
- `AppSettings` drops `use_deno`, `default_mode`, `default_mp4_profile`, and `language`: the first three are detected or asked for interactively, and the language lives at the top level of `config.json` because it must resolve before the settings load.
- `DownloadPlan` drops four argument fields that were built every cycle and never read; its profile fields are typed as the enums they are compared against.
- Removed `is_supported_url`, which computed a hostname and then unconditionally returned `True`, and eleven locale keys describing a status UI that was never built.
- yt-dlp 2025.03.21 or newer is now required, for the `--plugin-dirs` behavior archive mode's subtitle plugin relies on.

## [0.3.1] - 2026-07-28

Patch release that repairs the broken v0.3.0 artifact. **Anyone running v0.3.0 should upgrade** — that release shipped an unusable build.

### Fixed
- **v0.3.0 shipped untranslated**: the release tag predates the i18n repair commit, so the published ZIP printed raw translation keys (`prompt_url`, `prompt_mode`, …) instead of text. This release is the first one containing the fix.
- **Auto-update never worked**: `update.ps1` looked for a release asset named `YtDlpDownloader-Portable.zip` while CI published `YtDlpDownloader-Portable-<tag>.zip`, so every update check reported the asset as missing. CI now publishes the stable name the updater expects.
- **Update check compared mismatched formats**: `app_version.txt` stored `0.3.0` while it is compared against the GitHub tag `v0.3.0`, so the app considered itself outdated on every launch. The file now stores the tag form.
- **`app_version.txt` was missing from the portable ZIP**, leaving fresh portable installs with no local version to compare.
- **`update.sh` read the version from `pyproject.toml`**, which no longer carries a literal version; it now reads `app_version.txt`. It also copied the package *into* the existing `ytdlp_app/` directory (creating `ytdlp_app/ytdlp_app`) and could abort silently under `set -e` when an optional file was absent.

### Changed
- **Single-source versioning**: `ytdlp_app.__version__` is now the only place the version is written. `pyproject.toml` reads it dynamically, and `scripts/check_version.py` (wired into CI) fails the build if `app_version.txt` or the release tag disagrees.
- The portable ZIP now includes `run.sh`, `install.sh`, `update.sh`, and `app_version.txt`, so the documented Linux/macOS workflow actually works from a release download.
- Corrected metadata and docs that claimed Windows-only support and Python 3.10+; the app requires **Python 3.11+** (it uses `StrEnum`) and is tested on Linux, Windows, and macOS.

## [0.3.0] - 2026-01-11

### Added
- **Modern console UI**: boxed panels and styled menus.
- **Full localization (i18n)**: hardcoded strings moved behind a translation layer (English and Turkish).
- **CommandBuilder pattern**: a dedicated builder for assembling yt-dlp command lines.

### Changed
- **Architecture refactor**: the monolithic `run()` function became the modular `InteractiveSession` class in `session.py`.
- **Cleaner code**: magic numbers in menu choices replaced with readable enums.
- **Performance**: cached the system dependency checks (ffmpeg, yt-dlp, deno).

> Note: the published v0.3.0 artifact is broken — see [0.3.1].

## [0.2.0] - 2026-01-11

### Added

#### Package Management
- **pyproject.toml**: PEP 621 compliant modern Python package configuration
  - Project metadata (name, version, description, license)
  - Pinned dependencies (`yt-dlp>=2024.1.0`)
  - Developer dependencies (pytest, mypy, ruff, pytest-cov)
  - Tool configurations for pytest, mypy, ruff, and coverage
  - Console entry point (`ytdlp-downloader` command)
- **py.typed**: PEP 561 compliance marker for type checking

#### CI/CD Pipeline
- **GitHub Actions workflow** (`.github/workflows/ci.yml`)
  - Lint job: Ruff linter and mypy type checking
  - Test job: Matrix testing across 3 OS x 4 Python versions
  - Build job: Distributable package creation
  - Release job: Automatic GitHub release on tags
  - Supported platforms: Ubuntu, Windows, macOS
  - Python versions: 3.11, 3.12, 3.13

#### New Modules
- **exceptions.py**: Custom exception hierarchy for error handling
  - `YtDlpWrapperError` (base)
  - `ConfigurationError`, `CommandExecutionError`, `NetworkError`
  - `ValidationError`, `PlaylistError`, `DownloadError`
- **validators.py**: URL and path validation utilities
  - `is_valid_url()`, `is_youtube_url()`, `validate_url()`
  - `validate_path_string()` with shell injection protection
- **settings.py**: Advanced configurable settings system
  - `DownloadSettings`: concurrent_fragments, rate_limit, proxy, retries
  - `AudioSettings`: audio_quality, audio_format, embed options
  - `VideoSettings`: embed_thumbnail, subtitles, metadata
  - `OutputSettings`: Customizable output templates
  - `AppSettings`: Main settings class with load/save
- **i18n.py**: Internationalization support
  - `t(key, **kwargs)`: Translation function
  - `set_language()`, `get_language()`: Language management
  - `get_available_languages()`: List available languages

#### Localization
- **English translations** (`locales/en.json`): 70+ translation keys
- **Turkish translations** (`locales/tr.json`): 70+ translation keys

#### Cross-Platform Support
- **install.sh**: Unix installation script
  - Supports apt, dnf, pacman, brew package managers
  - Automatic OS detection and Python 3.11+ installation
- **run.sh**: Cross-platform launcher script
- **update.sh**: Cross-platform updater script with config backup

#### Test Infrastructure
- ~70 unit tests across 8 test files
- Shared fixtures in `conftest.py`
- Tests for: models, config, playlist, validators, exceptions, settings, i18n

#### Documentation
- Comprehensive docstrings for all public functions (Google-style)
- Package documentation in `ytdlp_app/__init__.py`
- Example settings file (`settings.example.json`)

### Changed
- Updated `__init__.py` with version number and extended `__all__` list
- Improved type hints in `config.py` (`dict` -> `dict[str, Any]`)

### Removed
- Removed stale `__pycache__/*.pyc` files from tests directory

## [0.1.0] - 2025-12-14

### Added
- Initial release
- MP4/MP3 download modes
- Playlist and single video support
- Quality profiles (Compatibility, Quality)
- Download archives to prevent duplicates
- Colorized console output
- Skip reason reporting for playlist items
- Session continuity for multiple downloads
- Auto-update from GitHub releases
- One-click Windows setup via winget

---

# Değişiklik Günlüğü (Türkçe)

## [Yayınlanmadı]

### Eklenenler
- **Windows ve Linux'ta tamamen taşınabilir.** İlk açılış, taşınabilir bir Python, ffmpeg ve Deno'yu program klasöründeki `runtime/` içine indirir ve yt-dlp'yi o Python'a kurar. Sisteme hiçbir şey kurulmaz, yönetici izni veya sudo gerekmez; klasör başka bir yere, başka bir bilgisayara ya da USB belleğe taşındıktan sonra da çalışır.
  - Her indirme yeni `runtime.lock` dosyasında sabitlenmiş SHA-256 ile doğrulanır; bir sürüm değişirse sonraki açılışta yalnızca o bileşen yenilenir.
  - yt-dlp açılışta haftada bir otomatik güncellenir (başarısızlık engel değildir, internetsiz açılış çalışır); `python -m ytdlp_app.portable update-ytdlp` isteğe bağlı günceller, `status` neyin kurulu olduğunu gösterir.
  - yt-dlp ve Deno önbellekleri kullanıcı profili yerine `cache/` içinde tutulur.
  - Yeni kurulumlar programın yanındaki `downloads/` klasörüne indirir; program klasörünün içindeki her klasör `config.json`'a göreli yazılır, böylece klasörle birlikte taşınır.
- **Arşiv modu** — silinme riski olan bir kanalı korumak için MP4 ve MP3'ün yanında üçüncü seçenek. Her video için videoyu (1080p'ye kadar, bölümler ve metadata gömülü MKV), açıklamayı, info JSON'u, kapak resmini ve Türkçe/İngilizce yüklenmiş + otomatik altyazıları (SRT'ye dönüştürülmüş) saklar; her video `<Videos>/yt-dlp/<kanal>/` altında kendi klasöründedir.
  - Yalnızca YouTube'da gerçekten var olan altyazılar saklanır. YouTube her otomatik altyazıyı istek üzerine makineyle çevirir; `--sub-langs tr.*` İngilizce bir videoda bu Türkçe çeviriyi de indirirdi. Programla gelen bir yt-dlp eklentisi (`ytdlp_app/plugins`) bu girdileri indirme başlamadan çıkarır. YouTube'un ilk hız sınırına takılan istekler de bu çevirilerdi.
  - Orijinal otomatik altyazı her dil için bir kez indirilir. YouTube onu aynı adresle iki kez (`en` ve `en-orig`) listeliyordu; bu, video başına fazladan bir altyazı isteği demekti. Yalnızca `en` saklanır.
  - Kanal URL'si (`/@handle`, `/channel/UC…`, `/c/…`, `/user/…` ya da sekmelerinden biri) bütünüyle arşivlenir: yt-dlp'nin iç içe Videos/Shorts/Live playlist'lerinin hepsi indirilir ve "tüm liste mi bu video mu" sorusu atlanır.
  - İndirme arşivi `archives/channel_<channel_id>_archive.txt` dosyasıdır ve gerçek kanal kimliğiyle adlandırılır (tek bir düz istekle öğrenilir); böylece bir kanalın her URL biçimi aynı arşivden devam eder.
  - YouTube sınırlarının altında kalacak tempo: `--sleep-requests 1.5`, `--sleep-interval 15`, `--max-sleep-interval 45`, `--sleep-subtitles 5` ve sonsuz yerine 10 deneme. Bekleme süreleri ayarlar menüsünden (*Arsiv modu bekleme sureleri*) değiştirilebilir ve `config.json` içinde `settings.archive` altında saklanır; hız sınırı ve proxy bu modda da geçerlidir.
  - **Ban koruması**: yt-dlp HTTP 429 ya da YouTube'un "Sign in to confirm you're not a bot" mesajını bildirdiğinde indirme hemen durdurulur, olay log'a `[BAN-GUARD]` olarak yazılır ve kullanıcıya birkaç saat bekleyip aynı URL'yi tekrar vermesi, indirmenin kaldığı yerden devam edeceği söylenir. Aynı kontrol kanal kimliği sorgusunu da kapsar.
  - Arşiv modu playlist listeleme ya da atlama yoklaması isteği göndermez ve `--ignore-errors` kullanmaz; altyazısı veya kapak resmi başarısız olan bir öğe tamamlanmış sayılmaz, sonraki çalıştırmada yeniden denenir.
- **Uygulama içi ayarlar menüsü**: URL isteminde `s` yazarak (veya indirme sonrası *Ayarlar* seçeneğiyle) arayüz dilini, indirme klasörlerini, vekil sunucuyu, hız sınırını, paralel parça sayısını, ses formatı ve kalitesini, altyazı seçeneklerini değiştirin. Her değişiklik anında `config.json` dosyasına yazılır ve dil değişimi yeniden başlatma gerektirmez.
- Gelişmiş ayarlar artık çalışma zamanında dikkate alınıyor. `config.json` içindeki `"settings"` anahtarı altında tutuluyorlar; bu değişiklikten önce yazılmış bir yapılandırmada bu anahtar yoktur ve önceki varsayılanlar birebir korunur, yani siz istemeden hiçbir şey değişmez. Tam şema için `settings.example.json` dosyasına bakın.
- URL istemi girdiyi doğruluyor ve her şeyi doğrudan yt-dlp'ye geçirmek yerine yeniden soruyor — en somut olarak, `-` ile başlayan bir adres artık komut satırı bayrağı sanılmıyor.
- Uygulama adını ve sürümünü gösteren açılış paneli.
- `CommandBuilder`, atlama nedeni yoklayıcısı ve ayarlar menüsü için testler; hiçbirinin testi yoktu.

### Düzeltilenler
- **YouTube altyazıları hiç indirilemiyordu.** yt-dlp her YouTube altyazısını tarayıcı taklidiyle ister; bunun için gereken isteğe bağlı `curl_cffi` paketi hiç kurulmuyordu ve YouTube bu isteklere HTTP 429 dönüyordu. yt-dlp artık `yt-dlp[default,curl-cffi]` olarak kuruluyor, mevcut taşınabilir kurulumlar bunu bir sonraki açılışta alıyor ve arşiv modu paket eksikse bunu ban diye bildirmek yerine baştan uyarıyor.
- **Global bir yt-dlp olmayan makinelerde yt-dlp "bulunamadı" görünüyordu.** Başlatıcılar `.venv` Python'unu doğrudan çalıştırdığı için `.venv` içindeki `yt-dlp` PATH'te değildi, uygulama ise yt-dlp'yi PATH'te arıyordu. yt-dlp artık uygulamanın kendi yorumlayıcısıyla `python -m yt_dlp` olarak çalışır.
- **Atlama raporu tamamen İngilizceydi**, Türkçe kullanımda bile — üstelik çevirileri zaten mevcuttu. On beş mesajın tamamı artık çeviri katmanından geçiyor; komut başlığı ile başarı, iptal ve hata satırları da öyle.
- `analyze_log_for_error` artık telif hakkı kaldırmalarını tanıyor; daha önce bunları genel "video kullanılamıyor" mesajıyla bildiriyordu.
- **Yeni bir klonda `./run.sh` "Permission denied" hatası veriyordu.** `run.sh`, `install.sh` ve `update.sh` çalıştırma izni olmadan commit'lenmişti; artık çalıştırılabilir.

### Değişenler
- `install.ps1` / `install.sh` Windows ve Linux'ta artık winget ya da apt/dnf/pacman kullanmıyor; bunun yerine taşınabilir çalışma ortamını kuruyor. macOS, Homebrew + `.venv` kurulumuyla devam ediyor. Güncelleyiciler artık `runtime/`, `cache/` ve `downloads/` klasörlerini de koruyor.
- Mevcut kurulumlar ayarlı indirme klasörlerini korur. `.venv` ve winget ile kurulan Python/ffmpeg/Deno artık kullanılmaz, kaldırılabilir.
- `AppSettings`'e `archive` bölümü, `OutputSettings`'e `archive_template` eklendi. Bunları içermeyen yapılandırmalar varsayılanları yükler, taşıma gerekmez. MP4 ve MP3 komutları değişmedi.
- `AppSettings`'ten `use_deno`, `default_mode`, `default_mp4_profile` ve `language` kaldırıldı: ilk üçü otomatik algılanıyor veya kullanıcıya soruluyor, dil ise ayarlardan önce çözülmesi gerektiği için `config.json`'un üst seviyesinde duruyor.
- `DownloadPlan`'dan her döngüde doldurulup hiç okunmayan dört argüman alanı kaldırıldı; profil alanları karşılaştırıldıkları enum türleriyle tiplendi.
- Bir alan adı hesaplayıp koşulsuz `True` dönen `is_supported_url` ve hiç yapılmamış bir durum arayüzünü tarif eden on bir çeviri anahtarı silindi.
- Arşiv modunun altyazı eklentisinin dayandığı `--plugin-dirs` davranışı için artık yt-dlp 2025.03.21 veya daha yenisi gerekiyor.

## [0.3.1] - 2026-07-28

Bozuk v0.3.0 paketini onaran yama sürümü. **v0.3.0 kullanan herkes güncellemeli** — o sürüm kullanılamaz bir paketle yayınlandı.

### Düzeltilenler
- **v0.3.0 çevirisiz yayınlandı**: sürüm etiketi i18n onarım commit'inden önce atıldığı için yayınlanan ZIP, metin yerine ham çeviri anahtarlarını (`prompt_url`, `prompt_mode`, …) yazdırıyordu. Düzeltmeyi içeren ilk sürüm budur.
- **Otomatik güncelleme hiç çalışmıyordu**: `update.ps1`, `YtDlpDownloader-Portable.zip` adlı bir dosya ararken CI `YtDlpDownloader-Portable-<etiket>.zip` yayınlıyordu; bu yüzden her kontrol "dosya bulunamadı" ile sonuçlanıyordu. CI artık güncelleyicinin beklediği sabit adı kullanıyor.
- **Sürüm karşılaştırması uyumsuz biçimdeydi**: `app_version.txt` içinde `0.3.0` yazarken karşılaştırma GitHub etiketi `v0.3.0` ile yapılıyordu; uygulama her açılışta kendini eski sanıyordu. Dosya artık etiket biçimini saklıyor.
- **`app_version.txt` taşınabilir ZIP'te yoktu**, bu yüzden yeni kurulumlarda karşılaştırılacak yerel sürüm bulunmuyordu.
- **`update.sh` sürümü `pyproject.toml`'dan okuyordu**; orada artık sabit bir sürüm yok, dosya artık `app_version.txt` okuyor. Ayrıca paketi mevcut `ytdlp_app/` dizininin *içine* kopyalıyordu (`ytdlp_app/ytdlp_app` oluşuyordu) ve isteğe bağlı bir dosya yoksa `set -e` nedeniyle sessizce sonlanabiliyordu.

### Değişenler
- **Tek kaynaklı sürüm yönetimi**: sürüm artık yalnızca `ytdlp_app.__version__` içinde yazılı. `pyproject.toml` onu dinamik okuyor ve CI'a bağlanan `scripts/check_version.py`, `app_version.txt` ya da sürüm etiketi uyuşmazsa derlemeyi durduruyor.
- Taşınabilir ZIP artık `run.sh`, `install.sh`, `update.sh` ve `app_version.txt` içeriyor; belgelenen Linux/macOS akışı böylece indirilen paketten gerçekten çalışıyor.
- Windows'a özel destek ve Python 3.10+ iddiasında bulunan meta veriler ve belgeler düzeltildi; uygulama **Python 3.11+** gerektiriyor (`StrEnum` kullanıyor) ve Linux, Windows, macOS üzerinde test ediliyor.

## [0.3.0] - 2026-01-11

### Eklenenler
- **Modern Konsol Arayüzü**: Kutucuklu paneller ve stilize menülerle geliştirilmiş görsel deneyim.
- **Tam Yerelleştirme (i18n)**: Kod içindeki sabit metinler temizlendi; arayüz artık tamamen çevrilebilir.
- **CommandBuilder Deseni**: Karmaşık yt-dlp komutlarını oluşturmak için yeni ve sağlam yapı.

### Değişenler
- **Mimari Yenileme**: Tek parça halindeki `run()` fonksiyonu modüler `InteractiveSession` sınıfına dönüştürüldü.
- **Temiz Kod**: Menü seçimlerindeki "sihirli sayılar" (magic numbers) okunabilir Enum yapılarıyla değiştirildi.
- **Performans**: Sistem bağımlılık kontrollerine (ffmpeg, yt-dlp, deno) önbellekleme eklendi.

> Not: yayınlanan v0.3.0 paketi bozuk — bkz. [0.3.1].

## [0.2.0] - 2026-01-11

### Eklenenler

#### Paket Yönetimi
- **pyproject.toml**: PEP 621 uyumlu modern Python paket yapılandırması
  - Proje meta verileri (isim, sürüm, açıklama, lisans)
  - Sabitlenmiş bağımlılıklar (`yt-dlp>=2024.1.0`)
  - Geliştirici bağımlılıkları (pytest, mypy, ruff, pytest-cov)
  - pytest, mypy, ruff ve coverage araç yapılandırmaları
  - Konsol giriş noktası (`ytdlp-downloader` komutu)
- **py.typed**: Tip kontrolü için PEP 561 uyumluluk işareti

#### CI/CD Pipeline
- **GitHub Actions workflow** (`.github/workflows/ci.yml`)
  - Lint işi: Ruff linter ve mypy tip kontrolü
  - Test işi: 3 İS x 4 Python sürümü matris testi
  - Build işi: Dağıtılabilir paket oluşturma
  - Release işi: Tag'lerde otomatik GitHub Release
  - Desteklenen platformlar: Ubuntu, Windows, macOS
  - Python sürümleri: 3.11, 3.12, 3.13

#### Yeni Modüller
- **exceptions.py**: Hata yönetimi için özel istisna hiyerarşisi
- **validators.py**: URL ve yol doğrulama fonksiyonları (enjeksiyon koruması dahil)
- **settings.py**: Gelişmiş yapılandırılabilir ayarlar sistemi
- **i18n.py**: Çoklu dil desteği altyapısı

#### Yerelleştirme
- **İngilizce çeviriler** (`locales/en.json`): 70+ çeviri anahtarı
- **Türkçe çeviriler** (`locales/tr.json`): 70+ çeviri anahtarı

#### Platformlar Arası Destek
- **install.sh**: Unix kurulum betiği (apt, dnf, pacman, brew desteği)
- **run.sh**: Platformlar arası başlatıcı
- **update.sh**: Platformlar arası güncelleyici

#### Test Altyapısı
- 8 test dosyasında ~70 birim testi
- `conftest.py` içinde paylaşılan fixture'lar

#### Dokümantasyon
- Tüm genel fonksiyonlar için kapsamlı docstring'ler (Google-style)
- Örnek ayarlar dosyası (`settings.example.json`)

### Değişenler
- `__init__.py` sürüm numarası ve genişletilmiş `__all__` listesi ile güncellendi
- `config.py` içinde tip ipuçları iyileştirildi

## [0.1.0] - 2025-12-14

### Eklenenler
- İlk sürüm
- MP4/MP3 indirme modları
- Playlist ve tek video desteği
- Kalite profilleri (Uyumluluk, Kalite)
- Tekrarları engelleyen indirme arşivleri
- Renkli konsol çıktısı
- Playlist öğeleri için atlama nedeni raporlama
- Çoklu indirmeler için oturum sürekliliği
- GitHub releases'tan otomatik güncelleme
- winget ile tek tıkla Windows kurulumu
