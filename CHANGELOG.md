# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - Python versions: 3.10, 3.11, 3.12, 3.13

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
  - Automatic OS detection and Python 3.10+ installation
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

## [0.3.0] - 2026-01-11

### Eklenenler
- **Modern Konsol Arayüzü**: Kutucuklu paneller ve stilize menülerle geliştirilmiş görsel deneyim.
- **Tam Yerelleştirme (i18n)**: Kod içindeki sabit metinler temizlendi; arayüz artık tamamen çevrilebilir.
- **CommandBuilder Deseni**: Karmaşık yt-dlp komutlarını oluşturmak için yeni ve sağlam yapı.

### Değişenler
- **Mimari Yenileme**: Tek parça halindeki `run()` fonksiyonu modüler `InteractiveSession` sınıfına dönüştürüldü.
- **Temiz Kod**: Menü seçimlerindeki "sihirli sayılar" (magic numbers) okunabilir Enum yapılarıyla değiştirildi.
- **Performans**: Sistem bağımlılık kontrollerine (ffmpeg, yt-dlp, deno) önbellekleme eklendi.

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
  - Python sürümleri: 3.10, 3.11, 3.12, 3.13

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
