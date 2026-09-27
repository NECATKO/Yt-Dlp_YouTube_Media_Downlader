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
- [ ] Commit on `archive-mode`: everything is STAGED; blocked because git has no user.name/user.email on this machine
- [ ] Push / tag / release: waiting for the user (auto-update pulls releases)
