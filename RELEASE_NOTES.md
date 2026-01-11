# Release Notes for v0.2.0

## GitHub Release Title
```
v0.2.0 - Infrastructure Strengthening
```

---

## GitHub Release Body (English)

```markdown
# yt-dlp Downloader v0.2.0

**Infrastructure Strengthening Release**

This release focuses on building a solid foundation for future development with modern Python tooling, comprehensive testing, and cross-platform support.

## Highlights

- **Modern Package Management**: PEP 621 compliant `pyproject.toml` with all tool configurations
- **CI/CD Pipeline**: Automated testing across 12 environments (3 OS × 4 Python versions)
- **~70 Unit Tests**: Comprehensive test coverage for core modules
- **Internationalization**: Full i18n support with English and Turkish translations
- **Cross-Platform Scripts**: New Unix installation and run scripts for Linux/macOS

## What's New

### Package & Build
- PEP 621 compliant `pyproject.toml` configuration
- PEP 561 type marker (`py.typed`)
- Console entry point: `ytdlp-downloader`

### CI/CD
- GitHub Actions workflow with lint, test, build, and release jobs
- Matrix testing: Ubuntu, Windows, macOS × Python 3.10-3.13
- Automatic release creation on tags

### New Modules
| Module | Description |
|--------|-------------|
| `exceptions.py` | Custom exception hierarchy for better error handling |
| `validators.py` | URL and path validation with security protections |
| `settings.py` | Advanced configurable settings system |
| `i18n.py` | Internationalization support |

### Cross-Platform
- `install.sh`: Unix installation script (apt, dnf, pacman, brew)
- `run.sh`: Cross-platform launcher
- `update.sh`: Cross-platform updater with config backup

### Localization
- English (`locales/en.json`)
- Turkish (`locales/tr.json`)

## Installation

### Windows
1. Download `ytdlp-downloader-v0.2.0.zip`
2. Extract to a folder
3. Run `Run.bat`

### Unix (Linux/macOS)
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

## Requirements
- Windows 10/11 with winget, or Linux/macOS
- Python 3.10+
- Internet connection

## Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete details.

---

**Full Changelog**: https://github.com/NECATKO/Yt-Dlp_YouTube_Media_Downlader/compare/v0.1.0...v0.2.0
```

---

## GitHub Release Body (Turkish / Türkçe)

```markdown
# yt-dlp Downloader v0.2.0

**Altyapı Güçlendirme Sürümü**

Bu sürüm, modern Python araçları, kapsamlı test altyapısı ve platformlar arası destek ile gelecekteki geliştirmeler için sağlam bir temel oluşturmaya odaklanmaktadır.

## Öne Çıkanlar

- **Modern Paket Yönetimi**: Tüm araç yapılandırmalarıyla PEP 621 uyumlu `pyproject.toml`
- **CI/CD Pipeline**: 12 ortamda (3 İS × 4 Python sürümü) otomatik test
- **~70 Birim Testi**: Çekirdek modüller için kapsamlı test kapsamı
- **Yerelleştirme**: İngilizce ve Türkçe çevirilerle tam i18n desteği
- **Platformlar Arası Betikler**: Linux/macOS için yeni Unix kurulum ve çalıştırma betikleri

## Yenilikler

### Paket ve Build
- PEP 621 uyumlu `pyproject.toml` yapılandırması
- PEP 561 tip işaretleyici (`py.typed`)
- Konsol giriş noktası: `ytdlp-downloader`

### CI/CD
- Lint, test, build ve release işleriyle GitHub Actions workflow
- Matris testi: Ubuntu, Windows, macOS × Python 3.10-3.13
- Tag'lerde otomatik release oluşturma

### Yeni Modüller
| Modül | Açıklama |
|-------|----------|
| `exceptions.py` | Daha iyi hata yönetimi için özel istisna hiyerarşisi |
| `validators.py` | Güvenlik korumalarıyla URL ve yol doğrulama |
| `settings.py` | Gelişmiş yapılandırılabilir ayarlar sistemi |
| `i18n.py` | Yerelleştirme desteği |

### Platformlar Arası
- `install.sh`: Unix kurulum betiği (apt, dnf, pacman, brew)
- `run.sh`: Platformlar arası başlatıcı
- `update.sh`: Yapılandırma yedeklemeli platformlar arası güncelleyici

### Dil Desteği
- İngilizce (`locales/en.json`)
- Türkçe (`locales/tr.json`)

## Kurulum

### Windows
1. `ytdlp-downloader-v0.2.0.zip` dosyasını indirin
2. Bir klasöre çıkartın
3. `Run.bat` dosyasını çalıştırın

### Unix (Linux/macOS)
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

## Gereksinimler
- winget ile Windows 10/11, veya Linux/macOS
- Python 3.10+
- İnternet bağlantısı

## Tam Değişiklik Günlüğü
Tüm detaylar için [CHANGELOG.md](CHANGELOG.md) dosyasına bakın.

---

**Tam Değişiklik Günlüğü**: https://github.com/NECATKO/Yt-Dlp_YouTube_Media_Downlader/compare/v0.1.0...v0.2.0
```

---

## Git Tag Command

```bash
git tag -a v0.2.0 -m "v0.2.0 - Infrastructure Strengthening"
git push origin v0.2.0
```

## GitHub CLI Release Command

```bash
gh release create v0.2.0 \
  --title "v0.2.0 - Infrastructure Strengthening" \
  --notes-file RELEASE_NOTES.md \
  ytdlp-downloader-v0.2.0.zip
```

## Checklist Before Release

- [x] Update version in `pyproject.toml` to `0.2.0`
- [x] Update version in `ytdlp_app/__init__.py` to `0.2.0`
- [x] Create `CHANGELOG.md`
- [x] Create release zip file
- [ ] Run tests: `pytest`
- [ ] Run linter: `ruff check .`
- [ ] Run type check: `mypy ytdlp_app`
- [ ] Commit all changes
- [ ] Create git tag
- [ ] Push tag to remote
- [ ] Create GitHub release with zip file
