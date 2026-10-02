# Aşama 3 — Uygulama doğruluğu (B03, B06, B09, B14, B15, B16) — uygulama planı

> **Uygulayıcı için:** ZORUNLU ALT-BECERİ: `superpowers:executing-plans`. Adımlar `- [ ]` kutularıyla izlenir.

**Hedef:** Oturum çıkış kodu önceki başarısızlığı unutmasın. Menü girdisi beklenmedik hataya düşmesin. Paneller geniş Unicode karakterlerde taşmasın. Menü geçersiz proxy veya hız sınırını kaydetmesin. WAV seçimi kapak gömme yüzünden başarısız olmasın. yt-dlp alt sınırı, kullanılan seçenekleri gerçekten destekleyen sürüm olsun.

**Spec:** `degerlendirme-raporlari/2026-10-02/master-prompt.md` §2 (B03, B06, B09, B14/B15, B16). Yol haritası Ç4: yeni bağımlılık yok, genişlik stdlib `unicodedata` ile hesaplanır.

## Genel kısıtlar
- Yeni Python bağımlılığı eklenmez. Kullanıcıya görünen metinler `en.json` ve `tr.json`'a yazılır (doğal Türkçe, aynı yer tutucular).
- Commit sonu: `Co-Authored-By` + `Claude-Session` satırları. Push yok.
- Doğrulama: pytest, ruff check/format (Markdown dahil), mypy, check_version, `bash -n`.

## Gözden geçirme odağı
1. **Ctrl+C ile biten oturum**, daha önce başarısız bir döngü olsa da 130 dönmeli (1 değil) → Görev 1 testi.
2. **Birleşen karakter içeren başlık** kırpılırken taban harf ile işareti ayrılmamalı → Görev 2 testi.
3. **Menüde boş giriş** geçerli değeri korumalı, `-` girişi temizlemeli; doğrulama bunları geçersiz saymamalı → Görev 3 testi.
4. **Elle yazılmış config'te WAV + `embed_thumbnail: true`** menüden geçmeden de gömme argümanı üretmemeli → Görev 4 testi.
5. **Harici (PATH'teki) eski bir yt-dlp**, indirme başlamadan açık bir yükseltme mesajı almalı; sürüm okunamazsa indirme engellenmemeli → Görev 5 testi.

---

### Görev 1: Oturum çıkış kodu (B16)
**Dosyalar:** `ytdlp_app/session.py`; test `tests/test_session_outcomes.py`.
- `InteractiveSession.__init__`: `self.had_failure = False`.
- `_note_failure()`: `self.had_failure = True`. Şu yollarda çağrılır: `handle_error` içinde (başarısızlıkların hepsi buradan geçer, `run_loop`'taki beklenmeyen hata dahil), `_stop_after_ban`, yalnızca dosyası eksik olan başarısız dal ve PARTIAL sonuç.
- `run_loop`: döngü `EXIT_SUCCESS` dönerse ve `had_failure` doğruysa 1 döner. `INTERRUPTED` her zaman 130 döner.
- Testler: başarısız döngü → devam → boş URL ile 1; temiz döngüler ve boş URL ile 0; başarısız döngü ardından Ctrl+C ile 130; başarısız döngü, ardından başarılı döngü ve çıkış seçimiyle 1.

### Görev 2: Menü sayısal girişi (B15) ve Unicode genişliği (B14)
**Dosyalar:** `ytdlp_app/ui.py`; test `tests/test_console.py`.
- `cell_width(ch)`: combining karakter, ZWJ (U+200D), varyasyon seçicileri (U+FE00–FE0F) ve kontrol karakterleri 0; `east_asian_width` W/F olanlar 2; geri kalanlar 1. `visible_len` ANSI'siz metnin hücre toplamını döndürür.
- `wrap_ansi`: sütun sayımı hücre genişliğiyle yapılır. Uzun kelime bölünürken `used + w > width` olduğunda yeni satıra geçilir, böylece sıfır genişlikli işaret tabanından ayrılmaz.
- Başlık kırpma `_truncate_cells(text, limit)` ile yapılır: hücre sınırına kadar alınır, ardından gelen sıfır genişlikli karakterler de eklenir, sonra "…".
- Gerçek terminal 20 sütundan darsa `print_panel` ve `pick` çerçevesiz düz metin yazar.
- `pick`: `isdigit` yerine `try: n = int(ans) except ValueError`. Böylece `²` ve 5000 haneli sayı normal "geçersiz seçim" olur.
- Testler: 40 sütunda CJK ve emoji paneli hiçbir satırda 40 hücreyi aşmamalı; birleşen işaret kırpmada korunmalı; `²` ve 5000 haneli girdi sonrası geçerli seçimle devam edilmeli; dar terminalde (`COLUMNS=12`) çerçeve karakteri basılmamalı; Türkçe ve `NO_COLOR` testleri yine geçmeli.

### Görev 3: Menüde alan doğrulaması (B09) ve "retries" etiketi
**Dosyalar:** `ytdlp_app/settings.py` (paylaşılan doğrulayıcılar), `ytdlp_app/settings_menu.py`, locales; test `tests/test_settings_menu.py`.
- `settings.py`: `check_proxy(text) -> str | None`, `check_rate_limit(text) -> str | None`, `check_text(text) -> str | None`. Config yükleyicideki `_optional_text`/`_text` bu doğrulayıcıları kullanır, böylece kurallar tek yerde kalır.
- Menü: `_ask_optional_text` ve `_ask_text` bir `check` alır. Geçersiz değerde `settings_invalid_value` (alan ipucuyla) gösterilir ve yeniden sorulur. Boş giriş mevcut değeri korur, `-` temizler.
- Locale: `settings_download` "Download (proxy, speed limit, fragments, waits)" / "İndirme (vekil sunucu, hız sınırı, parçalar, beklemeler)".
- Testler: `invalid proxy url` ve `fast` reddedilir, kayıt geçerli değerle yapılır; config dosyası yeniden yüklendiğinde değer aynı kalır; boş ve `-` sözleşmesi korunur.

### Görev 4: WAV ve kapak (B03)
**Dosyalar:** `ytdlp_app/settings.py` (`AudioSettings.to_args`), `ytdlp_app/settings_menu.py` (`_edit_audio` uyarısı), `ytdlp_app/session.py` (ses modunda uyarı), locales; testler `tests/test_settings.py`, `tests/test_engine_contract.py` (ses biçimleri, kapak açık).
- WAV ve `embed_thumbnail` birlikteyse `--embed-thumbnail` yerine `--write-thumbnail` (ve varsa `--convert-thumbnails`) kullanılır; kapak ayrı dosya olarak kalır.
- Menüde WAV seçilip kapak gömme açıksa ve oturumda ses modu WAV ile başlarsa `audio_wav_cover_note` gösterilir.
- Motor testi: mp3/m4a/opus/flac/wav/best varsayılan metaveri ve kapak ayarıyla, gerçek bir PNG kapakla indirilir. Hepsi 0 dönmeli ve arşive yazılmalı; WAV'da ayrı kapak dosyası olmalı.

### Görev 5: yt-dlp sürüm sözleşmesi (B06)
**Dosyalar:** `pyproject.toml`, `ytdlp_app/portable.py` (`YTDLP_REQUIREMENT`), `ytdlp_app/netctx.py` (`--js-runtimes`), `ytdlp_app/system.py` (`ytdlp_version()`, `MIN_YTDLP_VERSION`), `ytdlp_app/session.py` (ön kontrol), locales, `tests/engine.py` (`YTDLP_ENGINE_PYTHON`); testler `tests/test_netctx.py`, `tests/test_system.py`, `tests/test_session_flow.py`, `tests/test_portable.py`.
- `MIN_YTDLP_VERSION = "2025.11.12"`. pyproject ve `YTDLP_REQUIREMENT` = `yt-dlp[default,curl-cffi]>=2025.11.12` (ikisi aynı). Bir test, pyproject'teki gereksinimin `YTDLP_REQUIREMENT`'a eşit olduğunu denetler.
- `ytdlp_version()`: modül olarak çalışıyorsa `yt_dlp.version.__version__` okunur (import yapılmadan, `importlib.metadata.version("yt-dlp")` ile). Ayrı bir çalıştırılabilir dosyaysa `--version` çıktısı okunur. Okunamazsa None döner.
- Oturum ön kontrolü: sürüm bilinir ve alt sınırın altındaysa `error_ytdlp_too_old` mesajı verilir ve döngü EXIT_FAILURE ile biter. Sürüm bilinmiyorsa devam edilir.
- `js_runtime_args`: `--js-runtimes deno`.
- `tests/engine.py`: `YTDLP_ENGINE_PYTHON` tanımlıysa uygulamanın `python -m yt_dlp` çağrısı o yorumlayıcıyla çalıştırılır. Motor sözleşme testleri 2025.11.12 ile ayrıca çalıştırılır ve sonuç kaydedilir.

### Görev 6: Belgeler ve kapanış
- README (iki dil): gereksinim satırı (yt-dlp ≥ 2025.11.12), WAV'da kapağın ayrı dosya olması, oturum çıkış kodu sözleşmesi (0/1/130).
- CHANGELOG, TASKS, yol haritası; inceleme denemesi (`probes.py` ui ve ses kısımları); tüm kontroller; commit.
