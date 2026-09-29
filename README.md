# yt-dlp Downloader (portable)

A portable cross-platform console application that wraps yt-dlp and ffmpeg. Runs on Windows, Linux, and macOS; on Windows and Linux it is fully portable (see [Portable runtime](#portable-runtime)). Features interactive folder setup, MP4/MP3/Archive mode selection, playlist handling, download archives to prevent duplicates, colorized console output, and detailed logging.

## Features
- **Fully portable (Windows, Linux)**: On first launch Python, yt-dlp, ffmpeg and Deno are downloaded *into the program folder*. No administrator rights, nothing installed on the system; copy the folder to a USB stick or another PC and it keeps working
- **Auto-update**: Silent update checks from GitHub releases on each launch
- **Interactive prompts**: Choose MP4/MP3/Archive mode, playlist vs single video, and quality profiles
- **Archive mode**: Preserve a whole channel (or a single video) with its description, subtitles, thumbnail and metadata, paced to avoid rate limits and IP bans
- **Settings menu**: Change the language, download folders, proxy, speed limit, audio format, and subtitles from inside the app — type `s` at the URL prompt
- **Colorized output**: Syntax-highlighted console output (downloads in green, errors in red, warnings in yellow, etc.)
- **Skip reporting**: Explains why playlist items were skipped (private, region-blocked, age-restricted, members-only, etc.)
- **Session continuity**: Download multiple URLs in a single session without restarting

## How it works
1. Launch `Run.bat` (Windows) or `./run.sh` (Linux/macOS). On Windows and Linux the first launch downloads the portable runtime into `runtime/` (once, about 150 MB on Windows and 220 MB on Linux); macOS installs Python, ffmpeg and Deno with Homebrew and yt-dlp into `.venv`.
2. You are asked once for base download folders (defaults: `downloads/Videos` and `downloads/Music` inside the program folder). Choices are saved to `config.json`.
3. Each session: enter a URL, choose Video (MP4), Audio (MP3) or Archive (see [Archive mode](#archive-mode)), decide whether a playlist URL should grab the whole list or only that video, then pick the MP4 profile when relevant.
4. yt-dlp runs with resume/retry flags (`--continue`, `--retries infinite`, `--fragment-retries infinite`); archive files prevent duplicates; a log captures the full command output.
5. When a playlist is used, skipped items are probed and reasons are printed (private, region blocked, age-restricted, members-only, copyright, etc.).
6. After finishing, you can immediately start another download from the same session.

## Output layout
| Mode | Type | Output Path | Archive File |
|------|------|-------------|--------------|
| MP4 | Playlist | `<Videos>/yt-dlp/<playlist_title>/<index> - <title>.mp4` | `archives/playlist_<playlist_id>_mp4.txt` |
| MP4 | Single | `<Videos>/Downloaded Videos/<title>.mp4` | `archives/single_videos_mp4.txt` |
| MP3 | Playlist | `<Music>/yt-dlp/<playlist_title>/<index> - <title>.mp3` | `archives/playlist_<playlist_id>_mp3.txt` |
| MP3 | Single | `<Music>/Downloaded Music/<title>.mp3` | `archives/single_audios_mp3.txt` |
| Archive | Channel | `<Videos>/yt-dlp/<channel>/<upload_date> - <title> [<id>]/<title>.mkv` | `archives/channel_<channel_id>_archive.txt` |
| Archive | Playlist | same as above | `archives/playlist_<playlist_id>_archive.txt` |
| Archive | Single | same as above | `archives/single_videos_archive.txt` |

- Logs: `logs/yt-dlp_<mode>_<playlist|single>_<timestamp>.log`

## MP4 profiles
1. **Compatibility** (two-stage download):
   - Stage 1: Tries lossless MP4 merge when avc1 video + mp4a audio are available
   - Stage 2: Downloads remaining items and recodes to MP4
2. **Quality** (no recode):
   - Downloads best video + best audio without transcoding
   - Container choice:
     - **Safe (MKV)**: Recommended, always works
     - **MP4 remux**: May fail if codecs are incompatible

## MP3 mode
- Downloads best available audio (`bestaudio/best`)
- Converts to MP3 with highest quality (`--audio-quality 0`)
- Embeds metadata, thumbnail (converted to JPG)

## Archive mode
For preserving a channel that may disappear. Pick **Archive** as the mode and enter a channel URL (`https://www.youtube.com/@name`, `/channel/UC...`, or a tab such as `/@name/videos`), a playlist, or a single video.

- **What is kept, per video** (each in its own folder): the video (best quality up to your resolution limit, 1080p by default, merged into MKV with chapters and metadata embedded), `.description`, `.info.json`, the thumbnail, and uploaded plus auto-generated subtitles in Turkish and English converted to `.srt`. YouTube's machine translations are skipped (an English video gets no Turkish subtitle unless the channel uploaded one), so only subtitles that actually exist on the video are kept.
- **A channel URL archives the whole channel.** yt-dlp returns the Videos, Shorts and Live tabs as nested playlists; all of them are downloaded, and the "whole playlist or this video" question is skipped.
- **The archive file is keyed by the real channel id** (`channel_UC..._archive.txt`), so the handle URL, the `/channel/` URL and any tab URL of the same channel all resume one archive, even if the handle changes. The id comes from the same listing that feeds the size estimate, so there is no separate lookup; if the listing fails for a reason other than a block, the id in the URL is used instead.
- **Pacing** (defaults): 1.5 s between requests, 15–45 s (random) between videos, 5 s before each subtitle download, 10 retries instead of infinite. The waits can be changed with `s` → *Archive mode waits* and are stored under `settings.archive` in `config.json`. Your speed limit and proxy still apply.
- **Ban protection**: if yt-dlp reports `HTTP Error 429` or YouTube's *"Sign in to confirm you're not a bot"*, the download is stopped immediately, the event is written to the log (`[BAN-GUARD]`), and you are told to **wait a few hours and enter the same URL again: it resumes where it left off.** Items only enter the archive file once every part of them was saved, so nothing half-finished is skipped on the next run.
- To keep request volume low, archive mode lists a channel or playlist once (for the size estimate and the channel id, paced by the request wait) and never probes skipped items afterwards (the skip report is MP4/MP3 only). A single video sends no listing request.

## Size estimate and resolution limit
**Before downloading a playlist or channel** (MP4, MP3 and archive modes) the app shows a size estimate and checks free disk space. It reads the listing once (no extra request per video) and multiplies each video's duration by a typical bit rate, so the numbers are deliberately on the high side and are **estimates, not measurements**:

| Row | Assumed bit rate |
|-----|------------------|
| 1080p | 6000 kbit/s video + 160 kbit/s audio |
| 1440p (at most) | 12000 + 160 |
| 2160p (at most) | 30000 + 160 |

- 1440p and 2160p are labelled *at most*: a flat listing carries no resolution, and a video that does not exist at that resolution downloads smaller.
- **Space needed** = the total for the chosen resolution + the largest single video, because the source and the result sit on disk together while merging, recoding or converting.
- Videos already in the download archive are left out. A video without a duration (Shorts, live) is assumed to be 180 s (Shorts) or the median of the known durations; the screen says how many were assumed. If no duration is known at all, the estimate is skipped and the download continues.
- **MP3** shows one number, based on your audio format and quality (`mp3` quality 0 is about 245 kbit/s; `flac` and `wav` are much larger).
- Sizes are 1024-based (KiB/MiB/GiB), like Windows Explorer.
- **Not enough space?** You are warned and asked *Continue anyway / Cancel*. The download is never blocked.
- **Time:** a short (~5 s) speed test against `speed.cloudflare.com` (through your proxy; skipped for SOCKS proxies) turns the size into a download time. It measures your line, not YouTube, and sends your IP to that host. If it fails, the time column says so and nothing else changes. Archive mode also shows the *minimum* time the waits between videos alone will take.
- A single video is not estimated (that would need an extra request).

**Resolution limit.** After the estimate you are asked for the maximum resolution (1080p, 1440p, 2160p or unlimited) for MP4 and archive downloads, also for a single video. The saved default is marked; if you pick another one you can use it once or save it as the new default. It is applied to every video format selector (as `[height<=N]`, including the fallback). The compatibility MP4 profile stays at 1080p, because YouTube serves H.264 up to about 1080p and higher resolutions would be recoded slowly. Defaults: archive 1080p, MP4 unlimited (as before). Change them in `s` → *Video resolution limit* / *Archive resolution limit*, or in `config.json` (`settings.video.max_height`, `settings.archive.max_height`: `1080`, `1440`, `2160` or `null`).

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
- **Verified downloads**: every file is checked against the SHA-256 pinned in `runtime.lock` before it is unpacked; a mismatch aborts the setup. When an app update changes a pin, the next launch replaces just that component.
- **yt-dlp stays current**: it is upgraded automatically at launch once a week (YouTube changes break older versions). Offline launches simply keep the installed version. To upgrade now: `runtime/python/python -m ytdlp_app.portable update-ytdlp` (on Windows `runtime\python\python.exe`); `... status` shows what is installed.
- **Moving the folder**: folders inside the program folder are stored relative in `config.json`, so downloads, archives and settings follow the folder.
- Disk use after setup: about 360 MB on Windows, 530 MB on Linux (ffmpeg's Linux build is statically linked).
- Upgrading from an older version: the new launcher no longer uses `.venv` or the winget-installed Python/ffmpeg/Deno. The `.venv` folder can be deleted; the system packages can be uninstalled if nothing else needs them. Existing download folders in `config.json` are kept as they are.

## Config and state
| File | Description |
|------|-------------|
| `config.json` | Stores `app`, `videos_dir`, `music_dir`, `saved_at`, `language` and the advanced `settings` (including `settings.archive`). Folders inside the program folder are stored relative. Delete to reconfigure. |
| `archives/*.txt` | Download archives for `--download-archive`. Delete to force re-download. |
| `logs/*.log` | Full command output with timestamps. Useful for troubleshooting. |
| `app_version.txt` | Tracks current version for auto-update. |

## Files in this folder
| File | Description |
|------|-------------|
| `Run.bat` / `run.sh` | One-click start (Windows / Linux, macOS). Runs the update check, sets up or refreshes the portable runtime, launches the app. |
| `install.ps1` / `install.sh` | Sets up the portable runtime in `runtime/` (macOS: Homebrew + `.venv`). Safe to rerun. |
| `update.ps1` / `update.sh` | Auto-updater. Downloads new releases from GitHub; keeps `config.json`, `archives/`, `logs/`, `runtime/`, `cache/` and `downloads/`. |
| `runtime.lock` | Pinned URLs and SHA-256 checksums of the portable Python, ffmpeg and Deno. |
| `downloader.py` | Entry point that calls `ytdlp_app.app.run()`. |
| `ytdlp_app/` | Python package with modular components (see below). |

### ytdlp_app/ modules
| Module | Description |
|--------|-------------|
| `app.py` | Application entry point and configuration loading |
| `session.py` | Interactive session manager handling the main loop |
| `config.py` | Config loading/saving, interactive folder setup |
| `ui.py` | Console UI with styled panels and menus (Protocol-based) |
| `yt_dlp.py` | CommandBuilder class for constructing yt-dlp arguments |
| `exec.py` | Command execution with output streaming, logging, and the 429/bot ban guard |
| `playlist.py` | Playlist and channel detection, flat listing (channel tabs flattened, channel id), archive reading |
| `estimate.py` | Size, disk-space and time estimates (pure arithmetic) |
| `speedtest.py` | Short connection-speed measurement |
| `preflight.py` | Listing guard, estimate table, resolution question and free-space check |
| `skip_probe.py` | Probes skipped items to determine skip reason |
| `logging_utils.py` | Logging utilities with colorized output |
| `system.py` | Locates yt-dlp, ffmpeg and Deno |
| `portable.py` | Portable runtime setup (`python -m ytdlp_app.portable ensure / update-ytdlp / status`) |
| `models.py` | Data classes for paths, config, entries, and download plans |

## Requirements
- **Windows**: 64-bit Windows 10 (version 1803 or newer) or Windows 11. Nothing else.
- **Linux**: x86_64 or aarch64 with glibc (not Alpine/musl), plus `curl` or `wget`, `tar` and `sha256sum` (present on practically every distribution).
- **macOS**: Homebrew; Python 3.11+ is installed through it if missing.
- Internet connection for the first launch and for downloads

## Troubleshooting
| Problem | Solution |
|---------|----------|
| First-time setup fails | Check the internet connection and run `Run.bat` / `./run.sh` again; it resumes and only fetches what is missing. Administrator rights are not needed. |
| "Checksum mismatch" | The download was corrupted or altered and was discarded. Try again; if it persists, report it. |
| yt-dlp/ffmpeg not found | Run `install.ps1` (Windows) or `./install.sh` (Linux/macOS) again. |
| A video stopped working after a YouTube change | Update yt-dlp: `runtime/python/python -m ytdlp_app.portable update-ytdlp`. |
| Change download folders | Type `s` at the URL prompt and pick the folder to change. |
| Change the interface language | Type `s` at the URL prompt and pick "Interface language". |
| Force re-download | Delete the relevant archive file in `archives/`. |
| Archive stopped with "YouTube is temporarily blocking requests" | Wait a few hours and enter the same URL again; it resumes. Consider raising the archive waits (`s` → *Archive mode waits*) or using a proxy. |
| Deno warning appears | Run `install.ps1` / `./install.sh` again (macOS: `brew install deno`). |

## License
See [LICENSE](LICENSE) for details.

---

## yt-dlp Downloader (taşınabilir) — Türkçe

yt-dlp ve ffmpeg üzerine kurulu taşınabilir bir konsol uygulaması. Windows, Linux ve macOS üzerinde çalışır; Windows ve Linux'ta tamamen taşınabilirdir (bkz. *Taşınabilir çalışma ortamı*). İnteraktif klasör kurulumu, MP4/MP3/Arşiv mod seçimi, playlist yönetimi, tekrarları engelleyen arşiv sistemi, renkli konsol çıktısı ve detaylı loglama özellikleri sunar.

## Özellikler
- **Tamamen taşınabilir (Windows, Linux)**: İlk açılışta Python, yt-dlp, ffmpeg ve Deno *program klasörünün içine* indirilir. Yönetici izni gerekmez, sisteme hiçbir şey kurulmaz; klasörü USB belleğe veya başka bir bilgisayara kopyala, çalışmaya devam eder
- **Otomatik güncelleme**: Her açılışta GitHub'dan sessiz güncelleme kontrolü
- **İnteraktif menüler**: MP4/MP3/Arşiv modu, playlist/tek video seçimi ve kalite profilleri
- **Arşiv modu**: Bir kanalın tamamını (veya tek bir videoyu) açıklama, altyazı, kapak resmi ve metadata ile birlikte, hız sınırına ve IP ban'ına takılmayacak tempoda arşivler
- **Ayarlar menüsü**: Dil, indirme klasörleri, vekil sunucu, hız sınırı, ses formatı ve altyazıları uygulama içinden değiştir — URL isteminde `s` yaz
- **Renkli çıktı**: Söz dizimi vurgulu konsol çıktısı (indirmeler yeşil, hatalar kırmızı, uyarılar sarı, vb.)
- **Atlama raporu**: Playlist öğelerinin neden atlandığını açıklar (özel, bölge kısıtı, yaş kısıtı, üyelik gerekli, vb.)
- **Oturum sürekliliği**: Tek oturumda yeniden başlatmadan birden fazla URL indir

### Nasıl çalışır
1. `Run.bat` (Windows) veya `./run.sh` (Linux/macOS) ile başlat. Windows ve Linux'ta ilk açılış taşınabilir çalışma ortamını `runtime/` içine indirir (bir kereye mahsus; Windows'ta yaklaşık 150 MB, Linux'ta 220 MB); macOS'ta Python, ffmpeg ve Deno Homebrew ile, yt-dlp `.venv` içine kurulur.
2. İlk seferde video/müzik klasörlerini sorar (varsayılan: program klasöründeki `downloads/Videos` ve `downloads/Music`). Tercihler `config.json` içine kaydedilir.
3. Her oturumda: URL gir, Video (MP4), Ses (MP3) veya Arşiv (bkz. *Arşiv modu*) seç, playlist URL'si için tüm liste mi tek video mu karar ver, MP4 ise profil seç.
4. yt-dlp devam/tekrar dene bayraklarıyla (`--continue`, `--retries infinite`, `--fragment-retries infinite`) çalışır; arşiv dosyaları tekrar indirmeyi engeller; konsol çıktısı log'a yazılır.
5. Playlist indirirken atlananlar için sebep yoklama (özel, bölge kısıtı, yaş kısıtı, üyelik gerekli, telif hakkı, vb.) yapılır ve ekrana yazılır.
6. İndirme bitince aynı oturumda hemen yeni URL indirebilirsin.

### Çıktı düzeni
| Mod | Tür | Çıktı Yolu | Arşiv Dosyası |
|-----|-----|------------|---------------|
| MP4 | Playlist | `<Videos>/yt-dlp/<playlist_title>/<index> - <title>.mp4` | `archives/playlist_<playlist_id>_mp4.txt` |
| MP4 | Tek video | `<Videos>/Downloaded Videos/<title>.mp4` | `archives/single_videos_mp4.txt` |
| MP3 | Playlist | `<Music>/yt-dlp/<playlist_title>/<index> - <title>.mp3` | `archives/playlist_<playlist_id>_mp3.txt` |
| MP3 | Tek parça | `<Music>/Downloaded Music/<title>.mp3` | `archives/single_audios_mp3.txt` |
| Arşiv | Kanal | `<Videos>/yt-dlp/<channel>/<upload_date> - <title> [<id>]/<title>.mkv` | `archives/channel_<channel_id>_archive.txt` |
| Arşiv | Playlist | yukarıdakiyle aynı | `archives/playlist_<playlist_id>_archive.txt` |
| Arşiv | Tek video | yukarıdakiyle aynı | `archives/single_videos_archive.txt` |

- Loglar: `logs/yt-dlp_<mode>_<playlist|single>_<timestamp>.log`

### MP4 profilleri
1. **Uyumluluk** (iki aşamalı indirme):
   - Aşama 1: avc1 video + mp4a ses mevcutsa kayıpsız MP4 birleştirme dener
   - Aşama 2: Kalan öğeleri indirip MP4'e yeniden kodlar
2. **Kalite** (yeniden kodlama yok):
   - En iyi video + en iyi sesi transkod yapmadan indirir
   - Kapsayıcı seçimi:
     - **Güvenli (MKV)**: Önerilen, her zaman çalışır
     - **MP4 remux**: Codec uyumsuzsa hata verebilir

### MP3 modu
- Mevcut en iyi sesi indirir (`bestaudio/best`)
- En yüksek kalitede MP3'e dönüştürür (`--audio-quality 0`)
- Metadata ve thumbnail (JPG'ye dönüştürülmüş) gömer

### Arşiv modu
Silinme riski olan bir kanalı korumak için. Mod olarak **Arşiv**'i seç ve bir kanal URL'si (`https://www.youtube.com/@isim`, `/channel/UC...` ya da `/@isim/videos` gibi bir sekme), bir playlist veya tek bir video gir.

- **Her video için saklananlar** (her biri kendi klasöründe): video (çözünürlük sınırına kadar en iyi kalite, varsayılan 1080p; bölümler ve metadata gömülü MKV), `.description`, `.info.json`, kapak resmi ve Türkçe/İngilizce yüklenmiş + otomatik altyazılar (`.srt`'ye dönüştürülmüş). YouTube'un makine çevirileri atlanır (kanal yüklemediyse İngilizce bir videoya Türkçe altyazı gelmez); yalnızca videoda gerçekten var olan altyazılar saklanır.
- **Kanal URL'si kanalın tamamını arşivler.** yt-dlp Videos, Shorts ve Live sekmelerini iç içe playlist olarak döndürür; hepsi indirilir ve "tüm liste mi bu video mu" sorusu sorulmaz.
- **Arşiv dosyası gerçek kanal kimliğine göre adlandırılır** (`channel_UC..._archive.txt`). Böylece aynı kanalın handle URL'si, `/channel/` URL'si ve sekme URL'leri, handle değişse bile aynı arşivden devam eder. Kimlik, boyut tahminini de besleyen aynı listeden okunur (ayrı bir istek yok); liste engel dışı bir sebeple başarısız olursa URL'deki kimlik kullanılır.
- **Tempo** (varsayılanlar): istekler arası 1.5 sn, videolar arası 15–45 sn (rastgele), her altyazıdan önce 5 sn, sonsuz yerine 10 deneme. Bekleme süreleri `s` → *Arsiv modu bekleme sureleri* ile değiştirilir ve `config.json` içinde `settings.archive` altında saklanır. Hız sınırın ve proxy ayarın bu modda da geçerlidir.
- **Ban koruması**: yt-dlp `HTTP Error 429` ya da YouTube'un *"Sign in to confirm you're not a bot"* mesajını bildirirse indirme hemen durdurulur, olay log'a (`[BAN-GUARD]`) yazılır ve **birkaç saat bekleyip aynı URL'yi tekrar vermen, indirmenin kaldığı yerden devam edeceği** söylenir. Bir öğe ancak tüm parçaları kaydedildiğinde arşiv dosyasına girer; yarım kalan hiçbir şey sonraki çalıştırmada atlanmaz.
- İstek sayısını düşük tutmak için arşiv modu bir kanalı ya da playlist'i yalnızca bir kez listeler (boyut tahmini ve kanal kimliği için; istekler arası bekleme uygulanır) ve sonrasında atlanan öğeleri yoklamaz (atlama raporu yalnızca MP4/MP3'te). Tek video için liste isteği yapılmaz.

### Boyut tahmini ve çözünürlük sınırı
**Playlist ya da kanal indirmeden önce** (MP4, MP3 ve arşiv modları) uygulama bir boyut tahmini gösterir ve boş disk alanını kontrol eder. Listeyi bir kez okur (video başına ek istek yok) ve her videonun süresini tipik bir bit hızıyla çarpar; bu yüzden rakamlar bilerek yüksek taraftadır ve **ölçüm değil tahmindir**:

| Satır | Varsayılan bit hızı |
|-------|---------------------|
| 1080p | 6000 kbit/sn video + 160 kbit/sn ses |
| 1440p (en fazla) | 12000 + 160 |
| 2160p (en fazla) | 30000 + 160 |

- 1440p ve 2160p "en fazla" diye etiketlenir: düz listede çözünürlük yoktur ve o çözünürlükte olmayan video daha küçük iner.
- **Gereken alan** = seçilen çözünürlüğün toplamı + en büyük tek video; birleştirme, yeniden kodlama ve dönüştürme sırasında kaynak ve sonuç diskte birlikte durur.
- Arşivde kayıtlı videolar hariç tutulur. Süresi olmayan video (Shorts, canlı) 180 sn (Shorts) ya da bilinen sürelerin medyanı kabul edilir; ekranda kaç videonun varsayımla hesaplandığı yazar. Hiçbir süre bilinmiyorsa tahmin atlanır ve indirme devam eder.
- **MP3** tek rakam gösterir; ses biçimin ve kaliten esas alınır (`mp3` kalite 0 yaklaşık 245 kbit/sn; `flac` ve `wav` çok daha büyük).
- Boyutlar 1024 tabanlıdır (KiB/MiB/GiB), Windows Gezgini gibi.
- **Yer yetmiyor mu?** Uyarılır ve *Yine de devam et / İptal* sorulur. İndirme asla engellenmez.
- **Süre:** kısa (~5 sn) bir hız testi (`speed.cloudflare.com`, proxy'nden geçer; SOCKS proxy'de atlanır) boyutu indirme süresine çevirir. YouTube'u değil hattını ölçer ve IP adresini o sunucuya gönderir. Başarısız olursa süre sütunu bunu söyler, başka bir şey değişmez. Arşiv modu ayrıca yalnızca videolar arası beklemelerin **en az** ne kadar süreceğini gösterir.
- Tek video için tahmin yapılmaz (ek istek gerekirdi).

**Çözünürlük sınırı.** Tahminden sonra MP4 ve arşiv indirmeleri için (tek video dahil) en yüksek çözünürlük sorulur: 1080p, 1440p, 2160p ya da sınırsız. Kayıtlı varsayılan işaretlidir; başka bir seçenek seçersen yalnızca bu indirme için kullanabilir ya da yeni varsayılan olarak kaydedebilirsin. Sınır tüm video format seçicilerine (`[height<=N]`, yedek dahil) uygulanır. Uyumluluk MP4 profili 1080p'de kalır: YouTube H.264'ü yaklaşık 1080p'ye kadar verir, daha yükseği yavaşça yeniden kodlanırdı. Varsayılanlar: arşiv 1080p, MP4 sınırsız (eskisi gibi). `s` → *Video cozunurluk siniri* / *Arsiv cozunurluk siniri* ile ya da `config.json`'da (`settings.video.max_height`, `settings.archive.max_height`: `1080`, `1440`, `2160` ya da `null`) değiştirilir.

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
- **Doğrulanmış indirmeler**: her dosya açılmadan önce `runtime.lock` içinde sabitlenmiş SHA-256 ile karşılaştırılır; uyuşmazsa kurulum durur. Bir uygulama güncellemesi bir sürümü değiştirirse, sonraki açılış yalnızca o bileşeni yeniler.
- **yt-dlp güncel kalır**: açılışta haftada bir otomatik güncellenir (YouTube değişiklikleri eski sürümleri bozar). İnternet yoksa kurulu sürümle devam edilir. Hemen güncellemek için: `runtime/python/python -m ytdlp_app.portable update-ytdlp` (Windows'ta `runtime\python\python.exe`); `... status` neyin kurulu olduğunu gösterir.
- **Klasörü taşımak**: program klasörünün içindeki klasörler `config.json`'a göreli yazılır; indirmeler, arşivler ve ayarlar klasörle birlikte taşınır.
- Kurulum sonrası disk kullanımı: Windows'ta yaklaşık 360 MB, Linux'ta 530 MB (Linux ffmpeg derlemesi statik bağlıdır).
- Eski sürümden yükseltme: yeni başlatıcı artık `.venv`'i ve winget ile kurulan Python/ffmpeg/Deno'yu kullanmaz. `.venv` klasörü silinebilir; sistem paketleri başka bir şey kullanmıyorsa kaldırılabilir. `config.json`'daki mevcut indirme klasörleri olduğu gibi korunur.

### Ayarlar ve durum
| Dosya | Açıklama |
|-------|----------|
| `config.json` | `app`, `videos_dir`, `music_dir`, `saved_at`, `language` ve gelişmiş `settings` (`settings.archive` dahil) değerlerini saklar. Program klasörünün içindeki klasörler göreli saklanır. Yeniden yapılandırmak için sil. |
| `archives/*.txt` | `--download-archive` için indirme arşivleri. Yeniden indirmeyi zorlamak için sil. |
| `logs/*.log` | Zaman damgalı tam komut çıktısı. Sorun giderme için kullanışlı. |
| `app_version.txt` | Otomatik güncelleme için mevcut sürümü takip eder. |

### Bu klasördeki dosyalar
| Dosya | Açıklama |
|-------|----------|
| `Run.bat` / `run.sh` | Tek tıkla başlatma (Windows / Linux, macOS). Güncelleme kontrolü yapar, taşınabilir çalışma ortamını kurar veya yeniler, uygulamayı başlatır. |
| `install.ps1` / `install.sh` | Taşınabilir çalışma ortamını `runtime/` içine kurar (macOS: Homebrew + `.venv`). Tekrar çalıştırmak güvenlidir. |
| `update.ps1` / `update.sh` | Otomatik güncelleyici. GitHub'dan yeni sürümleri indirir; `config.json`, `archives/`, `logs/`, `runtime/`, `cache/` ve `downloads/` korunur. |
| `runtime.lock` | Taşınabilir Python, ffmpeg ve Deno için sabitlenmiş adresler ve SHA-256 değerleri. |
| `downloader.py` | `ytdlp_app.app.run()` fonksiyonunu çağıran giriş noktası. |
| `ytdlp_app/` | Modüler bileşenli Python paketi (aşağıya bakın). |

### ytdlp_app/ modülleri
| Modül | Açıklama |
|-------|----------|
| `app.py` | Uygulama giriş noktası ve yapılandırma yükleme |
| `session.py` | Ana döngüyü yöneten interaktif oturum yöneticisi |
| `config.py` | Yapılandırma yükleme/kaydetme, interaktif klasör kurulumu |
| `ui.py` | Stilize paneller ve menüler sunan konsol arayüzü |
| `yt_dlp.py` | yt-dlp argümanlarını oluşturan CommandBuilder sınıfı |
| `exec.py` | Çıktı akışı, loglama ve 429/bot ban koruması ile komut yürütme |
| `playlist.py` | Playlist ve kanal algılama, düz liste (kanal sekmeleri düzleştirilir, kanal kimliği), arşiv okuma |
| `estimate.py` | Boyut, disk alanı ve süre tahmini (saf hesap) |
| `speedtest.py` | Kısa bağlantı hızı ölçümü |
| `preflight.py` | Liste koruması, tahmin tablosu, çözünürlük sorusu ve boş alan kontrolü |
| `skip_probe.py` | Atlanan öğeleri atlama nedenini belirlemek için sorgular |
| `logging_utils.py` | Renkli çıktı ile loglama yardımcıları |
| `system.py` | yt-dlp, ffmpeg ve Deno'nun yerini bulur |
| `portable.py` | Taşınabilir çalışma ortamı kurulumu (`python -m ytdlp_app.portable ensure / update-ytdlp / status`) |
| `models.py` | Yollar, yapılandırma, girdiler ve indirme planları için veri sınıfları |

### Gereksinimler
- **Windows**: 64 bit Windows 10 (1803 veya üzeri) ya da Windows 11. Başka bir şey gerekmez.
- **Linux**: glibc'li x86_64 veya aarch64 (Alpine/musl değil), ayrıca `curl` veya `wget`, `tar` ve `sha256sum` (hemen her dağıtımda bulunur).
- **macOS**: Homebrew; Python 3.11+ yoksa onunla kurulur.
- İlk açılış ve indirmeler için internet bağlantısı

### Sorun giderme
| Sorun | Çözüm |
|-------|-------|
| İlk kurulum başarısız | İnternet bağlantısını kontrol edip `Run.bat` / `./run.sh`'i yeniden çalıştır; kaldığı yerden devam eder, yalnızca eksikleri indirir. Yönetici izni gerekmez. |
| "Checksum mismatch" | İndirilen dosya bozulmuş ya da değiştirilmiş ve silindi. Tekrar dene; sürerse bildir. |
| yt-dlp/ffmpeg bulunamıyor | `install.ps1` (Windows) veya `./install.sh` (Linux/macOS) dosyasını tekrar çalıştır. |
| YouTube değişikliğinden sonra video inmiyor | yt-dlp'yi güncelle: `runtime/python/python -m ytdlp_app.portable update-ytdlp`. |
| İndirme klasörlerini değiştir | URL isteminde `s` yaz ve değiştirmek istediğin klasörü seç. |
| Arayüz dilini değiştir | URL isteminde `s` yaz ve "Arayuz dili" seçeneğini seç. |
| Yeniden indirmeyi zorla | `archives/` içindeki ilgili arşiv dosyasını sil. |
| Arşiv "YouTube istekleri gecici olarak engelliyor" ile durdu | Birkaç saat bekle ve aynı URL'yi tekrar gir; kaldığı yerden devam eder. Arşiv bekleme sürelerini artırmayı (`s` → *Arsiv modu bekleme sureleri*) veya proxy kullanmayı düşün. |
| Deno uyarısı görünüyor | `install.ps1` / `./install.sh`'i yeniden çalıştır (macOS: `brew install deno`). |

### Lisans
Detaylar için [LICENSE](LICENSE) dosyasına bakın.
