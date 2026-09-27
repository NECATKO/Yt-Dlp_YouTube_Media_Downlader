# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Fully portable on Windows and Linux.** The first launch downloads a relocatable Python, ffmpeg and Deno into `runtime/` inside the program folder and installs yt-dlp into that Python. Nothing is installed system-wide, no administrator rights or sudo are needed, and the folder keeps working after being moved or copied to another machine or a USB stick.
  - Every download is verified against the SHA-256 pinned in the new `runtime.lock`; a changed pin replaces just that component on the next launch.
  - yt-dlp is upgraded automatically once a week at launch (failures are non-fatal, so offline launches work); `python -m ytdlp_app.portable update-ytdlp` upgrades it on demand and `status` shows what is installed.
  - yt-dlp's and Deno's caches are kept in `cache/` instead of the user profile.
  - New installs download into `downloads/` next to the program, and any folder inside the program folder is stored relative in `config.json`, so it follows the folder.
- **Archive mode** — a third option next to MP4 and MP3, for preserving a channel that may be deleted. For every video it keeps the video (up to 1080p, merged into MKV with chapters and metadata), the description, the info JSON, the thumbnail, and uploaded plus auto-generated Turkish/English subtitles converted to SRT, each video in its own folder under `<Videos>/yt-dlp/<channel>/`.
  - A channel URL (`/@handle`, `/channel/UC…`, `/c/…`, `/user/…`, or one of its tabs) is archived whole: yt-dlp's nested Videos/Shorts/Live playlists are all downloaded, and the playlist-or-video question is skipped.
  - The download archive is `archives/channel_<channel_id>_archive.txt`, keyed by the real channel id (looked up with one flat request), so every URL form of a channel resumes the same archive.
  - Paced to stay under YouTube's limits: `--sleep-requests 1.5`, `--sleep-interval 15`, `--max-sleep-interval 45`, `--sleep-subtitles 5`, and 10 retries instead of infinite. The waits are editable from the settings menu (*Archive mode waits*) and stored under `settings.archive` in `config.json`; the speed limit and proxy still apply.
  - **Ban guard**: when yt-dlp reports HTTP 429 or YouTube's "Sign in to confirm you're not a bot", the download is stopped at once, the event is logged as `[BAN-GUARD]`, and the user is told to wait a few hours and enter the same URL again to resume. The same check covers the channel id lookup.
  - Archive mode sends no playlist-listing or skip-probe requests, and does not pass `--ignore-errors`, so an item whose subtitles or thumbnail failed is retried on the next run instead of being recorded as done.
- **In-app settings menu**: type `s` at the URL prompt (or pick *Settings* after a download) to change the interface language, the download folders, the proxy, the speed limit, the parallel fragment count, the audio format and quality, and the subtitle options. Every change is written to `config.json` immediately, and a language switch applies without a restart.
- Advanced settings are now honored at runtime. They live under the `"settings"` key of `config.json`; a config written before this change has no such key and keeps the previous defaults exactly, so nothing changes until you opt in. See `settings.example.json` for the full shape.
- The URL prompt validates its input and asks again instead of passing anything straight to yt-dlp — most concretely, a URL starting with `-` is no longer read as a command-line flag.
- Startup banner showing the application name and version.
- Test coverage for `CommandBuilder`, the skip-reason prober, and the settings menu, none of which had any.

### Fixed
- **YouTube subtitles could not be downloaded at all.** yt-dlp requests every YouTube subtitle with browser impersonation, which needs the optional `curl_cffi` package that was never installed; YouTube answered those requests with HTTP 429. yt-dlp is now installed as `yt-dlp[default,curl-cffi]`, existing portable installs pick it up on their next launch, and archive mode warns up front when it is missing instead of reporting a ban.
- **yt-dlp was reported missing on machines without a global copy.** The launchers start the `.venv` Python directly, which does not put `.venv`'s `yt-dlp` on PATH, while the app looked yt-dlp up on PATH. yt-dlp now runs as `python -m yt_dlp` from the app's own interpreter.
- **The skip report was entirely in English**, even in Turkish, despite the translations for it already existing. All fifteen messages now go through the translation layer, as do the command banner and the success, cancellation, and failure lines.
- `analyze_log_for_error` now recognizes copyright takedowns, which it previously reported with the generic "video unavailable" message.

### Changed
- `install.ps1` / `install.sh` no longer use winget or apt/dnf/pacman on Windows and Linux; they set up the portable runtime instead. macOS keeps the Homebrew + `.venv` installation. The updaters now also preserve `runtime/`, `cache/` and `downloads/`.
- Existing installs keep their configured download folders. Their `.venv` and winget-installed Python/ffmpeg/Deno are no longer used and can be removed.
- `AppSettings` gains an `archive` section and `OutputSettings` an `archive_template`. Configs without them load the defaults, so no migration is needed. MP4 and MP3 commands are unchanged.
- `AppSettings` drops `use_deno`, `default_mode`, `default_mp4_profile`, and `language`: the first three are detected or asked for interactively, and the language lives at the top level of `config.json` because it must resolve before the settings load.
- `DownloadPlan` drops four argument fields that were built every cycle and never read; its profile fields are typed as the enums they are compared against.
- Removed `is_supported_url`, which computed a hostname and then unconditionally returned `True`, and eleven locale keys describing a status UI that was never built.

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

### Değişenler
- `install.ps1` / `install.sh` Windows ve Linux'ta artık winget ya da apt/dnf/pacman kullanmıyor; bunun yerine taşınabilir çalışma ortamını kuruyor. macOS, Homebrew + `.venv` kurulumuyla devam ediyor. Güncelleyiciler artık `runtime/`, `cache/` ve `downloads/` klasörlerini de koruyor.
- Mevcut kurulumlar ayarlı indirme klasörlerini korur. `.venv` ve winget ile kurulan Python/ffmpeg/Deno artık kullanılmaz, kaldırılabilir.
- `AppSettings`'e `archive` bölümü, `OutputSettings`'e `archive_template` eklendi. Bunları içermeyen yapılandırmalar varsayılanları yükler, taşıma gerekmez. MP4 ve MP3 komutları değişmedi.
- `AppSettings`'ten `use_deno`, `default_mode`, `default_mp4_profile` ve `language` kaldırıldı: ilk üçü otomatik algılanıyor veya kullanıcıya soruluyor, dil ise ayarlardan önce çözülmesi gerektiği için `config.json`'un üst seviyesinde duruyor.
- `DownloadPlan`'dan her döngüde doldurulup hiç okunmayan dört argüman alanı kaldırıldı; profil alanları karşılaştırıldıkları enum türleriyle tiplendi.
- Bir alan adı hesaplayıp koşulsuz `True` dönen `is_supported_url` ve hiç yapılmamış bir durum arayüzünü tarif eden on bir çeviri anahtarı silindi.

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
