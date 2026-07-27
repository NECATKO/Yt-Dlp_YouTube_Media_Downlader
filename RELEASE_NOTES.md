# Release Notes for v0.3.1

## GitHub Release Title
```
v0.3.1 - Critical Fixes for the v0.3.0 Release
```

---

## GitHub Release Body (English)

```markdown
# yt-dlp Downloader v0.3.1

**Critical patch release — if you are running v0.3.0, please upgrade.**

The v0.3.0 release was tagged before its internationalization fix was committed, so the published archive was unusable: the interface printed raw translation keys (`prompt_url`, `prompt_mode`, `tasks_completed`) instead of readable text. On top of that, the auto-updater could never find its own release asset, so it was unable to deliver a fix on its own. This release corrects both, along with the release pipeline that allowed them to ship.

## What's Fixed

### The v0.3.0 archive printed translation keys
The i18n repair landed one commit after the tag, so it was absent from the published ZIP. This is the first release that actually contains it.

### Auto-update never worked
- `update.ps1` searched for a release asset named `YtDlpDownloader-Portable.zip`, while CI published `YtDlpDownloader-Portable-<tag>.zip`. Every check ended with "asset missing". CI now publishes the stable name the updater expects.
- `app_version.txt` stored `0.3.0` but was compared against the GitHub tag `v0.3.0`, so the app considered itself out of date on every launch. The file now stores the tag form.
- `app_version.txt` was missing from the portable archive entirely, leaving fresh installs with nothing to compare.
- `update.sh` read its version from `pyproject.toml`, copied the package *into* the existing `ytdlp_app/` directory (producing `ytdlp_app/ytdlp_app`), and could exit silently under `set -e` when an optional file was absent.

### The portable archive was incomplete
`run.sh`, `install.sh`, and `update.sh` were never packaged, so the documented Linux/macOS workflow did not work from a release download. They are included now.

## Also Changed

- **Single-source versioning**: the version is written in exactly one place, `ytdlp_app.__version__`. `pyproject.toml` reads it dynamically, and a new CI step (`scripts/check_version.py`) fails the build whenever `app_version.txt` or the release tag disagrees — the class of mistake that produced this patch cannot reach a release again.
- **Corrected platform and version claims**: the project metadata advertised Windows-only support and the docs claimed Python 3.10+. The app requires **Python 3.11+** (it uses `StrEnum`) and is tested on Linux, Windows, and macOS.

## Installation

### Windows
1. Download `YtDlpDownloader-Portable.zip`
2. Extract to a folder
3. Run `Run.bat`

### Unix (Linux/macOS)
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

## Requirements
- Windows 10/11 with winget, or Linux/macOS with apt/dnf/pacman/brew
- Python 3.11+
- Internet connection

## Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete details.

---

**Full Changelog**: https://github.com/NECATKO/Yt-Dlp_YouTube_Media_Downlader/compare/v0.3.0...v0.3.1
```

---

## GitHub Release Body (Turkish / Türkçe)

```markdown
# yt-dlp Downloader v0.3.1

**Kritik yama sürümü — v0.3.0 kullanıyorsanız lütfen güncelleyin.**

v0.3.0 sürümü, yerelleştirme düzeltmesi commit'lenmeden önce etiketlendi; bu yüzden yayınlanan arşiv kullanılamaz durumdaydı: arayüz okunabilir metin yerine ham çeviri anahtarlarını (`prompt_url`, `prompt_mode`, `tasks_completed`) yazdırıyordu. Üstelik otomatik güncelleyici kendi sürüm dosyasını hiçbir zaman bulamadığı için düzeltmeyi kendi başına ulaştıramıyordu. Bu sürüm her ikisini de, bunların yayınlanmasına izin veren sürüm hattıyla birlikte düzeltiyor.

## Düzeltilenler

### v0.3.0 arşivi çeviri anahtarları yazdırıyordu
i18n onarımı etiketten bir commit sonra geldi ve yayınlanan ZIP'te yer almadı. Onarımı gerçekten içeren ilk sürüm budur.

### Otomatik güncelleme hiç çalışmıyordu
- `update.ps1`, `YtDlpDownloader-Portable.zip` adlı bir dosya ararken CI `YtDlpDownloader-Portable-<etiket>.zip` yayınlıyordu. Her kontrol "dosya bulunamadı" ile bitiyordu. CI artık güncelleyicinin beklediği sabit adı kullanıyor.
- `app_version.txt` içinde `0.3.0` yazıyordu ama karşılaştırma GitHub etiketi `v0.3.0` ile yapılıyordu; uygulama her açılışta kendini eski sanıyordu. Dosya artık etiket biçimini saklıyor.
- `app_version.txt` taşınabilir arşivde hiç yoktu; yeni kurulumlarda karşılaştırılacak bir sürüm bulunmuyordu.
- `update.sh` sürümünü `pyproject.toml`'dan okuyordu, paketi mevcut `ytdlp_app/` dizininin *içine* kopyalıyordu (`ytdlp_app/ytdlp_app` oluşuyordu) ve isteğe bağlı bir dosya yoksa `set -e` nedeniyle sessizce sonlanabiliyordu.

### Taşınabilir arşiv eksikti
`run.sh`, `install.sh` ve `update.sh` hiçbir zaman pakete girmiyordu; belgelenen Linux/macOS akışı indirilen paketten çalışmıyordu. Artık dahil ediliyorlar.

## Diğer Değişiklikler

- **Tek kaynaklı sürüm yönetimi**: sürüm tam olarak tek bir yerde, `ytdlp_app.__version__` içinde yazılı. `pyproject.toml` onu dinamik olarak okuyor ve yeni bir CI adımı (`scripts/check_version.py`), `app_version.txt` ya da sürüm etiketi uyuşmadığında derlemeyi durduruyor — bu yamaya yol açan hata sınıfı bir daha sürüme ulaşamaz.
- **Platform ve sürüm bilgileri düzeltildi**: proje meta verileri yalnızca Windows desteği ilan ediyordu ve belgeler Python 3.10+ diyordu. Uygulama **Python 3.11+** gerektiriyor (`StrEnum` kullanıyor) ve Linux, Windows, macOS üzerinde test ediliyor.

## Kurulum

### Windows
1. `YtDlpDownloader-Portable.zip` dosyasını indirin
2. Bir klasöre çıkartın
3. `Run.bat` dosyasını çalıştırın

### Unix (Linux/macOS)
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

## Gereksinimler
- winget ile Windows 10/11, veya apt/dnf/pacman/brew ile Linux/macOS
- Python 3.11+
- İnternet bağlantısı

## Tam Değişiklik Günlüğü
Tüm detaylar için [CHANGELOG.md](CHANGELOG.md) dosyasına bakın.

---

**Tam Değişiklik Günlüğü**: https://github.com/NECATKO/Yt-Dlp_YouTube_Media_Downlader/compare/v0.3.0...v0.3.1
```

---

## Git Tag Command

```bash
git tag -a v0.3.1 -m "v0.3.1 - Critical fixes for the v0.3.0 release"
git push origin v0.3.1
```

## Post-release: flag the broken v0.3.0

The v0.3.0 tag is left in place — moving a published tag breaks anyone who already fetched it. Mark the old release instead:

```bash
gh release edit v0.3.0 --prerelease
gh release delete-asset v0.3.0 YtDlpDownloader-Portable-v0.3.0.zip
```
