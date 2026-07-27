# yt-dlp Downloader (portable)

A portable cross-platform console application that wraps yt-dlp and ffmpeg. Runs on Windows, Linux, and macOS. Features interactive folder setup, MP4/MP3 mode selection, playlist handling, download archives to prevent duplicates, colorized console output, and detailed logging.

## Features
- **One-click setup**: Automatically installs Python 3.11+, yt-dlp, ffmpeg, and Deno (winget on Windows; apt/dnf/pacman/brew elsewhere)
- **Auto-update**: Silent update checks from GitHub releases on each launch
- **Interactive prompts**: Choose MP4/MP3 mode, playlist vs single video, and quality profiles
- **Colorized output**: Syntax-highlighted console output (downloads in green, errors in red, warnings in yellow, etc.)
- **Skip reporting**: Explains why playlist items were skipped (private, region-blocked, age-restricted, members-only, etc.)
- **Session continuity**: Download multiple URLs in a single session without restarting

## How it works
1. Launch `Run.bat` (Windows) or `./run.sh` (Linux/macOS). First run installs Python 3.11+, yt-dlp inside `.venv`, ffmpeg, and Deno through your platform's package manager.
2. You are asked once for base download folders (defaults: `Videos` and `Music`). Choices are saved to `config.json`.
3. Each session: enter a URL, choose Video (MP4) or Audio (MP3), decide whether a playlist URL should grab the whole list or only that video, then pick the MP4 profile when relevant.
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

## Config and state
| File | Description |
|------|-------------|
| `config.json` | Stores `app`, `videos_dir`, `music_dir`, `saved_at`. Delete to reconfigure. |
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
| `exec.py` | Command execution with output streaming and logging |

| `playlist.py` | Playlist detection, entry fetching, archive reading |
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
| Change download folders | Delete `config.json` and relaunch. |
| Force re-download | Delete the relevant archive file in `archives/`. |
| Deno warning appears | Install Deno: `winget install DenoLand.Deno` or rerun `install.ps1`. |

## License
See [LICENSE](LICENSE) for details.

---

## yt-dlp Downloader (taşınabilir) — Türkçe

yt-dlp ve ffmpeg üzerine kurulu taşınabilir bir konsol uygulaması. Windows, Linux ve macOS üzerinde çalışır. İnteraktif klasör kurulumu, MP4/MP3 mod seçimi, playlist yönetimi, tekrarları engelleyen arşiv sistemi, renkli konsol çıktısı ve detaylı loglama özellikleri sunar.

## Özellikler
- **Tek tıkla kurulum**: Python 3.11+, yt-dlp, ffmpeg ve Deno otomatik kurulur (Windows'ta winget; diğer sistemlerde apt/dnf/pacman/brew)
- **Otomatik güncelleme**: Her açılışta GitHub'dan sessiz güncelleme kontrolü
- **İnteraktif menüler**: MP4/MP3 modu, playlist/tek video seçimi ve kalite profilleri
- **Renkli çıktı**: Söz dizimi vurgulu konsol çıktısı (indirmeler yeşil, hatalar kırmızı, uyarılar sarı, vb.)
- **Atlama raporu**: Playlist öğelerinin neden atlandığını açıklar (özel, bölge kısıtı, yaş kısıtı, üyelik gerekli, vb.)
- **Oturum sürekliliği**: Tek oturumda yeniden başlatmadan birden fazla URL indir

### Nasıl çalışır
1. `Run.bat` (Windows) veya `./run.sh` (Linux/macOS) ile başlat. İlk çalıştırmada sisteminin paket yöneticisiyle Python 3.11+, `.venv` içinde yt-dlp, ffmpeg ve Deno kurulur.
2. İlk seferde video/müzik klasörlerini sorar (varsayılan: `Videos`, `Music`). Tercihler `config.json` içine kaydedilir.
3. Her oturumda: URL gir, Video (MP4) veya Ses (MP3) seç, playlist URL'si için tüm liste mi tek video mu karar ver, MP4 ise profil seç.
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

### Ayarlar ve durum
| Dosya | Açıklama |
|-------|----------|
| `config.json` | `app`, `videos_dir`, `music_dir`, `saved_at` değerlerini saklar. Yeniden yapılandırmak için sil. |
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
| `exec.py` | Çıktı akışı ve loglama ile komut yürütme |

| `playlist.py` | Playlist algılama, öğe çekme, arşiv okuma |
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
| İndirme klasörlerini değiştir | `config.json` dosyasını sil ve yeniden başlat. |
| Yeniden indirmeyi zorla | `archives/` içindeki ilgili arşiv dosyasını sil. |
| Deno uyarısı görünüyor | Deno kur: `winget install DenoLand.Deno` veya `install.ps1`'i yeniden çalıştır. |

### Lisans
Detaylar için [LICENSE](LICENSE) dosyasına bakın.
