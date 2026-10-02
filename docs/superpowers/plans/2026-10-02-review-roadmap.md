# Yol haritası — 2 Ekim 2026 incelemesi, Transkript modu ve TUI Faz 1

**Kaynaklar**
- İnceleme: `degerlendirme-raporlari/2026-10-02/inceleme-raporu.md` (B01–B16; yerel, git dışı)
- Uygulama talimatı: `degerlendirme-raporlari/2026-10-02/master-prompt.md` (yerel, git dışı)
- TUI görevi: kullanıcının 1 Ekim spec'i (Faz 0 commit `1d310f8`, Faz 1 onay bekliyor)

**Taban:** `feat/tui` @ `1d310f8`, sürüm 0.4.0. İnceleme bu commit üzerinde yapıldı ve
çalışma ağacı temiz. Bu yüzden 16 bulgunun hepsi güncel kodda geçerli. B02 (`ident in names`) ve
B04 (tek videoda `expected_ids=None`) kodda tek tek doğrulandı.

## 1. Çakışmalar ve kararlar

| # | Çakışma | Karar |
|---|---|---|
| Ç1 | Master prompt "yeni UI framework'ü ekleme" diyor; TUI Faz 1 ise Textual ekliyor. | Yasak, inceleme işinin kapsamı için geçerli. Faz 1 ayrı ve onaylı bir iş olarak **en sona** kalır. Transkript modu yalnızca `UI` Protocol'ünü (`pick`, `ask_text`, `print`, `print_panel`) kullanır. Böylece iki önyüzde de değişiklik gerekmeden çalışır. |
| Ç2 | B07/B08 `app.run()`'a top-level argparse ekliyor ve ilk kurulum sorularını TUI'ye ayırıyor. Faz 1 de aynı fonksiyonda `--tui`/`--console`'u ayıklıyor ve dil/klasör sorularını worker'a taşıyor. | Önce B07/B08 (Aşama 4) tek bir parser kurar. Faz 1 bu parser'a iki bayrak ekler. Faz 1 spec'indeki "args'tan çıkarılsın" ifadesi parser ile karşılanır. "Soruları worker'a taşı" adımı, B08'in "sorular yalnızca etkileşimli akışta" ayrımının üstüne kurulur. |
| Ç3 | Transkriptte Enter önerilen kapsamı kabul etmeli; `UI.pick` varsayılan seçimi bilmiyor. | Protokole geriye uyumlu `default: int \| None = None` eklenir (Aşama 5): `ConsoleUI` ile test sahteleri. Faz 1'deki `TextualUI` modal'ı bu varsayılanla açar. |
| Ç4 | B14 `wcwidth` bağımlılığı öneriyor; TUI spec'i "textual/pytest-asyncio dışında bağımlılık gerekirse dur ve sor" diyor. | Yeni bağımlılık eklenmez. Hücre genişliği stdlib `unicodedata` (`east_asian_width` + combining) ile hesaplanır. Emoji ZWJ dizileri yaklaşık kalır; bu README/TASKS'ta belirtilir. Textual tarafında Rich zaten hücre genişliği hesaplıyor. |
| Ç5 | TUI spec'i "CommandBuilder/yt-dlp argümanlarını değiştirme" diyor. B03 (WAV + kapak), B05 (ledger `root`), B06 (`--js-runtimes`) ve Transkript (yeni komut) ise argümanlara dokunuyor. | Yasak Faz 1 commit'inin kapsamına ait. Bu değişiklikler kendi commit'lerinde ve Faz 1'den önce yapılır; Faz 1 commit'i yine CommandBuilder'a dokunmaz. |
| Ç6 | TUI spec'i CI, plugin, `install.*` ve `runtime.lock` dosyaları için "dur ve sor" diyor. Master prompt ise ledger plugin'i (B05), `install.sh` (B11) ve Windows CI'ı (B01/B12/B13) istiyor. | Kullanıcı master prompt'u uygulama talimatı verdi; bu dosyalar o yetkiyle değişir. `runtime.lock`'a dokunulmaz. CI değişiklikleri push edilmeden çalışmaz, bu yüzden **"doğrulanmadı"** diye raporlanır. |
| Ç7 | Bağımlılık listelerine iki taraf da dokunuyor: B06 (yt-dlp alt sınırı: pyproject + portable gereksinimi + state anahtarı), B10 (`.venv` güncellemesinde extra'lar), Faz 1 (aynı listelere `textual`). | B06/B10 önce. Faz 1 `textual`'ı B06'nın ortak listesine ekler. B06 gereksinim metnini değiştirdiği için taşınabilir kurulum bir kez yeniden kurulum yapar (beklenen). |
| Ç8 | `update.sh`/`update.ps1`'e B01, B10, B12 ve Faz 1 (`.venv`'e textual) dokunuyor. | Güncelleyici işleri Aşama 2'de toplanır. Faz 1 yalnızca gereksinim satırını değiştirir. |
| Ç9 | B16 oturum çıkış kodunu değiştiriyor; Faz 1'de Ctrl+Q `run_loop` sonucuyla çıkıyor. | B16 önce (Aşama 3). Faz 1 testleri yeni sözleşmeyi doğrular: temiz 0, başarısız/kısmi 1, iptal 130. |
| Ç10 | TUI açık maddesi: konsola doğrudan yazan yollar (`logging_utils.log_error`) Textual'ı bozar. | Yeni kod (Transkript, menü doğrulaması) tüm çıktıyı `ui.print` ya da Faz 0'ın `sink`'i üzerinden verir; iptal için `cancel` event'ini kullanır. `log_error` düzeltmesi Faz 1'de kalır. `audit` CLI her zaman konsoldur, sorun değil. |
| Ç11 | Dal: hafızadaki not "main tek dal" diyor; TUI işi ise `feat/tui`'deydi. | 2 Ekim'de kullanıcı her şeyin `main`'de olmasını istedi: `feat/tui` `main`'e alındı ve silindi. Bundan sonra doğrudan `main`'e commit edilir; PR yok, GitHub CI kapalı (`gh workflow disable CI`). |
| Ç12 | Master prompt bir yerde "TUI" derken mevcut soru-cevap arayüzünü kastediyor; Faz 1'in "TUI"si Textual. | Bu belgede **konsol arayüzü** = `ConsoleUI`, **TUI** = Textual (`--tui`). |

## 2. Aşamalar

Her aşamanın sonunda şunlar çalıştırılır: `pytest`, `ruff check .`, `ruff format --check .`,
`mypy ytdlp_app --ignore-missing-imports`, `scripts/check_version.py`,
`bash -n run.sh install.sh update.sh`. Ardından aşama commit'lenir.
Her aşama, başlamadan önce güncel koda göre kendi ayrıntılı planını
(`docs/superpowers/plans/2026-10-02-stageN-*.md`) alır. Önceki aşama dosyaları değiştirdiği için
planlar önceden yazılmaz.

| Aşama | Kapsam | Ana dosyalar | Bağımlılık | Not |
|---|---|---|---|---|
| **1 — Arşiv kanıtı** (P1) | B02, B04, B05 | yeni `evidence.py`, `archive_audit.py`, `outcome.py`, ledger plugin, `yt_dlp.py`, `session.py`, `playlist.py` | — | Ayrıntılı plan: `2026-10-02-stage1-archive-evidence.md` |
| **2 — Kurulum/güncelleme** | B01 (P1), B10, B11, B12, B13 + Windows CI işi | `update.sh`, `update.ps1`, `install.sh`, `Run.bat`, `.github/workflows/*`, `tests/test_update_sh.py` | — | Windows/macOS yerelde çalıştırılamaz; CI değişikliği push edilmeden doğrulanmaz |
| **3 — Uygulama doğruluğu** | B03, B06, B09 (+"retries" etiketi), B14, B15, B16 | `settings.py`, `settings_menu.py`, `validators.py`, `netctx.py`, `portable.py`, `pyproject.toml`, `ui.py`, `session.py` | 1 (B16 sonuç modeli) | B06'da en eski sürümle motor kontratı yalnızca offline wheel varsa çalışır |
| **4 — Komut satırı** | B07, B08, audit'te mutually exclusive grup, README CLI bölümü ve Linux motor yolu | `app.py`, `config.py`, `archive_audit.py`, `README.md` | 3 | Faz 1'in parser'ı buraya eklenecek (Ç2) |
| **5 — Transkript modu** | Master prompt §4 | yeni `transcript/` paketi (seçim, ayrıştırma, kalıcılık, birleştirme), `models.py`, `session.py`, `ui.py` (`pick` default), locales, README | 1, 3, 4 | Önce kısa bir tasarım notu (`docs/superpowers/specs/`), ardından plan |
| **6 — TUI Faz 1** | 1 Ekim spec'i, Ç2/Ç3/Ç7/Ç9 uyarlamalarıyla | `ytdlp_app/tui/`, `app.py`, `pyproject.toml`, `portable.py`, güncelleyiciler | 4, 5 | **Onay kapısı:** kullanıcı onaylamadan başlamaz |
| **7 — Teslim** | TASKS, CHANGELOG, README; Türkçe teslimat raporu (B01–B16 durumu, testler, çalıştırılmayan platformlar) | belgeler | hepsi | Sürüm artışı (0.5.0?) ve tag/release kararı kullanıcının |

### Sıralama gerekçesi
- **Önce P1'ler.** Aşama 1 ile Aşama 2 birbirinden bağımsız. Aşama 1 önce gelir, çünkü Transkript modunun
  "kendi dosya kanıtı" ilkesi (tek dosyaya güvenmeme, `.part`'ı kanıt saymama) burada kurulan
  `evidence.py` dersleriyle aynı.
- **Aşama 3, 4'ten önce.** B16 (oturum çıkış kodu) ve B09 (menü doğrulaması) oturumun
  sözleşmesini değiştirir; CLI ve TUI bu sözleşmeye göre yazılır.
- **Transkript, Faz 1'den önce.** Spec'i kullanıcı kararlarıyla hazır. Faz 1 ise onay bekliyor.
  TextualUI, `pick(default=)` dahil son hâline gelmiş Protocol'ü bir kez sarar.

## 3. Aşama dışı bırakılanlar (bilerek)
- İnceleme §"Geliştirme önerileri" 4 (runtime kilidi/tekil staging) ve 5 (haftalık pip sağlık kontrolü):
  yeniden üretilmedi; master prompt bunları zorunlu kapsam dışı sayıyor.
- Genel headless indirme CLI'si, cookie/auth, gerçek metadata ile boyut tahmini (öneri 7).
- Bit hızı tablosu değer kararı (PR #5'ten açık kalan, kullanıcı kararı).
- Otomatik güncelleyici/release (kullanıcı erteledi), repo adı (kullanıcı değiştirmeme kararı verdi).

## 4. Durum

| Aşama | Durum |
|---|---|
| 1 | tamam (B02, B04, B05) |
| 2 | tamam (B01, B10, B11, B12, B13) |
| 3 | tamam (B03, B06, B09, B14, B15, B16) |
| 4–5, 7 | bekliyor |
| 6 | onay bekliyor |
