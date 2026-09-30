# yt-dlp Downloader (portable)

A portable cross-platform console application that wraps yt-dlp and ffmpeg. Runs on Windows, Linux, and macOS; on Windows and Linux it is fully portable (see [Portable runtime](#portable-runtime)). Features interactive folder setup, MP4/MP3/Archive mode selection, playlist handling, download archives to prevent duplicates, colorized console output, and detailed logging.

**Scope.** The app is built around YouTube: playlists, channels, the size estimate and the channel archives all rest on YouTube's URL forms and ids. A URL from another site is still handed to yt-dlp, but only ever as a single item (you are told so); it is never treated as a playlist or channel.

## Features
- **Fully portable (Windows, Linux)**: On first launch Python, yt-dlp, ffmpeg and Deno are downloaded *into the program folder*. No administrator rights, nothing installed on the system; copy the folder to a USB stick or another PC and it keeps working
- **Verified updates**: on Windows a newer release is looked for quietly at every launch (`Run.bat`); on Linux/macOS you update on request with `bash update.sh`. Either way a release is installed only after the new package has been checked, and a failed update keeps the working version (see [Updating](#updating))
- **Interactive prompts**: Choose MP4/MP3/Archive mode, playlist vs single video, and quality profiles
- **Honest results**: a run is judged by what it left behind (the download archive and the files), not by yt-dlp's exit code; you are told what was downloaded, what was already there, what failed and what is missing
- **Archive mode**: Preserve a whole channel (or a single video) with its description, subtitles, thumbnail and metadata, paced to avoid rate limits and IP bans
- **Archive check and repair**: compare the archives with the files on disk, preview a repair, redownload what is missing (type `a` at the URL prompt, or `downloader.py audit`)
- **Settings menu**: Change the language, download folders, proxy, speed limit, audio format, and subtitles from inside the app — type `s` at the URL prompt
- **Colorized output**: Syntax-highlighted console output on a terminal; plain text when redirected or when `NO_COLOR` is set
- **Skip reporting**: Explains why playlist items were skipped (private, region-blocked, age-restricted, members-only, etc.)
- **Session continuity**: Download multiple URLs in a single session without restarting

## How it works
1. Launch `Run.bat` (Windows) or `bash run.sh` (Linux/macOS; `./run.sh` works once the file is executable, which a ZIP download does not preserve). On Windows and Linux the first launch downloads the portable runtime into `runtime/` (once, about 150 MB on Windows and 220 MB on Linux); macOS installs Python, ffmpeg and Deno with Homebrew and yt-dlp into `.venv`.
2. You are asked once for base download folders (defaults: `downloads/Videos` and `downloads/Music` inside the program folder). Choices are saved to `config.json`.
3. Each session: enter a URL, choose Video (MP4), Audio (in the format set in the settings, MP3 by default) or Archive (see [Archive mode](#archive-mode)), decide whether a playlist URL should grab the whole list or only that video, then pick the MP4 profile when relevant.
4. yt-dlp runs with resume/retry flags (`--continue`, `--retries infinite`, `--fragment-retries infinite`); a download that keeps failing skips to the next playlist item, but a failed conversion, merge or embedding step, or a fragment that stays missing, leaves the item **undone** (it is not written to the download archive) so the next run retries it; a log captures the full command output.
5. When the run ends you get one of three verdicts: *all done*, *finished with problems* (some items downloaded, some not; the ones that did not are listed) or *nothing was downloaded*. After a partly failed run, leaving the app returns exit code 1.
6. When a playlist is used, items that were not downloaded are probed and the reasons are printed (private, region blocked, age-restricted, members-only, copyright, etc.). The probing stops at once on Ctrl+C or when YouTube starts blocking.
7. After finishing, you can immediately start another download from the same session.

## Output layout
File names carry the video id, so two different videos with the same title are two files (without it the second was silently taken for a duplicate of the first). In playlists the position stays as a prefix, for ordering only.

| Mode | Type | Output Path | Archive File |
|------|------|-------------|--------------|
| MP4 | Playlist | `<Videos>/yt-dlp/<playlist_title>/<index> - <title> [<id>].mp4` | `archives/playlist_<playlist_id>_mp4.txt` |
| MP4 | Channel | as above | `archives/channel_<channel_id>_mp4.txt` |
| MP4 | Single | `<Videos>/Downloaded Videos/<title> [<id>].mp4` | `archives/single_videos_mp4.txt` |
| Audio | Playlist | `<Music>/yt-dlp/<playlist_title>/<index> - <title> [<id>].<format>` | `archives/playlist_<playlist_id>_mp3.txt` |
| Audio | Channel | as above | `archives/channel_<channel_id>_mp3.txt` |
| Audio | Single | `<Music>/Downloaded Music/<title> [<id>].<format>` | `archives/single_audios_mp3.txt` |
| Archive | Channel | `<Videos>/yt-dlp/<channel>/<upload_date> - <title> [<id>]/<title>.mkv` | `archives/channel_<channel_id>_archive.txt` |
| Archive | Playlist | same as above | `archives/playlist_<playlist_id>_archive.txt` |
| Archive | Single | same as above | `archives/single_videos_archive.txt` |

- Audio archives keep the `mp3` name whichever audio format you choose: the archive records *which videos are done*, not in which format, and renaming it per format would hide everything already downloaded.
- Every archive file name is built from a sanitised id (a playlist id such as `/../../x` cannot climb out of `archives/`) and checked to stay inside the archives folder. Two ids that would sanitise to the same text get different names.
- A channel URL (handle, `/channel/`, `/c/`, `/user/` or any of their tabs) is keyed by the real channel id in every mode, so the tab name never stands in for the channel. `/@name/live` is the single video it redirects to, not a playlist.
- **Upgrading.** Your saved output templates are migrated only where they are still exactly the old defaults (`%(title)s.%(ext)s` and the playlist one); a template you wrote yourself is never changed, but you are told when it lacks `%(id)s`. Files downloaded before the change keep their old names, and existing archives keep working. A channel archive that older versions kept under the channel's handle is still used until an id-keyed one exists.
- Logs: `logs/yt-dlp_<mode>_<playlist|single>_<timestamp>.log`

## MP4 profiles
1. **Compatibility** — the result is **an MP4 file with H.264 video and AAC audio**, and that is checked, not assumed:
   - Stage 1 asks for an H.264 + AAC rendition, which merges into MP4 without re-encoding.
   - Stage 2 takes whatever else is best and a bundled yt-dlp plugin (`Mp4Compat`) probes the result with ffprobe. A file that already is H.264 + AAC in MP4 is left exactly as it is (no quality loss); a file with the right video and the wrong audio keeps its video untouched and only the audio is converted; anything else (AV1, VP9, HEVC, a WebM/MKV container, even an `.mp4` holding AV1) is converted. The converted file is probed again and must be H.264 + AAC, or the item fails and is retried next run.
   - yt-dlp's own `--recode-video mp4` is not used: it goes by the container, so an `.mp4` holding AV1 is "already in the target format" and would have been kept.
   - An item that stage 1 could not finish is not in the archive, so stage 2 really processes it; a clean stage 2 does not hide an unresolved stage 1.
2. **Quality** (no re-encode):
   - Downloads best video + best audio without transcoding
   - Container choice:
     - **MKV**: always works; a video that arrives as one combined stream (a single MP4) is remuxed (stream copy) into MKV, not left as MP4
     - **MP4 remux**: May fail if codecs are incompatible

## Audio mode
- Downloads best available audio (`bestaudio/best`)
- Converts to the chosen format (`mp3`, `m4a`, `opus`, `flac`, `wav`, or `best` to keep the source codec; `s` → *Audio*); the mode menu, the summary and the messages name that format
- Embeds metadata, thumbnail (converted to JPG)

## Archive mode
For preserving a channel that may disappear. Pick **Archive** as the mode and enter a channel URL (`https://www.youtube.com/@name`, `/channel/UC...`, or a tab such as `/@name/videos`), a playlist, or a single video.

- **What is kept, per video** (each in its own folder): the video (best quality up to your resolution limit, 1080p by default, always delivered as MKV with chapters and metadata embedded), `.description`, `.info.json`, the thumbnail, and uploaded plus auto-generated subtitles in Turkish and English converted to `.srt`. YouTube's machine translations are skipped (an English video gets no Turkish subtitle unless the channel uploaded one), so only subtitles that actually exist on the video are kept.
- **Complete or not at all.** An item enters the archive file only when everything it has was saved:
  - a missing HLS/DASH fragment fails the item (yt-dlp's default is to skip it and report success, leaving a video with a hole in it); after the 10 retries the item is left out of the archive and the next run fetches it again;
  - a subtitle that exists but could not be downloaded, or thumbnails that were listed but none of which could be saved, stop the item too (a bundled plugin, `ArchiveComplete`, checks before the video is downloaded, so no bandwidth is spent on it). A video that has *no* subtitles or thumbnail is complete without them, and a 404 on the best thumbnail does not matter while a lesser one arrived.
- **A channel URL archives the whole channel.** yt-dlp returns the Videos, Shorts and Live tabs as nested playlists; all of them are downloaded, and the "whole playlist or this video" question is skipped.
- **The archive file is keyed by the real channel id** (`channel_UC..._archive.txt`), so the handle URL, the `/channel/` URL and any tab URL of the same channel all resume one archive, even if the handle changes. The id comes from the same listing that feeds the size estimate, so there is no separate lookup; if the listing fails for a reason other than a block, the id in the URL is used instead.
- **Pacing** (defaults): 1.5 s between requests, 15–45 s (random) between videos, 5 s before each subtitle download, 10 retries instead of infinite. The waits can be changed with `s` → *Archive mode waits* and are stored under `settings.archive` in `config.json`. Your speed limit and proxy still apply.
- **Ban protection**: if yt-dlp reports `HTTP Error 429` or YouTube's *"Sign in to confirm you're not a bot"*, the download is stopped immediately (yt-dlp and everything it started, ffmpeg included), the event is written to the log (`[BAN-GUARD]`), and you are told to **wait a few hours and enter the same URL again: it resumes where it left off.**
- To keep request volume low, archive mode lists a channel or playlist once (for the size estimate and the channel id, paced by the request wait) and never probes skipped items afterwards (the skip report is MP4/audio only). A single video sends no listing request.

## What "already downloaded" means
The download archive records **which videos are done**, keyed by video id. It does not record the folder, the resolution or the audio format. So when you later change any of those:

| You change | What happens to items already in the archive |
|------------|----------------------------------------------|
| The download folder | They are skipped; nothing is copied to the new folder |
| The resolution limit | They are skipped; nothing is downloaded again in the new quality |
| The audio format | They are skipped; nothing is converted again |
| Nothing, but you deleted a file | It is skipped too, unless the archive check finds it (below) |

The app says so after a run that skipped items. To download something again, use the archive tools:

- **Missing files** — `a` at the URL prompt → *Download missing files again*, or `downloader.py audit --repair` (a preview) then `--repair --apply`. Only records whose file is *proven* gone are removed. The check knows a file's location from the manifest kept next to each archive (`archives/<name>.files.tsv`, written for everything downloaded from now on) or from `[id]` in a file or folder name. A record with neither (a download from before names carried the id) is reported as *cannot be checked*, never repaired on a guess.
- **A few videos again** — `downloader.py audit --forget ID [ID ...] --archive NAME [--apply]`.
- **Everything of an archive again (for example in a better quality)** — `a` → *Download one archive's items again*, or `--forget-all --archive NAME`. Choose a different download folder first (or move the old files away): files are named by id, and yt-dlp does not overwrite an existing one.

Every command that changes an archive is a **preview until you add `--apply`** (in the menu: until you confirm), copies the archive to `archives/backups/<name>.<time>.bak` first, rewrites it atomically, leaves comment and blank lines alone, and never deletes anything else. To undo, copy the backup over the archive file. `downloader.py audit` with no option is a read-only report.

## Size estimate and resolution limit
**Before downloading a playlist or channel** (video, audio and archive modes) the app shows a size estimate and checks free disk space. It reads the listing once (no extra request per video) and multiplies each video's duration by a typical bit rate, so the numbers are deliberately on the high side and are **estimates, not measurements**:

| Row | Assumed bit rate |
|-----|------------------|
| 1080p | 6000 kbit/s video + 160 kbit/s audio |
| 1440p (at most) | 12000 + 160 |
| 2160p (at most) | 30000 + 160 |
| Unlimited (up to 8K) | 80000 + 160 |

- 1440p and 2160p are labelled *at most*: a flat listing carries no resolution, and a video that does not exist at that resolution downloads smaller.
- **Unlimited is not 2160p.** It takes the best format there is, which can be 8K, so it has a row of its own and the disk check for an unlimited download uses it. The real size depends on the formats each video offers.
- **Space needed** = the total for the chosen resolution + the largest single video, because the source and the result sit on disk together while merging or recoding. For audio it is the total of the outputs + the largest *source* stream (which is on disk while it is converted, and is bigger than a low-bit-rate output).
- Videos already in the download archive are left out. A video without a duration (Shorts, live) is assumed to be 180 s (Shorts) or the median of the known durations; the screen says how many were assumed. If no duration is known at all, the estimate is skipped and the download continues.
- **Audio** shows one number, based on your audio format and quality (`mp3` quality 0 is about 245 kbit/s; `flac` and `wav` are much larger).
- Sizes are 1024-based (KiB/MiB/GiB), like Windows Explorer.
- **Not enough space?** You are warned and asked *Continue anyway / Cancel*. The download is never blocked.
- **Time:** a short speed test (at most about 10 MB, and never longer than 8 seconds whatever the connection does) against `speed.cloudflare.com` (through your proxy; skipped for SOCKS proxies) turns the size into a rough download time. It measures your line to that server, not YouTube, so treat the times as rough; it sends your IP to that host. If it fails, the time column says so and nothing else changes. **It can be switched off** (`s` → *Connection speed test*, or `settings.download.speed_test`); the size estimate remains. Archive mode also shows the waits between videos as *at least* (every wait at its minimum) and *about* (the average).
- A single video is not estimated (that would need an extra request).

**Resolution limit.** After the estimate you are asked for the maximum resolution (1080p, 1440p, 2160p or unlimited) for MP4 and archive downloads, also for a single video. The saved default is marked; if you pick another one you can use it once or save it as the new default. It is applied to every video format selector (as `[height<=N]`, including the fallback). The compatibility MP4 profile stays at 1080p, because YouTube serves H.264 up to about 1080p and higher resolutions would be recoded slowly. Defaults: archive 1080p, MP4 unlimited. Change them in `s` → *Video resolution limit* / *Archive resolution limit*, or in `config.json` (`settings.video.max_height`, `settings.archive.max_height`: `1080`, `1440`, `2160` or `null`).

## Network, proxy and privacy
- **One set of rules for every yt-dlp call.** The download, the playlist listing and the skip probes all get the same proxy, JavaScript runtime, network time-out (30 s per stalled read; a download has no overall time limit) and pacing. Listing and probes additionally have a time limit on the whole request (30 and 3 minutes) so a hung one cannot freeze the app.
- **Your own yt-dlp config files are ignored by default** (`--ignore-config`): a `--skip-download` or `--extract-audio` left in your `yt-dlp.conf` would otherwise change what a download does, and the app's settings would no longer be what decides. If you want them honoured, turn on `s` → *Read my own yt-dlp config files* (`settings.download.allow_external_config`).
- **Proxy credentials are masked** (`http://***:***@host:port`) in everything shown or logged: the console, the settings screen, the command banner, the `CMD:` line of the log, error messages and yt-dlp's own output. Only the arguments that really run keep them.
- The speed test goes through your proxy too; the app talks to `speed.cloudflare.com` for it and to GitHub for updates and the runtime downloads.

## Stopping cleanly
yt-dlp starts ffmpeg, and Ctrl+C in a terminal does not reliably reach a child of a child. The app therefore starts each command in its own process group and, on Ctrl+C, a ban, a full disk (log write error), a broken console or any unexpected error, stops the whole group: an interrupt first (yt-dlp then stops ffmpeg and exits cleanly, keeping its partial files for resuming), then a terminate, then a kill, waiting between them, and finally a sweep of stragglers. Pipes are closed and the process is reaped before the call returns. On Windows the group receives `CTRL_BREAK` and then `taskkill /T /F` on the whole tree. **The Windows branch could not be run in the environment this was developed in**; it is covered by unit tests of its decisions only.

## Portable runtime
On Windows (x64) and Linux (x86_64, aarch64; glibc-based distributions) everything the app needs lives in its own folder:

| Folder | Contents |
|--------|----------|
| `runtime/python` | A relocatable Python 3.12 ([python-build-standalone](https://github.com/astral-sh/python-build-standalone)) with yt-dlp installed into it |
| `runtime/ffmpeg` | ffmpeg and ffprobe ([yt-dlp's FFmpeg builds](https://github.com/yt-dlp/FFmpeg-Builds)) |
| `runtime/deno` | Deno, which yt-dlp uses to solve YouTube's JavaScript challenges |
| `cache/` | yt-dlp's and Deno's caches (normally written to your user profile) |
| `downloads/` | Default download location |

- **Nothing touches the system**: no winget/apt, no administrator rights or sudo, no PATH changes. Deleting the folder removes everything.
- **Verified downloads**: every file is checked against the SHA-256 pinned in `runtime.lock` before it is unpacked; a mismatch aborts the setup. When an app update changes a pin, the next launch replaces just that component. Replacing a component (or Python) is a rename, never delete-then-move: the old copy is set aside until the new one is in place, and an interrupted swap is put right on the next launch.
- **yt-dlp stays current**: it is upgraded automatically at launch once a week (YouTube changes break older versions). Offline launches simply keep the installed version. To upgrade now: `runtime/python/python -m ytdlp_app.portable update-ytdlp` (on Windows `runtime\python\python.exe`); `... status` shows what is installed.
- **Moving the folder**: folders inside the program folder are stored relative in `config.json`, so downloads, archives and settings follow the folder.
- Disk use after setup: about 360 MB on Windows, 530 MB on Linux (ffmpeg's Linux build is statically linked).
- Upgrading from an older version: the new launcher no longer uses `.venv` or the winget-installed Python/ffmpeg/Deno. The `.venv` folder can be deleted; the system packages can be uninstalled if nothing else needs them. Existing download folders in `config.json` are kept as they are.

## Updating
The app package (the `ytdlp_app` folder and the scripts) is updated from GitHub releases by the same transaction on every platform, but started differently:
- **Windows:** `Run.bat` runs `update.ps1 -Quiet` at every launch; nothing is asked, being offline is fine, and it never stops the launch. Set `YTDLP_NO_AUTO_UPDATE=1` to skip it, or run `update.ps1` yourself to be asked first.
- **Linux/macOS:** `run.sh` does **not** check for updates. Run `bash update.sh` when you want one (it asks first); `bash update.sh --check-only` only says whether a newer release exists.

An update is one transaction:
1. The release ZIP is downloaded to a private temporary folder inside the app folder (unique per run) and unpacked there. `unzip` is used if present, otherwise the bundled Python or `python3`, then `bsdtar`; if none exists the update stops before downloading anything and says so.
2. If the release publishes a `.sha256` checksum, the download must match it; otherwise the package is verified structurally only (the SHA-256 pins of `runtime.lock` are a separate thing: they protect the Python, ffmpeg and Deno downloads, not the app package).
3. The new package is checked **without touching the install**: the files a release needs are there, its version equals the release tag and is *newer* than the installed one (semantic ordering: `0.10.0` is newer than `0.9.0`, `1.0.0` than `1.0.0-rc1`; an older or equal release is never installed), and it imports under the bundled Python.
4. Every new file is first copied next to its place; only when all copies exist is each old file moved into a backup folder and the new one moved in.
5. `app_version.txt` is written last, so it never names a version that was not installed. If anything fails at any point, everything moved is put back and the previous version keeps running. The old version stays in `.previous-version/`.
6. Only one update runs at a time (a lock), and an update that was killed half way is undone the next time the updater starts.

`config.json`, `logs/`, `archives/`, `downloads/`, `cache/`, `runtime/` and `.venv/` are never touched. **`Run.bat` itself is not replaced** by the auto-update (cmd.exe reads a batch file while it runs, so swapping it underneath the launch could derail it): when a release changes `Run.bat`, copy it over by hand. The Linux/macOS updater replaces `run.sh` safely (a rename; the running script keeps its old copy). A ZIP download does not preserve the executable bit of `run.sh`, `install.sh` and `update.sh`; use `bash run.sh`, or `chmod +x run.sh install.sh update.sh` once.

## Config and state
| File | Description |
|------|-------------|
| `config.json` | Stores `config_version`, `app`, `videos_dir`, `music_dir`, `saved_at`, `language` and the advanced `settings` (including `settings.archive`). Folders inside the program folder are stored relative. Delete to reconfigure. |
| `archives/*.txt` | Download archives for `--download-archive`. |
| `archives/*.files.tsv` | Manifests: which file each finished item was written to. Used by the archive check. |
| `archives/backups/` | Copies made before an archive was repaired. |
| `logs/*.log` | Full command output with timestamps. Useful for troubleshooting. |
| `app_version.txt` | Tracks current version for auto-update. |

- **Bad edits do not crash the app.** Every section and field of `settings` is type- and range-checked when it is read: a section that is not an object, a number that is NaN, infinite, negative or out of range, an unknown audio format, a retry value that is neither a number nor `infinite`, an unusable proxy or output template (absolute, or containing `..`) is reported **by name** at startup and replaced by its default; the rest of the config is used as it is.
- **Saves are interruption-proof.** `config.json` and `runtime/state.json` are written to a temporary file and renamed into place, so a full disk or a crash leaves the previous valid file. If a save fails, the running app goes back to what is on disk (the settings menu edits are undone) so memory and disk never disagree.
- **A config that cannot be read** is copied to `config.json.corrupt-<time>` before defaults are used, so the next save cannot destroy what could still be recovered.
- **`config_version`** (currently 2) marks the schema. An older file is migrated in memory when read and written in the new form on the next save, after a copy of the old one is kept as `config.json.v1.bak`.

## Files in this folder
| File | Description |
|------|-------------|
| `Run.bat` / `run.sh` | One-click start (Windows / Linux, macOS). Sets up or refreshes the portable runtime and launches the app; `Run.bat` also updates quietly first. |
| `install.ps1` / `install.sh` | Sets up the portable runtime in `runtime/` (macOS: Homebrew + `.venv`). Safe to rerun. |
| `update.ps1` / `update.sh` | Transactional app updater (see [Updating](#updating)). |
| `runtime.lock` | Pinned URLs and SHA-256 checksums of the portable Python, ffmpeg and Deno. |
| `downloader.py` | Entry point that calls `ytdlp_app.app.run()`. `downloader.py audit ...` runs the archive check. |
| `ytdlp_app/` | Python package with modular components (see below). |

### ytdlp_app/ modules
| Module | Description |
|--------|-------------|
| `app.py` | Application entry point, configuration loading, the `audit` command |
| `session.py` | Interactive session manager handling the main loop |
| `planning.py` | Output folders, templates and archive file names (checked to stay inside `archives/`) |
| `outcome.py` | The result model: completed / already present / failed / missing / banned / cancelled, judged from the archive, the manifest and the disk, and the messages built from it |
| `archive_audit.py` | Archive check, repair preview, backup and apply, and the archive tools menu |
| `config.py` | Config loading/saving (atomic), schema migration, interactive folder setup |
| `settings.py` | Settings dataclasses with full validation and the schema defaults |
| `settings_menu.py` | The in-app settings menu (each edit applied whole or not at all) |
| `atomic.py` | Write-to-temp-then-rename for config and state files |
| `netctx.py` | The network context shared by downloads, listings and probes |
| `redact.py` | Masks proxy credentials in anything shown or logged |
| `ui.py` | Console UI with panels and menus that fit the terminal (Protocol-based) |
| `yt_dlp.py` | CommandBuilder class for constructing yt-dlp arguments |
| `plugins/` | yt-dlp plugins: `original_subs` (no machine-translated subtitles), `mp4_compat` (H.264 + AAC), `complete` (no item with an unsaved subtitle or thumbnail), `ledger` (the manifest) |
| `exec.py` | Command execution with output streaming, logging, the ban guard, process-group cleanup and time limits |
| `playlist.py` | YouTube URL classification, playlist and channel listing (channel tabs flattened, channel id), archive reading |
| `estimate.py` | Size, disk-space and time estimates (pure arithmetic) |
| `speedtest.py` | Short connection-speed measurement with a hard time budget |
| `preflight.py` | Listing guard, estimate table, resolution question and free-space check |
| `skip_probe.py` | Probes skipped items to determine skip reason; stops on cancel or ban |
| `logging_utils.py` | Logging and colour policy |
| `system.py` | Locates yt-dlp, ffmpeg and Deno |
| `portable.py` | Portable runtime setup (`python -m ytdlp_app.portable ensure / update-ytdlp / status`) |
| `models.py` | Data classes for paths, config, entries, and download plans |

## Requirements
- **Windows**: 64-bit Windows 10 (version 1803 or newer) or Windows 11. Nothing else.
- **Linux**: x86_64 or aarch64 with glibc (not Alpine/musl), plus `curl` or `wget`, `tar` and `sha256sum` (present on practically every distribution). Updating also needs `unzip`, `python3` or `bsdtar` (the bundled Python counts).
- **macOS**: Homebrew; Python 3.11+ is installed through it if missing.
- Internet connection for the first launch and for downloads

## Troubleshooting
| Problem | Solution |
|---------|----------|
| First-time setup fails | Check the internet connection and run `Run.bat` / `bash run.sh` again; it resumes and only fetches what is missing. Administrator rights are not needed. |
| "Permission denied" starting `./run.sh` | ZIP downloads lose the executable bit: run `bash run.sh`, or `chmod +x run.sh install.sh update.sh`. |
| "Checksum mismatch" | The download was corrupted or altered and was discarded. Try again; if it persists, report it. |
| yt-dlp/ffmpeg not found | Run `install.ps1` (Windows) or `bash install.sh` (Linux/macOS) again. |
| A video stopped working after a YouTube change | Update yt-dlp: `runtime/python/python -m ytdlp_app.portable update-ytdlp`. |
| An update failed | The previous version was restored; read the message, fix the cause (often a missing `unzip`) and run `bash update.sh` again. The previous version is also in `.previous-version/`. |
| Change download folders | Type `s` at the URL prompt and pick the folder to change. |
| Change the interface language | Type `s` at the URL prompt and pick "Interface language". |
| Download something again / a file was deleted | Type `a` at the URL prompt (archive tools) or run `downloader.py audit`; see [What "already downloaded" means](#what-already-downloaded-means). Deleting an archive file by hand also works, but forgets everything in it. |
| "Finished with problems" | The items that were not downloaded are listed; run the same URL again to retry them (the log has the reasons). |
| Archive stopped with "YouTube is temporarily blocking requests" | Wait a few hours and enter the same URL again; it resumes. Consider raising the archive waits (`s` → *Archive mode waits*) or using a proxy. |
| A setting was replaced by its default at startup | The message names the field and why; fix it in `config.json` or in the settings menu. |
| Deno warning appears | Run `install.ps1` / `bash install.sh` again (macOS: `brew install deno`). |

## License
See [LICENSE](LICENSE) for details.

---

## yt-dlp Downloader (taşınabilir) — Türkçe

yt-dlp ve ffmpeg üzerine kurulu taşınabilir bir konsol uygulaması. Windows, Linux ve macOS üzerinde çalışır; Windows ve Linux'ta tamamen taşınabilirdir (bkz. *Taşınabilir çalışma ortamı*). İnteraktif klasör kurulumu, MP4/MP3/Arşiv mod seçimi, oynatma listesi yönetimi, tekrarları engelleyen arşiv sistemi, renkli konsol çıktısı ve ayrıntılı günlükleme sunar.

**Kapsam.** Uygulama YouTube'a göredir: oynatma listeleri, kanallar, boyut tahmini ve kanal arşivleri YouTube'un URL biçimlerine ve kimliklerine dayanır. Başka bir sitenin URL'si yine yt-dlp'ye verilir, ama yalnızca tek öğe olarak (bu size söylenir); asla oynatma listesi ya da kanal sayılmaz.

## Özellikler
- **Tamamen taşınabilir (Windows, Linux)**: İlk açılışta Python, yt-dlp, ffmpeg ve Deno *program klasörünün içine* indirilir. Yönetici izni gerekmez, sisteme hiçbir şey kurulmaz; klasörü USB belleğe veya başka bir bilgisayara kopyalayın, çalışmaya devam eder
- **Doğrulanmış güncelleme**: Windows'ta yeni bir sürüm her açılışta sessizce aranır (`Run.bat`); Linux/macOS'ta istediğinizde `bash update.sh` ile güncellersiniz. İki durumda da sürüm ancak yeni paket denetlendikten sonra kurulur ve başarısız bir güncelleme çalışan sürümü korur (bkz. *Güncelleme*)
- **İnteraktif menüler**: MP4/MP3/Arşiv modu, oynatma listesi/tek video seçimi ve kalite profilleri
- **Dürüst sonuçlar**: bir çalıştırma yt-dlp'nin çıkış koduna değil, geride bıraktıklarına (indirme arşivi ve dosyalar) göre değerlendirilir; neyin indirildiği, neyin zaten var olduğu, neyin başarısız olduğu ve neyin eksik olduğu söylenir
- **Arşiv modu**: Bir kanalın tamamını (veya tek bir videoyu) açıklama, altyazı, kapak resmi ve metaveri ile birlikte, hız sınırına ve IP engeline takılmayacak tempoda arşivler
- **Arşiv denetimi ve onarımı**: arşivleri diskteki dosyalarla karşılaştırır, onarımı önizler, eksik olanı yeniden indirir (URL isteminde `a` yazın ya da `downloader.py audit`)
- **Ayarlar menüsü**: Dil, indirme klasörleri, vekil sunucu, hız sınırı, ses biçimi ve altyazıları uygulama içinden değiştirin — URL isteminde `s` yazın
- **Renkli çıktı**: Terminalde söz dizimi vurgulu çıktı; yönlendirilince ya da `NO_COLOR` tanımlıysa düz metin
- **Atlama raporu**: Oynatma listesi öğelerinin neden atlandığını açıklar (gizli, bölge kısıtı, yaş kısıtı, üyelik gerekli, vb.)
- **Oturum sürekliliği**: Tek oturumda yeniden başlatmadan birden fazla URL indirin

### Nasıl çalışır
1. `Run.bat` (Windows) veya `bash run.sh` (Linux/macOS; dosya çalıştırılabilir olduğunda `./run.sh` da olur, ZIP indirmesi bu biti korumaz) ile başlatın. Windows ve Linux'ta ilk açılış taşınabilir çalışma ortamını `runtime/` içine indirir (bir kereye mahsus; Windows'ta yaklaşık 150 MB, Linux'ta 220 MB); macOS'ta Python, ffmpeg ve Deno Homebrew ile, yt-dlp `.venv` içine kurulur.
2. İlk seferde video/müzik klasörlerini sorar (varsayılan: program klasöründeki `downloads/Videos` ve `downloads/Music`). Tercihler `config.json` içine kaydedilir.
3. Her oturumda: URL girin, Video (MP4), Ses (ayarlarda seçilen biçimde, varsayılan MP3) veya Arşiv (bkz. *Arşiv modu*) seçin, oynatma listesi URL'si için tüm liste mi tek video mu karar verin, MP4 ise profil seçin.
4. yt-dlp devam/yeniden dene bayraklarıyla (`--continue`, `--retries infinite`, `--fragment-retries infinite`) çalışır; sürekli başarısız olan bir indirme listedeki sonraki öğeye geçer, ama başarısız bir dönüştürme, birleştirme ya da gömme adımı ya da eksik kalan bir parça öğeyi **tamamlanmamış** bırakır (indirme arşivine yazılmaz) ve sonraki çalıştırma yeniden dener; konsol çıktısı günlüğe yazılır.
5. Çalıştırma bittiğinde üç sonuçtan biri verilir: *her şey tamam*, *sorunlarla tamamlandı* (bazı öğeler indi, bazıları inmedi; inmeyenler listelenir) ya da *hiçbir şey indirilemedi*. Kısmen başarısız bir çalıştırmadan sonra uygulamadan çıkış, 1 çıkış kodu döndürür.
6. Oynatma listesi kullanıldığında indirilmeyen öğeler için neden yoklaması yapılır ve ekrana yazılır (gizli, bölge kısıtı, yaş kısıtı, üyelik gerekli, telif hakkı, vb.). Yoklama, Ctrl+C'de ya da YouTube engellemeye başladığında hemen durur.
7. İndirme bitince aynı oturumda hemen yeni URL indirebilirsiniz.

### Çıktı düzeni
Dosya adları video kimliğini taşır; böylece aynı başlıklı iki farklı video iki ayrı dosya olur (kimlik olmadan ikincisi sessizce birincinin kopyası sanılıyordu). Oynatma listelerinde sıra numarası yalnızca sıralama için önek olarak kalır.

| Mod | Tür | Çıktı Yolu | Arşiv Dosyası |
|-----|-----|------------|---------------|
| MP4 | Oynatma listesi | `<Videos>/yt-dlp/<playlist_title>/<index> - <title> [<id>].mp4` | `archives/playlist_<playlist_id>_mp4.txt` |
| MP4 | Kanal | yukarıdaki gibi | `archives/channel_<channel_id>_mp4.txt` |
| MP4 | Tek video | `<Videos>/Downloaded Videos/<title> [<id>].mp4` | `archives/single_videos_mp4.txt` |
| Ses | Oynatma listesi | `<Music>/yt-dlp/<playlist_title>/<index> - <title> [<id>].<biçim>` | `archives/playlist_<playlist_id>_mp3.txt` |
| Ses | Kanal | yukarıdaki gibi | `archives/channel_<channel_id>_mp3.txt` |
| Ses | Tek parça | `<Music>/Downloaded Music/<title> [<id>].<biçim>` | `archives/single_audios_mp3.txt` |
| Arşiv | Kanal | `<Videos>/yt-dlp/<channel>/<upload_date> - <title> [<id>]/<title>.mkv` | `archives/channel_<channel_id>_archive.txt` |
| Arşiv | Oynatma listesi | yukarıdakiyle aynı | `archives/playlist_<playlist_id>_archive.txt` |
| Arşiv | Tek video | yukarıdakiyle aynı | `archives/single_videos_archive.txt` |

- Hangi ses biçimini seçerseniz seçin ses arşivleri `mp3` adını korur: arşiv *hangi videoların tamamlandığını* kaydeder, hangi biçimde olduğunu değil; biçime göre yeniden adlandırmak halihazırda indirilen her şeyin kaydını gizlerdi.
- Her arşiv dosyası adı temizlenmiş bir kimlikten üretilir (`/../../x` gibi bir oynatma listesi kimliği `archives/` dışına çıkamaz) ve arşiv klasörünün içinde kaldığı doğrulanır. Temizlenince aynı metne dönüşecek iki kimlik farklı adlar alır.
- Kanal URL'si (handle, `/channel/`, `/c/`, `/user/` ya da bunların sekmeleri) her modda gerçek kanal kimliğiyle adlandırılır; sekme adı asla kanalın yerine geçmez. `/@ad/live`, yönlendirdiği tek videodur; oynatma listesi değildir.
- **Yükseltme.** Kayıtlı çıktı şablonlarınız yalnızca hâlâ tam olarak eski varsayılanlarsa (`%(title)s.%(ext)s` ve oynatma listesi olan) taşınır; kendi yazdığınız şablon asla değiştirilmez, ama `%(id)s` içermiyorsa bu size söylenir. Değişiklikten önce indirilen dosyalar eski adlarını korur, mevcut arşivler çalışmaya devam eder. Eski sürümlerin bir kanal için handle adıyla tuttuğu arşiv, kimlikle adlandırılmış olan oluşana kadar kullanılmaya devam eder.
- Günlükler: `logs/yt-dlp_<mod>_<playlist|single>_<zaman>.log`

### MP4 profilleri
1. **Uyumluluk** — sonuç **H.264 video ve AAC ses içeren bir MP4 dosyasıdır** ve bu varsayılmaz, denetlenir:
   - Aşama 1 H.264 + AAC sürümünü ister; bu, yeniden kodlamadan MP4'e birleşir.
   - Aşama 2 geriye kalanın en iyisini alır ve paketle gelen bir yt-dlp eklentisi (`Mp4Compat`) sonucu ffprobe ile inceler. Zaten MP4 içinde H.264 + AAC olan dosyaya dokunulmaz (kalite kaybı yok); videosu doğru sesi yanlış olan dosyada video olduğu gibi kalır, yalnızca ses dönüştürülür; geri kalan her şey (AV1, VP9, HEVC, WebM/MKV kapsayıcı, hatta AV1 taşıyan bir `.mp4`) dönüştürülür. Dönüştürülen dosya yeniden incelenir ve H.264 + AAC olmalıdır; değilse öğe başarısız sayılır ve sonraki çalıştırmada yeniden denenir.
   - yt-dlp'nin kendi `--recode-video mp4` seçeneği kullanılmaz: kapsayıcıya bakar, dolayısıyla AV1 taşıyan bir `.mp4` "zaten hedef biçimde" sayılıp olduğu gibi kalırdı.
   - Aşama 1'in bitiremediği öğe arşivde olmadığından Aşama 2 onu gerçekten işler; temiz biten bir Aşama 2, çözülmemiş bir Aşama 1'i gizlemez.
2. **Kalite** (yeniden kodlama yok):
   - En iyi video + en iyi sesi dönüştürmeden indirir
   - Kapsayıcı seçimi:
     - **MKV**: her zaman çalışır; tek bir birleşik akış olarak gelen video (tek bir MP4) MKV'ye aktarılır (akış kopyası), MP4 olarak bırakılmaz
     - **MP4 remux**: Codec'ler uyumsuzsa hata verebilir

### Ses modu
- Mevcut en iyi sesi indirir (`bestaudio/best`)
- Seçilen biçime dönüştürür (`mp3`, `m4a`, `opus`, `flac`, `wav` ya da kaynak codec'ini korumak için `best`; `s` → *Ses*); mod menüsü, özet ve iletiler bu biçimi adıyla söyler
- Metaveri ve kapak resmi (JPG'ye dönüştürülmüş) gömer

### Arşiv modu
Silinme riski olan bir kanalı korumak için. Mod olarak **Arşiv**'i seçin ve bir kanal URL'si (`https://www.youtube.com/@isim`, `/channel/UC...` ya da `/@isim/videos` gibi bir sekme), bir oynatma listesi veya tek bir video girin.

- **Her video için saklananlar** (her biri kendi klasöründe): video (çözünürlük sınırına kadar en iyi kalite, varsayılan 1080p; her zaman MKV olarak, bölümler ve metaveri gömülü), `.description`, `.info.json`, kapak resmi ve Türkçe/İngilizce yüklenmiş + otomatik altyazılar (`.srt`'ye dönüştürülmüş). YouTube'un makine çevirileri atlanır (kanal yüklemediyse İngilizce bir videoya Türkçe altyazı gelmez); yalnızca videoda gerçekten var olan altyazılar saklanır.
- **Ya tam ya hiç.** Bir öğe arşiv dosyasına ancak sahip olduğu her şey kaydedildiğinde girer:
  - eksik bir HLS/DASH parçası öğeyi başarısız kılar (yt-dlp'nin varsayılanı onu atlayıp başarı bildirmektir; ortaya deliği olan bir video çıkar); 10 denemeden sonra öğe arşivin dışında kalır ve sonraki çalıştırma yeniden indirir;
  - var olduğu hâlde indirilemeyen bir altyazı ya da listelenmiş olduğu hâlde hiçbiri kaydedilemeyen kapak resimleri de öğeyi durdurur (paketle gelen `ArchiveComplete` eklentisi videoyu indirmeden önce denetler; böylece bant genişliği boşa harcanmaz). Hiç altyazısı ya da kapak resmi *olmayan* bir video onlarsız da tamamdır; en iyi kapak resmi 404 verse de daha düşüğü geldiyse sorun olmaz.
- **Kanal URL'si kanalın tamamını arşivler.** yt-dlp Videos, Shorts ve Live sekmelerini iç içe oynatma listesi olarak döndürür; hepsi indirilir ve "tüm liste mi bu video mu" sorusu sorulmaz.
- **Arşiv dosyası gerçek kanal kimliğine göre adlandırılır** (`channel_UC..._archive.txt`). Böylece aynı kanalın handle URL'si, `/channel/` URL'si ve sekme URL'leri, handle değişse bile aynı arşivden devam eder. Kimlik, boyut tahminini de besleyen aynı listeden okunur (ayrı bir istek yok); liste engel dışı bir nedenle başarısız olursa URL'deki kimlik kullanılır.
- **Tempo** (varsayılanlar): istekler arası 1,5 sn, videolar arası 15–45 sn (rastgele), her altyazıdan önce 5 sn, sonsuz yerine 10 deneme. Bekleme süreleri `s` → *Arşiv modu bekleme süreleri* ile değiştirilir ve `config.json` içinde `settings.archive` altında saklanır. Hız sınırınız ve vekil sunucunuz bu modda da geçerlidir.
- **Engel koruması**: yt-dlp `HTTP Error 429` ya da YouTube'un *"Sign in to confirm you're not a bot"* iletisini bildirirse indirme hemen durdurulur (yt-dlp ve başlattığı her şey, ffmpeg dahil), olay günlüğe (`[BAN-GUARD]`) yazılır ve **birkaç saat bekleyip aynı URL'yi yeniden vermeniz, indirmenin kaldığı yerden devam edeceği** söylenir.
- İstek sayısını düşük tutmak için arşiv modu bir kanalı ya da oynatma listesini yalnızca bir kez listeler (boyut tahmini ve kanal kimliği için; istekler arası bekleme uygulanır) ve sonrasında atlanan öğeleri yoklamaz (atlama raporu yalnızca MP4/ses modunda). Tek video için liste isteği yapılmaz.

### "Zaten indirilmiş" ne demek
İndirme arşivi **hangi videoların tamamlandığını** video kimliğine göre kaydeder. Klasörü, çözünürlüğü ya da ses biçimini kaydetmez. Bunlardan birini sonradan değiştirirseniz:

| Değiştirdiğiniz | Arşivde zaten kayıtlı öğelere ne olur |
|-----------------|---------------------------------------|
| İndirme klasörü | Atlanırlar; yeni klasöre hiçbir şey kopyalanmaz |
| Çözünürlük sınırı | Atlanırlar; yeni kalitede yeniden indirilmez |
| Ses biçimi | Atlanırlar; yeniden dönüştürülmez |
| Hiçbiri, ama bir dosyayı sildiniz | O da atlanır; arşiv denetimi (aşağıda) onu bulmadıkça |

Öğe atlayan bir çalıştırmadan sonra uygulama bunu söyler. Bir şeyi yeniden indirmek için arşiv araçlarını kullanın:

- **Eksik dosyalar** — URL isteminde `a` → *Eksik dosyaları yeniden indir* ya da `downloader.py audit --repair` (önizleme), ardından `--repair --apply`. Yalnızca dosyasının kesin olarak yok olduğu kayıtlar silinir. Denetim, bir dosyanın yerini her arşivin yanında tutulan manifestten (`archives/<ad>.files.tsv`; bundan sonra indirilen her şey için yazılır) ya da dosya/klasör adındaki `[kimlik]`ten bilir. İkisi de olmayan kayıt (adlarda kimlik bulunmadan önceki bir indirme) *denetlenemedi* diye bildirilir; tahminle asla onarılmaz.
- **Birkaç video yeniden** — `downloader.py audit --forget KİMLİK [KİMLİK ...] --archive AD [--apply]`.
- **Bir arşivin tamamı yeniden (örneğin daha iyi kalitede)** — `a` → *Bir arşivdeki her şeyi yeniden indir* ya da `--forget-all --archive AD`. Önce başka bir indirme klasörü seçin (ya da eski dosyaları kaldırın): dosyalar kimlikle adlandırılır ve yt-dlp var olan bir dosyanın üzerine yazmaz.

Bir arşivi değiştiren her komut **`--apply` ekleyene kadar bir önizlemedir** (menüde: onaylayana kadar), önce arşivi `archives/backups/<ad>.<zaman>.bak` olarak kopyalar, atomik biçimde yeniden yazar, yorum ve boş satırlara dokunmaz ve başka hiçbir şeyi silmez. Geri almak için yedeği arşiv dosyasının üzerine kopyalayın. Seçeneksiz `downloader.py audit` salt okunur bir rapordur.

### Boyut tahmini ve çözünürlük sınırı
**Oynatma listesi ya da kanal indirmeden önce** (video, ses ve arşiv modları) uygulama bir boyut tahmini gösterir ve boş disk alanını denetler. Listeyi bir kez okur (video başına ek istek yok) ve her videonun süresini tipik bir bit hızıyla çarpar; bu yüzden rakamlar bilerek yüksek taraftadır ve **ölçüm değil tahmindir**:

| Satır | Varsayılan bit hızı |
|-------|---------------------|
| 1080p | 6000 kbit/sn video + 160 kbit/sn ses |
| 1440p (en fazla) | 12000 + 160 |
| 2160p (en fazla) | 30000 + 160 |
| Sınırsız (8K'ya kadar) | 80000 + 160 |

- 1440p ve 2160p "en fazla" diye etiketlenir: düz listede çözünürlük yoktur ve o çözünürlükte olmayan video daha küçük iner.
- **Sınırsız, 2160p değildir.** Var olan en iyi biçimi alır; bu 8K olabilir. Bu yüzden kendi satırı vardır ve sınırsız indirme için disk denetimi onu kullanır. Gerçek boyut, her videonun sunduğu biçimlere bağlıdır.
- **Gereken alan** = seçilen çözünürlüğün toplamı + en büyük tek video; birleştirme ya da yeniden kodlama sırasında kaynak ve sonuç diskte birlikte durur. Ses için: çıktıların toplamı + en büyük *kaynak* akış (dönüştürülürken diskte durur ve düşük bit hızlı bir çıktıdan büyüktür).
- Arşivde kayıtlı videolar hariç tutulur. Süresi olmayan video (Shorts, canlı) 180 sn (Shorts) ya da bilinen sürelerin ortancası kabul edilir; ekranda kaç videonun varsayımla hesaplandığı yazar. Hiçbir süre bilinmiyorsa tahmin atlanır ve indirme devam eder.
- **Ses** tek rakam gösterir; ses biçiminiz ve kaliteniz esas alınır (`mp3` kalite 0 yaklaşık 245 kbit/sn; `flac` ve `wav` çok daha büyük).
- Boyutlar 1024 tabanlıdır (KiB/MiB/GiB), Windows Gezgini gibi.
- **Yer yetmiyor mu?** Uyarılırsınız ve *Yine de devam et / İptal* sorulur. İndirme asla engellenmez.
- **Süre:** kısa bir hız testi (en fazla yaklaşık 10 MB, bağlantı ne yaparsa yapsın 8 saniyeyi geçmez; `speed.cloudflare.com`, vekil sunucunuzdan geçer; SOCKS vekilde atlanır) boyutu kaba bir indirme süresine çevirir. YouTube'u değil, o sunucuya olan hattınızı ölçer; süreleri kaba sayın; IP adresinizi o sunucuya gönderir. Başarısız olursa süre sütunu bunu söyler, başka bir şey değişmez. **Kapatılabilir** (`s` → *Bağlantı hızı testi* ya da `settings.download.speed_test`); boyut tahmini kalır. Arşiv modu ayrıca videolar arası beklemeleri *en az* (her bekleme en kısa değerinde) ve *yaklaşık* (ortalama) olarak gösterir.
- Tek video için tahmin yapılmaz (ek istek gerekirdi).

**Çözünürlük sınırı.** Tahminden sonra MP4 ve arşiv indirmeleri için (tek video dahil) en yüksek çözünürlük sorulur: 1080p, 1440p, 2160p ya da sınırsız. Kayıtlı varsayılan işaretlidir; başka bir seçenek seçerseniz yalnızca bu indirme için kullanabilir ya da yeni varsayılan olarak kaydedebilirsiniz. Sınır tüm video biçim seçicilerine (`[height<=N]`, yedek dahil) uygulanır. Uyumluluk MP4 profili 1080p'de kalır: YouTube H.264'ü yaklaşık 1080p'ye kadar verir, daha yükseği yavaşça yeniden kodlanırdı. Varsayılanlar: arşiv 1080p, MP4 sınırsız. `s` → *Video çözünürlük sınırı* / *Arşiv çözünürlük sınırı* ile ya da `config.json`'da (`settings.video.max_height`, `settings.archive.max_height`: `1080`, `1440`, `2160` ya da `null`) değiştirilir.

### Ağ, vekil sunucu ve gizlilik
- **Her yt-dlp çağrısı için tek kural kümesi.** İndirme, oynatma listesi listelemesi ve atlama yoklamaları aynı vekil sunucuyu, JavaScript çalışma ortamını, ağ zaman aşımını (takılan her okuma için 30 sn; indirmenin toplam süre sınırı yoktur) ve tempoyu alır. Listeleme ve yoklamaların ayrıca tüm isteğe uygulanan bir süre sınırı vardır (30 ve 3 dakika); takılan bir istek uygulamayı donduramaz.
- **Kendi yt-dlp yapılandırma dosyalarınız varsayılan olarak yok sayılır** (`--ignore-config`): `yt-dlp.conf` dosyanızda unutulmuş bir `--skip-download` ya da `--extract-audio` bir indirmenin ne yaptığını değiştirirdi ve karar veren artık uygulamanın ayarları olmazdı. Dikkate alınmalarını istiyorsanız `s` → *Kendi yt-dlp yapılandırma dosyalarımı oku* seçeneğini açın (`settings.download.allow_external_config`).
- **Vekil sunucu kimlik bilgileri maskelenir** (`http://***:***@host:port`): konsolda, ayar ekranında, komut başlığında, günlüğün `CMD:` satırında, hata iletilerinde ve yt-dlp'nin kendi çıktısında gösterilen ya da günlüğe yazılan her yerde. Yalnızca gerçekten çalıştırılan argümanlar onları korur.
- Hız testi de vekil sunucunuzdan geçer; uygulama bunun için `speed.cloudflare.com` ile, güncellemeler ve çalışma ortamı indirmeleri için GitHub ile konuşur.

### Temiz durdurma
yt-dlp ffmpeg'i başlatır ve terminaldeki Ctrl+C, çocuğun çocuğuna güvenilir biçimde ulaşmaz. Bu yüzden uygulama her komutu kendi süreç grubunda başlatır ve Ctrl+C'de, engelde, dolu diskte (günlük yazma hatası), bozulan bir konsolda ya da beklenmeyen herhangi bir hatada grubun tamamını durdurur: önce bir kesme (yt-dlp ffmpeg'i durdurup temiz çıkar, yarım dosyalarını devam etmek için saklar), sonra sonlandırma, sonra öldürme; aralarında beklenir ve en sonda artakalanlar süpürülür. Çağrı dönmeden önce borular kapatılır ve süreç toplanır. Windows'ta grup `CTRL_BREAK` alır, ardından tüm ağaca `taskkill /T /F` uygulanır. **Windows dalı, bunun geliştirildiği ortamda çalıştırılamadı**; yalnızca kararlarının birim testleriyle kapsanmıştır.

### Taşınabilir çalışma ortamı
Windows (x64) ve Linux'ta (x86_64, aarch64; glibc tabanlı dağıtımlar) uygulamanın ihtiyaç duyduğu her şey kendi klasöründe durur:

| Klasör | İçerik |
|--------|--------|
| `runtime/python` | Taşınabilir Python 3.12 ([python-build-standalone](https://github.com/astral-sh/python-build-standalone)), yt-dlp bunun içine kurulur |
| `runtime/ffmpeg` | ffmpeg ve ffprobe ([yt-dlp'nin FFmpeg derlemeleri](https://github.com/yt-dlp/FFmpeg-Builds)) |
| `runtime/deno` | yt-dlp'nin YouTube JavaScript doğrulamalarını çözmek için kullandığı Deno |
| `cache/` | yt-dlp ve Deno önbellekleri (normalde kullanıcı profiline yazılırlar) |
| `downloads/` | Varsayılan indirme konumu |

- **Sisteme dokunulmaz**: winget/apt yok, yönetici izni veya sudo yok, PATH değişikliği yok. Klasörü silmek her şeyi kaldırır.
- **Doğrulanmış indirmeler**: her dosya açılmadan önce `runtime.lock` içinde sabitlenmiş SHA-256 ile karşılaştırılır; uyuşmazsa kurulum durur. Bir uygulama güncellemesi bir sürümü değiştirirse, sonraki açılış yalnızca o bileşeni yeniler. Bir bileşeni (ya da Python'u) değiştirmek bir yeniden adlandırmadır; sil-sonra-taşı değildir: eski kopya, yenisi yerine oturana kadar kenarda tutulur ve yarım kalan bir değişim sonraki açılışta düzeltilir.
- **yt-dlp güncel kalır**: açılışta haftada bir otomatik güncellenir (YouTube değişiklikleri eski sürümleri bozar). İnternet yoksa kurulu sürümle devam edilir. Hemen güncellemek için: `runtime/python/python -m ytdlp_app.portable update-ytdlp` (Windows'ta `runtime\python\python.exe`); `... status` neyin kurulu olduğunu gösterir.
- **Klasörü taşımak**: program klasörünün içindeki klasörler `config.json`'a göreli yazılır; indirmeler, arşivler ve ayarlar klasörle birlikte taşınır.
- Kurulum sonrası disk kullanımı: Windows'ta yaklaşık 360 MB, Linux'ta 530 MB (Linux ffmpeg derlemesi statik bağlıdır).
- Eski sürümden yükseltme: yeni başlatıcı artık `.venv`'i ve winget ile kurulan Python/ffmpeg/Deno'yu kullanmaz. `.venv` klasörü silinebilir; sistem paketleri başka bir şey kullanmıyorsa kaldırılabilir. `config.json`'daki mevcut indirme klasörleri olduğu gibi korunur.

### Güncelleme
Uygulama paketi (`ytdlp_app` klasörü ve betikler) GitHub sürümlerinden her platformda aynı işlemle güncellenir, ama farklı başlatılır:
- **Windows:** `Run.bat` her açılışta `update.ps1 -Quiet` çalıştırır; hiçbir şey sorulmaz, internetsiz olmak sorun değildir ve açılışı asla engellemez. Atlamak için `YTDLP_NO_AUTO_UPDATE=1` tanımlayın; önce sorulmasını istiyorsanız `update.ps1` komutunu kendiniz çalıştırın.
- **Linux/macOS:** `run.sh` güncelleme **denetlemez**. İstediğinizde `bash update.sh` çalıştırın (önce sorar); `bash update.sh --check-only` yalnızca yeni sürüm olup olmadığını söyler.

Bir güncelleme tek bir işlemdir:
1. Sürüm ZIP'i, uygulama klasörünün içinde, her çalıştırmaya özgü geçici bir klasöre indirilir ve orada açılır. `unzip` varsa o, yoksa paketle gelen Python ya da `python3`, sonra `bsdtar` kullanılır; hiçbiri yoksa güncelleme bir şey indirmeden durur ve bunu söyler.
2. Sürüm bir `.sha256` sağlama toplamı yayımlıyorsa indirme onunla eşleşmelidir; yayımlamıyorsa paket yalnızca yapısal olarak doğrulanır (`runtime.lock`'taki SHA-256 sabitleri ayrı bir şeydir: Python, ffmpeg ve Deno indirmelerini korurlar, uygulama paketini değil).
3. Yeni paket **kurulu olana dokunmadan** denetlenir: bir sürümün ihtiyaç duyduğu dosyalar vardır, sürümü etiketine eşittir ve kurulu olandan *yenidir* (anlamsal sıralama: `0.10.0`, `0.9.0`'dan; `1.0.0`, `1.0.0-rc1`'den yenidir; eski ya da eşit bir sürüm asla kurulmaz) ve paketle gelen Python altında içe aktarılabilir.
4. Her yeni dosya önce yerinin yanına kopyalanır; yalnızca tüm kopyalar varsa her eski dosya bir yedek klasöre taşınır ve yenisi yerine konur.
5. `app_version.txt` en son yazılır; böylece kurulmamış bir sürümü asla adıyla anmaz. Herhangi bir noktada bir şey başarısız olursa taşınan her şey geri konur ve önceki sürüm çalışmaya devam eder. Eski sürüm `.previous-version/` içinde kalır.
6. Aynı anda yalnızca bir güncelleme çalışır (bir kilit) ve yarıda kesilmiş bir güncelleme, güncelleyici bir sonraki başladığında geri alınır.

`config.json`, `logs/`, `archives/`, `downloads/`, `cache/`, `runtime/` ve `.venv/`'e asla dokunulmaz. **`Run.bat`'ın kendisi otomatik güncellemeyle değiştirilmez** (cmd.exe bir toplu iş dosyasını çalışırken okur; altından değiştirmek açılışı bozabilir): bir sürüm `Run.bat`'ı değiştirirse elle kopyalayın. Linux/macOS güncelleyicisi `run.sh`'ı güvenle değiştirir (bir yeniden adlandırma; çalışan betik eski kopyasını korur). ZIP indirmesi `run.sh`, `install.sh` ve `update.sh` dosyalarının çalıştırılabilir bitini korumaz; `bash run.sh` kullanın ya da bir kez `chmod +x run.sh install.sh update.sh` yapın.

### Ayarlar ve durum
| Dosya | Açıklama |
|-------|----------|
| `config.json` | `config_version`, `app`, `videos_dir`, `music_dir`, `saved_at`, `language` ve gelişmiş `settings` (`settings.archive` dahil) değerlerini saklar. Program klasörünün içindeki klasörler göreli saklanır. Yeniden yapılandırmak için silin. |
| `archives/*.txt` | `--download-archive` için indirme arşivleri. |
| `archives/*.files.tsv` | Manifestler: bitmiş her öğenin hangi dosyaya yazıldığı. Arşiv denetimi bunu kullanır. |
| `archives/backups/` | Bir arşiv onarılmadan önce alınan kopyalar. |
| `logs/*.log` | Zaman damgalı tam komut çıktısı. Sorun giderme için kullanışlı. |
| `app_version.txt` | Otomatik güncelleme için mevcut sürümü takip eder. |

- **Hatalı düzenlemeler uygulamayı çökertmez.** `settings` altındaki her bölüm ve alan okunurken tür ve aralık bakımından denetlenir: nesne olmayan bir bölüm, NaN, sonsuz, negatif ya da aralık dışı bir sayı, bilinmeyen bir ses biçimi, sayı da `infinite` de olmayan bir yeniden deneme değeri, kullanılamaz bir vekil sunucu ya da çıktı şablonu (mutlak yol ya da `..` içeren) açılışta **adıyla** bildirilir ve varsayılanıyla değiştirilir; yapılandırmanın geri kalanı olduğu gibi kullanılır.
- **Kayıtlar kesintiye dayanıklıdır.** `config.json` ve `runtime/state.json` geçici bir dosyaya yazılıp yerine yeniden adlandırılır; dolu bir disk ya da çökme önceki geçerli dosyayı bırakır. Bir kayıt başarısız olursa çalışan uygulama diskteki duruma döner (ayar menüsündeki düzenlemeler geri alınır); bellek ve disk hiçbir zaman ayrışmaz.
- **Okunamayan bir yapılandırma**, varsayılanlar kullanılmadan önce `config.json.corrupt-<zaman>` olarak kopyalanır; böylece sonraki kayıt hâlâ kurtarılabilecek olanı yok edemez.
- **`config_version`** (şu an 2) şemayı işaretler. Eski bir dosya okunurken bellekte taşınır ve bir sonraki kayıtta yeni biçimde yazılır; eskisinin bir kopyası önce `config.json.v1.bak` olarak saklanır.

### Bu klasördeki dosyalar
| Dosya | Açıklama |
|-------|----------|
| `Run.bat` / `run.sh` | Tek tıkla başlatma (Windows / Linux, macOS). Taşınabilir çalışma ortamını kurar veya yeniler, uygulamayı başlatır; `Run.bat` ayrıca önce sessizce günceller. |
| `install.ps1` / `install.sh` | Taşınabilir çalışma ortamını `runtime/` içine kurar (macOS: Homebrew + `.venv`). Yeniden çalıştırmak güvenlidir. |
| `update.ps1` / `update.sh` | İşlem bütünlüklü uygulama güncelleyicisi (bkz. *Güncelleme*). |
| `runtime.lock` | Taşınabilir Python, ffmpeg ve Deno için sabitlenmiş adresler ve SHA-256 değerleri. |
| `downloader.py` | `ytdlp_app.app.run()` fonksiyonunu çağıran giriş noktası. `downloader.py audit ...` arşiv denetimini çalıştırır. |
| `ytdlp_app/` | Modüler bileşenli Python paketi (aşağıya bakın). |

### ytdlp_app/ modülleri
| Modül | Açıklama |
|-------|----------|
| `app.py` | Uygulama giriş noktası, yapılandırma yükleme, `audit` komutu |
| `session.py` | Ana döngüyü yöneten interaktif oturum yöneticisi |
| `planning.py` | Çıktı klasörleri, şablonlar ve arşiv dosyası adları (`archives/` içinde kaldığı doğrulanır) |
| `outcome.py` | Sonuç modeli: tamamlanan / zaten var olan / başarısız / eksik / engellenen / iptal edilen; arşivden, manifestten ve diskten değerlendirilir; iletiler bundan üretilir |
| `archive_audit.py` | Arşiv denetimi, onarım önizlemesi, yedek ve uygulama, arşiv araçları menüsü |
| `config.py` | Yapılandırma yükleme/kaydetme (atomik), şema göçü, interaktif klasör kurulumu |
| `settings.py` | Tam doğrulamalı ayar veri sınıfları ve şema varsayılanları |
| `settings_menu.py` | Uygulama içi ayar menüsü (her düzenleme bütünüyle uygulanır ya da hiç) |
| `atomic.py` | Yapılandırma ve durum dosyaları için geçiciye-yaz-sonra-yeniden-adlandır |
| `netctx.py` | İndirme, listeleme ve yoklamaların paylaştığı ağ bağlamı |
| `redact.py` | Gösterilen ya da günlüğe yazılan her yerde vekil sunucu kimlik bilgilerini maskeler |
| `ui.py` | Terminale sığan paneller ve menülerle konsol arayüzü (Protocol tabanlı) |
| `yt_dlp.py` | yt-dlp argümanlarını oluşturan CommandBuilder sınıfı |
| `plugins/` | yt-dlp eklentileri: `original_subs` (makine çevirisi altyazı yok), `mp4_compat` (H.264 + AAC), `complete` (kaydedilmemiş altyazı ya da kapak resmi olan öğe yok), `ledger` (manifest) |
| `exec.py` | Çıktı akışı, günlükleme, engel koruması, süreç grubu temizliği ve süre sınırlarıyla komut yürütme |
| `playlist.py` | YouTube URL sınıflandırması, oynatma listesi ve kanal listeleme (kanal sekmeleri düzleştirilir, kanal kimliği), arşiv okuma |
| `estimate.py` | Boyut, disk alanı ve süre tahmini (saf hesap) |
| `speedtest.py` | Kesin süre bütçeli kısa bağlantı hızı ölçümü |
| `preflight.py` | Liste koruması, tahmin tablosu, çözünürlük sorusu ve boş alan denetimi |
| `skip_probe.py` | Atlanan öğeleri atlama nedenini belirlemek için yoklar; iptal ya da engelde durur |
| `logging_utils.py` | Günlükleme ve renk politikası |
| `system.py` | yt-dlp, ffmpeg ve Deno'nun yerini bulur |
| `portable.py` | Taşınabilir çalışma ortamı kurulumu (`python -m ytdlp_app.portable ensure / update-ytdlp / status`) |
| `models.py` | Yollar, yapılandırma, girdiler ve indirme planları için veri sınıfları |

### Gereksinimler
- **Windows**: 64 bit Windows 10 (1803 veya üzeri) ya da Windows 11. Başka bir şey gerekmez.
- **Linux**: glibc'li x86_64 veya aarch64 (Alpine/musl değil), ayrıca `curl` veya `wget`, `tar` ve `sha256sum` (hemen her dağıtımda bulunur). Güncelleme ayrıca `unzip`, `python3` ya da `bsdtar` gerektirir (paketle gelen Python sayılır).
- **macOS**: Homebrew; Python 3.11+ yoksa onunla kurulur.
- İlk açılış ve indirmeler için internet bağlantısı

### Sorun giderme
| Sorun | Çözüm |
|-------|-------|
| İlk kurulum başarısız | İnternet bağlantısını denetleyip `Run.bat` / `bash run.sh`'ı yeniden çalıştırın; kaldığı yerden devam eder, yalnızca eksikleri indirir. Yönetici izni gerekmez. |
| `./run.sh` başlatılırken "Permission denied" | ZIP indirmeleri çalıştırılabilir biti kaybeder: `bash run.sh` çalıştırın ya da `chmod +x run.sh install.sh update.sh` yapın. |
| "Checksum mismatch" | İndirilen dosya bozulmuş ya da değiştirilmiş ve silindi. Yeniden deneyin; sürerse bildirin. |
| yt-dlp/ffmpeg bulunamıyor | `install.ps1` (Windows) veya `bash install.sh` (Linux/macOS) dosyasını yeniden çalıştırın. |
| YouTube değişikliğinden sonra video inmiyor | yt-dlp'yi güncelleyin: `runtime/python/python -m ytdlp_app.portable update-ytdlp`. |
| Güncelleme başarısız oldu | Önceki sürüm geri yüklendi; iletiyi okuyun, nedeni giderin (çoğunlukla eksik `unzip`) ve `bash update.sh`'ı yeniden çalıştırın. Önceki sürüm ayrıca `.previous-version/` içindedir. |
| İndirme klasörlerini değiştirme | URL isteminde `s` yazın ve değiştirmek istediğiniz klasörü seçin. |
| Arayüz dilini değiştirme | URL isteminde `s` yazın ve "Arayüz dili" seçeneğini seçin. |
| Bir şeyi yeniden indirme / bir dosya silindi | URL isteminde `a` yazın (arşiv araçları) ya da `downloader.py audit` çalıştırın; bkz. *"Zaten indirilmiş" ne demek*. Bir arşiv dosyasını elle silmek de işe yarar, ama içindeki her şeyi unutturur. |
| "Sorunlarla tamamlandı" | İndirilemeyen öğeler listelenir; yeniden denemek için aynı URL'yi tekrar çalıştırın (nedenler günlüktedir). |
| Arşiv "YouTube istekleri geçici olarak engelliyor" ile durdu | Birkaç saat bekleyin ve aynı URL'yi tekrar girin; kaldığı yerden devam eder. Arşiv bekleme sürelerini artırmayı (`s` → *Arşiv modu bekleme süreleri*) ya da vekil sunucu kullanmayı düşünün. |
| Açılışta bir ayar varsayılanıyla değiştirildi | İleti alanın adını ve nedenini söyler; `config.json`'da ya da ayar menüsünde düzeltin. |
| Deno uyarısı görünüyor | `install.ps1` / `bash install.sh`'ı yeniden çalıştırın (macOS: `brew install deno`). |

### Lisans
Ayrıntılar için [LICENSE](LICENSE) dosyasına bakın.
