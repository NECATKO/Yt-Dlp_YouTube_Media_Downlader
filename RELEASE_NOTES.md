# Release Notes for v0.3.0

## GitHub Release Title
```
v0.3.0 - UI Modernization & Architecture Refactoring
```

---

## GitHub Release Body (English)

```markdown
# yt-dlp Downloader v0.3.0

**UI Modernization & Architecture Refactoring Release**

This release brings a significant visual upgrade to the console interface and major internal architectural improvements for better maintainability and performance.

## Highlights

- **Modern Console UI**: Enhanced visual experience with box-drawing panels, styled menus, and organized summary screens.
- **Full Internationalization (i18n)**: Removed all hardcoded strings; the entire interface is now fully translatable.
- **Performance Boost**: Added intelligent caching for system dependency checks (ffmpeg, yt-dlp, deno) to speed up operations.
- **Solid Foundation**: Major refactoring of the codebase including the introduction of a robust `CommandBuilder` pattern.

## What's New

### User Interface (UI)
- **Boxed Menus**: Selection menus now appear in stylized boxes with clear borders.
- **Summary Panels**: Download summaries are presented in clean, color-coded panels.
- **Improved Readability**: Better visual hierarchy and status indicators.

### Architecture & Internals
- **InteractiveSession**: Refactored the monolithic `run()` loop into a modular session manager.
- **CommandBuilder**: centralized logic for generating yt-dlp command-line arguments.
- **Enums**: Replaced "magic numbers" with readable Enums for easier maintenance.
- **System Checks Caching**: Reduced overhead by caching environmental checks.

### Localization
- Complete extraction of all user-facing strings to `locales/*.json`.
- Full English and Turkish support.

## Installation

### Windows
1. Download `ytdlp-downloader-v0.3.0.zip`
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

**Full Changelog**: https://github.com/NECATKO/Yt-Dlp_YouTube_Media_Downlader/compare/v0.2.0...v0.3.0
```

---

## GitHub Release Body (Turkish / Türkçe)

```markdown
# yt-dlp Downloader v0.3.0

**Arayüz Modernizasyonu ve Mimari İyileştirme Sürümü**

Bu sürüm, konsol arayüzüne önemli bir görsel güncelleme ve daha iyi bakım yapılabilirlik/performans için büyük iç mimari iyileştirmeler getiriyor.

## Öne Çıkanlar

- **Modern Konsol Arayüzü**: Kutucuklu paneller, stilize menüler ve düzenli özet ekranları ile geliştirilmiş görsel deneyim.
- **Tam Yerelleştirme (i18n)**: Kod içindeki tüm sabit metinler temizlendi; arayüz artık tamamen çevrilebilir.
- **Performans Artışı**: İşlemleri hızlandırmak için sistem bağımlılık kontrollerine (ffmpeg, yt-dlp, deno) akıllı önbellekleme eklendi.
- **Sağlam Temel**: `CommandBuilder` deseni dahil olmak üzere kod tabanında büyük yeniden yapılandırma.

## Yenilikler

### Kullanıcı Arayüzü (UI)
- **Kutulu Menüler**: Seçim menüleri artık net kenarlıklı stilize kutular içinde görünüyor.
- **Özet Panelleri**: İndirme özetleri temiz, renk kodlu panellerde sunuluyor.
- **Okunabilirlik**: Daha iyi görsel hiyerarşi ve durum göstergeleri.

### Mimari ve İç Yapı
- **InteractiveSession**: Tek parça `run()` döngüsü modüler bir oturum yöneticisine dönüştürüldü.
- **CommandBuilder**: yt-dlp komut satırı argümanlarını oluşturmak için merkezi mantık.
- **Enum Yapıları**: "Sihirli sayılar" (magic numbers) okunabilir Enum yapılarıyla değiştirildi.
- **Sistem Kontrol Önbelleği**: Çevresel kontroller önbelleğe alınarak yük azaltıldı.

### Yerelleştirme
- Tüm kullanıcı arayüzü metinleri `locales/*.json` dosyalarına taşındı.
- Tam İngilizce ve Türkçe desteği.

## Kurulum

### Windows
1. `ytdlp-downloader-v0.3.0.zip` dosyasını indirin
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

**Tam Değişiklik Günlüğü**: https://github.com/NECATKO/Yt-Dlp_YouTube_Media_Downlader/compare/v0.2.0...v0.3.0
```

---

## Git Tag Command

```bash
git tag -a v0.3.0 -m "v0.3.0 - UI Modernization & Architecture Refactoring"
git push origin v0.3.0
```
