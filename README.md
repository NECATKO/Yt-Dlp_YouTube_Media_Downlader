# yt-dlp Downloader (portable)

A portable cross-platform console application that wraps yt-dlp and ffmpeg. Runs on Windows, Linux, and macOS. Features interactive folder setup, MP4/MP3/Archive mode selection, playlist handling, download archives to prevent duplicates, colorized console output, and detailed logging.

## Features
- **One-click setup**: Automatically installs Python 3.11+, yt-dlp, ffmpeg, and Deno (winget on Windows; apt/dnf/pacman/brew elsewhere)
- **Auto-update**: Silent update checks from GitHub releases on each launch
- **Interactive prompts**: Choose MP4/MP3/Archive mode, playlist vs single video, and quality profiles
- **Archive mode**: Preserve a whole channel (or a single video) with its description, subtitles, thumbnail and metadata, paced to avoid rate limits and IP bans
- **Settings menu**: Change the language, download folders, proxy, speed limit, audio format, and subtitles from inside the app — type `s` at the URL prompt
- **Colorized output**: Syntax-highlighted console output (downloads in green, errors in red, warnings in yellow, etc.)
- **Skip reporting**: Explains why playlist items were skipped (private, region-blocked, age-restricted, members-only, etc.)
- **Session continuity**: Download multiple URLs in a single session without restarting

## How it works
1. Launch `Run.bat` (Windows) or `./run.sh` (Linux/macOS). First run installs Python 3.11+, yt-dlp inside `.venv`, ffmpeg, and Deno through your platform's package manager.
2. You are asked once for base download folders (defaults: `Videos` and `Music`). Choices are saved to `config.json`.
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

- **What is kept, per video** (each in its own folder): the video (best quality up to 1080p, merged into MKV with chapters and metadata embedded), `.description`, `.info.json`, the thumbnail, and uploaded plus auto-generated subtitles in Turkish and English converted to `.srt`.
- **A channel URL archives the whole channel.** yt-dlp returns the Videos, Shorts and Live tabs as nested playlists; all of them are downloaded, and the "whole playlist or this video" question is skipped.
- **The archive file is keyed by the real channel id** (`channel_UC..._archive.txt`), so the handle URL, the `/channel/` URL and any tab URL of the same channel all resume one archive, even if the handle changes. Looking the id up costs one request; if it fails for a reason other than a block, the id in the URL is used instead.
- **Pacing** (defaults): 1.5 s between requests, 15–45 s (random) between videos, 5 s before each subtitle download, 10 retries instead of infinite. The waits can be changed with `s` → *Archive mode waits* and are stored under `settings.archive` in `config.json`. Your speed limit and proxy still apply.
- **Ban protection**: if yt-dlp reports `HTTP Error 429` or YouTube's *"Sign in to confirm you're not a bot"*, the download is stopped immediately, the event is written to the log (`[BAN-GUARD]`), and you are told to **wait a few hours and enter the same URL again: it resumes where it left off.** Items only enter the archive file once every part of them was saved, so nothing half-finished is skipped on the next run.
- To keep request volume low, archive mode does not fetch the playlist listing or probe skipped items afterwards (the skip report is MP4/MP3 only).

## Config and state
| File | Description |
|------|-------------|
| `config.json` | Stores `app`, `videos_dir`, `music_dir`, `saved_at`, `language` and the advanced `settings` (including `settings.archive`). Delete to reconfigure. |
| `archives/*.txt` | Download archives for `--download-archive`. Delete to force re-download. |
| `logs/*.log` | Full command output with timestamps. Useful for troubleshooting. |
| `app_version.txt` | Tracks current version for auto-update. |

## Files in this folder
| File | Description |
|------|-------------|
| `Run.bat` | One-click start. Runs silent update check, installs deps if needed, launches app. |
| `install.ps1` | Installs Python, ffmpeg, Deno via winget. Creates `.venv` with yt-dlp. |
| `update.ps1` | Auto-updater. Downloads new releases from GitHub, preserves user data. |
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
| `playlist.py` | Playlist and channel detection, channel id lookup, entry fetching, archive reading |
| `skip_probe.py` | Probes skipped items to determine skip reason |
| `logging_utils.py` | Logging utilities with colorized output |
| `system.py` | Checks for ffmpeg, yt-dlp, deno availability |
| `models.py` | Data classes for paths, config, entries, and download plans |

## Requirements
- Python 3.11 or newer
- Windows 10/11 with winget (Windows App Installer), or Linux/macOS with apt/dnf/pacman/brew
- Internet connection for installation and downloads

## Troubleshooting
| Problem | Solution |
|---------|----------|
| Install fails | Run `Run.bat` as Administrator (Windows). Ensure your package manager and internet access work. |
| yt-dlp/ffmpeg not found | Rerun `install.ps1` (Windows) or `install.sh` (Linux/macOS), or open a new terminal after installation. |
| Change download folders | Type `s` at the URL prompt and pick the folder to change. |
| Change the interface language | Type `s` at the URL prompt and pick "Interface language". |
| Force re-download | Delete the relevant archive file in `archives/`. |
| Archive stopped with "YouTube is temporarily blocking requests" | Wait a few hours and enter the same URL again; it resumes. Consider raising the archive waits (`s` → *Archive mode waits*) or using a proxy. |
| Deno warning appears | Install Deno: `winget install DenoLand.Deno` or rerun `install.ps1`. |

## License
See [LICENSE](LICENSE) for details.

---

## yt-dlp Downloader (taşınabilir) — Türkçe

yt-dlp ve ffmpeg üzerine kurulu taşınabilir bir konsol uygulaması. Windows, Linux ve macOS üzerinde çalışır. İnteraktif klasör kurulumu, MP4/MP3/Arşiv mod seçimi, playlist yönetimi, tekrarları engelleyen arşiv sistemi, renkli konsol çıktısı ve detaylı loglama özellikleri sunar.

## Özellikler
- **Tek tıkla kurulum**: Python 3.11+, yt-dlp, ffmpeg ve Deno otomatik kurulur (Windows'ta winget; diğer sistemlerde apt/dnf/pacman/brew)
- **Otomatik güncelleme**: Her açılışta GitHub'dan sessiz güncelleme kontrolü
- **İnteraktif menüler**: MP4/MP3/Arşiv modu, playlist/tek video seçimi ve kalite profilleri
- **Arşiv modu**: Bir kanalın tamamını (veya tek bir videoyu) açıklama, altyazı, kapak resmi ve metadata ile birlikte, hız sınırına ve IP ban'ına takılmayacak tempoda arşivler
- **Ayarlar menüsü**: Dil, indirme klasörleri, vekil sunucu, hız sınırı, ses formatı ve altyazıları uygulama içinden değiştir — URL isteminde `s` yaz
- **Renkli çıktı**: Söz dizimi vurgulu konsol çıktısı (indirmeler yeşil, hatalar kırmızı, uyarılar sarı, vb.)
- **Atlama raporu**: Playlist öğelerinin neden atlandığını açıklar (özel, bölge kısıtı, yaş kısıtı, üyelik gerekli, vb.)
- **Oturum sürekliliği**: Tek oturumda yeniden başlatmadan birden fazla URL indir

### Nasıl çalışır
1. `Run.bat` (Windows) veya `./run.sh` (Linux/macOS) ile başlat. İlk çalıştırmada sisteminin paket yöneticisiyle Python 3.11+, `.venv` içinde yt-dlp, ffmpeg ve Deno kurulur.
2. İlk seferde video/müzik klasörlerini sorar (varsayılan: `Videos`, `Music`). Tercihler `config.json` içine kaydedilir.
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

- **Her video için saklananlar** (her biri kendi klasöründe): video (1080p'ye kadar en iyi kalite, bölümler ve metadata gömülü MKV), `.description`, `.info.json`, kapak resmi ve Türkçe/İngilizce yüklenmiş + otomatik altyazılar (`.srt`'ye dönüştürülmüş).
- **Kanal URL'si kanalın tamamını arşivler.** yt-dlp Videos, Shorts ve Live sekmelerini iç içe playlist olarak döndürür; hepsi indirilir ve "tüm liste mi bu video mu" sorusu sorulmaz.
- **Arşiv dosyası gerçek kanal kimliğine göre adlandırılır** (`channel_UC..._archive.txt`). Böylece aynı kanalın handle URL'si, `/channel/` URL'si ve sekme URL'leri, handle değişse bile aynı arşivden devam eder. Kimliği öğrenmek tek istek gerektirir; engel dışı bir sebeple başarısız olursa URL'deki kimlik kullanılır.
- **Tempo** (varsayılanlar): istekler arası 1.5 sn, videolar arası 15–45 sn (rastgele), her altyazıdan önce 5 sn, sonsuz yerine 10 deneme. Bekleme süreleri `s` → *Arsiv modu bekleme sureleri* ile değiştirilir ve `config.json` içinde `settings.archive` altında saklanır. Hız sınırın ve proxy ayarın bu modda da geçerlidir.
- **Ban koruması**: yt-dlp `HTTP Error 429` ya da YouTube'un *"Sign in to confirm you're not a bot"* mesajını bildirirse indirme hemen durdurulur, olay log'a (`[BAN-GUARD]`) yazılır ve **birkaç saat bekleyip aynı URL'yi tekrar vermen, indirmenin kaldığı yerden devam edeceği** söylenir. Bir öğe ancak tüm parçaları kaydedildiğinde arşiv dosyasına girer; yarım kalan hiçbir şey sonraki çalıştırmada atlanmaz.
- İstek sayısını düşük tutmak için arşiv modu playlist listesini çekmez ve sonrasında atlanan öğeleri yoklamaz (atlama raporu yalnızca MP4/MP3'te).

### Ayarlar ve durum
| Dosya | Açıklama |
|-------|----------|
| `config.json` | `app`, `videos_dir`, `music_dir`, `saved_at`, `language` ve gelişmiş `settings` (`settings.archive` dahil) değerlerini saklar. Yeniden yapılandırmak için sil. |
| `archives/*.txt` | `--download-archive` için indirme arşivleri. Yeniden indirmeyi zorlamak için sil. |
| `logs/*.log` | Zaman damgalı tam komut çıktısı. Sorun giderme için kullanışlı. |
| `app_version.txt` | Otomatik güncelleme için mevcut sürümü takip eder. |

### Bu klasördeki dosyalar
| Dosya | Açıklama |
|-------|----------|
| `Run.bat` | Tek tıkla başlatma. Sessiz güncelleme kontrolü, gerekirse bağımlılık kurulumu, uygulamayı başlatır. |
| `install.ps1` | Python, ffmpeg, Deno'yu winget ile kurar. yt-dlp ile `.venv` oluşturur. |
| `update.ps1` | Otomatik güncelleyici. GitHub'dan yeni sürümleri indirir, kullanıcı verilerini korur. |
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
| `playlist.py` | Playlist ve kanal algılama, kanal kimliği sorgulama, öğe çekme, arşiv okuma |
| `skip_probe.py` | Atlanan öğeleri atlama nedenini belirlemek için sorgular |
| `logging_utils.py` | Renkli çıktı ile loglama yardımcıları |
| `system.py` | ffmpeg, yt-dlp, deno kullanılabilirliğini kontrol eder |
| `models.py` | Yollar, yapılandırma, girdiler ve indirme planları için veri sınıfları |

### Gereksinimler
- Python 3.11 veya üzeri
- Winget (Windows Uygulama Yükleyicisi) ile Windows 10/11, veya apt/dnf/pacman/brew ile Linux/macOS
- Kurulum ve indirmeler için internet bağlantısı

### Sorun giderme
| Sorun | Çözüm |
|-------|-------|
| Kurulum başarısız | `Run.bat`'i Yönetici olarak çalıştır (Windows). Paket yöneticisi ve internet erişimini doğrula. |
| yt-dlp/ffmpeg bulunamıyor | `install.ps1` (Windows) veya `install.sh` (Linux/macOS) dosyasını tekrar çalıştır, ya da kurulumdan sonra yeni bir terminal aç. |
| İndirme klasörlerini değiştir | URL isteminde `s` yaz ve değiştirmek istediğin klasörü seç. |
| Arayüz dilini değiştir | URL isteminde `s` yaz ve "Arayuz dili" seçeneğini seç. |
| Yeniden indirmeyi zorla | `archives/` içindeki ilgili arşiv dosyasını sil. |
| Arşiv "YouTube istekleri gecici olarak engelliyor" ile durdu | Birkaç saat bekle ve aynı URL'yi tekrar gir; kaldığı yerden devam eder. Arşiv bekleme sürelerini artırmayı (`s` → *Arsiv modu bekleme sureleri*) veya proxy kullanmayı düşün. |
| Deno uyarısı görünüyor | Deno kur: `winget install DenoLand.Deno` veya `install.ps1`'i yeniden çalıştır. |

### Lisans
Detaylar için [LICENSE](LICENSE) dosyasına bakın.
