# Archive mode — task checklist

Branch: `archive-mode`. Nothing is pushed, tagged or released.

## Setup
- [x] Create the `archive-mode` branch
- [x] Create `.venv` (uv, Python 3.11) with the dev deps and upgrade yt-dlp (2026.08.19)
- [x] Baseline: 188 tests pass, ruff and mypy are clean
- [x] Check that yt-dlp recognizes every archive-mode flag

## Implementation
- [x] models: `DownloadMode.ARCHIVE`, `ModeChoice.ARCHIVE`
- [x] settings: `ArchiveSettings` (waits) under `settings.archive` in config.json, plus `output.archive_template`
- [x] yt_dlp.py: `CommandBuilder.build_archive()` with the specified flags, rate limit and proxy
- [x] playlist.py: channel URL detection and channel id resolution (tolerates nested tab playlists)
- [x] exec.py: ban guard (HTTP 429 / "not a bot") that stops yt-dlp, logs the event and returns a dedicated code
- [x] session.py: third mode option, channel archive path/template, ban message, no skip probe or playlist fetch in archive mode
- [x] settings_menu.py: archive wait editor
- [x] locales: EN + TR strings

## Tests
- [x] CommandBuilder archive argument list
- [x] Channel URL detection and channel id resolution
- [x] 429 / bot message detection and process termination
- [x] Session: archive mode skips the skip probe and reports a ban
- [x] Settings: archive section round trip and menu editor
- [x] Full suite, ruff, ruff format, and mypy are green

## Real network test
- [x] Offline: yt-dlp's own option parser accepts the full archive command (proxy + rate limit included)
- [ ] Download ONE short video in archive mode, then check for mkv, .info.json, .description, a thumbnail and at least one .srt
      BLOCKED: the video URL in the request is still the placeholder "[kanaldan kısa bir video URL'si]".
      Also note: Deno is not installed on this machine (node is), so the app will not pass a JS runtime to yt-dlp.

## Docs
- [x] README (EN + TR)
- [x] CHANGELOG
- [x] settings.example.json

## Wrap-up
- [x] Commit on `archive-mode` (9597784); 265 tests pass on that commit alone
- [ ] Push / tag / release: waiting for the user (auto-update pulls releases)

---

# Portable mode: task checklist

Decisions (user): download runtimes on first launch · Windows + Linux · downloads next to the program.
Branch `portable`, opened from `archive-mode`.

- [x] Pin Python 3.12.14 (stripped), ffmpeg (yt-dlp month-end build), and Deno 2.9.7 with SHA-256 in `runtime.lock`
- [x] `ytdlp_app/portable.py`: verified download, safe extraction (no ffplay), state/pins, yt-dlp install plus weekly update, CLI
- [x] yt-dlp runs as `python -m yt_dlp`; fixes the existing "yt-dlp not found" bug (`.venv` was never on PATH)
- [x] Environment: bundled ffmpeg/Deno go first on PATH; yt-dlp and Deno caches go in `cache/`
- [x] Relative paths in config.json; new installs default to `downloads/Videos` and `downloads/Music`
- [x] install.ps1 / Run.bat (no winget, no admin), install.sh / run.sh (Linux portable, macOS unchanged)
- [x] update.ps1 / update.sh keep runtime/cache/downloads; runtime.lock added to CI's portable ZIP
- [x] Tests: 322 pass (55 new); ruff, format, and mypy clean
- [x] Real Linux test: fresh setup, second run (0.3 s), re-pin upgrade, folder move, run.sh start and exit
- [x] Real Windows 11 test: install.ps1, folder move, Run.bat start and exit
- [x] README (EN + TR), CHANGELOG (EN + TR)
- [x] Commit on the `portable` branch
- [ ] Push / tag / release: waiting for the user (auto-update pulls releases)
