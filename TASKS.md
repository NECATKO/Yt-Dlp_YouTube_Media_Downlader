# Durum — 28 Eylül 2026

Arşiv modu ve taşınabilir çalışma ortamı `main`'e birleşti (PR #2, `ce7ba12`).
Henüz **tag ya da release yok**: otomatik güncelleyici release'leri çektiği için
yayın kararı ayrıca verilecek.

## Neler değişti

### Arşiv modu (yeni)
MP4 ve MP3'ün yanında üçüncü mod; silinme riski olan bir kanalı korumak için.

- **Her video kendi klasöründe:** `<Videos>/yt-dlp/<kanal>/<tarih> - <başlık> [<id>]/`
  - video: 1080p'ye kadar, bölümler ve metadata gömülü MKV
  - `.description`, `.info.json`, kapak resmi
  - Türkçe/İngilizce altyazılar (`.srt`)
- **Kanal adresi = kanalın tamamı:** Videos, Shorts ve Live sekmeleri iner; "tüm
  liste mi bu video mu" sorusu sorulmaz.
- **Kaldığı yerden devam:** arşiv dosyası kanalın gerçek kimliğiyle adlanır
  (`archives/channel_<UC…>_archive.txt`). `@isim`, `/channel/` ya da sekme
  adresi fark etmez; kanal adını değiştirse bile aynı arşivden devam eder.
  Parçalarından biri (altyazı, kapak) inmeyen video tamamlandı sayılmaz,
  sonraki çalıştırmada yeniden denenir.
- **Yavaş tempo:** istekler arası 1,5 sn, videolar arası 15–45 sn (rastgele),
  altyazı öncesi 5 sn, 10 yeniden deneme (sınırsız değil). Ayarlardan
  (`s` → *Arşiv modu beklemeleri*) değiştirilebilir.
- **Ban koruyucusu:** HTTP 429 ya da "bot olmadığını doğrula" görülünce indirme
  hemen durur, loga `[BAN-GUARD]` yazılır, kullanıcıya "birkaç saat bekle, aynı
  URL'yi tekrar gir" denir.
- **Yalnızca gerçek altyazılar:** programla gelen yt-dlp eklentisi
  (`ytdlp_app/plugins`) iki şeyi indirme başlamadan eler:
  - YouTube'un makine çevirileri (İngilizce videoya Türkçe çeviri gibi). Dünkü
    429 hatalarının sebebi bunlardı.
  - Aynı altyazının ikinci kopyası: YouTube orijinal otomatik altyazıyı aynı
    adresle hem `en` hem `en-orig` olarak listeliyor; yalnızca `en` kalır.
    Böylece video başına bir altyazı isteği daha az gider.

### Taşınabilir çalışma ortamı (Windows ve Linux)
- İlk açılışta Python, ffmpeg ve Deno program klasöründeki `runtime/` içine
  iner (her biri `runtime.lock`'taki SHA-256 ile doğrulanır). Yönetici izni,
  winget/apt ya da PATH değişikliği gerekmez.
- Klasör taşınabilir: USB belleğe ya da başka makineye kopyalanınca çalışmaya
  devam eder. İndirmeler varsayılan olarak `downloads/` klasörüne gider.
- yt-dlp haftada bir kendini günceller.
- macOS eskisi gibi Homebrew + `.venv` kullanır.

### Düzeltilen hatalar
- YouTube altyazıları hiç inmiyordu (`curl_cffi` eksikti → 429).
- Global yt-dlp olmayan makinelerde "yt-dlp bulunamadı" hatası.
- Windows'ta alt süreç çıktısı bozuk kodlanıyordu; ban koruyucusu YouTube'un
  bot uyarısını kaçırabiliyordu.
- Atlanan videolar raporu Türkçe arayüzde bile İngilizceydi.

### Gereksinim
- yt-dlp 2025.03.21 veya daha yenisi (altyazı eklentisi için). Taşınabilir
  kurulum her zaman en yenisini kullanır.

## Test durumu
- 346 test geçiyor; ruff, format ve mypy temiz.
- CI: Windows, macOS, Ubuntu × Python 3.11/3.12/3.13 yeşil.
- **Gerçek indirme** (tek izinli test videosu:
  https://www.youtube.com/watch?v=izx6nkLpoOA):

  | Deneme | Sonuç | Sebep → çözüm |
  |---|---|---|
  | 1 — 27 Eylül | ❌ `tr` altyazıda 429 | `curl_cffi` eksikti → eklendi |
  | 2 — 27 Eylül | ❌ `tr` altyazıda 429 | `tr` makine çevirisiydi → eklentiyle elendi |
  | 3 — 28 Eylül | ✅ Başarılı | Tüm dosyalar indi, arşive kaydedildi |

  `en`/`en-orig` düzeltmesi 3. denemenin `info.json` verisiyle ağa çıkmadan
  doğrulandı (iki adres aynı; eklenti yalnızca `en`'i bırakıyor).

## Açık işler
- [ ] `en`/`en-orig` düzeltmesini `main`'e almak (dal: `fix/duplicate-orig-subs`)
- [ ] Windows'ta gerçek bir arşiv indirmesi (kurulum ve açılış test edildi,
      arşiv indirmesi yalnızca Linux/WSL'de denendi)
- [ ] **Sonraya bırakıldı:** otomatik güncelleyici ve ilk release kararı.
      O zamana kadar tag ya da release yayınlanmayacak.

## Kurallar
- Testlerde yalnızca yukarıdaki video kullanılır; kanaldan başka hiçbir şey
  indirilmez.
- Tag ya da release yalnızca açık onayla yayınlanır.

## Boyut tahmini, disk kontrolü ve çözünürlük sınırı
Dal: `feat/disk-space-and-resolution` · Spec: `docs/superpowers/specs/2026-09-29-disk-space-and-resolution-design.md` · Plan: `docs/superpowers/plans/2026-09-29-disk-space-and-resolution.md`

- [x] Spec yazıldı ve onaylandı
- [x] Plan yazıldı
- [x] Yeni metinler (`en.json`, `tr.json`)
- [x] Kanal düzleştirme hatası: önce test, sonra düzeltme (`playlist.py`)
- [x] `estimate.py` (hesap ve biçimlendirme)
- [ ] `speedtest.py` (ağ hızı ölçümü)
- [ ] `max_height` ayarı, `s` menüsü, `settings.example.json`
- [ ] Format seçicileri ve `CommandBuilder.set_max_height`
- [ ] `preflight.py` (liste sarmalayıcı, tablo, çözünürlük sorusu, disk kontrolü)
- [ ] `session.py` entegrasyonu; `resolve_channel_id` kalktı
- [ ] README, CHANGELOG
- [ ] pytest / ruff / mypy temiz (346'nın altına düşmeden)
- [ ] Gerçek deneme (izinli video): MP4, MP3, arşiv tek video
- [ ] PR açıldı (merge kullanıcıda)

### Bu işte bulunanlar
- Kanal düzleştirme hatası doğrulandı: çıplak kanal adresinde `fetch_playlist_entries` 3 video yerine 2 sekme sayıyordu (`['videos-tab', 'shorts-tab']`). `fetch_listing` özyinelemeli düzleştiriyor; açılmamış `YoutubeTab` kalıntıları sayılmıyor.
- (uygulama sırasında eklenir)
