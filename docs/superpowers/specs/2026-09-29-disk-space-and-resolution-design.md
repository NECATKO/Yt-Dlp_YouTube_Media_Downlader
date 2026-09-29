# Boyut tahmini, disk kontrolü ve çözünürlük sınırı — tasarım

Tarih: 2026-09-29 · Dal: `feat/disk-space-and-resolution` · Durum: onay bekliyor

## 1. Amaç

İndirmeden önce "bu iş diske sığar mı, ne kadar sürer" görülsün. Yer yetmezse
kullanıcı uyarılsın ama **hiçbir zaman engellenmesin**. Çözünürlük sınırı bu
tabloya bakılarak seçilebilsin ve tüm video komutlarına uygulansın.

İki özellik birbirine bağlı: tahmin tablosu çözünürlük seçimini besler, seçim
gereken alanı belirler.

## 2. Kesinleşmiş kararlar

Kullanıcı tarafından verildi, bu spec'te yeniden tartışılmaz.

- Boyut, liste verisindeki **süre × tipik bit hızı** ile tahmin edilir. Video
  başına ek istek yok; süre eksik olsa bile yedek `-J` çağrısı yok.
- Tahmin 1080p, 1440p ve 2160p için ayrı ayrı gösterilir.
- Programa çözünürlük sınırı eklenir.
- Yer yetmezse uyar ve sor: *Yine de devam et / İptal*. Asla engelleme.
- Süre uyarıları gösterilir (bölüm 7).
- Oynatma listelerinde de çalışır, yalnız kanalda değil.

Bu oturumda verilen kararlar:

| # | Soru | Karar |
|---|---|---|
| 1 | Çözünürlük nerede seçilsin? | Tahmin tablosundan hemen sonra, her indirmede. Varsayılan ayardan gelir. Seçim ayardakinden farklıysa "yalnız bu indirme / varsayılan olarak kaydet" sorulur. |
| 2 | Uyumluluk profili (H.264) | Sınır 1080p'de sabit. 1440p/2160p yalnızca Kalite profilinde. |
| 3 | Süre uyarısı | Bekleme kaynaklı uyarılar **ve** indirme süresi tahmini **ve** kısa ağ hızı testi. |
| 4 | Tek video tahmini | Yok. Tek videoda indirme öncesi `-J` çağrısı zaten yok ve eklenmeyecek. |
| 5 | Tek videoda çözünürlük sorusu | Sorulur, tablo olmadan. |
| 6 | Hız testi kaynağı | Harici uç nokta, kısa ölçüm (bölüm 6). |

### Kapsam daralması (karar 4'ün sonucu)

İlk taslak "tek video, liste ve kanal" hepsinde tahmini istiyordu. Karar 4 ile:

- **Tahmin, disk kontrolü, süre uyarıları:** yalnızca oynatma listesi ve kanal.
- **Çözünürlük sınırı ve sorusu:** her yerde (tek video dahil), MP3 hariç.

### Kapsam dışı

Otomatik güncelleyici ve release, repo adı, `run.sh` çalıştırma izni.

## 3. Bugünkü durum (koddan doğrulandı)

- Format seçicileri `ytdlp_app/yt_dlp.py`: uyumluluk aşama 1 ve 2, kalite mkv ve
  mp4, arşiv (`bv*[height<=1080]+ba/b`, `ARCHIVE_CONTENT_ARGS`) ve MP3
  (`bestaudio/best`).
- Tek videoda indirme öncesi `-J` yok. `-J` yalnızca `fetch_playlist_entries`
  (liste, arşiv dışı) ve `probe_skip_reason` (indirme sonrası) içinde.
- Arşiv modunda liste çağrısı yok; kanal kimliği `resolve_channel_id` ile ayrı
  bir `--flat-playlist -J --playlist-items 1` çağrısıyla alınıyor
  (`session.py:185-228`).
- `base_dir` kontrolden önce zaten oluşturuluyor (`session.py:431`).
- `ui.pick` Enter ile varsayılan seçmeyi desteklemiyor (`ui.py:133`).
- `PlaylistEntry` süre taşımıyor.
- `session.py` 707 satır; `_process_one_cycle` ~250 satır.

### Bilinen hata: kanal adresinde düz liste

Kurulu yt-dlp 2026.08.19 (`extractor/youtube/_tab.py`), çıplak kanal adresinde
sekmeleri (Videos, Shorts, Live) **iç içe ve içleri doldurulmuş** playlist olarak
döndürür (`_tab.py:2403-2426`: `entries.extend(map(self._real_extract,
extra_tabs))`). `fetch_playlist_entries` yalnızca en üst seviyeyi okuduğu için
kanalda 3 "video" sayar. MP4 modunda kanal adresinin atlanan-video raporunu da
büyük olasılıkla bozuyor. `tests/test_playlist.py::_nested_channel_json` sekmeleri
`_type: "url"` olarak modelliyor; gerçek şekil doldurulmuş.

Shorts girdileri (`shortsLockupViewModel`, `_tab.py:419-433`) `duration` taşımaz
ve adresleri `/shorts/<id>`. Yeni `lockupViewModel` yolu (`_tab.py:380`)
`duration` taşır. *Satır numaraları yt-dlp sürümüyle kayar; uygulamada yeniden
kontrol edilir.*

## 4. Mimari

Hesap, ölçüm ve ekran akışı üç ayrı modülde; `session.py` yalnızca çağırır.

| Modül | Sorumluluk | Bağımlılık |
|---|---|---|
| `estimate.py` (yeni) | Saf hesap: bit hızı tablosu, tekrar eleme, arşiv düşme, süre varsayımı, gereken alan, indirme süresi, biçimlendirme. I/O yok. | yok |
| `speedtest.py` (yeni) | Kısa ağ hızı ölçümü (stdlib). Hatada `None`. | ayarlar (proxy) |
| `preflight.py` (yeni) | UI ile konuşan orkestrasyon. `PreflightResult` döner. Dosya yazmaz. | `estimate`, `speedtest`, `playlist`, `UI` |
| `playlist.py` (değişir) | Özyinelemeli düzleştirme, `duration` ve `is_short`, liste çağrısına `extra_args`, kanal kimliğinin aynı JSON'dan okunması. | — |
| `settings.py`, `settings_menu.py`, `yt_dlp.py`, `models.py`, `i18n` (değişir) | Bölüm 5. | — |

`PreflightResult`: `PROCEED(max_height)`, `CANCEL`, `BAN`, `INTERRUPTED`.
`session.py` bunu `CycleOutcome`'a çevirir: `CANCEL` → `CONTINUE` (loga yazılır),
`INTERRUPTED` → `INTERRUPTED`, `BAN` → `report_ban()` + bugünkü çıkış istemi.

### Akış

Liste ve kanal (MP4, MP3 ve arşiv):

1. Süre uyarısı (bölüm 7.1), ardından liste çağrısı.
2. Hız ölçümü.
3. Tablo (bölüm 8).
4. Çözünürlük sorusu (MP3'te yok; uyumluluk profilinde yok, 1080p sabit).
5. Disk kontrolü; yetmezse *Yine de devam et / İptal*.
6. Arşivde "en az" bekleme uyarısı (bölüm 7.2).
7. İndirme; `CommandBuilder` `max_height` alır.

Tek video (MP4 ve arşiv): yalnızca 4. adım, tablo olmadan. MP3: yalnızca
liste/kanalda 1-3 ve 5, çözünürlük yok.

Arşiv modunda sıra: liste → kanal kimliği → arşiv dosya adı → arşivdekileri
düşme → tahmin. `resolve_channel_id`'nin ayrı çağrısı kalkar; kimlik listeden
okunur. `/channel/UC…` adreslerinde bugünkü gibi istek gerekmez. MP4/MP3
listelerinde zaten çalışan `fetch_playlist_entries` sonucu yeniden kullanılır,
ek istek yok. Arşivin liste çağrısı arşivin `--sleep-requests` beklemesini ve
`network_args`'ı kullanır.

### Hata yönetimi

- Tahmin hesaplanamazsa "boyut hesaplanamadı" yazılır, indirme devam eder.
- rc 130 → `INTERRUPTED`.
- Hata metninde `find_ban_signal` bir sinyal bulursa indirme başlamaz,
  `[BAN-GUARD]` loglanır, `report_ban()` çağrılır (`_archive_file_name` deseni).
- Hız ölçümü başarısızsa yalnızca süre satırları "hesaplanamadı" der.

## 5. Ayarlar ve format seçicileri

### Ayar modeli

- `video.max_height` (MP4 modu) ve `archive.max_height` (arşiv modu). Geçerli
  değerler: 1080, 1440, 2160 veya `null` (sınırsız). Geçersiz değer varsayılana
  düşer (`ArchiveSettings.from_dict` deseni).
- Varsayılanlar: arşiv **1080** (bugünkü davranış), MP4 **`null`** (bugünkü
  davranış). Mevcut kullanıcıda kendiliğinden hiçbir şey değişmez.
- `null` iken seçiciler bugünkü metinleriyle aynıdır; mevcut `test_yt_dlp.py`
  testleri değişmez.
- `s` menüsünde iki giriş, `settings.example.json` ve README güncellenir.

### Seçici dönüşümü (sınır N)

| Yer | Seçici |
|---|---|
| Uyumluluk aşama 1 | `bestvideo[vcodec^=avc1][height<=N]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1][height<=N]` |
| Uyumluluk aşama 2, kalite mkv/mp4, arşiv | `bv*[height<=N]+ba/b[height<=N]` |
| MP3 | değişmez |

- Sınır `/b` yedeğine de uygulanır: sınırın amacı disk. Bedel: yüksekliği
  bilinmeyen bir video "format yok" hatası verebilir. **Doğrulanacak:** yt-dlp'nin
  kendi seçici motoruyla, sentetik format listeleriyle, ağsız test.
- Uyumluluk profilinde sınır `min(ayar, 1080)`.

### Çözünürlük sorusu

- Seçenekler: 1080p, 1440p, 2160p, sınırsız. Ayardaki değer seçeneğin yanında
  "(varsayılan)" ile işaretlenir; `UI` protokolü değişmez, Enter varsayılan seçmez.
- Seçim ayardakinden **farklıysa** ikinci soru: *Yalnızca bu indirme için devam
  et / Varsayılan olarak kaydet ve devam et*. Aynıysa ikinci soru yok.
- Kayıt, moda göre `video.max_height` veya `archive.max_height`'a `save_settings`
  ile yazılır. `preflight.py` dosya yazmaz; `session.py` ona
  `persist_default(max_height)` geri çağrısı verir.
- Kayıt hatası indirmeyi durdurmaz: "Varsayılan kaydedilemedi" uyarısı, indirme
  bu seçimle devam eder.

## 6. Hesap

### Bit hızı tablosu (kbit/s; bilerek yüksek taraf)

| Satır | Değer | Gerekçe |
|---|---|---|
| 1080p video | 6000 | H.264 1080p tipik 3-6 Mbit/s; 60 fps üst ucu. Uyumluluk profili H.264 istediği için VP9'un düşük değeri alınmadı. |
| 1440p video | 12000 | VP9 1440p tipik 6-12 Mbit/s. |
| 2160p video | 30000 | VP9 2160p tipik 15-35 Mbit/s. |
| Ses (`ba`) | 160 | Opus ~130-160, m4a ~128. |
| MP3 VBR q0…q9 | 245 / 225 / 190 / 175 / 165 / 130 / 115 / 100 / 85 / 65 | LAME V0-V9 belgelenmiş ortalamaları; ayardaki `audio_quality` ile seçilir. |
| MP3 modu, diğer biçimler | m4a, opus, best: 160 · flac: 1100 · wav: 1536 | wav 48 kHz × 16 bit × 2 kanal (kesin). flac kayıplı kaynağın açılmış hali (kaba). |

Bayt = süre(sn) × kbit/s × 1000 ÷ 8. **Doğrulanmadı:** tablonun hiçbir değeri
gerçek veriyle doğrulanmadı; hepsi genel bilgiden. Uygulamada izinli test
videosunda tek `-J` çağrısıyla `tbr` değerlerine bakılıp makullük kontrolü
yapılacak; tek örnek olduğu için bu tabloyu kanıtlamaz.

Örnek: 100 video × 10 dk → 1080p ≈ 43 GiB, 1440p ≈ 85 GiB, 2160p ≈ 210 GiB.

### Girdiler ve eleme

- Kimliğe göre tekrarlar elenir. Arşivdekiler (`read_archive_ids`) hariç.
  Kimliksiz girdi sayılır ama eleme dışında kalır.
- Süresi olmayan girdi (Shorts, canlı, prömiyer): `/shorts/` adresliyse 180 sn,
  diğerleri bilinen sürelerin medyanı. Ekranda "N videonun süresi varsayımla
  hesaplandı" yazar. Hiç süre bilinmiyor ve Shorts da değilse: "boyut
  hesaplanamadı".

### Gereken alan

**Seçilen çözünürlükteki toplam + en büyük tek videonun tahmini.** Sebep:
birleştirme, uyumluluk profilinin `--recode-video` aşaması ve MP3 dönüşümü
sırasında kaynak ve çıktı aynı anda diskte durur. MP3'e özel bir inceltme yok.

MP3 modunda tek rakam gösterilir, çözünürlük satırı yoktur.

### İndirme süresi

- Ağa inecek bayt ÷ hız. MP3'te ağa inen kaynak ses (160 kbit/s), çıktı değil.
- `download.rate_limit` ayarlıysa hız `min(ölçülen, limit)`; limit
  ayrıştırılamazsa yok sayılır.

### Hız ölçümü (`speedtest.py`)

- Harici uç nokta, ~5 sn / en fazla ~10 MB. Aday: Cloudflare hız uç noktası
  (`https://speed.cloudflare.com/__down?bytes=10000000`). **Doğrulanmadı:** adres
  ve davranış; gerçek istekten önce kullanıcıdan ayrıca izin istenecek.
- Yalnızca stdlib. `download.proxy` ayarını kullanır. `urllib` SOCKS
  desteklemediği için SOCKS proxy'de ölçüm yapılmaz, `None` döner.
- Zaman aşımı, ağ hatası veya hız 0 → `None`; akış devam eder.
- Üçüncü tarafa IP gider; YouTube'un kısıtlamasını yansıtmaz. README'de yazılır.
- Testlerde her zaman sahte kaynakla çalışır.

## 7. Süre uyarıları

1. **Liste çağrısından önce:** büyük kanal/listede kontrolün birkaç dakika
   sürebileceği (sayfa başına ~30 video, sayfa başına `sleep-requests` kadar
   bekleme).
2. **Arşiv modunda tahminden sonra:** "En az: video sayısı × ortalama bekleme"
   (`(sleep_interval + max_sleep_interval) / 2`), indirme hızı hariç, "en az"
   etiketli.
3. **Tabloda:** ölçülen hıza göre indirme süresi (bölüm 6).

## 8. Ekran

- Sütunlar: Çözünürlük · Boyut · Gereken alan · İndirme süresi.
- 1440p ve 2160p "en fazla" etiketli: düz listede çözünürlük yok, o çözünürlükte
  olmayan video daha düşük iner. 1080p de aslında üst sınırdır ama karar gereği
  etiketlenmez.
- Uyumluluk profilinde yalnızca 1080p satırı ve tek satırlık not.
- Altında: "N video, M'i arşivde (atlandı), K'sı süre varsayımıyla", boş alan.
- Boyutlar 1024 tabanlı (KiB/MiB/GiB), Windows Gezgini ile aynı.
- Boş alan `shutil.disk_usage(base_dir).free`.
- Yetmezse: "Gereken X, boş Y." + *Yine de devam et / İptal*.
- Yeni metinler `tr.json` ve `en.json`'a; `test_locales.py` anahtar eşitliğini
  denetler.

## 9. Test planı

Sıra test-önce. Kanal ve liste davranışı yalnızca fixture ile test edilir;
başka bir video, liste veya kanala gerçek istek yok.

1. **Kanal düzleştirme:** önce bugünkü hatayı gösteren test (iç içe sekmeli JSON'da
   3 "video"), sonra özyinelemeli düzleştirme. Hem `_type: "url"` hem doldurulmuş
   şekil. MP4 modunda atlanan-video raporuna etkisi aynı testle.
2. `estimate.py`: bit hızı, tekrar eleme, arşiv düşme, süre varsayımı (Shorts,
   medyan, hiç süre yok), gereken alan, süre, `rate_limit` ayrıştırma.
3. `speedtest.py`: sahte kaynak; hata, zaman aşımı, SOCKS, proxy.
4. Ayarlar ve seçiciler: `max_height` doğrulaması, `null` iken bugünkü metin,
   `/b` yedeği, yt-dlp seçici motorunda ağsız doğrulama.
5. `preflight.py`: sahte UI ve sahte çalıştırıcı; tablo, çözünürlük sorusu,
   "varsayılan kaydet", disk yetmiyor → devam/iptal, hesaplanamadı → devam,
   rc 130, ban sinyali → indirme başlamaz + `report_ban`, kayıt hatası.
6. `session.py` entegrasyonu: MP4, MP3 ve arşiv × tek, liste, kanal. Arşivde
   kanal kimliğinin listeden okunduğu, `resolve_channel_id`'nin ayrı çağrısının
   kalktığı, `--sleep-requests` ve `network_args`'ın listeye geçtiği.
7. Ayar menüsü, örnek ayar dosyası, README, `tr.json` / `en.json`.

## 10. Bitti demek

- `pytest` (şu an **346** geçiyor; sayı düşmemeli), `ruff check`,
  `ruff format --check` ve `mypy` temiz.
- İzinli test videosuyla gerçek deneme (MP4 ve MP3, uyumluluk ve kalite, arşiv
  tek video); ekran çıktısı raporlanır.
- `TASKS.md` güncel, PR açık. Merge kullanıcıda.

### Gerçek ortamda doğrulanamayacaklar

İzinli tek test videosu tek video olduğu için şunlar yalnızca fixture ve mock
ile doğrulanır ve raporda "gerçek ortamda doğrulanmadı" diye işaretlenir:
tablo, disk kontrolü, süre uyarıları, liste ve kanal akışı, hız testi, bit hızı
değerleri.

## 11. Riskler

- Büyük kanalda arşivin liste çağrısı `--sleep-requests` yüzünden dakikalar
  sürer; bu yüzden 7.1 uyarısı var.
- yt-dlp sürümü değişirse düz liste şekli değişebilir; düzleştirme iki şekli de
  destekler.
- Bit hızı tablosu yüksek tarafta: tahmin gerçekten fazla çıkabilir, eksik
  çıkması hedeflenmedi.
- Hız testi harici bir hizmete bağlı; erişilemezse süre satırları boş kalır,
  indirme etkilenmez.
