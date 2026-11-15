# yt-dlp Downloader (portable)

A portable console application that wraps yt-dlp and ffmpeg. Runs in the Windows and Linux terminal, with everything it needs inside its own folder (see [Portable runtime](#portable-runtime)). The interface is in English. Features interactive folder setup, MP4/MP3/Archive mode selection, playlist handling, download archives to prevent duplicates, colorized console output, and detailed logging.

**Scope.** The app is built around YouTube: playlists, channels and the channel archives all rest on YouTube's URL forms and ids. A URL from another site is still handed to yt-dlp, but only ever as a single item (you are told so); it is never treated as a playlist or channel.

## Features
- **Fully portable (Windows, Linux)**: On first launch Python, yt-dlp, ffmpeg and Deno are downloaded *into the program folder*. No administrator rights, nothing installed on the system; copy the folder to a USB stick or another PC and it keeps working
- **Interactive prompts**: Choose MP4/MP3/Archive mode, playlist vs single video, and quality profiles
- **Honest results**: a run is judged by what it left behind (the download archive and the files), not by yt-dlp's exit code; you are told what was downloaded, what was already there, what failed and what is missing
- **Archive mode**: Preserve a whole channel (or a single video) with its description, subtitles, thumbnail and metadata, paced to avoid rate limits and IP bans
- **Archive check and repair**: compare the archives with the files on disk, preview a repair, redownload what is missing (type `a` at the URL prompt, or `downloader.py audit`)
- **Settings in one file**: download folders, proxy, speed limit, audio format, subtitles, resolution limits and the archive waits are in `config.json` (see [Settings](#settings))
- **Colorized output**: Syntax-highlighted console output on a terminal; plain text when redirected or when `NO_COLOR` is set
- **Session continuity**: Download multiple URLs in a single session without restarting

## How it works
1. Launch `Run.bat` (Windows) or `bash run.sh` (Linux; `./run.sh` works once the file is executable, which a ZIP download does not preserve). The first launch downloads the portable runtime into `runtime/` (once, about 150 MB on Windows and 220 MB on Linux).
2. You are asked once for base download folders (defaults: `downloads/Videos` and `downloads/Music` inside the program folder). Choices are saved to `config.json`.
3. Each session: enter a URL, choose Video (MP4), Audio (in the format set in the settings, MP3 by default) or Archive (see [Archive mode](#archive-mode)), decide whether a playlist URL should grab the whole list or only that video, then pick the MP4 profile when relevant.
4. yt-dlp runs with resume/retry flags (`--continue`, `--retries infinite`, `--fragment-retries infinite`); a download that keeps failing skips to the next playlist item, but a failed conversion, merge or embedding step, or a fragment that stays missing, leaves the item **undone** (it is not written to the download archive) so the next run retries it; a log captures the full command output.
5. When the run ends you get one of three verdicts: *all done*, *finished with problems* (some items downloaded, some not; the ones that did not are listed) or *nothing was downloaded*. The exit code describes the whole session: 0 when everything went well, 1 when any download failed or left items undone (even if a later one succeeded), 130 when you cancelled with Ctrl+C.
6. After finishing, you can immediately start another download from the same session.

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
   - One yt-dlp command asks for an H.264 + AAC rendition first, which merges into MP4 without re-encoding, and falls back to the best rendition of any codec when a video has none.
   - A bundled yt-dlp plugin (`Mp4Compat`) probes the result with ffprobe. A file that already is H.264 + AAC in MP4 is left exactly as it is (no quality loss); a file with the right video and the wrong audio keeps its video untouched and only the audio is converted; anything else (AV1, VP9, HEVC, a WebM/MKV container, even an `.mp4` holding AV1) is converted. The converted file is probed again and must be H.264 + AAC, or the item fails and is retried next run.
   - yt-dlp's own `--recode-video mp4` is not used: it goes by the container, so an `.mp4` holding AV1 is "already in the target format" and would have been kept.
   - The profile is limited to 1080p (or your lower `settings.video.max_height`): YouTube serves H.264 up to about 1080p, and anything above would be re-encoded slowly.
2. **Quality** (no re-encode):
   - Downloads best video + best audio without transcoding
   - Container choice:
     - **MKV**: always works; a video that arrives as one combined stream (a single MP4) is remuxed (stream copy) into MKV, not left as MP4
     - **MP4 remux**: May fail if codecs are incompatible

## Audio mode
- Downloads best available audio (`bestaudio/best`)
- Converts to the chosen format (`mp3`, `m4a`, `opus`, `flac`, `wav`, or `best` to keep the source codec; `settings.audio.audio_format`); the mode menu, the summary and the messages name that format
- Embeds metadata, thumbnail (converted to JPG). WAV cannot hold a cover, so with `wav` the cover is saved as a separate `.jpg` next to the file (the app says so)

## Archive mode
For preserving a channel that may disappear. Pick **Archive** as the mode and enter a channel URL (`https://www.youtube.com/@name`, `/channel/UC...`, or a tab such as `/@name/videos`), a playlist, or a single video.

- **What is kept, per video** (each in its own folder): the video (best quality up to your resolution limit, 1080p by default, always delivered as MKV with chapters and metadata embedded), `.description`, `.info.json`, the thumbnail, and uploaded plus auto-generated subtitles in English converted to `.srt`. YouTube's machine translations are skipped (a video in another language gets no English subtitle unless the channel uploaded one), so only subtitles that actually exist on the video are kept.
- **Complete or not at all.** An item enters the archive file only when everything it has was saved:
  - a missing HLS/DASH fragment fails the item (yt-dlp's default is to skip it and report success, leaving a video with a hole in it); after the 10 retries the item is left out of the archive and the next run fetches it again;
  - a subtitle that exists but could not be downloaded, or thumbnails that were listed but none of which could be saved, stop the item too (a bundled plugin, `ArchiveComplete`, checks before the video is downloaded, so no bandwidth is spent on it). A video that has *no* subtitles or thumbnail is complete without them, and a 404 on the best thumbnail does not matter while a lesser one arrived.
- **A channel URL archives the whole channel.** yt-dlp returns the Videos, Shorts and Live tabs as nested playlists; all of them are downloaded, and the "whole playlist or this video" question is skipped. A tab URL (`/@name/videos`, `/shorts`, `/streams`, ...) would make yt-dlp list that tab only, so archive mode replaces it with the channel URL for the listing and the download, and says so; the log records both. `/@name/live` and a tab URL with `list=` are left as entered. The video and audio modes keep the tab you gave.
- **The archive file is keyed by the real channel id** (`channel_UC..._archive.txt`), so the handle URL, the `/channel/` URL and any tab URL of the same channel all resume one archive, even if the handle changes. The id comes from the one listing request, so there is no separate lookup; if the listing fails for a reason other than a block, the id in the URL is used instead.
- **Pacing** (defaults): 1.5 s between requests, 15–45 s (random) between videos, 5 s before each subtitle download, 10 retries instead of infinite. The waits are under `settings.archive` in `config.json`. Your speed limit and proxy still apply.
- **Ban protection**: if yt-dlp reports `HTTP Error 429` or YouTube's *"Sign in to confirm you're not a bot"*, the download is stopped immediately (yt-dlp and everything it started, ffmpeg included), the event is written to the log (`[BAN-GUARD]`), and you are told to **wait a few hours and enter the same URL again: it resumes where it left off.**
- To keep request volume low, a channel or playlist is listed once (for the channel id and the list of items the run is judged against, paced by the request wait). A single video sends no listing request.

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

## Resolution limit and free space
- **Resolution limit.** MP4 and archive downloads are capped by `settings.video.max_height` and `settings.archive.max_height` in `config.json` (`1080`, `1440`, `2160` or `null` for no cap). Defaults: archive 1080p, MP4 unlimited. The cap is applied to every video format selector (as `[height<=N]`, including the fallback). The compatibility MP4 profile never goes above 1080p.
- **Free space.** Before a download starts, the disk that holds the target folder is checked. With less than 2 GB free you are warned and asked *Continue anyway / Cancel*; a download is never blocked, and a disk that cannot be measured is not a reason to stop.

## Network, proxy and privacy
- **One set of rules for every yt-dlp call.** The download and the playlist listing get the same proxy, JavaScript runtime, network time-out (30 s per stalled read; a download has no overall time limit) and pacing. The listing additionally has a time limit on the whole request (30 minutes) so a hung one cannot freeze the app.
- **Your own yt-dlp config files are ignored by default** (`--ignore-config`): a `--skip-download` or `--extract-audio` left in your `yt-dlp.conf` would otherwise change what a download does, and the app's settings would no longer be what decides. If you want them honoured, set `settings.download.allow_external_config` to `true`.
- **Proxy credentials are masked** (`http://***:***@host:port`) in everything shown or logged: the console, the command banner, the `CMD:` line of the log, error messages and yt-dlp's own output. Only the arguments that really run keep them.
- Besides YouTube, the app talks to GitHub and PyPI only: for the runtime downloads and the weekly yt-dlp upgrade.

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
- **Verified downloads**: every file is checked against the SHA-256 pinned in `runtime.lock` before it is unpacked; a mismatch aborts the setup. When a new version of the app changes a pin, the next launch replaces just that component. Replacing a component (or Python) is a rename, never delete-then-move: the old copy is set aside until the new one is in place, and an interrupted swap is put right on the next launch.
- **yt-dlp stays current**: it is upgraded automatically at launch once a week (YouTube changes break older versions). Offline launches simply keep the installed version. To upgrade now: `runtime/python/python -m ytdlp_app.portable update-ytdlp` (on Windows `runtime\python\python.exe`); `... status` shows what is installed.
- **Moving the folder**: folders inside the program folder are stored relative in `config.json`, so downloads, archives and settings follow the folder.
- Disk use after setup: about 360 MB on Windows, 530 MB on Linux (ffmpeg's Linux build is statically linked).
- Upgrading from an older version: the new launcher no longer uses `.venv` or the winget-installed Python/ffmpeg/Deno. The `.venv` folder can be deleted; the system packages can be uninstalled if nothing else needs them. Existing download folders in `config.json` are kept as they are.

## Updating
- **yt-dlp** is upgraded automatically at launch once a week, which is the update that matters most: YouTube changes break older versions.
- **The app itself** has no updater. Download the new release ZIP and unpack it over the program folder (or into a new folder and copy `config.json`, `archives/` and your `downloads/` across). Unpacking leaves `config.json`, `logs/`, `archives/`, `downloads/`, `cache/` and `runtime/` as they are. The release ships a `.sha256` file to check the download against.

A ZIP download does not preserve the executable bit of `run.sh` and `install.sh`; use `bash run.sh`, or `chmod +x run.sh install.sh` once.

## Settings
Everything is in `config.json`, written with all its defaults on first launch; edit it and start the app again. `settings.example.json` shows every key with its default. A value of the wrong type or outside its range is reported by name at startup and replaced by the default.

| Key | What it sets |
|-----|--------------|
| `videos_dir`, `music_dir` | The download folders |
| `settings.download` | Proxy, speed limit, retries, parallel fragments, waits between downloads, whether your own yt-dlp config files are read |
| `settings.audio` | Audio format and quality, cover and metadata embedding |
| `settings.video` | Subtitles, cover and metadata embedding, resolution limit |
| `settings.archive` | Archive mode waits and resolution limit |
| `settings.output` | File name templates |

## Config and state
| File | Description |
|------|-------------|
| `config.json` | Stores `config_version`, `app`, `videos_dir`, `music_dir`, `saved_at` and the advanced `settings` (including `settings.archive`). Folders inside the program folder are stored relative. Delete to reconfigure. |
| `archives/*.txt` | Download archives for `--download-archive`. |
| `archives/*.files.tsv` | Manifests: which file each finished item was written to. Used by the archive check. |
| `archives/backups/` | Copies made before an archive was repaired. |
| `logs/*.log` | Full command output with timestamps. Useful for troubleshooting. |
| `app_version.txt` | The version, in release-tag form. |

- **Bad edits do not crash the app.** Every section and field of `settings` is type- and range-checked when it is read: a section that is not an object, a number that is NaN, infinite, negative or out of range, an unknown audio format, a retry value that is neither a number nor `infinite`, an unusable proxy or output template (absolute, or containing `..`) is reported **by name** at startup and replaced by its default; the rest of the config is used as it is.
- **Saves are interruption-proof.** `config.json` and `runtime/state.json` are written to a temporary file and renamed into place, so a full disk or a crash leaves the previous valid file.
- **A config that cannot be read** is copied to `config.json.corrupt-<time>` before defaults are used, so the next save cannot destroy what could still be recovered.
- **`config_version`** (currently 2) marks the schema. An older file is migrated in memory when read and written in the new form on the next save, after a copy of the old one is kept as `config.json.v1.bak`.

## Files in this folder
| File | Description |
|------|-------------|
| `Run.bat` / `run.sh` | One-click start (Windows / Linux). Sets up or refreshes the portable runtime and launches the app; Both return the app's exit code; `Run.bat` waits for a key only when started without arguments, so `Run.bat audit ...` works in scripts. |
| `install.ps1` / `install.sh` | Sets up the portable runtime in `runtime/`. Safe to rerun. |
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
| `atomic.py` | Write-to-temp-then-rename for config and state files |
| `netctx.py` | The network context shared by downloads and listings |
| `redact.py` | Masks proxy credentials in anything shown or logged |
| `ui.py` | Console UI with panels and menus that fit the terminal (Protocol-based) |
| `yt_dlp.py` | CommandBuilder class for constructing yt-dlp arguments |
| `plugins/` | yt-dlp plugins: `original_subs` (no machine-translated subtitles), `mp4_compat` (H.264 + AAC), `complete` (no item with an unsaved subtitle or thumbnail), `ledger` (the manifest) |
| `exec.py` | Command execution with output streaming, logging, the ban guard, process-group cleanup and time limits |
| `windows_process.py` | Windows job objects: a command and everything it starts are stopped together, also after the command itself has exited |
| `playlist.py` | YouTube URL classification, playlist and channel listing (channel tabs flattened, channel id), archive reading |
| `preflight.py` | Listing guard and free-space check |
| `logging_utils.py` | Logging and colour policy |
| `system.py` | Locates yt-dlp, ffmpeg and Deno |
| `portable.py` | Portable runtime setup (`python -m ytdlp_app.portable ensure / update-ytdlp / status`) |
| `models.py` | Data classes for paths, config, entries, and download plans |

## Requirements
- **Windows**: 64-bit Windows 10 (version 1803 or newer) or Windows 11. Nothing else.
- **Linux**: x86_64 or aarch64 with glibc (not Alpine/musl), plus `curl` or `wget`, `tar` and `sha256sum` (present on practically every distribution).
- yt-dlp 2025.11.12 or newer (the portable runtime keeps it current; an older one on the PATH is reported before a download starts)
- Internet connection for the first launch and for downloads

## Troubleshooting
| Problem | Solution |
|---------|----------|
| First-time setup fails | Check the internet connection and run `Run.bat` / `bash run.sh` again; it resumes and only fetches what is missing. Administrator rights are not needed. |
| "Permission denied" starting `./run.sh` | ZIP downloads lose the executable bit: run `bash run.sh`, or `chmod +x run.sh install.sh`. |
| "Checksum mismatch" | The download was corrupted or altered and was discarded. Try again; if it persists, report it. |
| yt-dlp/ffmpeg not found | Run `install.ps1` (Windows) or `bash install.sh` (Linux) again. |
| A video stopped working after a YouTube change | Update yt-dlp: `runtime/python/python -m ytdlp_app.portable update-ytdlp`. |
| Change download folders | Edit `videos_dir` / `music_dir` in `config.json` and start the app again. |
| Download something again / a file was deleted | Type `a` at the URL prompt (archive tools) or run `downloader.py audit`; see [What "already downloaded" means](#what-already-downloaded-means). Deleting an archive file by hand also works, but forgets everything in it. |
| "Finished with problems" | The items that were not downloaded are listed; run the same URL again to retry them (the log has the reasons). |
| Archive stopped with "YouTube is temporarily blocking requests" | Wait a few hours and enter the same URL again; it resumes. Consider raising the archive waits (`settings.archive` in `config.json`) or using a proxy. |
| A setting was replaced by its default at startup | The message names the field and why; fix it in `config.json`. |
| Deno warning appears | Run `install.ps1` / `bash install.sh` again. |

## License
See [LICENSE](LICENSE) for details.
