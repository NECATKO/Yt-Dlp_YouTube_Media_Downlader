# Boyut tahmini, disk kontrolü ve çözünürlük sınırı — uygulama planı

> **Uygulayıcı için:** ZORUNLU ALT-BECERİ: `superpowers:subagent-driven-development` (önerilen) ya da `superpowers:executing-plans` ile görev görev uygula. Adımlar `- [ ]` kutularıyla izlenir.

**Hedef:** Liste ve kanal indirmelerinde indirmeden önce boyut/süre tahmini ve disk kontrolü göstermek; MP4 ve arşiv modlarına (tek video dahil) tüm format seçicilerine uygulanan bir çözünürlük sınırı eklemek.

**Mimari:** Saf hesap `estimate.py`'de, ağ hızı ölçümü `speedtest.py`'de, ekran akışı ve liste sarmalayıcısı `preflight.py`'de. `session.py` yalnızca çağırır. Liste çağrısı `playlist.py`'de özyinelemeli düzleştirir ve arşivde kanal kimliğini aynı JSON'dan okur. `CommandBuilder` seçilen sınırı alır.

**Teknoloji:** Python ≥ 3.11, yalnızca stdlib (yeni bağımlılık yok), pytest, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-29-disk-space-and-resolution-design.md`

**Spec'ten sapma (davranış aynı, yer farklı):** Spec `PreflightResult`'ın `BAN` ve `INTERRUPTED` dönebileceğini söylüyor. Arşiv modunda dosya adı (kanal kimliği) listeden geldiği için liste çağrısı `preflight`'tan **önce** yapılmak zorunda. Bu yüzden iki aşama var: `guarded_listing` (`OK/FAILED/BAN/INTERRUPTED`) ve `run_preflight` (`PROCEED/CANCEL`). Kullanıcıya görünen davranış spec'tekiyle aynıdır.

## Genel kısıtlar (her görev için geçerli)

- Python ≥ 3.11; satır uzunluğu 100; `mypy ytdlp_app --ignore-missing-imports` temiz (CI böyle çalıştırıyor).
- **Ağa hiçbir test çıkmaz.** Hız ölçümü, liste çağrısı ve disk alanı testlerde sahte fonksiyonla değiştirilir. Gerçek istek yalnızca Görev 10'da ve yalnızca `https://www.youtube.com/watch?v=izx6nkLpoOA` ile.
- `tr.json` yalnızca ASCII içerir (Türkçe karakter yok); `en.json` ile aynı `{yer_tutucu}` kümesi (test_locales denetler).
- Kullanıcıya görünen her yeni metin `t()` ile ve iki dil dosyasında.
- Kapsam dışı: otomatik güncelleyici/release, repo adı, `run.sh` çalıştırma izni. `main`'e commit, merge, tag, force-push ve dosya silme yok.
- Test sayısı 346'nın altına düşmemeli. Her görevin sonunda `pytest` tam çalıştırılır.
- Her commit iletisi şu satırla biter: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
- Doğrulama komutları (her görev sonunda): 
  `.venv/bin/python -m pytest -q` · `.venv/bin/ruff check . && .venv/bin/ruff format --check .` · `.venv/bin/mypy ytdlp_app --ignore-missing-imports`
  Import sırası ya da biçim hatasında `.venv/bin/ruff check --fix . && .venv/bin/ruff format .` çalıştır.

## Gözden geçirme odağı

Spec'in ima ettiği ama görev testlerinin doğal olarak kapsamadığı durumlar; her birinin testi sahibi görevde:

1. **Kanal listesi iki şekilde gelir** (doldurulmuş sekmeler ve açılmamış `YoutubeTab` kalıntıları): kalıntılar sayılmaz, hepsi kalıntıysa "boyut hesaplanamadı" yazılır ve indirme sürer. → Görev 2 ve 7.
2. **Listedeki her video zaten arşivde:** "yeni bir şey yok" denir, çözünürlük sorusu sorulmaz, hata yok. → Görev 7.
3. **Hiçbir girdinin süresi yok** (Shorts da değil): tahmin yapılmaz, indirme sürer. → Görev 3 ve 7.
4. **Elle bozulmuş ayar dosyası:** `max_height` 720, `"1080"`, `true`, `1080.5` → varsayılana düşer, program açılır. → Görev 5.
5. **Ölçülemeyen şeyler indirmeyi durdurmaz:** boş disk alanı (`OSError`), hız (SOCKS proxy, ağ hatası), varsayılan kaydı (yazma hatası). → Görev 4 ve 7.
6. **Ctrl+C liste sırasında:** `INTERRUPTED`, indirme başlamaz. → Görev 7 ve 8.

---

## Dosya haritası

| Dosya | Durum | Sorumluluk |
|---|---|---|
| `ytdlp_app/estimate.py` | yeni | Saf hesap ve biçimlendirme |
| `ytdlp_app/speedtest.py` | yeni | Kısa ağ hızı ölçümü |
| `ytdlp_app/preflight.py` | yeni | `guarded_listing`, `run_preflight`, `free_bytes` |
| `ytdlp_app/playlist.py` | değişir | `fetch_listing`, düzleştirme, `duration`/`is_short`; `resolve_channel_id` kalkar (Görev 8) |
| `ytdlp_app/models.py` | değişir | `PlaylistEntry` +`duration`, +`is_short` |
| `ytdlp_app/settings.py` | değişir | `max_height` alanları, `listing_args` |
| `ytdlp_app/settings_menu.py` | değişir | İki yeni menü girişi |
| `ytdlp_app/yt_dlp.py` | değişir | Seçici fonksiyonları, `set_max_height` |
| `ytdlp_app/session.py` | değişir | Liste, preflight, sınırın komuta iletilmesi |
| `ytdlp_app/locales/en.json`, `tr.json` | değişir | Yeni metinler (Görev 1) |
| `tests/test_estimate.py`, `test_speedtest.py`, `test_preflight.py`, `test_session_preflight.py` | yeni | |
| `tests/test_playlist.py`, `test_settings.py`, `test_settings_menu.py`, `test_yt_dlp.py`, `test_session_archive.py`, `conftest.py` | değişir | |
| `settings.example.json`, `README.md`, `CHANGELOG.md`, `TASKS.md` | değişir | |

---

### Görev 1: Kontrol listesi ve yeni metinler

**Dosyalar:**
- Değişir: `TASKS.md` (sona bölüm ekle)
- Değişir: `ytdlp_app/locales/en.json`, `ytdlp_app/locales/tr.json`

**Arayüzler:**
- Üretir: aşağıdaki `t()` anahtarları; sonraki görevler bunları adıyla kullanır.

- [ ] **Adım 1: TASKS.md'ye kontrol listesi ekle**

```bash
cat >> TASKS.md <<'EOF'

## Boyut tahmini, disk kontrolü ve çözünürlük sınırı
Dal: `feat/disk-space-and-resolution` · Spec: `docs/superpowers/specs/2026-09-29-disk-space-and-resolution-design.md` · Plan: `docs/superpowers/plans/2026-09-29-disk-space-and-resolution.md`

- [x] Spec yazıldı ve onaylandı
- [x] Plan yazıldı
- [x] Yeni metinler (`en.json`, `tr.json`)
- [ ] Kanal düzleştirme hatası: önce test, sonra düzeltme (`playlist.py`)
- [ ] `estimate.py` (hesap ve biçimlendirme)
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
- (uygulama sırasında eklenir)
EOF
```

- [ ] **Adım 2: `en.json` sonuna anahtarları ekle**

`ytdlp_app/locales/en.json` dosyasında son satırı bul ve Edit ile değiştir:

eski:
```
  "config_file_at": "Config: {path}"
}
```
yeni:
```
  "config_file_at": "Config: {path}",
  "preflight_listing_warning": "Reading a large channel or playlist can take several minutes: about 30 videos are read per page.",
  "preflight_listing_warning_wait": " Each page also waits {seconds} s between requests.",
  "preflight_measuring_speed": "Measuring connection speed (a few seconds)...",
  "preflight_speed_measured": "Measured speed: {mbps} Mbit/s",
  "preflight_speed_unknown": "Connection speed could not be measured; download time is not estimated.",
  "estimate_title": "Estimated size (high-side estimate: duration x typical bit rate)",
  "estimate_col_resolution": "Resolution",
  "estimate_col_format": "Format",
  "estimate_col_size": "Size",
  "estimate_col_needed": "Space needed",
  "estimate_col_time": "Download time",
  "estimate_row_plain": "{height}p",
  "estimate_row_at_most": "{height}p (at most)",
  "estimate_time_unknown": "n/a",
  "estimate_summary": "{count} videos to download, {archived} already in the archive, {assumed} with an assumed duration",
  "estimate_free_space": "Free space: {free}",
  "estimate_unavailable": "Size could not be calculated; the download continues.",
  "estimate_nothing_new": "Every video in this list is already in the archive; nothing new to download.",
  "estimate_free_unknown": "Free disk space could not be measured; skipping the space check.",
  "estimate_compat_note": "The compatibility profile is limited to 1080p (H.264).",
  "disk_low_warning": "Not enough free space: about {needed} needed, {free} free.",
  "disk_low_prompt": "What do you want to do?",
  "disk_low_continue": "Continue anyway",
  "disk_low_cancel": "Cancel",
  "disk_low_cancelled": "Cancelled: not enough free disk space.",
  "archive_wait_minimum": "Waiting between videos alone will take at least {duration} ({count} videos, about {average} s each); download time is not included.",
  "duration_days_hours": "{days} d {hours} h",
  "duration_hours_minutes": "{hours} h {minutes} min",
  "duration_minutes": "{minutes} min",
  "duration_seconds": "{seconds} s",
  "prompt_resolution": "Choose the maximum resolution:",
  "resolution_option": "{height}p",
  "resolution_unlimited": "Unlimited",
  "resolution_default_mark": "{label} (default)",
  "prompt_resolution_save": "Use this choice only for this download, or make it the default?",
  "resolution_save_once": "Only for this download",
  "resolution_save_default": "Save as default and continue",
  "resolution_save_failed": "Could not save the default ({error}). Continuing with your choice.",
  "settings_video_height": "Video resolution limit (MP4 mode)",
  "settings_archive_height": "Archive resolution limit"
}
```

- [ ] **Adım 3: `tr.json` sonuna aynı anahtarları (ASCII Türkçe) ekle**

eski:
```
  "config_file_at": "Yapilandirma: {path}"
}
```
yeni:
```
  "config_file_at": "Yapilandirma: {path}",
  "preflight_listing_warning": "Buyuk bir kanali ya da listeyi okumak birkac dakika surebilir: sayfa basina yaklasik 30 video okunur.",
  "preflight_listing_warning_wait": " Her sayfada istekler arasinda ayrica {seconds} sn beklenir.",
  "preflight_measuring_speed": "Baglanti hizi olculuyor (birkac saniye)...",
  "preflight_speed_measured": "Olculen hiz: {mbps} Mbit/sn",
  "preflight_speed_unknown": "Baglanti hizi olculemedi; indirme suresi tahmin edilmedi.",
  "estimate_title": "Tahmini boyut (yuksek taraftan tahmin: sure x tipik bit hizi)",
  "estimate_col_resolution": "Cozunurluk",
  "estimate_col_format": "Bicim",
  "estimate_col_size": "Boyut",
  "estimate_col_needed": "Gereken alan",
  "estimate_col_time": "Indirme suresi",
  "estimate_row_plain": "{height}p",
  "estimate_row_at_most": "{height}p (en fazla)",
  "estimate_time_unknown": "yok",
  "estimate_summary": "{count} video indirilecek, {archived} tanesi arsivde, {assumed} tanesinin suresi varsayimla hesaplandi",
  "estimate_free_space": "Bos alan: {free}",
  "estimate_unavailable": "Boyut hesaplanamadi; indirme devam ediyor.",
  "estimate_nothing_new": "Bu listedeki her video zaten arsivde; indirilecek yeni bir sey yok.",
  "estimate_free_unknown": "Bos disk alani olculemedi; alan kontrolu atlandi.",
  "estimate_compat_note": "Uyumluluk profili 1080p (H.264) ile sinirlidir.",
  "disk_low_warning": "Bos alan yetersiz: yaklasik {needed} gerekiyor, {free} bos.",
  "disk_low_prompt": "Ne yapmak istersin?",
  "disk_low_continue": "Yine de devam et",
  "disk_low_cancel": "Iptal",
  "disk_low_cancelled": "Iptal edildi: bos disk alani yetersiz.",
  "archive_wait_minimum": "Yalnizca videolar arasi beklemeler en az {duration} surecek ({count} video, her biri icin yaklasik {average} sn); indirme suresi dahil degil.",
  "duration_days_hours": "{days} g {hours} sa",
  "duration_hours_minutes": "{hours} sa {minutes} dk",
  "duration_minutes": "{minutes} dk",
  "duration_seconds": "{seconds} sn",
  "prompt_resolution": "En yuksek cozunurlugu sec:",
  "resolution_option": "{height}p",
  "resolution_unlimited": "Sinirsiz",
  "resolution_default_mark": "{label} (varsayilan)",
  "prompt_resolution_save": "Bu secim yalnizca bu indirme icin mi gecerli olsun, varsayilan mi yapilsin?",
  "resolution_save_once": "Yalnizca bu indirme icin",
  "resolution_save_default": "Varsayilan olarak kaydet ve devam et",
  "resolution_save_failed": "Varsayilan kaydedilemedi ({error}). Secimle devam ediliyor.",
  "settings_video_height": "Video cozunurluk siniri (MP4 modu)",
  "settings_archive_height": "Arsiv cozunurluk siniri"
}
```

- [ ] **Adım 4: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_locales.py -q`
Beklenen: PASS (anahtar eşitliği ve yer tutucu eşleşmesi). Ardından `.venv/bin/python -c "import json;[json.load(open(f'ytdlp_app/locales/{l}.json',encoding='utf-8')) for l in ('en','tr')]"` hatasız çalışmalı.

- [ ] **Adım 5: Commit**

```bash
git add TASKS.md ytdlp_app/locales/en.json ytdlp_app/locales/tr.json
git commit -m "docs: add TASKS checklist and locale strings for size estimate and resolution cap" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 2: Kanal düzleştirme hatası ve `fetch_listing`

**Dosyalar:**
- Değişir: `ytdlp_app/models.py` (`PlaylistEntry`)
- Değişir: `ytdlp_app/playlist.py`
- Test: `tests/test_playlist.py`

**Arayüzler:**
- Üretir:
  - `PlaylistEntry(playlist_index: int, id: str, title: str, watch_url: str, duration: float | None = None, is_short: bool = False)`
  - `PlaylistListing(entries: list[PlaylistEntry], channel_id: str | None)` (frozen dataclass)
  - `fetch_listing(url: str, extra_args: list[str], runner: CaptureRunner) -> PlaylistListing`; rc 130'da `KeyboardInterrupt`, başarısızlıkta `PlaylistError` fırlatır.
  - `fetch_playlist_entries(url, js_args, runner) -> list[PlaylistEntry]` aynı imzayla kalır; artık `fetch_listing(...).entries` döner.
- Tüketir: mevcut `_find_channel_id`, `channel_id_from_url`, `CaptureRunner`, `PlaylistError`, `t`.

- [ ] **Adım 1: Hatayı gösteren testi yaz**

`tests/test_playlist.py` içinde import listesine dokunma (`fetch_playlist_entries` henüz import edilmemiş; ekle). Import bloğunu şöyle yap:

```python
from ytdlp_app.playlist import (
    channel_id_from_url,
    fetch_playlist_entries,
    get_playlist_id,
    is_channel_url,
    is_playlist_url,
    read_archive_ids,
    resolve_channel_id,
    safe_archive_token,
)
```

Dosyanın sonuna ekle:

```python
def _video(vid: str, *, duration: Any = None, short: bool = False) -> dict[str, Any]:
    """One flat-listing video entry, as yt-dlp emits it."""
    path = f"shorts/{vid}" if short else f"watch?v={vid}"
    raw: dict[str, Any] = {
        "_type": "url",
        "ie_key": "Youtube",
        "id": vid,
        "url": f"https://www.youtube.com/{path}",
        "title": f"Title {vid}",
    }
    if duration is not None:
        raw["duration"] = duration
    return raw


def _filled_channel_json() -> dict[str, Any]:
    """What yt-dlp really returns for a bare channel URL: the tabs come back as
    nested playlists whose entries are already filled in (extractor/youtube/_tab.py
    runs _real_extract on each extra tab)."""
    return {
        "_type": "playlist",
        "id": CHANNEL_ID,
        "channel_id": CHANNEL_ID,
        "title": "Channel",
        "entries": [
            {
                "_type": "playlist",
                "id": "videos-tab",
                "title": "Channel - Videos",
                "entries": [_video("vid1", duration=600), _video("vid2", duration=300)],
            },
            {
                "_type": "playlist",
                "id": "shorts-tab",
                "title": "Channel - Shorts",
                "entries": [_video("sh1", short=True)],
            },
        ],
    }


class TestFlatListing:
    def test_channel_tabs_are_flattened_into_their_videos(self) -> None:
        runner = FakeRunner(out=json.dumps(_filled_channel_json()))

        entries = fetch_playlist_entries("https://www.youtube.com/@ChannelHandle", [], runner)

        assert [e.id for e in entries] == ["vid1", "vid2", "sh1"]
        assert [e.playlist_index for e in entries] == [1, 2, 3]
```

- [ ] **Adım 2: Testin şimdiki hatayla düştüğünü gör**

Çalıştır: `.venv/bin/python -m pytest tests/test_playlist.py::TestFlatListing -v`
Beklenen: FAIL, `assert ['videos-tab', 'shorts-tab'] == ['vid1', 'vid2', 'sh1']` (kanalda üç "video" değil iki sekme sayılıyor: hata gösterildi). Çıktıyı TASKS.md "Bulunanlar" bölümüne bir satırla not et.

- [ ] **Adım 3: Uygula**

`ytdlp_app/models.py` içinde `PlaylistEntry`:

```text
    Attributes:
        playlist_index: 1-based position in the playlist.
        id: Video/audio identifier (e.g., YouTube video ID).
        title: Display title of the entry.
        watch_url: Direct URL to watch/play this entry.
        duration: Length in seconds, or None when the listing did not carry one
            (Shorts and live/upcoming items).
        is_short: Whether the listing gave a /shorts/ address for the entry.
    """

    playlist_index: int
    id: str
    title: str
    watch_url: str
    duration: float | None = None
    is_short: bool = False
```

`ytdlp_app/playlist.py`: `from dataclasses import dataclass` ekle (import bloğunda `import json`, `import re` yanına) ve `fetch_playlist_entries`'i şununla değiştir (dosyanın sonu; `resolve_channel_id` yerinde kalır, Görev 8'de kalkar):

```python
#: yt-dlp's key for a channel tab or playlist that was listed but not expanded.
_TAB_IE_KEY = "YoutubeTab"


@dataclass(frozen=True, slots=True)
class PlaylistListing:
    """What one flat listing of a playlist or channel returned.

    Attributes:
        entries: The videos, with channel tabs flattened into one list.
        channel_id: The channel id when the URL or the listing carries one.
    """

    entries: list[PlaylistEntry]
    channel_id: str | None


def _leaf_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect the video entries of a flat listing, descending into nested playlists.

    A bare channel URL comes back as a playlist of tab playlists (Videos, Shorts,
    Live). Their contents are already there, so nothing extra is requested. A tab
    that is only a stub (an unexpanded YoutubeTab reference) has no videos to
    read and is skipped rather than fetched.
    """
    leaves: list[dict[str, Any]] = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("entries"), list):
            leaves.extend(_leaf_entries(entry))
        elif entry.get("ie_key") == _TAB_IE_KEY:
            continue
        else:
            leaves.append(entry)
    return leaves


def _as_duration(value: Any) -> float | None:
    """Return a usable duration in seconds, or None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value > 0 else None


def _to_entry(index: int, raw: dict[str, Any]) -> PlaylistEntry:
    vid = raw.get("id") or raw.get("url")
    url = raw.get("url")
    return PlaylistEntry(
        playlist_index=index,
        id=vid or "",
        title=raw.get("title") or "",
        watch_url=f"https://www.youtube.com/watch?v={vid}" if vid else "",
        duration=_as_duration(raw.get("duration")),
        is_short=isinstance(url, str) and "/shorts/" in url,
    )


def fetch_listing(url: str, extra_args: list[str], runner: CaptureRunner) -> PlaylistListing:
    """List a playlist or channel with one flat yt-dlp request.

    Args:
        url: The playlist or channel URL.
        extra_args: JS runtime, pacing, proxy and rate-limit arguments.
        runner: Executes yt-dlp and captures its output.

    Raises:
        PlaylistError: yt-dlp failed or returned unusable output.
        KeyboardInterrupt: the user pressed Ctrl+C during the request.
    """
    cmd = ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", url, *extra_args]
    rc, out, err = runner(cmd)
    if rc == 130:
        # run_capture turns Ctrl+C into a return code; carrying on would start
        # the download the user just cancelled.
        raise KeyboardInterrupt
    if rc != 0 or not out.strip():
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))

    try:
        data = json.loads(out)
    except json.JSONDecodeError as ex:
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=str(ex))) from ex
    if not isinstance(data, dict):
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))

    entries = [_to_entry(i, raw) for i, raw in enumerate(_leaf_entries(data), start=1)]
    return PlaylistListing(
        entries=entries,
        channel_id=channel_id_from_url(url) or _find_channel_id(data),
    )


def fetch_playlist_entries(
    url: str, js_args: list[str], runner: CaptureRunner
) -> list[PlaylistEntry]:
    """List the videos of a playlist or channel (see fetch_listing)."""
    return fetch_listing(url, js_args, runner).entries
```

Ve mevcut `fetch_playlist_entries` gövdesini (eski sürüm) sil.

- [ ] **Adım 4: Kalan testleri ekle**

`tests/test_playlist.py` import bloğuna `PlaylistListing` gerekmez; `fetch_listing` ekle (`channel_id_from_url` satırının altına, alfabetik) ve sonuna ekle:

```python
class TestFetchListing:
    URL = "https://www.youtube.com/@ChannelHandle"

    def test_unexpanded_tab_stubs_contribute_no_videos(self) -> None:
        runner = FakeRunner(out=json.dumps(_nested_channel_json()))
        assert fetch_listing(self.URL, [], runner).entries == []

    def test_expanded_and_stub_tabs_can_be_mixed(self) -> None:
        data = _filled_channel_json()
        data["entries"].append(
            {
                "_type": "url",
                "ie_key": "YoutubeTab",
                "url": "https://www.youtube.com/@ChannelHandle/streams",
                "title": "Channel - Live",
            }
        )
        entries = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(data))).entries
        assert [e.id for e in entries] == ["vid1", "vid2", "sh1"]

    def test_duration_and_shorts_are_carried(self) -> None:
        entries = fetch_listing(
            self.URL, [], FakeRunner(out=json.dumps(_filled_channel_json()))
        ).entries
        vid1, _vid2, short = entries

        assert vid1.duration == 600.0
        assert vid1.is_short is False
        assert short.duration is None
        assert short.is_short is True
        # The watch URL stays a plain watch URL, which is what the skip probe wants.
        assert short.watch_url == "https://www.youtube.com/watch?v=sh1"

    @pytest.mark.parametrize("bad", ["abc", True, 0, -5])
    def test_unusable_durations_are_dropped(self, bad: Any) -> None:
        data = {"_type": "playlist", "entries": [{**_video("v1"), "duration": bad}]}
        (entry,) = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(data))).entries
        assert entry.duration is None

    def test_channel_id_is_read_from_the_listing(self) -> None:
        listing = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(_filled_channel_json())))
        assert listing.channel_id == CHANNEL_ID

    def test_channel_id_in_the_url_wins(self) -> None:
        data = {"_type": "playlist", "entries": [_video("v1")]}
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}"
        listing = fetch_listing(url, [], FakeRunner(out=json.dumps(data)))
        assert listing.channel_id == CHANNEL_ID

    def test_plain_playlist_has_no_channel_id(self, sample_playlist_json: dict[str, Any]) -> None:
        listing = fetch_listing(
            "https://www.youtube.com/playlist?list=PLtest123",
            [],
            FakeRunner(out=json.dumps(sample_playlist_json)),
        )
        assert listing.channel_id is None

    def test_extra_args_follow_the_url_and_nothing_limits_the_listing(self) -> None:
        runner = FakeRunner(out=json.dumps(_filled_channel_json()))
        extra = ["--sleep-requests", "1.5", "--proxy", "http://p:1"]

        fetch_listing(self.URL, extra, runner)

        (cmd,) = runner.calls
        assert cmd == ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", self.URL, *extra]

    def test_interrupt_is_raised(self) -> None:
        with pytest.raises(KeyboardInterrupt):
            fetch_listing(self.URL, [], FakeRunner(rc=130))

    def test_failure_raises_with_stderr(self) -> None:
        with pytest.raises(PlaylistError, match="boom"):
            fetch_listing(self.URL, [], FakeRunner(rc=1, err="boom"))

    @pytest.mark.parametrize("out", ["not json", "[]", "   "])
    def test_unusable_output_raises(self, out: str) -> None:
        with pytest.raises(PlaylistError):
            fetch_listing(self.URL, [], FakeRunner(out=out))

    def test_fetch_playlist_entries_still_lists_a_plain_playlist(
        self, sample_playlist_json: dict[str, Any]
    ) -> None:
        entries = fetch_playlist_entries(
            "https://www.youtube.com/playlist?list=PLtest123",
            [],
            FakeRunner(out=json.dumps(sample_playlist_json)),
        )
        assert [e.id for e in entries] == ["vid1", "vid2", "vid3"]
        assert entries[0].watch_url == "https://www.youtube.com/watch?v=vid1"
```

- [ ] **Adım 5: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_playlist.py -v`
Beklenen: hepsi PASS (eski `resolve_channel_id` testleri dahil). Sonra tam paket: `.venv/bin/python -m pytest -q` → 346'dan fazla, hepsi geçer. ruff ve mypy komutları temiz.

- [ ] **Adım 6: Commit**

```bash
git add ytdlp_app/models.py ytdlp_app/playlist.py tests/test_playlist.py TASKS.md
git commit -m "fix: flatten nested channel tabs in the playlist listing" -m "A bare channel URL returns its tabs as filled-in nested playlists, so the flat listing counted the tabs instead of the videos. Add fetch_listing, which flattens them and carries duration and shorts info." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

(TASKS.md'yi yalnızca "Bulunanlar" notunu eklediysen `git add` et; bu görevin kutusunu `[x]` yap.)

---

### Görev 3: `estimate.py`

**Dosyalar:**
- Oluşturur: `ytdlp_app/estimate.py`
- Test: `tests/test_estimate.py`

**Arayüzler:**
- Tüketir: `PlaylistEntry` (Görev 2), `t()` (Görev 1 anahtarları `duration_*`).
- Üretir (Görev 7 kullanır):
  - `RESOLUTIONS: tuple[int, ...] = (1080, 1440, 2160)`
  - `audio_output_kbps(audio_format: str, audio_quality: int) -> int`
  - `size_bytes(seconds: float, kbps: int) -> int`
  - `VideoSet(seconds: tuple[float, ...], assumed: int, archived: int)` + `.count`, `.total_seconds`, `.longest_seconds`
  - `plan_videos(entries: Iterable[PlaylistEntry], archived_ids: Collection[str]) -> VideoSet | None`
  - `SizeEstimate(height: int | None, total_bytes: int, required_bytes: int, download_bytes: int)`
  - `estimate_video(videos: VideoSet, height: int) -> SizeEstimate`, `estimate_audio(videos: VideoSet, output_kbps: int) -> SizeEstimate`
  - `parse_rate_limit(text: str | None) -> float | None`, `effective_speed(measured: float | None, rate_limit: str | None) -> float | None`
  - `download_seconds(download_bytes: int, bytes_per_second: float | None) -> float | None`
  - `archive_wait_seconds(count: int, sleep_interval: float, max_sleep_interval: float) -> float`
  - `format_size(num_bytes: float) -> str`, `format_duration(seconds: float) -> str`

- [ ] **Adım 1: Testleri yaz**

`tests/test_estimate.py`:

```python
"""Tests for ytdlp_app.estimate: the pure size, space and time arithmetic."""

import pytest

from ytdlp_app.estimate import (
    RESOLUTIONS,
    VideoSet,
    archive_wait_seconds,
    audio_output_kbps,
    download_seconds,
    effective_speed,
    estimate_audio,
    estimate_video,
    format_duration,
    format_size,
    parse_rate_limit,
    plan_videos,
    size_bytes,
)
from ytdlp_app.i18n import set_language
from ytdlp_app.models import PlaylistEntry


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


def _entry(vid: str, duration: float | None = None, *, short: bool = False) -> PlaylistEntry:
    return PlaylistEntry(
        playlist_index=1,
        id=vid,
        title="t",
        watch_url=f"https://www.youtube.com/watch?v={vid}",
        duration=duration,
        is_short=short,
    )


class TestBitRates:
    def test_size_is_seconds_times_kilobits_over_eight(self) -> None:
        assert size_bytes(3600, 8) == 3_600_000

    @pytest.mark.parametrize(
        ("fmt", "quality", "expected"),
        [
            ("mp3", 0, 245),
            ("mp3", 5, 130),
            ("mp3", 9, 65),
            ("mp3", 99, 65),
            ("mp3", -1, 245),
            ("flac", 0, 1100),
            ("wav", 0, 1536),
            ("m4a", 0, 160),
            ("opus", 0, 160),
            ("best", 0, 160),
            ("aac", 0, 160),
        ],
    )
    def test_audio_output_bit_rate(self, fmt: str, quality: int, expected: int) -> None:
        assert audio_output_kbps(fmt, quality) == expected

    def test_offered_resolutions(self) -> None:
        assert RESOLUTIONS == (1080, 1440, 2160)


class TestPlanVideos:
    def test_duplicates_by_id_are_counted_once(self) -> None:
        videos = plan_videos([_entry("a", 100), _entry("a", 100), _entry("b", 200)], set())
        assert videos is not None
        assert videos.seconds == (100.0, 200.0)

    def test_archived_videos_are_left_out_and_counted(self) -> None:
        videos = plan_videos([_entry("a", 100), _entry("b", 200)], {"a"})
        assert videos is not None
        assert videos.seconds == (200.0,)
        assert videos.archived == 1

    def test_entries_without_an_id_are_kept_each(self) -> None:
        videos = plan_videos([_entry("", 100), _entry("", 100)], {""})
        assert videos is not None
        assert videos.count == 2

    def test_shorts_without_a_duration_get_180_seconds(self) -> None:
        videos = plan_videos([_entry("a", 600), _entry("s", None, short=True)], set())
        assert videos is not None
        assert videos.seconds == (600.0, 180.0)
        assert videos.assumed == 1

    def test_other_missing_durations_get_the_median(self) -> None:
        entries = [_entry("a", 100), _entry("b", 300), _entry("c", 500), _entry("d")]
        videos = plan_videos(entries, set())
        assert videos is not None
        assert videos.seconds == (100.0, 300.0, 500.0, 300.0)
        assert videos.assumed == 1

    def test_the_median_also_counts_archived_videos(self) -> None:
        videos = plan_videos([_entry("x", 1000), _entry("y")], {"x"})
        assert videos is not None
        assert videos.seconds == (1000.0,)

    def test_an_archived_video_without_a_duration_is_not_an_assumption(self) -> None:
        videos = plan_videos([_entry("a", 100), _entry("z")], {"z"})
        assert videos is not None
        assert videos.assumed == 0

    def test_no_known_duration_and_no_shorts_cannot_be_estimated(self) -> None:
        assert plan_videos([_entry("a"), _entry("b")], set()) is None

    def test_only_shorts_can_still_be_estimated(self) -> None:
        videos = plan_videos([_entry("s1", None, short=True)], set())
        assert videos is not None
        assert videos.seconds == (180.0,)

    def test_no_entries_cannot_be_estimated(self) -> None:
        assert plan_videos([], set()) is None

    def test_everything_archived_leaves_nothing_to_download(self) -> None:
        videos = plan_videos([_entry("a", 100)], {"a"})
        assert videos is not None
        assert videos.count == 0
        assert videos.archived == 1

    def test_video_set_totals(self) -> None:
        videos = VideoSet(seconds=(60.0, 120.0), assumed=0, archived=0)
        assert videos.count == 2
        assert videos.total_seconds == 180.0
        assert videos.longest_seconds == 120.0
        assert VideoSet((), 0, 0).longest_seconds == 0.0


class TestEstimates:
    VIDEOS = VideoSet(seconds=(600.0, 1200.0), assumed=0, archived=0)

    def test_video_1080p(self) -> None:
        estimate = estimate_video(self.VIDEOS, 1080)
        # (6000 + 160) kbit/s: 462 MB for 600 s, 924 MB for 1200 s.
        assert estimate.height == 1080
        assert estimate.total_bytes == 1_386_000_000
        # Space needed = everything + the largest single video (source and output coexist).
        assert estimate.required_bytes == 1_386_000_000 + 924_000_000
        assert estimate.download_bytes == estimate.total_bytes

    def test_higher_resolutions_need_more(self) -> None:
        sizes = [estimate_video(self.VIDEOS, h).total_bytes for h in RESOLUTIONS]
        assert sizes == sorted(sizes)
        assert len(set(sizes)) == 3

    def test_audio_counts_output_for_space_and_the_source_for_the_download(self) -> None:
        videos = VideoSet(seconds=(600.0,), assumed=0, archived=0)
        estimate = estimate_audio(videos, 245)

        assert estimate.height is None
        assert estimate.total_bytes == 18_375_000
        assert estimate.required_bytes == 36_750_000
        # The network carries the ~160 kbit/s source stream, not the MP3.
        assert estimate.download_bytes == 12_000_000


class TestSpeed:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1M", 1024.0**2),
            ("500K", 512_000.0),
            ("4.2M", 4.2 * 1024**2),
            ("2g", 2 * 1024.0**3),
            ("50", 50.0),
        ],
    )
    def test_rate_limit_is_parsed(self, text: str, expected: float) -> None:
        assert parse_rate_limit(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["fast", "", None, "0", "M", "1 M"])
    def test_unusable_rate_limits_are_ignored(self, text: str | None) -> None:
        assert parse_rate_limit(text) is None

    def test_effective_speed_is_capped_by_the_limit(self) -> None:
        assert effective_speed(2_000_000, "1M") == 1024.0**2
        assert effective_speed(500_000, "1M") == 500_000

    def test_effective_speed_without_a_measurement_is_unknown(self) -> None:
        assert effective_speed(None, "1M") is None
        assert effective_speed(0, None) is None

    def test_an_unusable_limit_does_not_change_the_speed(self) -> None:
        assert effective_speed(1_000_000, "bogus") == 1_000_000

    def test_download_seconds(self) -> None:
        assert download_seconds(1000, 100.0) == 10.0
        assert download_seconds(1000, None) is None
        assert download_seconds(1000, 0.0) is None


class TestArchiveWait:
    def test_average_wait_times_video_count(self) -> None:
        assert archive_wait_seconds(10, 15, 45) == 300.0

    def test_a_max_below_the_min_is_treated_as_the_min(self) -> None:
        assert archive_wait_seconds(10, 20, 5) == 200.0


class TestFormatting:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0 B"),
            (1023, "1023 B"),
            (1024, "1.0 KiB"),
            (1536, "1.5 KiB"),
            (1024**2, "1.0 MiB"),
            (43 * 1024**3, "43.0 GiB"),
            (5 * 1024**4, "5.0 TiB"),
            (2000 * 1024**4, "2000.0 TiB"),
            (-5, "0 B"),
        ],
    )
    def test_sizes_are_1024_based(self, value: float, expected: str) -> None:
        assert format_size(value) == expected

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "0 s"),
            (45, "45 s"),
            (90, "1 min"),
            (3600, "1 h 0 min"),
            (3720, "1 h 2 min"),
            (90000, "1 d 1 h"),
        ],
    )
    def test_durations(self, seconds: float, expected: str) -> None:
        assert format_duration(seconds) == expected

    def test_durations_follow_the_language(self) -> None:
        set_language("tr")
        assert format_duration(3720) == "1 sa 2 dk"
```

- [ ] **Adım 2: Düştüğünü gör**

Çalıştır: `.venv/bin/python -m pytest tests/test_estimate.py -q`
Beklenen: `ModuleNotFoundError: No module named 'ytdlp_app.estimate'`.

- [ ] **Adım 3: Uygula**

`ytdlp_app/estimate.py`:

```python
"""Size, disk-space and time estimates for a listing, made before downloading.

Nothing here touches the network or the disk. The numbers are deliberately on
the high side: a flat listing carries a duration but no resolution, so the
bit rates below stand in for "a typical video at that resolution". Running out
of space mid-download is worse than being told to expect a bit more.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .i18n import t

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from .models import PlaylistEntry

#: The resolution caps the estimate table shows.
RESOLUTIONS: Final[tuple[int, ...]] = (1080, 1440, 2160)

#: Video bit rate in kbit/s per resolution. 1080p is YouTube's H.264 upper end
#: (60 fps), because the compatibility profile asks for H.264; 1440p and 2160p
#: are the upper end of typical VP9.
VIDEO_KBPS: Final[dict[int, int]] = {1080: 6000, 1440: 12000, 2160: 30000}

#: Bit rate of the audio stream YouTube pairs with the video (Opus ~130-160, m4a ~128).
AUDIO_KBPS: Final = 160

#: LAME's documented average bit rates for VBR quality 0 (best) to 9.
MP3_VBR_KBPS: Final = (245, 225, 190, 175, 165, 130, 115, 100, 85, 65)

#: Output bit rate for the other audio formats. wav is exact (48 kHz x 16 bit x 2
#: channels); flac is the decoded lossy source, so it is rough.
AUDIO_OUTPUT_KBPS: Final[dict[str, int]] = {
    "m4a": 160,
    "opus": 160,
    "best": 160,
    "flac": 1100,
    "wav": 1536,
}

#: Assumed length of a Short whose listing entry has no duration.
SHORT_SECONDS: Final = 180.0

_RATE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)([KMGT]?)$", re.IGNORECASE)
_RATE_UNITS: Final = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
_SIZE_UNITS: Final = ("B", "KiB", "MiB", "GiB", "TiB")


def audio_output_kbps(audio_format: str, audio_quality: int) -> int:
    """Bit rate of the file the audio settings produce."""
    if audio_format == "mp3":
        index = min(max(audio_quality, 0), len(MP3_VBR_KBPS) - 1)
        return MP3_VBR_KBPS[index]
    return AUDIO_OUTPUT_KBPS.get(audio_format, AUDIO_KBPS)


def size_bytes(seconds: float, kbps: int) -> int:
    """Bytes for a stream of the given length and bit rate."""
    return int(seconds * kbps * 1000 / 8)


@dataclass(frozen=True, slots=True)
class VideoSet:
    """The videos a run will download, with the length assumed for each.

    Attributes:
        seconds: One length per video still to download.
        assumed: How many of those lengths are assumptions, not listing data.
        archived: How many listed videos were left out as already archived.
    """

    seconds: tuple[float, ...]
    assumed: int
    archived: int

    @property
    def count(self) -> int:
        return len(self.seconds)

    @property
    def total_seconds(self) -> float:
        return sum(self.seconds)

    @property
    def longest_seconds(self) -> float:
        return max(self.seconds, default=0.0)


def plan_videos(entries: Iterable[PlaylistEntry], archived_ids: Collection[str]) -> VideoSet | None:
    """Work out which listed videos will be downloaded and how long each is.

    Duplicates (by id) count once and archived ids are left out. A missing
    duration is assumed: 180 s for a /shorts/ address, otherwise the median of
    the durations the listing does give.

    Returns:
        The set, or None when it cannot be estimated (an empty listing, or no
        known duration to take a median from).
    """
    seen: set[str] = set()
    todo: list[PlaylistEntry] = []
    known: list[float] = []
    archived = 0
    unique = 0

    for entry in entries:
        if entry.id:
            if entry.id in seen:
                continue
            seen.add(entry.id)
        unique += 1
        if entry.duration:
            known.append(entry.duration)
        if entry.id and entry.id in archived_ids:
            archived += 1
            continue
        todo.append(entry)

    if unique == 0:
        return None

    median = statistics.median(known) if known else None
    seconds: list[float] = []
    assumed = 0
    for entry in todo:
        if entry.duration:
            seconds.append(entry.duration)
        elif entry.is_short:
            seconds.append(SHORT_SECONDS)
            assumed += 1
        elif median is not None:
            seconds.append(float(median))
            assumed += 1
        else:
            return None
    return VideoSet(tuple(seconds), assumed, archived)


@dataclass(frozen=True, slots=True)
class SizeEstimate:
    """Estimated bytes for one row of the table.

    Attributes:
        height: The resolution cap this row is for; None for an audio row.
        total_bytes: Size of everything that stays on disk.
        required_bytes: total_bytes plus the largest single video, because the
            source and the output coexist while merging, recoding or converting.
        download_bytes: What crosses the network.
    """

    height: int | None
    total_bytes: int
    required_bytes: int
    download_bytes: int


def estimate_video(videos: VideoSet, height: int) -> SizeEstimate:
    """Estimate a video download capped at the given resolution."""
    kbps = VIDEO_KBPS[height] + AUDIO_KBPS
    total = sum(size_bytes(s, kbps) for s in videos.seconds)
    return SizeEstimate(height, total, total + size_bytes(videos.longest_seconds, kbps), total)


def estimate_audio(videos: VideoSet, output_kbps: int) -> SizeEstimate:
    """Estimate an audio extraction: the output stays, the source is downloaded."""
    total = sum(size_bytes(s, output_kbps) for s in videos.seconds)
    largest = size_bytes(videos.longest_seconds, output_kbps)
    downloaded = sum(size_bytes(s, AUDIO_KBPS) for s in videos.seconds)
    return SizeEstimate(None, total, total + largest, downloaded)


def parse_rate_limit(text: str | None) -> float | None:
    """Parse a yt-dlp rate limit such as '500K' or '4.2M' into bytes per second."""
    if not text:
        return None
    match = _RATE_PATTERN.match(text.strip())
    if match is None:
        return None
    value = float(match.group(1)) * _RATE_UNITS[match.group(2).upper()]
    return value if value > 0 else None


def effective_speed(measured: float | None, rate_limit: str | None) -> float | None:
    """The speed a download will get: the measurement, capped by the speed limit."""
    if measured is None or measured <= 0:
        return None
    limit = parse_rate_limit(rate_limit)
    return min(measured, limit) if limit is not None else measured


def download_seconds(download_bytes: int, bytes_per_second: float | None) -> float | None:
    """Time to move the bytes at the given speed, or None when the speed is unknown."""
    if bytes_per_second is None or bytes_per_second <= 0:
        return None
    return download_bytes / bytes_per_second


def archive_wait_seconds(count: int, sleep_interval: float, max_sleep_interval: float) -> float:
    """Lower bound for archive mode: the wait between videos, times the videos."""
    high = max(sleep_interval, max_sleep_interval)
    return count * (sleep_interval + high) / 2


def format_size(num_bytes: float) -> str:
    """Format a byte count in 1024-based units, matching Windows Explorer."""
    value = float(max(num_bytes, 0))
    for unit in _SIZE_UNITS[:-1]:
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {_SIZE_UNITS[-1]}"


def format_duration(seconds: float) -> str:
    """Format a length of time using the two largest units that apply."""
    total = max(int(round(seconds)), 0)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return t("duration_days_hours", days=days, hours=hours)
    if hours:
        return t("duration_hours_minutes", hours=hours, minutes=minutes)
    if minutes:
        return t("duration_minutes", minutes=minutes)
    return t("duration_seconds", seconds=secs)
```

- [ ] **Adım 4: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_estimate.py -v`
Beklenen: PASS. `"1 M"` ve `"M"` desenle eşleşmediği için `None` döner; testte öyle bekleniyor. Tam paket, ruff, mypy temiz olmalı.

- [ ] **Adım 5: Commit**

```bash
git add ytdlp_app/estimate.py tests/test_estimate.py TASKS.md
git commit -m "feat: add the size, space and time estimate arithmetic" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 4: `speedtest.py`

**Dosyalar:**
- Oluşturur: `ytdlp_app/speedtest.py`
- Test: `tests/test_speedtest.py`

**Arayüzler:**
- Üretir (Görev 7 ve 8 kullanır): `measure_speed(proxy: str | None, *, open_url: UrlOpener | None = None, clock: Callable[[], float] = time.monotonic) -> float | None` (bayt/sn ya da `None`); `SPEED_TEST_URL`, `MAX_BYTES`, `MAX_SECONDS`.

- [ ] **Adım 1: Testleri yaz**

`tests/test_speedtest.py`:

```python
"""Tests for ytdlp_app.speedtest. Nothing here reaches the network."""

import urllib.error
import urllib.request
from typing import Any

import pytest

from ytdlp_app import speedtest
from ytdlp_app.speedtest import MAX_BYTES, MAX_SECONDS, measure_speed

CHUNK = b"x" * 65_536


class _Response:
    """A response that serves chunks until told to stop, counting the reads."""

    def __init__(self, chunks: int | None = None) -> None:
        self.remaining = chunks
        self.reads = 0

    def read(self, _size: int = -1) -> bytes:
        self.reads += 1
        if self.remaining is None:
            return CHUNK
        if self.remaining == 0:
            return b""
        self.remaining -= 1
        return CHUNK

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None


class _Clock:
    """A clock that advances a fixed step on every call."""

    def __init__(self, step: float) -> None:
        self.now = -step
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def _opener(response: _Response, seen: list[tuple[str, float]] | None = None):
    def open_url(request: urllib.request.Request, timeout: float) -> _Response:
        if seen is not None:
            seen.append((request.full_url, timeout))
        return response

    return open_url


def test_returns_bytes_per_second() -> None:
    response = _Response(chunks=10)
    speed = measure_speed(None, open_url=_opener(response), clock=_Clock(0.1))

    assert speed is not None
    assert speed > 0


def test_asks_for_the_test_url_with_a_timeout() -> None:
    seen: list[tuple[str, float]] = []
    measure_speed(None, open_url=_opener(_Response(chunks=1), seen), clock=_Clock(0.1))

    ((url, timeout),) = seen
    assert url == speedtest.SPEED_TEST_URL
    assert timeout > 0


def test_stops_at_the_byte_cap() -> None:
    response = _Response(chunks=None)
    measure_speed(None, open_url=_opener(response), clock=_Clock(0.0001))

    assert response.reads <= MAX_BYTES // len(CHUNK) + 1


def test_stops_at_the_time_cap() -> None:
    response = _Response(chunks=None)
    # Each clock call advances 2 s: the cap is reached after a few reads.
    measure_speed(None, open_url=_opener(response), clock=_Clock(2.0))

    assert response.reads <= MAX_SECONDS // 2 + 2


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("no route"),
        TimeoutError("slow"),
        ConnectionResetError("reset"),
        ValueError("bad url"),
    ],
)
def test_network_errors_mean_unknown(error: Exception) -> None:
    def failing(_request: urllib.request.Request, _timeout: float) -> _Response:
        raise error

    assert measure_speed(None, open_url=failing, clock=_Clock(0.1)) is None


def test_an_empty_body_means_unknown() -> None:
    assert measure_speed(None, open_url=_opener(_Response(chunks=0)), clock=_Clock(0.1)) is None


@pytest.mark.parametrize("proxy", ["socks5://h:1080", "SOCKS5H://h:1080", " socks4://h:1"])
def test_socks_proxies_are_not_measured(proxy: str) -> None:
    called: list[bool] = []

    def open_url(_request: urllib.request.Request, _timeout: float) -> _Response:
        called.append(True)
        return _Response(chunks=1)

    assert measure_speed(proxy, open_url=open_url, clock=_Clock(0.1)) is None
    assert called == []


def test_a_keyboard_interrupt_is_not_swallowed() -> None:
    def interrupted(_request: urllib.request.Request, _timeout: float) -> _Response:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        measure_speed(None, open_url=interrupted, clock=_Clock(0.1))


@pytest.mark.parametrize(
    ("proxy", "expected"),
    [
        ("host:3128", "http://host:3128"),
        ("http://h:1", "http://h:1"),
        ("https://h:1", "https://h:1"),
    ],
)
def test_proxy_without_a_scheme_is_treated_as_http(proxy: str, expected: str) -> None:
    assert speedtest._normalize_proxy(proxy) == expected
```

- [ ] **Adım 2: Düştüğünü gör**

Çalıştır: `.venv/bin/python -m pytest tests/test_speedtest.py -q`
Beklenen: `ImportError` (modül yok).

- [ ] **Adım 3: Uygula**

`ytdlp_app/speedtest.py`:

```python
"""A short connection-speed measurement, used to turn a size estimate into a
time estimate.

It downloads a few seconds' worth of a public test file, so it measures the
line, not YouTube: it cannot see YouTube-specific throttling, and it tells the
test host the user's IP. It goes through the configured proxy, is skipped for
SOCKS proxies (urllib cannot use them) and reports None on any failure, which
callers treat as "speed unknown", never as an error.
"""

from __future__ import annotations

import http.client
import time
import urllib.request
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import IO, cast

#: A public speed-test download endpoint (about 10 MB).
SPEED_TEST_URL = "https://speed.cloudflare.com/__down?bytes=10000000"

#: Stop after this many bytes or seconds, whichever comes first.
MAX_BYTES = 10_000_000
MAX_SECONDS = 5.0

#: Connect/read timeout for the request.
TIMEOUT_SECONDS = 5.0

_CHUNK_BYTES = 65_536

UrlOpener = Callable[[urllib.request.Request, float], AbstractContextManager[IO[bytes]]]


def _is_socks(proxy: str) -> bool:
    return proxy.strip().lower().startswith("socks")


def _normalize_proxy(proxy: str) -> str:
    """yt-dlp accepts 'host:port'; urllib needs a scheme."""
    proxy = proxy.strip()
    return proxy if "://" in proxy else f"http://{proxy}"


def _default_opener(proxy: str | None) -> UrlOpener:
    handlers: list[urllib.request.BaseHandler] = []
    if proxy:
        url = _normalize_proxy(proxy)
        handlers.append(urllib.request.ProxyHandler({"http": url, "https": url}))
    director = urllib.request.build_opener(*handlers)

    def open_url(
        request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[IO[bytes]]:
        return cast("AbstractContextManager[IO[bytes]]", director.open(request, timeout=timeout))

    return open_url


def measure_speed(
    proxy: str | None,
    *,
    open_url: UrlOpener | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> float | None:
    """Measure the download speed in bytes per second.

    Args:
        proxy: The configured proxy, or None.
        open_url: Opens the request; replaced in tests.
        clock: Monotonic seconds; replaced in tests.

    Returns:
        Bytes per second, or None when it could not be measured.

    Raises:
        KeyboardInterrupt: the user pressed Ctrl+C during the measurement.
    """
    if proxy and _is_socks(proxy):
        return None

    opener = open_url if open_url is not None else _default_opener(proxy)
    request = urllib.request.Request(SPEED_TEST_URL, headers={"User-Agent": "ytdlp-downloader"})
    received = 0
    try:
        start = clock()
        with opener(request, TIMEOUT_SECONDS) as response:
            while received < MAX_BYTES:
                chunk = response.read(_CHUNK_BYTES)
                if not chunk:
                    break
                received += len(chunk)
                if clock() - start >= MAX_SECONDS:
                    break
        elapsed = clock() - start
    except (OSError, http.client.HTTPException, ValueError):
        return None

    if received <= 0 or elapsed <= 0:
        return None
    return received / elapsed
```

- [ ] **Adım 4: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_speedtest.py -v` → PASS. Tam paket, ruff, mypy temiz (mypy `cast` ve `AbstractContextManager` uyarısı verirse `cast` satırını mypy'nin istediği biçime uyarla; davranış değişmez).

- [ ] **Adım 5: Commit**

```bash
git add ytdlp_app/speedtest.py tests/test_speedtest.py TASKS.md
git commit -m "feat: add a short connection-speed measurement" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 5: `max_height` ayarı, menü ve örnek dosya

**Dosyalar:**
- Değişir: `ytdlp_app/settings.py`, `ytdlp_app/settings_menu.py`, `settings.example.json`
- Test: `tests/test_settings.py`, `tests/test_settings_menu.py`

**Arayüzler:**
- Üretir (Görev 6, 7, 8 kullanır):
  - `ALLOWED_MAX_HEIGHTS: tuple[int, ...] = (1080, 1440, 2160)`
  - `VideoSettings.max_height: int | None = None`, `ArchiveSettings.max_height: int | None = 1080`
  - `ArchiveSettings.listing_args() -> list[str]` (`["--sleep-requests", "<sn>"]`)
  - `s` menüsünde 8. giriş (video sınırı) ve 9. giriş (arşiv sınırı); *Geri* 10. olur.

- [ ] **Adım 1: Ayar testlerini yaz**

`tests/test_settings.py` sonuna ekle (dosyanın üstündeki mevcut import'ları kullanır; `pytest`, `AppSettings`, `ArchiveSettings` zaten import edilmiş olmalı — değilse ekle):

```python
class TestMaxHeight:
    def test_defaults_keep_todays_behaviour(self) -> None:
        settings = AppSettings()
        assert settings.video.max_height is None
        assert settings.archive.max_height == 1080

    @pytest.mark.parametrize("value", [1080, 1440, 2160, None])
    def test_the_offered_caps_are_accepted(self, value: int | None) -> None:
        settings = AppSettings.from_dict(
            {"video": {"max_height": value}, "archive": {"max_height": value}}
        )
        assert settings.video.max_height == value
        assert settings.archive.max_height == value

    @pytest.mark.parametrize("bad", [720, "1080", True, 1080.5, [], 0, -1080])
    def test_anything_else_falls_back_to_the_default(self, bad: object) -> None:
        settings = AppSettings.from_dict(
            {"video": {"max_height": bad}, "archive": {"max_height": bad}}
        )
        assert settings.video.max_height is None
        assert settings.archive.max_height == 1080

    def test_archive_without_the_key_keeps_1080(self) -> None:
        settings = AppSettings.from_dict({"archive": {"sleep_requests": 2}})
        assert settings.archive.max_height == 1080

    def test_video_without_the_key_stays_unlimited(self) -> None:
        settings = AppSettings.from_dict({"video": {"embed_thumbnail": False}})
        assert settings.video.max_height is None

    def test_round_trip(self) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        settings.archive.max_height = None

        restored = AppSettings.from_dict(settings.to_dict())

        assert restored.video.max_height == 1440
        assert restored.archive.max_height is None

    def test_listing_args_carry_only_the_request_wait(self) -> None:
        assert ArchiveSettings(sleep_requests=2.5).listing_args() == ["--sleep-requests", "2.5"]
        assert ArchiveSettings().listing_args() == ["--sleep-requests", "1.5"]
```

- [ ] **Adım 2: Menü testlerini yaz**

`tests/test_settings_menu.py` sonuna ekle:

```python
class TestResolutionLimitMenu:
    """Entries 8 and 9 edit the MP4 and archive resolution caps."""

    VIDEO_ENTRY = 8
    ARCHIVE_ENTRY = 9

    def _run(
        self,
        entry: int,
        answer: int,
        config_file: Path,
        user_config: UserConfig,
        settings: AppSettings,
    ) -> FakeUI:
        ui = FakeUI(picks=[entry, answer, BACK])
        _menu(ui, config_file, user_config, settings=settings).run()
        return ui

    @pytest.mark.parametrize(("answer", "expected"), [(1, 1080), (2, 1440), (3, 2160), (4, None)])
    def test_video_limit_is_stored_and_persisted(
        self,
        answer: int,
        expected: int | None,
        config_file: Path,
        user_config: UserConfig,
    ) -> None:
        settings = AppSettings()
        settings.video.max_height = 1080  # so that "unlimited" is a real change

        self._run(self.VIDEO_ENTRY, answer, config_file, user_config, settings)

        assert settings.video.max_height == expected
        stored = load_settings(json.loads(config_file.read_text(encoding="utf-8")))
        assert stored.video.max_height == expected

    def test_archive_limit_is_stored_and_the_video_limit_is_untouched(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()

        self._run(self.ARCHIVE_ENTRY, 3, config_file, user_config, settings)

        assert settings.archive.max_height == 2160
        assert settings.video.max_height is None

    def test_the_current_value_is_marked_in_the_options(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        seen: list[list[str]] = []

        class Recording(FakeUI):
            def pick(self, prompt: str, options: list[str]) -> int:
                seen.append(options)
                return super().pick(prompt, options)

        ui = Recording(picks=[self.ARCHIVE_ENTRY, 1, BACK])
        _menu(ui, config_file, user_config).run()

        # seen[0] is the top menu; seen[1] is the resolution list.
        assert seen[1] == ["1080p (default)", "1440p", "2160p", "Unlimited"]
```

(`json`, `Path`, `load_settings`, `AppSettings`, `UserConfig`, `BACK`, `FakeUI`, `_menu` bu dosyada zaten var; `pytest` de.)

- [ ] **Adım 3: Düştüklerini gör**

Çalıştır: `.venv/bin/python -m pytest tests/test_settings.py tests/test_settings_menu.py -q`
Beklenen: yeni testler FAIL (`AttributeError: max_height`, menü girişi yok).

- [ ] **Adım 4: `settings.py`'yi uygula**

Dosya başına import ve sabit (mevcut `from typing import Any` satırını `from typing import Any, Final` yap):

```python
#: The resolution caps the app offers. None (no cap) is always allowed.
ALLOWED_MAX_HEIGHTS: Final[tuple[int, ...]] = (1080, 1440, 2160)


def _as_max_height(value: Any, default: int | None) -> int | None:
    """Return a usable resolution cap: an offered height, None (no cap) or the default."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value in ALLOWED_MAX_HEIGHTS:
        return value
    return default
```

`_as_max_height`'i `_format_seconds`'in altına, `ArchiveSettings`'ten önce koy (mevcut `_as_number` yakınında).

`VideoSettings`:
- Docstring `Attributes` listesine ekle: `max_height: Resolution cap for MP4 downloads (1080, 1440, 2160), or None for no cap.`
- Alan: `max_height: int | None = None` (`write_subtitles` satırının altına).

`ArchiveSettings`:
- Docstring `Attributes` listesine: `max_height: Resolution cap for archive downloads (1080, 1440, 2160), or None for no cap.`
- Alan: `max_height: int | None = 1080` (`sleep_subtitles: float = 5` altına).
- Yeni metot (`to_args`'ın altına):

```text
    def listing_args(self) -> list[str]:
        """Arguments for the playlist listing: only the wait between requests.

        The listing is a few requests, not a download, so the per-video waits and
        the retry policy of to_args do not apply.
        """
        return ["--sleep-requests", _format_seconds(self.sleep_requests)]
```

- `from_dict` içinde `return cls(...)`'a ekle:

```text
            max_height=_as_max_height(data.get("max_height", defaults.max_height), defaults.max_height),
```
- `to_dict` dönüş tipini `dict[str, float | None]` yap ve sözlüğe `"max_height": self.max_height,` ekle.

`AppSettings.from_dict` video bloğuna (`write_subtitles=...` satırının altına):

```text
                max_height=_as_max_height(vi.get("max_height"), None),
```
`AppSettings.to_dict` `"video"` sözlüğüne: `"max_height": self.video.max_height,`.

- [ ] **Adım 5: `settings_menu.py`'yi uygula**

Sabitler bölümüne (`_MAX_WAIT_SECONDS` altına):

```python
#: The resolution caps offered in the menu, in the order shown; None is "unlimited".
_HEIGHT_CHOICES: tuple[int | None, ...] = (1080, 1440, 2160, None)
```

`_entries` listesine `settings_archive` girişinin altına ekle:

```text
            (t("settings_video_height"), self._edit_video_height),
            (t("settings_archive_height"), self._edit_archive_height),
```

Yeni metotlar (`_edit_archive`'in altına, sınıf içinde):

```text
    def _height_label(self, height: int | None, current: int | None) -> str:
        label = t("resolution_unlimited") if height is None else t("resolution_option", height=height)
        return t("resolution_default_mark", label=label) if height == current else label

    def _pick_height(self, label: str, current: int | None) -> int | None:
        """Ask for a resolution cap; the current one is marked as the default."""
        self._prompt_header(
            label,
            t("resolution_unlimited") if current is None else t("resolution_option", height=current),
            "",
        )
        options = [self._height_label(h, current) for h in _HEIGHT_CHOICES]
        return _HEIGHT_CHOICES[self.ui.pick(label, options) - 1]

    def _edit_video_height(self) -> None:
        video = self.settings.video
        video.max_height = self._pick_height(t("settings_video_height"), video.max_height)
        self._persist()

    def _edit_archive_height(self) -> None:
        archive = self.settings.archive
        archive.max_height = self._pick_height(t("settings_archive_height"), archive.max_height)
        self._persist()
```

`_pick_height` içindeki `_prompt_header` FakeUI'da `ui.print` kullanır (pick değil), test sırasını bozmaz.

- [ ] **Adım 6: `settings.example.json`**

`"video"` bloğuna `"write_subtitles": false` satırından sonra `,\n      "max_height": null` ekle; `"archive"` bloğuna `"sleep_subtitles": 5` satırından sonra `,\n      "max_height": 1080` ekle. `_comment`'in sonuna cümle ekle: `max_height is 1080, 1440, 2160 or null (no cap).` — yani `_comment` değerini şöyle bitir: `... falls back to the default shown here. max_height is 1080, 1440, 2160 or null (no cap).`

Doğrula: `.venv/bin/python -c "import json;json.load(open('settings.example.json'))"`.

- [ ] **Adım 7: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_settings.py tests/test_settings_menu.py -v` → PASS. Tam paket, ruff, mypy temiz. (`test_locales` yeni `settings_*_height` anahtarlarını Görev 1'den buluyor.)

- [ ] **Adım 8: Commit**

```bash
git add ytdlp_app/settings.py ytdlp_app/settings_menu.py settings.example.json tests/test_settings.py tests/test_settings_menu.py TASKS.md
git commit -m "feat: add the max_height resolution cap to the settings" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 6: Format seçicileri ve `CommandBuilder`

**Dosyalar:**
- Değişir: `ytdlp_app/yt_dlp.py`
- Test: `tests/test_yt_dlp.py`

**Arayüzler:**
- Tüketir: `VideoSettings.max_height`, `ArchiveSettings.max_height` (Görev 5).
- Üretir (Görev 8 kullanır):
  - `video_format(max_height: int | None) -> str`, `compat_stage1_format(max_height: int | None) -> str`
  - `CommandBuilder.set_max_height(max_height: int | None) -> None`

- [ ] **Adım 1: Testleri yaz**

`tests/test_yt_dlp.py` içinde sabit `ARCHIVE_DEFAULT_PREFIX`'teki seçiciyi güncelle (bilinçli değişiklik: sınır artık yedeğe de uygulanıyor):

```text
    "bv*[height<=1080]+ba/b[height<=1080]",
```

İmport bloğunu genişlet: `from ytdlp_app.yt_dlp import PLUGINS_DIR, CommandBuilder, compat_stage1_format, video_format`. Dosyanın sonuna ekle:

```python
def _selector(cmd: list[str]) -> str:
    return cmd[cmd.index("-f") + 1]


class TestSelectors:
    def test_no_cap_gives_todays_selectors(self) -> None:
        assert video_format(None) == "bv*+ba/b"
        assert compat_stage1_format(None) == (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]"
        )

    def test_the_cap_is_applied_to_every_alternative(self) -> None:
        assert video_format(1440) == "bv*[height<=1440]+ba/b[height<=1440]"
        assert compat_stage1_format(1080) == (
            "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]"
            "/best[vcodec^=avc1][height<=1080]"
        )


class TestBuilderResolutionCap:
    def test_defaults_do_not_change_the_video_commands(self, builder: CommandBuilder) -> None:
        assert _selector(builder.build_mp4_quality_mkv()) == "bv*+ba/b"
        assert _selector(builder.build_mp4_quality_remux()) == "bv*+ba/b"
        assert _selector(builder.build_mp4_compatibility_stage2()) == "bv*+ba/b"
        assert _selector(builder.build_mp4_compatibility_stage1()) == (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]"
        )

    def test_the_saved_video_cap_applies_without_a_choice(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        builder = CommandBuilder(
            URL, "%(title)s.%(ext)s", tmp_path / "a.txt", False, settings=settings
        )
        assert _selector(builder.build_mp4_quality_mkv()) == video_format(1440)

    def test_a_choice_overrides_the_saved_cap(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        builder = CommandBuilder(
            URL, "%(title)s.%(ext)s", tmp_path / "a.txt", False, settings=settings
        )
        builder.set_max_height(None)
        assert _selector(builder.build_mp4_quality_mkv()) == "bv*+ba/b"

    def test_the_choice_reaches_every_video_command(self, builder: CommandBuilder) -> None:
        builder.set_max_height(2160)
        for cmd in (
            builder.build_mp4_quality_mkv(),
            builder.build_mp4_quality_remux(),
            builder.build_mp4_compatibility_stage2(),
        ):
            assert _selector(cmd) == "bv*[height<=2160]+ba/b[height<=2160]"
        assert "[height<=2160]" in _selector(builder.build_mp4_compatibility_stage1())

    def test_audio_ignores_the_cap(self, builder: CommandBuilder) -> None:
        builder.set_max_height(1080)
        assert _selector(builder.build_mp3()) == "bestaudio/best"

    def test_archive_defaults_to_1080(self, builder: CommandBuilder) -> None:
        assert _selector(builder.build_archive()) == "bv*[height<=1080]+ba/b[height<=1080]"

    @pytest.mark.parametrize(
        ("choice", "expected"),
        [
            (1440, "bv*[height<=1440]+ba/b[height<=1440]"),
            (None, "bv*+ba/b"),
        ],
    )
    def test_archive_follows_the_choice(
        self, builder: CommandBuilder, choice: int | None, expected: str
    ) -> None:
        builder.set_max_height(choice)
        assert _selector(builder.build_archive()) == expected

    def test_archive_uses_its_own_saved_cap(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.archive.max_height = 2160
        builder = CommandBuilder(
            URL, "%(title)s.%(ext)s", tmp_path / "a.txt", False, settings=settings
        )
        assert _selector(builder.build_archive()) == video_format(2160)


yt_dlp = pytest.importorskip("yt_dlp")


def _format(fid: str, height: int | None, vcodec: str, acodec: str, ext: str = "mp4") -> dict:
    return {
        "format_id": fid,
        "height": height,
        "width": 1,
        "vcodec": vcodec,
        "acodec": acodec,
        "ext": ext,
        "protocol": "https",
        "url": "http://example.invalid/x",
        "tbr": height or 1,
    }


def _pick(selector: str, formats: list[dict]) -> list[str]:
    """Run a selector through yt-dlp's own engine, offline, on synthetic formats."""
    ydl = yt_dlp.YoutubeDL({"quiet": True})
    chosen = ydl.build_format_selector(selector)({"formats": formats, "incomplete_formats": False})
    return [f["format_id"] for f in chosen]


class TestSelectorsAgainstYtDlp:
    SPLIT = [
        _format("a", None, "none", "opus", "webm"),
        _format("v720", 720, "avc1", "none"),
        _format("v1080", 1080, "avc1", "none"),
        _format("v2160", 2160, "vp09", "none"),
    ]

    def test_the_cap_picks_the_best_stream_within_it(self) -> None:
        assert _pick(video_format(1080), self.SPLIT) == ["v1080+a"]
        assert _pick(video_format(None), self.SPLIT) == ["v2160+a"]

    def test_the_cap_holds_in_the_fallback(self) -> None:
        # Only a 2160p combined stream exists: the old "/b" fallback would take it.
        progressive = [_format("p", 2160, "avc1", "mp4a")]
        assert _pick(video_format(None), progressive) == ["p"]
        assert _pick(video_format(1080), progressive) == []

    def test_the_fallback_still_serves_streams_within_the_cap(self) -> None:
        progressive = [_format("p", 360, "avc1", "mp4a")]
        assert _pick(video_format(1080), progressive) == ["p"]

    def test_the_compatibility_selector_prefers_avc1_within_the_cap(self) -> None:
        formats = [
            _format("a", None, "none", "mp4a.40.2", "m4a"),
            _format("h264", 1080, "avc1.640028", "none"),
            _format("vp9", 1080, "vp09", "none"),
        ]
        assert _pick(compat_stage1_format(1080), formats) == ["h264+a"]
```

(`AppSettings`, `Path`, `pytest`, `URL`, `builder` fixture zaten dosyada.)

- [ ] **Adım 2: Düştüğünü gör**

Çalıştır: `.venv/bin/python -m pytest tests/test_yt_dlp.py -q`
Beklenen: `ImportError` (`video_format`, `compat_stage1_format`).

- [ ] **Adım 3: Uygula**

`ytdlp_app/yt_dlp.py`:

`ARCHIVE_CONTENT_ARGS`'tan `"-f",` ve `"bv*[height<=1080]+ba/b",` satırlarını sil; docstring'i güncelle:

```text
#: Archive mode keeps everything a channel publishes that could be lost with it:
#: the video (capped by the archive resolution limit, 1080p by default, to bound
#: disk use), its description, the raw metadata, the thumbnail, and both uploaded
#: and auto-generated subtitles. The format selector is built per run by
#: video_format(), because the cap can change.
ARCHIVE_CONTENT_ARGS = [
    "--merge-output-format",
    "mkv",
    ...
```
(kalanı aynı).

`js_runtime_args`'ın üstüne ekle:

```python
def _height_filter(max_height: int | None) -> str:
    return "" if max_height is None else f"[height<={max_height}]"


def video_format(max_height: int | None) -> str:
    """Build the video+audio format selector, capped at max_height (None = no cap).

    The cap is on both alternatives: without it on the "/b" fallback a video with
    only a combined stream above the cap would be downloaded anyway.
    """
    cap = _height_filter(max_height)
    return f"bv*{cap}+ba/b{cap}"


def compat_stage1_format(max_height: int | None) -> str:
    """Build the H.264 + AAC selector of the compatibility profile's first stage."""
    cap = _height_filter(max_height)
    return f"bestvideo[vcodec^=avc1]{cap}+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]{cap}"
```

`CommandBuilder.__init__` sonuna (`self.settings = ...` altına):

```text
        # The cap chosen for this download, once the user has been asked. Until
        # then each mode uses the default saved in the settings.
        self._max_height: int | None = None
        self._has_max_height = False
```

Yeni metotlar (`js_args` özelliğinin üstüne):

```text
    def set_max_height(self, max_height: int | None) -> None:
        """Apply the resolution cap chosen for this download (None = no cap).

        Overrides the default saved in the settings for this builder only.
        """
        self._max_height = max_height
        self._has_max_height = True

    def _cap(self, saved: int | None) -> int | None:
        return self._max_height if self._has_max_height else saved
```

Komut metotlarında:
- `build_mp4_compatibility_stage1`: `"bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]"` yerine `compat_stage1_format(self._cap(self.settings.video.max_height))`.
- `build_mp4_compatibility_stage2`, `build_mp4_quality_mkv`, `build_mp4_quality_remux`: `"bv*+ba/b"` yerine `video_format(self._cap(self.settings.video.max_height))`.
- `build_archive`: listeyi şöyle başlat:

```text
        return [
            "yt-dlp",
            "-f",
            video_format(self._cap(self.settings.archive.max_height)),
            *ARCHIVE_CONTENT_ARGS,
            ...
```
- `build_mp3` değişmez.

Docstring'lerde "capped at" notunu ekle.

- [ ] **Adım 4: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_yt_dlp.py -v` → PASS (yt-dlp motor testleri dahil; `importorskip` atlarsa raporla). Mevcut `test_archive_default_prefix` benzeri testler yeni sabitle geçmeli. Tam paket, ruff, mypy temiz.

- [ ] **Adım 5: Commit**

```bash
git add ytdlp_app/yt_dlp.py tests/test_yt_dlp.py TASKS.md
git commit -m "feat: cap every video format selector at the chosen resolution" -m "The archive selector's fallback is now capped too, so the limit holds for videos that only offer a combined stream above it." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 7: `preflight.py`

**Dosyalar:**
- Oluşturur: `ytdlp_app/preflight.py`
- Test: `tests/test_preflight.py`

**Arayüzler:**
- Tüketir: Görev 2 (`PlaylistEntry`), 3 (`estimate`), 4 (`measure_speed`), 5 (`max_height`, `listing` yok), Görev 1 anahtarları, `find_ban_signal`, `append_log`, `log_error`.
- Üretir (Görev 8 kullanır):
  - `ListingStatus` (`OK`, `FAILED`, `BAN`, `INTERRUPTED`), `GuardedListing[T](status, value=None, error="")`
  - `guarded_listing(fetch: Callable[[], T], log_path: Path | None) -> GuardedListing[T]`
  - `PreflightAction` (`PROCEED`, `CANCEL`), `PreflightResult(action, max_height=None)`
  - `PreflightRequest(mode, is_playlist, entries, archived_ids, mp4_profile, base_dir, log_path)`
  - `run_preflight(request, *, ui, settings, persist_default, measure=measure_speed, disk_free=free_bytes) -> PreflightResult`
  - `free_bytes(path: Path) -> int`

- [ ] **Adım 1: Testleri yaz**

`tests/test_preflight.py`:

```python
"""Tests for ytdlp_app.preflight: the listing guard and the estimate/resolution/space flow."""

from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.estimate import format_size
from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.i18n import set_language
from ytdlp_app.models import DownloadMode, PlaylistEntry, ProfileChoice
from ytdlp_app.preflight import (
    ListingStatus,
    PreflightAction,
    PreflightRequest,
    free_bytes,
    guarded_listing,
    run_preflight,
)
from ytdlp_app.settings import AppSettings

BAN_TEXT = "ERROR: [youtube:tab] @Handle: Sign in to confirm you\u2019re not a bot."


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


class ScriptedUI:
    def __init__(self, picks: list[int] | None = None) -> None:
        self.picks = list(picks or [])
        self.messages: list[str] = []
        self.prompts: list[tuple[str, list[str]]] = []

    def print(self, text: object = "") -> None:
        self.messages.append(str(text))

    def print_panel(self, text: str, title: str | None = None, color: str = "") -> None:
        self.messages.append(text)

    def pick(self, prompt: str, options: list[str]) -> int:
        self.prompts.append((prompt, options))
        if not self.picks:
            raise AssertionError(f"unexpected pick(): {prompt!r} with {options!r}")
        return self.picks.pop(0)

    def ask_text(self, prompt: str) -> str:
        raise AssertionError(f"unexpected ask_text(): {prompt!r}")

    def prompt_exit_on_failure(self) -> bool:
        return True

    def text(self) -> str:
        return "\n".join(self.messages)


def _entry(vid: str, duration: float | None = 600, *, short: bool = False) -> PlaylistEntry:
    return PlaylistEntry(1, vid, "t", f"https://www.youtube.com/watch?v={vid}", duration, short)


def _request(tmp_path: Path, **overrides: Any) -> PreflightRequest:
    values: dict[str, Any] = {
        "mode": DownloadMode.VIDEO,
        "is_playlist": True,
        "entries": [_entry("a"), _entry("b"), _entry("c")],
        "archived_ids": frozenset(),
        "mp4_profile": ProfileChoice.QUALITY,
        "base_dir": tmp_path,
        "log_path": tmp_path / "session.log",
    }
    values.update(overrides)
    return PreflightRequest(**values)


def _run(
    request: PreflightRequest,
    ui: ScriptedUI,
    settings: AppSettings | None = None,
    *,
    measured: float | None = 1_000_000.0,
    free: int = 10**15,
    persist: Any = None,
):
    def no_speed_test(_proxy: str | None) -> float | None:
        return measured

    def disk_free(_path: Path) -> int:
        if isinstance(free, Exception):
            raise free
        return free

    return run_preflight(
        request,
        ui=ui,
        settings=settings if settings is not None else AppSettings(),
        persist_default=persist if persist is not None else (lambda _h: None),
        measure=no_speed_test,
        disk_free=disk_free,
    )


class TestGuardedListing:
    def test_success_returns_the_value(self, tmp_path: Path) -> None:
        result = guarded_listing(lambda: [1, 2], tmp_path / "log")
        assert result.status is ListingStatus.OK
        assert result.value == [1, 2]

    def test_ctrl_c_is_reported_not_raised(self, tmp_path: Path) -> None:
        def interrupted() -> list[int]:
            raise KeyboardInterrupt

        assert guarded_listing(interrupted, tmp_path / "log").status is ListingStatus.INTERRUPTED

    def test_a_ban_signal_is_flagged_and_logged(self, tmp_path: Path) -> None:
        log = tmp_path / "log"

        def banned() -> list[int]:
            raise PlaylistError(f"returncode=1\nstderr:\n{BAN_TEXT}")

        result = guarded_listing(banned, log)

        assert result.status is ListingStatus.BAN
        assert "Sign in to confirm" in result.error
        text = log.read_text(encoding="utf-8")
        assert "[BAN-GUARD" in text
        assert "Not starting the download" in text

    def test_another_failure_is_reported_with_its_text(self, tmp_path: Path) -> None:
        log = tmp_path / "log"

        def failing() -> list[int]:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        result = guarded_listing(failing, log)

        assert result.status is ListingStatus.FAILED
        assert "Unable to download webpage" in result.error
        assert log.exists()

    def test_an_unexpected_exception_is_a_failed_listing(self, tmp_path: Path) -> None:
        def broken() -> list[int]:
            raise ValueError("bad")

        result = guarded_listing(broken, tmp_path / "log")
        assert result.status is ListingStatus.FAILED
        assert "bad" in result.error

    def test_a_missing_log_path_is_fine(self) -> None:
        def failing() -> list[int]:
            raise PlaylistError("x")

        assert guarded_listing(failing, None).status is ListingStatus.FAILED


class TestEstimateTable:
    def test_video_table_has_three_rows_and_the_summary(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui)

        text = ui.text()
        assert "1080p" in text
        assert "1440p (at most)" in text
        assert "2160p (at most)" in text
        assert "3 videos to download, 0 already in the archive, 0 with an assumed duration" in text
        assert "Free space:" in text

    def test_sizes_and_times_follow_the_bit_rates(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, measured=1_000_000.0)

        text = ui.text()
        # 3 videos x 600 s at (6000 + 160) kbit/s = 1.386 GB; 1386 s at 1 MB/s.
        assert format_size(1_386_000_000) in text
        assert "23 min" in text
        assert "1 h 53 min" in text  # 2160p: 6.786 GB

    def test_the_measured_speed_is_shown(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, measured=1_000_000.0)
        assert "Measured speed: 8.0 Mbit/s" in ui.text()

    def test_an_unmeasurable_speed_leaves_the_time_column_empty(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, measured=None)

        text = ui.text()
        assert "could not be measured" in text
        assert "n/a" in text

    def test_assumed_durations_are_reported(self, tmp_path: Path) -> None:
        entries = [_entry("a", 600), _entry("s", None, short=True)]
        ui = ScriptedUI([4])
        _run(_request(tmp_path, entries=entries), ui)
        assert "1 with an assumed duration" in ui.text()

    def test_audio_shows_one_row_for_the_configured_format(self, tmp_path: Path) -> None:
        request = _request(
            tmp_path,
            mode=DownloadMode.AUDIO,
            mp4_profile=None,
            entries=[_entry("a", 600)],
        )
        ui = ScriptedUI()

        result = _run(request, ui)

        text = ui.text()
        assert "mp3" in text
        assert "17.5 MiB" in text  # 600 s at 245 kbit/s
        assert "1080p" not in text
        assert result.action is PreflightAction.PROCEED
        assert result.max_height is None

    def test_the_compatibility_profile_shows_only_1080p(self, tmp_path: Path) -> None:
        request = _request(tmp_path, mp4_profile=ProfileChoice.COMPATIBILITY)
        ui = ScriptedUI()

        result = _run(request, ui)

        text = ui.text()
        assert "1440p" not in text
        assert "limited to 1080p" in text
        assert result.max_height == 1080
        assert ui.prompts == []  # no resolution question

    def test_archive_mode_warns_about_the_waits(self, tmp_path: Path) -> None:
        entries = [_entry(f"v{i}") for i in range(10)]
        request = _request(tmp_path, mode=DownloadMode.ARCHIVE, mp4_profile=None, entries=entries)
        ui = ScriptedUI([1])

        _run(request, ui)  # 10 videos x 30 s average = 5 min

        assert "at least 5 min" in ui.text()
        assert "10 videos" in ui.text()

    def test_other_modes_do_not_show_the_wait_line(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui)
        assert "Waiting between videos" not in ui.text()


class TestUnavailableEstimate:
    def test_a_failed_listing_says_so_and_still_asks_the_resolution(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])

        def must_not_measure(_proxy: str | None) -> float | None:
            raise AssertionError("no speed test without an estimate")

        result = run_preflight(
            _request(tmp_path, entries=None),
            ui=ui,
            settings=AppSettings(),
            persist_default=lambda _h: None,
            measure=must_not_measure,
            disk_free=lambda _p: 10**15,
        )

        assert "Size could not be calculated" in ui.text()
        assert result.action is PreflightAction.PROCEED
        assert len(ui.prompts) == 1

    def test_no_known_duration_cannot_be_estimated(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path, entries=[_entry("a", None), _entry("b", None)]), ui)
        assert "Size could not be calculated" in ui.text()

    def test_an_empty_listing_cannot_be_estimated(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path, entries=[]), ui)
        assert "Size could not be calculated" in ui.text()

    def test_everything_archived_means_nothing_to_ask(self, tmp_path: Path) -> None:
        ui = ScriptedUI()
        request = _request(tmp_path, archived_ids=frozenset({"a", "b", "c"}))

        result = _run(request, ui)

        assert "nothing new to download" in ui.text()
        assert ui.prompts == []
        assert result.action is PreflightAction.PROCEED
        assert result.max_height is None  # the video default

    def test_everything_archived_in_archive_mode_keeps_the_archive_default(
        self, tmp_path: Path
    ) -> None:
        request = _request(
            tmp_path,
            mode=DownloadMode.ARCHIVE,
            mp4_profile=None,
            archived_ids=frozenset({"a", "b", "c"}),
        )
        result = _run(request, ScriptedUI())
        assert result.max_height == 1080


class TestResolutionQuestion:
    def test_default_is_marked_and_choosing_it_asks_nothing_more(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])

        result = _run(_request(tmp_path), ui)

        ((_prompt, options),) = ui.prompts
        assert options == ["1080p", "1440p", "2160p", "Unlimited (default)"]
        assert result == result.__class__(PreflightAction.PROCEED, None)

    def test_archive_default_is_1080(self, tmp_path: Path) -> None:
        request = _request(tmp_path, mode=DownloadMode.ARCHIVE, mp4_profile=None)
        ui = ScriptedUI([1])

        result = _run(request, ui)

        assert ui.prompts[0][1][0] == "1080p (default)"
        assert result.max_height == 1080

    def test_a_different_choice_asks_whether_to_keep_it(self, tmp_path: Path) -> None:
        saved: list[int | None] = []
        ui = ScriptedUI([2, 1])  # 1440p, then "only for this download"

        result = _run(_request(tmp_path), ui, persist=saved.append)

        assert result.max_height == 1440
        assert saved == []
        assert len(ui.prompts) == 2

    def test_saving_as_default_calls_the_callback(self, tmp_path: Path) -> None:
        saved: list[int | None] = []
        ui = ScriptedUI([2, 2])  # 1440p, then "save as default"

        result = _run(_request(tmp_path), ui, persist=saved.append)

        assert result.max_height == 1440
        assert saved == [1440]

    def test_a_save_failure_warns_and_continues(self, tmp_path: Path) -> None:
        def failing(_height: int | None) -> None:
            raise OSError("disk full")

        ui = ScriptedUI([2, 2])

        result = _run(_request(tmp_path), ui, persist=failing)

        assert result.action is PreflightAction.PROCEED
        assert result.max_height == 1440
        assert "Could not save the default (disk full)" in ui.text()

    def test_a_single_video_asks_the_resolution_without_a_table(self, tmp_path: Path) -> None:
        request = _request(tmp_path, is_playlist=False, entries=None)
        ui = ScriptedUI([3, 1])  # 2160p, only this once

        result = _run(request, ui)

        assert result.max_height == 2160
        assert "Estimated size" not in ui.text()
        assert "Size could not be calculated" not in ui.text()

    def test_a_single_compatibility_video_is_capped_without_asking(self, tmp_path: Path) -> None:
        request = _request(
            tmp_path,
            is_playlist=False,
            entries=None,
            mp4_profile=ProfileChoice.COMPATIBILITY,
        )
        ui = ScriptedUI()

        result = _run(request, ui)

        assert result.max_height == 1080
        assert ui.prompts == []

    def test_a_single_audio_download_asks_nothing(self, tmp_path: Path) -> None:
        request = _request(
            tmp_path, is_playlist=False, entries=None, mode=DownloadMode.AUDIO, mp4_profile=None
        )
        ui = ScriptedUI()

        result = _run(request, ui)

        assert result.max_height is None
        assert ui.prompts == []
        assert ui.messages == []

    def test_the_saved_video_default_is_marked(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        ui = ScriptedUI([2])

        result = _run(_request(tmp_path), ui, settings)

        assert ui.prompts[0][1][1] == "1440p (default)"
        assert result.max_height == 1440


class TestDiskSpace:
    def test_enough_space_asks_nothing(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, free=10**15)
        assert "Not enough free space" not in ui.text()
        assert len(ui.prompts) == 1

    def test_too_little_space_offers_to_continue_anyway(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4, 1])  # unlimited, continue anyway

        result = _run(_request(tmp_path), ui, free=1000)

        assert "Not enough free space" in ui.text()
        assert result.action is PreflightAction.PROCEED

    def test_cancelling_is_logged(self, tmp_path: Path) -> None:
        request = _request(tmp_path)
        ui = ScriptedUI([4, 2])  # unlimited, cancel

        result = _run(request, ui, free=1000)

        assert result.action is PreflightAction.CANCEL
        assert "Cancelled: not enough free disk space" in ui.text()
        assert "Cancelled" in (tmp_path / "session.log").read_text(encoding="utf-8")

    def test_the_check_uses_the_chosen_resolution(self, tmp_path: Path) -> None:
        # 1.386 GB fits at 1080p; unlimited (the 2160p row, 6.786 GB + the largest) does not.
        free = 5_000_000_000
        ui_small = ScriptedUI([1, 1])  # 1080p differs from the unlimited default: save question
        result = _run(_request(tmp_path), ui_small, free=free)
        assert result.action is PreflightAction.PROCEED
        assert "Not enough free space" not in ui_small.text()

        ui_big = ScriptedUI([4, 1])
        _run(_request(tmp_path), ui_big, free=free)
        assert "Not enough free space" in ui_big.text()

    def test_unmeasurable_free_space_skips_the_check(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])

        result = _run(_request(tmp_path), ui, free=OSError("gone"))  # type: ignore[arg-type]

        assert "Free disk space could not be measured" in ui.text()
        assert result.action is PreflightAction.PROCEED
        assert len(ui.prompts) == 1

    def test_audio_checks_space_too(self, tmp_path: Path) -> None:
        request = _request(tmp_path, mode=DownloadMode.AUDIO, mp4_profile=None)
        ui = ScriptedUI([2])  # cancel

        result = _run(request, ui, free=1000)

        assert result.action is PreflightAction.CANCEL

    def test_free_bytes_reads_the_real_disk(self, tmp_path: Path) -> None:
        assert free_bytes(tmp_path) > 0
```

- [ ] **Adım 2: Düştüğünü gör**

Çalıştır: `.venv/bin/python -m pytest tests/test_preflight.py -q`
Beklenen: `ModuleNotFoundError: No module named 'ytdlp_app.preflight'`.

- [ ] **Adım 3: Uygula**

`ytdlp_app/preflight.py`:

```python
"""Everything between choosing what to download and starting it.

Two phases, both driven by session.py:

1. guarded_listing wraps the one flat listing request, turning Ctrl+C, a ban
   signal and any other failure into a status the caller can act on.
2. run_preflight shows the size estimate, asks for the resolution cap, checks
   free disk space and reports whether to go on.

The speed test and the free-space probe are passed in, so tests never reach the
network or the real disk. Nothing here blocks a download: a missing estimate,
an unmeasurable disk or a failed save all end in "carry on".
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar

from .estimate import (
    RESOLUTIONS,
    SizeEstimate,
    VideoSet,
    archive_wait_seconds,
    audio_output_kbps,
    download_seconds,
    effective_speed,
    estimate_audio,
    estimate_video,
    format_duration,
    format_size,
    plan_videos,
)
from .exceptions import PlaylistError
from .exec import find_ban_signal
from .i18n import t
from .logging_utils import Colors, append_log, log_error, paint
from .models import DownloadMode, ProfileChoice
from .speedtest import measure_speed

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .models import PlaylistEntry
    from .settings import AppSettings
    from .ui import UI

_T = TypeVar("_T")

#: The compatibility profile asks for H.264, which YouTube mostly serves up to 1080p.
COMPAT_MAX_HEIGHT = 1080

#: The resolution question's options, in the order shown; None is "unlimited".
RESOLUTION_CHOICES: tuple[int | None, ...] = (1080, 1440, 2160, None)


def _stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def free_bytes(path: Path) -> int:
    """Free space, in bytes, on the disk that holds path."""
    return shutil.disk_usage(path).free


# -- phase 1: the listing -------------------------------------------------


class ListingStatus(Enum):
    OK = "ok"
    FAILED = "failed"
    BAN = "ban"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class GuardedListing(Generic[_T]):
    """The outcome of a listing request.

    Attributes:
        status: What happened.
        value: The listing, when status is OK.
        error: The failure text, when status is FAILED or BAN.
    """

    status: ListingStatus
    value: _T | None = None
    error: str = ""


def guarded_listing(fetch: Callable[[], _T], log_path: Path | None) -> GuardedListing[_T]:
    """Run a listing request and classify how it ended.

    A ban signal in the error text means YouTube is blocking us: the caller must
    not start the download (a [BAN-GUARD] line is logged, as for a download).
    """
    try:
        return GuardedListing(ListingStatus.OK, fetch())
    except KeyboardInterrupt:
        return GuardedListing(ListingStatus.INTERRUPTED)
    except PlaylistError as ex:
        signal = find_ban_signal(str(ex))
        if signal is not None:
            append_log(
                log_path,
                f"\n[WARN {_stamp()}] Playlist listing failed: {ex}\n"
                f"[BAN-GUARD {_stamp()}] Not starting the download: "
                f"{signal.value} during the playlist listing\n",
            )
            return GuardedListing(ListingStatus.BAN, error=str(ex))
        log_error(log_path, t("playlist_fetch_failed_log"), ex)
        return GuardedListing(ListingStatus.FAILED, error=str(ex))
    except Exception as ex:
        log_error(log_path, t("playlist_fetch_failed_log"), ex)
        return GuardedListing(ListingStatus.FAILED, error=str(ex))


# -- phase 2: estimate, resolution, space ----------------------------------


class PreflightAction(Enum):
    PROCEED = "proceed"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """What to do next and which resolution cap to download with.

    Attributes:
        action: Go on or cancel (the user declined to continue on low disk space).
        max_height: The cap for this download; None means no cap.
    """

    action: PreflightAction
    max_height: int | None = None


@dataclass(frozen=True, slots=True)
class PreflightRequest:
    """Everything run_preflight needs to know about the coming download.

    Attributes:
        mode: MP4, MP3 or archive.
        is_playlist: Whether a playlist or channel is being downloaded. Only then
            is there an estimate; a single video sends no listing request.
        entries: The listing, or None when it was not obtained (a failed request).
        archived_ids: Ids already in the download archive; they are not downloaded again.
        mp4_profile: The MP4 profile, or None outside MP4 mode.
        base_dir: Where the files go; its disk is the one checked.
        log_path: The session log, for the cancel record.
    """

    mode: DownloadMode
    is_playlist: bool
    entries: list[PlaylistEntry] | None
    archived_ids: frozenset[str]
    mp4_profile: ProfileChoice | None
    base_dir: Path
    log_path: Path | None


@dataclass(frozen=True, slots=True)
class _Sizes:
    rows: list[SizeEstimate]
    videos: VideoSet


def _default_height(mode: DownloadMode, settings: AppSettings) -> int | None:
    if mode == DownloadMode.ARCHIVE:
        return settings.archive.max_height
    if mode == DownloadMode.VIDEO:
        return settings.video.max_height
    return None


def _table_lines(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    widths = [max(len(line[i]) for line in [header, *rows]) for i in range(len(header))]
    return [
        "  "
        + "  ".join(cell.ljust(width) for cell, width in zip(line, widths, strict=True)).rstrip()
        for line in [header, *rows]
    ]


def _free_or_none(disk_free: Callable[[Path], int], path: Path) -> int | None:
    try:
        return disk_free(path)
    except OSError:
        return None


def _show_estimate(
    request: PreflightRequest,
    settings: AppSettings,
    ui: UI,
    measure: Callable[[str | None], float | None],
    compat: bool,
    free: int | None,
) -> _Sizes | None:
    """Print the estimate table; None when it cannot be calculated."""
    videos = (
        plan_videos(request.entries, request.archived_ids) if request.entries is not None else None
    )
    if videos is None:
        ui.print(paint(t("estimate_unavailable"), Colors.YELLOW))
        return None
    if videos.count == 0:
        ui.print(paint(t("estimate_nothing_new"), Colors.GREEN))
        return _Sizes([], videos)

    ui.print(paint(t("preflight_measuring_speed"), Colors.CYAN))
    measured = measure(settings.download.proxy)
    speed = effective_speed(measured, settings.download.rate_limit)
    if measured is None:
        ui.print(paint(t("preflight_speed_unknown"), Colors.YELLOW))
    else:
        ui.print(t("preflight_speed_measured", mbps=f"{measured * 8 / 1_000_000:.1f}"))

    if request.mode == DownloadMode.AUDIO:
        kbps = audio_output_kbps(settings.audio.audio_format, settings.audio.audio_quality)
        rows = [estimate_audio(videos, kbps)]
        labels = [settings.audio.audio_format]
        first_column = t("estimate_col_format")
    else:
        heights = (COMPAT_MAX_HEIGHT,) if compat else RESOLUTIONS
        rows = [estimate_video(videos, height) for height in heights]
        labels = [
            t("estimate_row_plain", height=height)
            if height == RESOLUTIONS[0]
            else t("estimate_row_at_most", height=height)
            for height in heights
        ]
        first_column = t("estimate_col_resolution")

    cells: list[tuple[str, ...]] = []
    for label, row in zip(labels, rows, strict=True):
        seconds = download_seconds(row.download_bytes, speed)
        cells.append(
            (
                label,
                format_size(row.total_bytes),
                format_size(row.required_bytes),
                format_duration(seconds) if seconds is not None else t("estimate_time_unknown"),
            )
        )
    header = (
        first_column,
        t("estimate_col_size"),
        t("estimate_col_needed"),
        t("estimate_col_time"),
    )

    ui.print("\n" + paint(t("estimate_title"), Colors.CYAN, Colors.BOLD))
    for line in _table_lines(header, cells):
        ui.print(line)
    ui.print(
        t(
            "estimate_summary",
            count=videos.count,
            archived=videos.archived,
            assumed=videos.assumed,
        )
    )
    if free is None:
        ui.print(paint(t("estimate_free_unknown"), Colors.YELLOW))
    else:
        ui.print(t("estimate_free_space", free=format_size(free)))

    if request.mode == DownloadMode.ARCHIVE:
        archive = settings.archive
        wait = archive_wait_seconds(
            videos.count, archive.sleep_interval, archive.max_sleep_interval
        )
        average = (
            archive.sleep_interval + max(archive.sleep_interval, archive.max_sleep_interval)
        ) / 2
        ui.print(
            paint(
                t(
                    "archive_wait_minimum",
                    duration=format_duration(wait),
                    count=videos.count,
                    average=f"{average:g}",
                ),
                Colors.YELLOW,
            )
        )
    return _Sizes(rows, videos)


def _height_label(height: int | None, default: int | None) -> str:
    label = t("resolution_unlimited") if height is None else t("resolution_option", height=height)
    return t("resolution_default_mark", label=label) if height == default else label


def _choose_height(
    request: PreflightRequest,
    settings: AppSettings,
    ui: UI,
    persist_default: Callable[[int | None], None],
    compat: bool,
) -> int | None:
    """Decide the resolution cap, asking only where a choice exists."""
    if request.mode == DownloadMode.AUDIO:
        return None
    if compat:
        ui.print(paint(t("estimate_compat_note"), Colors.YELLOW))
        return COMPAT_MAX_HEIGHT

    default = _default_height(request.mode, settings)
    options = [_height_label(height, default) for height in RESOLUTION_CHOICES]
    height = RESOLUTION_CHOICES[ui.pick(t("prompt_resolution"), options) - 1]

    if height != default:
        keep = ui.pick(
            t("prompt_resolution_save"),
            [t("resolution_save_once"), t("resolution_save_default")],
        )
        if keep == 2:
            try:
                persist_default(height)
            except OSError as ex:
                ui.print(paint(t("resolution_save_failed", error=ex), Colors.YELLOW))
    return height


def _row_for(rows: list[SizeEstimate], height: int | None) -> SizeEstimate:
    """The row for a cap; "unlimited" is judged by the largest row (2160p)."""
    for row in rows:
        if height is not None and row.height == height:
            return row
    return rows[-1]


def _confirm_low_space(ui: UI, request: PreflightRequest, needed: int, free: int) -> bool:
    """Warn that the disk is too small; True to carry on, False to cancel."""
    ui.print(
        paint(
            t("disk_low_warning", needed=format_size(needed), free=format_size(free)),
            Colors.RED,
            Colors.BOLD,
        )
    )
    choice = ui.pick(t("disk_low_prompt"), [t("disk_low_continue"), t("disk_low_cancel")])
    if choice == 1:
        return True
    ui.print(paint(t("disk_low_cancelled"), Colors.YELLOW))
    append_log(
        request.log_path,
        f"\n[INFO {_stamp()}] Cancelled by the user: not enough free disk space "
        f"(needed about {needed} bytes, free {free} bytes)\n",
    )
    return False


def run_preflight(
    request: PreflightRequest,
    *,
    ui: UI,
    settings: AppSettings,
    persist_default: Callable[[int | None], None],
    measure: Callable[[str | None], float | None] = measure_speed,
    disk_free: Callable[[Path], int] = free_bytes,
) -> PreflightResult:
    """Show the estimate, ask the resolution cap and check the disk.

    Args:
        request: What is about to be downloaded.
        ui: Where to print and ask.
        settings: Saved settings (defaults, proxy, rate limit, waits, audio format).
        persist_default: Saves a cap as the default for the current mode; may raise OSError.
        measure: Measures the connection speed in bytes per second (None = unknown).
        disk_free: Returns the free bytes on a path's disk; may raise OSError.

    Returns:
        PROCEED with the cap to use, or CANCEL when the user declined to continue
        on too little free space.
    """
    compat = (
        request.mode == DownloadMode.VIDEO and request.mp4_profile == ProfileChoice.COMPATIBILITY
    )

    sizes: _Sizes | None = None
    free: int | None = None
    if request.is_playlist:
        free = _free_or_none(disk_free, request.base_dir)
        sizes = _show_estimate(request, settings, ui, measure, compat, free)
        if sizes is not None and sizes.videos.count == 0:
            if compat:
                return PreflightResult(PreflightAction.PROCEED, COMPAT_MAX_HEIGHT)
            return PreflightResult(PreflightAction.PROCEED, _default_height(request.mode, settings))

    height = _choose_height(request, settings, ui, persist_default, compat)

    if sizes is not None and free is not None:
        needed = _row_for(sizes.rows, height).required_bytes
        if free < needed and not _confirm_low_space(ui, request, needed, free):
            return PreflightResult(PreflightAction.CANCEL)

    return PreflightResult(PreflightAction.PROCEED, height)
```

- [ ] **Adım 4: Doğrula**

Çalıştır: `.venv/bin/python -m pytest tests/test_preflight.py -v`
Beklenen: PASS. Olası ayrıntılar:
- `test_the_check_uses_the_chosen_resolution`: 1080p satırı için gereken alan 1.386 GB + 0.462 GB = 1.85 GB < 5 GB (yeter); "Sınırsız" 2160p satırı 6.786 GB + 2.262 GB > 5 GB (yetmez). Testin sayıları bu iki durumu ayırt eder.
- `test_the_check_uses_...` içindeki ilk çağrıda seçim 1 (1080p) varsayılandan farklı (varsayılan sınırsız), bu yüzden ikinci "kaydet" sorusu için ikinci pick `1` gerekir; test bunu sağlıyor.
- Tam paket, ruff (satır uzunluğu: uzun satırlarda `ruff format` düzeltir), mypy temiz.

- [ ] **Adım 5: Commit**

```bash
git add ytdlp_app/preflight.py tests/test_preflight.py TASKS.md
git commit -m "feat: add the preflight listing guard, estimate table and disk check" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 8: `session.py` entegrasyonu

**Dosyalar:**
- Değişir: `ytdlp_app/session.py`, `ytdlp_app/playlist.py` (`resolve_channel_id` kalkar), `ytdlp_app/locales/en.json`, `tr.json` (`archive_resolving_channel` kalkar)
- Değişir: `tests/conftest.py`, `tests/test_session_archive.py`, `tests/test_playlist.py` (`TestResolveChannelId` kalkar)
- Oluşturur: `tests/test_session_preflight.py`

**Arayüzler:**
- Tüketir: Görev 2 (`fetch_listing`, `PlaylistListing`, `channel_id_from_url`), 4 (`measure_speed`), 5 (`listing_args`), 6 (`set_max_height`), 7 (`guarded_listing`, `ListingStatus`, `run_preflight`, `PreflightRequest`, `PreflightAction`, `free_bytes`).

- [ ] **Adım 1: Ağa çıkışı engelleyen autouse fixture (önce bu)**

`tests/conftest.py` sonuna ekle:

```python
@pytest.fixture(autouse=True)
def _no_speed_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session tests must never reach the network for a speed measurement."""
    import ytdlp_app.session as session_module  # noqa: PLC0415

    monkeypatch.setattr(session_module, "measure_speed", lambda _proxy: None, raising=False)
```

(`raising=False`: Görev 8 adım 4'te `session.measure_speed` oluşana kadar mevcut testler kırılmasın; adım 4'ten sonra bu satırı `raising=True` varsayılanına çevir: `, raising=False` kısmını sil.)

- [ ] **Adım 2: Yeni oturum testlerini yaz**

`tests/test_session_preflight.py`:

```python
"""Session-level tests for the estimate, resolution question and disk check."""

import json
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.session as session_module
from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.i18n import set_language, t
from ytdlp_app.models import ActionChoice, AppPaths, ModeChoice, PlaylistEntry
from ytdlp_app.playlist import PlaylistListing
from ytdlp_app.session import CycleOutcome
from tests.test_session_archive import Recorder, ScriptedUI, _session

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
LIST_URL = "https://www.youtube.com/playlist?list=PLabc"
CHANNEL_URL = "https://www.youtube.com/@ChannelHandle"
CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"

VIDEO, AUDIO, ARCHIVE = (int(ModeChoice.VIDEO), int(ModeChoice.AUDIO), int(ModeChoice.ARCHIVE))
EXIT = int(ActionChoice.EXIT)
FULL_PLAYLIST = 1
QUALITY, MKV, COMPAT = 2, 1, 1
UNLIMITED = 4
BAN_TEXT = "ERROR: [youtube:tab] @Handle: Sign in to confirm you\u2019re not a bot."


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(
        app_dir=tmp_path,
        config_file=tmp_path / "config.json",
        logs_dir=tmp_path / "logs",
        archives_dir=tmp_path / "archives",
    )


def _entries(count: int = 3) -> list[PlaylistEntry]:
    return [
        PlaylistEntry(i, f"v{i}", "t", f"https://www.youtube.com/watch?v=v{i}", 600.0)
        for i in range(1, count + 1)
    ]


def _selector(cmd: list[str]) -> str:
    return cmd[cmd.index("-f") + 1]


class TestMp4Playlist:
    def _start(self, monkeypatch, tmp_path, paths, ui, runner, url: str = LIST_URL):
        session = _session(monkeypatch, tmp_path, paths, ui, url, runner)
        monkeypatch.setattr(session_module, "fetch_playlist_entries", lambda *_a: _entries())
        return session

    def test_the_estimate_is_shown_before_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, EXIT])
        runner = Recorder()
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        text = ui.text()
        assert t("preflight_listing_warning") in text
        assert "1440p (at most)" in text
        assert "3 videos to download" in text
        assert _selector(runner.calls[0]["cmd"]) == "bv*+ba/b"

    def test_the_chosen_cap_reaches_the_command(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, 2, 1, EXIT])  # 1440p, once
        runner = Recorder()
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)

        session._process_one_cycle()

        assert _selector(runner.calls[0]["cmd"]) == "bv*[height<=1440]+ba/b[height<=1440]"
        assert session.settings.video.max_height is None

    def test_saving_the_choice_updates_the_settings_and_the_config_file(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, 2, 2, EXIT])  # 1440p, default
        session = self._start(monkeypatch, tmp_path, paths, ui, Recorder())

        session._process_one_cycle()

        assert session.settings.video.max_height == 1440
        stored = json.loads(paths.config_file.read_text(encoding="utf-8"))
        assert stored["settings"]["video"]["max_height"] == 1440

    def test_too_little_space_can_cancel_without_downloading(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, 2])  # cancel
        runner = Recorder()
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)
        monkeypatch.setattr(session_module, "free_bytes", lambda _path: 1000)

        assert session._process_one_cycle() == CycleOutcome.CONTINUE

        assert runner.calls == []
        assert session.log_path is not None
        assert "Cancelled" in session.log_path.read_text(encoding="utf-8")

    def test_too_little_space_can_continue_anyway(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, 1, EXIT])
        runner = Recorder()
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)
        monkeypatch.setattr(session_module, "free_bytes", lambda _path: 1000)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS
        assert len(runner.calls) == 1

    def test_compatibility_is_capped_at_1080_without_a_question(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, COMPAT, EXIT])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        session._process_one_cycle()

        assert len(runner.calls) == 2  # stage 1 and stage 2
        assert "[height<=1080]" in _selector(runner.calls[0]["cmd"])
        assert "[height<=1080]" in _selector(runner.calls[1]["cmd"])
        assert t("prompt_resolution") not in ui.prompts

    def test_a_failed_listing_is_reported_and_can_stop_the_run(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV], exit_on_failure=True)
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def failing(*_a: Any) -> list[PlaylistEntry]:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        monkeypatch.setattr(session_module, "fetch_playlist_entries", failing)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE
        assert t("playlist_fetch_failed") in ui.text()
        assert runner.calls == []

    def test_a_failed_listing_can_continue_without_an_estimate(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI(
            [VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, EXIT], exit_on_failure=False
        )
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def failing(*_a: Any) -> list[PlaylistEntry]:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        monkeypatch.setattr(session_module, "fetch_playlist_entries", failing)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS
        assert t("estimate_unavailable") in ui.text()
        assert len(runner.calls) == 1

    def test_a_ban_during_the_listing_never_starts_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV], exit_on_failure=True)
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def banned(*_a: Any) -> list[PlaylistEntry]:
            raise PlaylistError(f"returncode=1\nstderr:\n{BAN_TEXT}")

        monkeypatch.setattr(session_module, "fetch_playlist_entries", banned)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE
        assert runner.calls == []
        assert t("ban_retry_hint") in ui.text()

    def test_ctrl_c_during_the_listing_stops_before_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def interrupted(*_a: Any) -> list[PlaylistEntry]:
            raise KeyboardInterrupt

        monkeypatch.setattr(session_module, "fetch_playlist_entries", interrupted)

        assert session._process_one_cycle() == CycleOutcome.INTERRUPTED
        assert runner.calls == []


class TestMp3Playlist:
    def test_one_row_and_no_resolution_question(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([AUDIO, FULL_PLAYLIST, EXIT])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        monkeypatch.setattr(session_module, "fetch_playlist_entries", lambda *_a: _entries())

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        assert "mp3" in ui.text()
        assert t("prompt_resolution") not in ui.prompts
        assert "height" not in " ".join(runner.calls[0]["cmd"])


class TestArchive:
    def test_a_playlist_is_listed_once_for_the_estimate(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, FULL_PLAYLIST, 2, 1, EXIT])  # 1440p, only this once
        runner = Recorder()
        seen: list[tuple[str, list[str]]] = []

        def listing(url: str, extra_args: list[str], _runner: Any) -> PlaylistListing:
            seen.append((url, extra_args))
            return PlaylistListing(_entries(), None)

        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        monkeypatch.setattr(session_module, "fetch_listing", listing)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        ((url, extra_args),) = seen
        assert url == LIST_URL
        assert extra_args[extra_args.index("--sleep-requests") + 1] == "1.5"
        cmd = runner.calls[0]["cmd"]
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / "playlist_PLabc_archive.txt"
        )
        assert _selector(cmd) == "bv*[height<=1440]+ba/b[height<=1440]"
        assert "at least" in ui.text()  # the wait warning

    def test_videos_already_in_the_archive_are_not_counted(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        paths.archives_dir.mkdir(parents=True)
        (paths.archives_dir / "playlist_PLabc_archive.txt").write_text(
            "youtube v1\nyoutube v2\n", encoding="utf-8"
        )
        ui = ScriptedUI([ARCHIVE, FULL_PLAYLIST, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, Recorder())
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing(_entries(), None)
        )

        session._process_one_cycle()

        assert "1 videos to download, 2 already in the archive" in ui.text()

    def test_the_listing_warning_mentions_the_request_wait(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, Recorder())
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing(_entries(), CHANNEL_ID)
        )

        session._process_one_cycle()

        assert t("preflight_listing_warning") in ui.text()
        assert "waits 1.5 s" in ui.text()

    def test_a_single_video_sends_no_listing_request(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        def forbidden(*_a: Any) -> Any:
            raise AssertionError("a single video must not be listed")

        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, Recorder())
        monkeypatch.setattr(session_module, "fetch_listing", forbidden)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS
        assert "Estimated size" not in ui.text()

    def test_ctrl_c_during_the_channel_listing_stops_everything(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        def interrupted(*_a: Any) -> Any:
            raise KeyboardInterrupt

        ui = ScriptedUI([ARCHIVE])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)
        monkeypatch.setattr(session_module, "fetch_listing", interrupted)

        assert session._process_one_cycle() == CycleOutcome.INTERRUPTED
        assert runner.calls == []
```

`tests.test_session_archive` import yolu: `tests/__init__.py` var, pytest rootdir'den `tests.` paketiyle çözülür. Mevcut testlerdeki gibi `ruff` isort'ta `tests` first-party dışında kalabilir; `ruff check --fix` sıralar.

- [ ] **Adım 3: Mevcut arşiv testlerini yeni davranışa uyarla**

`tests/test_session_archive.py`:

1. Import: `from ytdlp_app.playlist import PlaylistListing` ekle; `_forbidden` açıklamasını güncelle: `"archive mode must not send skip-report listing or skip-probe requests"`.
2. `test_single_video`: `resolve_channel_id` monkeypatch satırını sil; `ScriptedUI([ARCHIVE, EXIT])` → `ScriptedUI([ARCHIVE, 1, EXIT])` (arşiv tek videoda çözünürlük sorusu 1080p = varsayılan, ikinci soru yok).
3. `test_channel_uses_the_resolved_channel_id` → adı `test_channel_uses_the_channel_id_from_the_listing`; gövde:

```text
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()
        lookups: list[tuple[str, list[str]]] = []

        def fake_listing(url: str, extra_args: list[str], _runner: Any) -> PlaylistListing:
            lookups.append((url, extra_args))
            return PlaylistListing(entries=[], channel_id=CHANNEL_ID)

        monkeypatch.setattr(session_module, "fetch_listing", fake_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)
        session.settings.download.proxy = "http://proxy:3128"

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        cmd = runner.calls[0]["cmd"]
        assert "--yes-playlist" in cmd
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / f"channel_{CHANNEL_ID}_archive.txt"
        )
        # The listing goes through the same proxy as the download, with the archive's request wait.
        ((url, extra_args),) = lookups
        assert url == CHANNEL_URL
        assert "http://proxy:3128" in extra_args
        assert extra_args[extra_args.index("--sleep-requests") + 1] == "1.5"
        assert t("prompt_playlist") not in ui.prompts
```
4. `test_lookup_failure_falls_back_to_the_handle`: `failing_resolve` → `failing_listing` (`def failing_listing(*_args: Any) -> PlaylistListing: raise PlaylistError(...)`), `monkeypatch.setattr(session_module, "fetch_listing", failing_listing)`, picks `[ARCHIVE, 1, EXIT]`; ek assert: `assert t("estimate_unavailable") in ui.text()`.
5. `TestBanProtection.test_ban_during_download_explains_how_to_resume` ve `test_ban_can_return_to_the_prompt`: `ScriptedUI([ARCHIVE])` → `ScriptedUI([ARCHIVE, 1])` (indirmeden önce çözünürlük sorusu sorulur).
6. `test_ban_during_channel_lookup_never_starts_the_download`: `banned_resolve` → `banned_listing` ve `monkeypatch.setattr(session_module, "fetch_listing", banned_listing)`; picks aynı (`[ARCHIVE]`); testin adını `test_ban_during_the_channel_listing_never_starts_the_download` yap; assert'ler aynı.
7. `TestRegularModesUnchanged.test_mp4_channel_still_asks_and_still_reports_skips`: picks `[int(ModeChoice.VIDEO), 1, 2, 1, EXIT]` → `[int(ModeChoice.VIDEO), 1, 2, 1, 4, EXIT]` (4 = "Unlimited", MP4 varsayılanı; yorum: `# Video, whole playlist, Quality profile, MKV, no resolution cap, then exit.`).
8. `TestImpersonationWarning`: `test_archive_mode_warns_when_it_is_missing` ve `test_no_warning_when_present_or_unknown`: `ScriptedUI([ARCHIVE, EXIT])` → `ScriptedUI([ARCHIVE, 1, EXIT])`.

`tests/test_playlist.py`: `TestResolveChannelId` sınıfının **tamamını** sil ve `resolve_channel_id` import'unu kaldır; eşdeğer davranış Görev 2'de `TestFetchListing` (`test_channel_id_is_read_from_the_listing`, `test_channel_id_in_the_url_wins`) ile kapsanıyor. `_nested_channel_json` yardımcısı `TestFetchListing` tarafından kullanılıyor, kalır. Ek olarak ekle (eski "iç içe sekmeden kimlik" testinin karşılığı):

```text
    def test_channel_id_falls_back_to_the_nested_entries(self) -> None:
        data = _nested_channel_json(top_level_id=False)
        listing = fetch_listing(
            "https://www.youtube.com/@ChannelHandle", [], FakeRunner(out=json.dumps(data))
        )
        assert listing.channel_id == CHANNEL_ID
```
(bunu `TestFetchListing` içine koy.)

- [ ] **Adım 4: `session.py`'yi uygula**

Import'lar (`ruff check --fix` ile sırala; kullanılmayanları ruff raporlar):

- `from .config import save_settings` ekle.
- `from .exceptions import PlaylistError, ValidationError` → `from .exceptions import ValidationError`.
- `from .exec import BAN_RETURN_CODE, find_ban_signal, run_capture, run_cmd_tee` → `from .exec import BAN_RETURN_CODE, run_capture, run_cmd_tee`.
- playlist import'undan `resolve_channel_id` çıkar; ekle: `PlaylistListing`, `channel_id_from_url`, `fetch_listing`.
- Ekle: `from .preflight import ListingStatus, PreflightAction, PreflightRequest, free_bytes, guarded_listing, run_preflight` ve `from .speedtest import measure_speed`.
- `TYPE_CHECKING` bloğuna `from collections.abc import Callable` ve `from .preflight import GuardedListing` ekle; `_T = TypeVar("_T")` için `from typing import TYPE_CHECKING, Any, TypeVar` yap ve modül düzeyine `_T = TypeVar("_T")` koy.

`_archive_file_name`'i tamamen değiştir:

```text
    def _archive_file_name(
        self,
        url: str,
        channel_archive: bool,
        playlist_id: str | None,
        listing: PlaylistListing | None,
    ) -> str:
        """Pick the download archive file for an archive-mode run.

        A channel is keyed by its real channel id, so the handle URL, the
        /channel/ URL and any tab URL of one channel all resume one archive. The
        id comes from the URL when it carries one, otherwise from the listing
        that also feeds the size estimate.
        """
        if not channel_archive:
            if playlist_id:
                return f"playlist_{safe_archive_token(playlist_id)}_archive.txt"
            return "single_videos_archive.txt"

        channel_id = channel_id_from_url(url) or (listing.channel_id if listing else None)
        if channel_id is None:
            # Not fatal: fall back to the identifier in the URL, which still
            # resumes correctly as long as the same URL is used again.
            channel_id = get_playlist_id(url)
            self.ui.print(
                f"{paint(t('label_warning'), Colors.YELLOW, Colors.BOLD)} "
                f"{paint(t('archive_channel_id_fallback', id=channel_id), Colors.YELLOW)}"
            )
        return f"channel_{safe_archive_token(channel_id)}_archive.txt"
```

Yeni yardımcılar (`report_ban`'ın altına):

```text
    def _stop_after_ban(self) -> CycleOutcome:
        """Report a ban and let the user choose between exiting and a new URL."""
        self.report_ban()
        if self.ui.prompt_exit_on_failure():
            return CycleOutcome.EXIT_FAILURE
        return CycleOutcome.CONTINUE

    def _list_playlist(
        self, fetch: Callable[[], _T], *, archive_mode: bool
    ) -> GuardedListing[_T]:
        """Warn that reading a big listing is slow, then run the request."""
        warning = t("preflight_listing_warning")
        if archive_mode:
            wait = f"{self.settings.archive.sleep_requests:g}"
            warning += t("preflight_listing_warning_wait", seconds=wait)
        self.ui.print(paint(warning, Colors.CYAN))
        return guarded_listing(fetch, self.log_path)

    def _persist_default_height(self, mode: DownloadMode, height: int | None) -> None:
        """Save a resolution cap as the default for its mode."""
        if mode == DownloadMode.ARCHIVE:
            self.settings.archive.max_height = height
        else:
            self.settings.video.max_height = height
        save_settings(self.paths.config_file, self.cfg, self.settings)
```

`_process_one_cycle` adım 6, arşiv dalı (eski blok → yeni blok):

eski:
```text
        templates = self.settings.output
        if archive_mode:
            base_dir = self.config.videos_dir / "yt-dlp"
            output_template = str(base_dir / templates.archive_template)
            archive_name = self._archive_file_name(url, channel_archive, playlist_id, deno_ok)
            if archive_name is None:
                # YouTube is already blocking us; report_ban has told the user.
                if self.ui.prompt_exit_on_failure():
                    return CycleOutcome.EXIT_FAILURE
                return CycleOutcome.CONTINUE
            archive_path = self.paths.archives_dir / archive_name
```
yeni:
```text
        templates = self.settings.output
        listing: PlaylistListing | None = None
        if archive_mode:
            base_dir = self.config.videos_dir / "yt-dlp"
            output_template = str(base_dir / templates.archive_template)
            if is_playlist:
                # One flat listing feeds the size estimate and, for a channel, the
                # archive file name, so there is no separate channel id request.
                listing_args = [
                    *js_runtime_args(deno_ok),
                    *self.settings.archive.listing_args(),
                    *self.settings.download.network_args(),
                ]
                guarded = self._list_playlist(
                    lambda: fetch_listing(url, listing_args, run_capture), archive_mode=True
                )
                if guarded.status is ListingStatus.INTERRUPTED:
                    return CycleOutcome.INTERRUPTED
                if guarded.status is ListingStatus.BAN:
                    # YouTube is already blocking us; the guard has logged it.
                    return self._stop_after_ban()
                listing = guarded.value
            archive_name = self._archive_file_name(url, channel_archive, playlist_id, listing)
            archive_path = self.paths.archives_dir / archive_name
```

Adım 8 ve 9 (eski blok → yeni blok):

eski:
```text
        # 8) Playlist mapping. Archive mode skips it: the listing exists only for
        # the skip report, whose per-item probes are exactly the kind of extra
        # traffic archive mode avoids.
        entries = []
        if plan.is_playlist and not archive_mode:
            try:
                entries = fetch_playlist_entries(plan.url, plan.js_args, run_capture)
            except Exception as ex:
                log_error(log_path, t("playlist_fetch_failed_log"), ex)
                self.ui.print(f"{t('playlist_fetch_failed')}\n{ex}\n")
                if self.ui.prompt_exit_on_failure():
                    return CycleOutcome.EXIT_FAILURE

        # 9) DOWNLOAD
        final_rc = self._execute_download(plan, cmd_builder)
        if final_rc == 130:
            return CycleOutcome.INTERRUPTED
        if final_rc == BAN_RETURN_CODE:
            self.report_ban()
            if self.ui.prompt_exit_on_failure():
                return CycleOutcome.EXIT_FAILURE
            return CycleOutcome.CONTINUE
```
yeni:
```text
        # 8) Playlist listing. Archive mode already listed in step 6, and never
        # runs the skip report, whose per-item probes are exactly the kind of
        # extra traffic archive mode avoids.
        entries: list[PlaylistEntry] = []
        estimate_entries: list[PlaylistEntry] | None = None
        if archive_mode:
            estimate_entries = listing.entries if listing is not None else None
        elif plan.is_playlist:
            guarded_entries = self._list_playlist(
                lambda: fetch_playlist_entries(plan.url, plan.js_args, run_capture),
                archive_mode=False,
            )
            if guarded_entries.status is ListingStatus.INTERRUPTED:
                return CycleOutcome.INTERRUPTED
            if guarded_entries.status is ListingStatus.BAN:
                return self._stop_after_ban()
            if guarded_entries.status is ListingStatus.FAILED:
                self.ui.print(f"{t('playlist_fetch_failed')}\n{guarded_entries.error}\n")
                if self.ui.prompt_exit_on_failure():
                    return CycleOutcome.EXIT_FAILURE
            else:
                entries = guarded_entries.value or []
                estimate_entries = entries

        # 8b) Size estimate, resolution cap and free-space check.
        preflight = run_preflight(
            PreflightRequest(
                mode=mode,
                is_playlist=plan.is_playlist,
                entries=estimate_entries,
                archived_ids=(
                    frozenset(read_archive_ids(archive_path))
                    if plan.is_playlist
                    else frozenset()
                ),
                mp4_profile=mp4_profile,
                base_dir=base_dir,
                log_path=log_path,
            ),
            ui=self.ui,
            settings=self.settings,
            persist_default=lambda height: self._persist_default_height(mode, height),
            measure=measure_speed,
            disk_free=free_bytes,
        )
        if preflight.action is PreflightAction.CANCEL:
            return CycleOutcome.CONTINUE
        cmd_builder.set_max_height(preflight.max_height)

        # 9) DOWNLOAD
        final_rc = self._execute_download(plan, cmd_builder)
        if final_rc == 130:
            return CycleOutcome.INTERRUPTED
        if final_rc == BAN_RETURN_CODE:
            return self._stop_after_ban()
```

`playlist.py`: `resolve_channel_id` fonksiyonunu sil (`json`, `PlaylistError`, `t` başka yerde kullanılıyor; ruff kullanılmayanı bildirir). `locales`: `en.json` ve `tr.json`'dan `"archive_resolving_channel": ...` satırını sil (başka yerde kullanılmıyor: `grep -rn archive_resolving_channel ytdlp_app tests` boş dönmeli). `tests/conftest.py`'daki `raising=False`'u kaldır.

- [ ] **Adım 5: Doğrula**

Çalıştır: `.venv/bin/python -m pytest -q`
Beklenen: hepsi PASS; sayı ≥ 346 (sil/ekle sonrası; çok daha fazla olmalı). Düşen test varsa **dur ve sebebini açıkla** (açıklayamazsan kullanıcıya sor). `ruff check --fix . && ruff format .`, `ruff check . && ruff format --check .`, `mypy ytdlp_app --ignore-missing-imports` temiz.
Elle kontrol: `grep -rn "resolve_channel_id\|archive_resolving_channel" ytdlp_app tests` boş.

- [ ] **Adım 6: Commit**

```bash
git add -A ytdlp_app tests TASKS.md
git commit -m "feat: show the estimate and ask the resolution before every video download" -m "The archive listing now also supplies the channel id, so the separate lookup request is gone. Existing session tests gained the resolution pick." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 9: README ve CHANGELOG

**Dosyalar:**
- Değişir: `README.md`, `CHANGELOG.md`, `TASKS.md`

- [ ] **Adım 1: README (İngilizce) — arşiv maddeleri**

Edit ile:
- eski: `the video (best quality up to 1080p, merged into MKV with chapters and metadata embedded)` → yeni: `the video (best quality up to your resolution limit, 1080p by default, merged into MKV with chapters and metadata embedded)`
- eski: `Looking the id up costs one request; if it fails for a reason other than a block, the id in the URL is used instead.` → yeni: `The id comes from the same listing that feeds the size estimate, so there is no separate lookup; if the listing fails for a reason other than a block, the id in the URL is used instead.`
- eski: `- To keep request volume low, archive mode does not fetch the playlist listing or probe skipped items afterwards (the skip report is MP4/MP3 only).` → yeni: `- To keep request volume low, archive mode lists a channel or playlist once (for the size estimate and the channel id, paced by the request wait) and never probes skipped items afterwards (the skip report is MP4/MP3 only). A single video sends no listing request.`

- [ ] **Adım 2: README (İngilizce) — yeni bölüm**

`## Portable runtime` başlığından hemen önce (Edit: eski `\n## Portable runtime\n`) ekle:

```markdown
## Size estimate and resolution limit
**Before downloading a playlist or channel** (MP4, MP3 and archive modes) the app shows a size estimate and checks free disk space. It reads the listing once (no extra request per video) and multiplies each video's duration by a typical bit rate, so the numbers are deliberately on the high side and are **estimates, not measurements**:

| Row | Assumed bit rate |
|-----|------------------|
| 1080p | 6000 kbit/s video + 160 kbit/s audio |
| 1440p (at most) | 12000 + 160 |
| 2160p (at most) | 30000 + 160 |

- 1440p and 2160p are labelled *at most*: a flat listing carries no resolution, and a video that does not exist at that resolution downloads smaller.
- **Space needed** = the total for the chosen resolution + the largest single video, because the source and the result sit on disk together while merging, recoding or converting.
- Videos already in the download archive are left out. A video without a duration (Shorts, live) is assumed to be 180 s (Shorts) or the median of the known durations; the screen says how many were assumed. If no duration is known at all, the estimate is skipped and the download continues.
- **MP3** shows one number, based on your audio format and quality (`mp3` quality 0 is about 245 kbit/s; `flac` and `wav` are much larger).
- Sizes are 1024-based (KiB/MiB/GiB), like Windows Explorer.
- **Not enough space?** You are warned and asked *Continue anyway / Cancel*. The download is never blocked.
- **Time:** a short (~5 s) speed test against `speed.cloudflare.com` (through your proxy; skipped for SOCKS proxies) turns the size into a download time. It measures your line, not YouTube, and sends your IP to that host. If it fails, the time column says so and nothing else changes. Archive mode also shows the *minimum* time the waits between videos alone will take.
- A single video is not estimated (that would need an extra request).

**Resolution limit.** After the estimate you are asked for the maximum resolution (1080p, 1440p, 2160p or unlimited) for MP4 and archive downloads, also for a single video. The saved default is marked; if you pick another one you can use it once or save it as the new default. It is applied to every video format selector (as `[height<=N]`, including the fallback). The compatibility MP4 profile stays at 1080p, because YouTube serves H.264 up to about 1080p and higher resolutions would be recoded slowly. Defaults: archive 1080p, MP4 unlimited (as before). Change them in `s` → *Video resolution limit* / *Archive resolution limit*, or in `config.json` (`settings.video.max_height`, `settings.archive.max_height`: `1080`, `1440`, `2160` or `null`).

```

- [ ] **Adım 3: README (İngilizce) — modül tablosu**

Edit: eski satır
`| `playlist.py` | Playlist and channel detection, channel id lookup, entry fetching, archive reading |`
yeni:
```
| `playlist.py` | Playlist and channel detection, flat listing (channel tabs flattened, channel id), archive reading |
| `estimate.py` | Size, disk-space and time estimates (pure arithmetic) |
| `speedtest.py` | Short connection-speed measurement |
| `preflight.py` | Listing guard, estimate table, resolution question and free-space check |
```

- [ ] **Adım 4: README (Türkçe)**

Edit ile:
- eski: `video (1080p'ye kadar en iyi kalite, bölümler ve metadata gömülü MKV)` → yeni: `video (çözünürlük sınırına kadar en iyi kalite, varsayılan 1080p; bölümler ve metadata gömülü MKV)`
- eski: `Kimliği öğrenmek tek istek gerektirir; engel dışı bir sebeple başarısız olursa URL'deki kimlik kullanılır.` → yeni: `Kimlik, boyut tahminini de besleyen aynı listeden okunur (ayrı bir istek yok); liste engel dışı bir sebeple başarısız olursa URL'deki kimlik kullanılır.`
- eski: `- İstek sayısını düşük tutmak için arşiv modu playlist listesini çekmez ve sonrasında atlanan öğeleri yoklamaz (atlama raporu yalnızca MP4/MP3'te).` → yeni: `- İstek sayısını düşük tutmak için arşiv modu bir kanalı ya da playlist'i yalnızca bir kez listeler (boyut tahmini ve kanal kimliği için; istekler arası bekleme uygulanır) ve sonrasında atlanan öğeleri yoklamaz (atlama raporu yalnızca MP4/MP3'te). Tek video için liste isteği yapılmaz.`
- `### Taşınabilir çalışma ortamı` başlığından önce (Edit: eski `\n### Taşınabilir çalışma ortamı\n`) ekle:

```markdown
### Boyut tahmini ve çözünürlük sınırı
**Playlist ya da kanal indirmeden önce** (MP4, MP3 ve arşiv modları) uygulama bir boyut tahmini gösterir ve boş disk alanını kontrol eder. Listeyi bir kez okur (video başına ek istek yok) ve her videonun süresini tipik bir bit hızıyla çarpar; bu yüzden rakamlar bilerek yüksek taraftadır ve **ölçüm değil tahmindir**:

| Satır | Varsayılan bit hızı |
|-------|---------------------|
| 1080p | 6000 kbit/sn video + 160 kbit/sn ses |
| 1440p (en fazla) | 12000 + 160 |
| 2160p (en fazla) | 30000 + 160 |

- 1440p ve 2160p "en fazla" diye etiketlenir: düz listede çözünürlük yoktur ve o çözünürlükte olmayan video daha küçük iner.
- **Gereken alan** = seçilen çözünürlüğün toplamı + en büyük tek video; birleştirme, yeniden kodlama ve dönüştürme sırasında kaynak ve sonuç diskte birlikte durur.
- Arşivde kayıtlı videolar hariç tutulur. Süresi olmayan video (Shorts, canlı) 180 sn (Shorts) ya da bilinen sürelerin medyanı kabul edilir; ekranda kaç videonun varsayımla hesaplandığı yazar. Hiçbir süre bilinmiyorsa tahmin atlanır ve indirme devam eder.
- **MP3** tek rakam gösterir; ses biçimin ve kaliten esas alınır (`mp3` kalite 0 yaklaşık 245 kbit/sn; `flac` ve `wav` çok daha büyük).
- Boyutlar 1024 tabanlıdır (KiB/MiB/GiB), Windows Gezgini gibi.
- **Yer yetmiyor mu?** Uyarılır ve *Yine de devam et / İptal* sorulur. İndirme asla engellenmez.
- **Süre:** kısa (~5 sn) bir hız testi (`speed.cloudflare.com`, proxy'nden geçer; SOCKS proxy'de atlanır) boyutu indirme süresine çevirir. YouTube'u değil hattını ölçer ve IP adresini o sunucuya gönderir. Başarısız olursa süre sütunu bunu söyler, başka bir şey değişmez. Arşiv modu ayrıca yalnızca videolar arası beklemelerin **en az** ne kadar süreceğini gösterir.
- Tek video için tahmin yapılmaz (ek istek gerekirdi).

**Çözünürlük sınırı.** Tahminden sonra MP4 ve arşiv indirmeleri için (tek video dahil) en yüksek çözünürlük sorulur: 1080p, 1440p, 2160p ya da sınırsız. Kayıtlı varsayılan işaretlidir; başka bir seçenek seçersen yalnızca bu indirme için kullanabilir ya da yeni varsayılan olarak kaydedebilirsin. Sınır tüm video format seçicilerine (`[height<=N]`, yedek dahil) uygulanır. Uyumluluk MP4 profili 1080p'de kalır: YouTube H.264'ü yaklaşık 1080p'ye kadar verir, daha yükseği yavaşça yeniden kodlanırdı. Varsayılanlar: arşiv 1080p, MP4 sınırsız (eskisi gibi). `s` → *Video cozunurluk siniri* / *Arsiv cozunurluk siniri* ile ya da `config.json`'da (`settings.video.max_height`, `settings.archive.max_height`: `1080`, `1440`, `2160` ya da `null`) değiştirilir.

```

- Modül tablosu (Türkçe): eski satır `| `playlist.py` | Playlist ve kanal algılama, kanal kimliği sorgulama, öğe çekme, arşiv okuma |` → yeni:
```
| `playlist.py` | Playlist ve kanal algılama, düz liste (kanal sekmeleri düzleştirilir, kanal kimliği), arşiv okuma |
| `estimate.py` | Boyut, disk alanı ve süre tahmini (saf hesap) |
| `speedtest.py` | Kısa bağlantı hızı ölçümü |
| `preflight.py` | Liste koruması, tahmin tablosu, çözünürlük sorusu ve boş alan kontrolü |
```

- [ ] **Adım 5: CHANGELOG**

Edit ile (`## [Unreleased]` altındaki `### Added` başlığının hemen sonrasına yeni madde; eski `### Added\n- **Fully portable on Windows and Linux.**` → yeni aynı satır önüne şu maddeyi ekleyerek):

```markdown
- **Size estimate, disk check and resolution limit.** Before a playlist or channel download (MP4, MP3 and archive) the app reads the listing once and shows a high-side size estimate for 1080p, 1440p and 2160p from each video's duration and a typical bit rate (no per-video request), checks free disk space (*Continue anyway / Cancel*, never blocked) and, using a short speed test against `speed.cloudflare.com`, estimates the download time. Archive mode also shows the minimum time the waits between videos take. A resolution limit (1080p, 1440p, 2160p or unlimited) is asked after the estimate for MP4 and archive downloads, also for single videos, and can be saved as the new default; it is applied to every video format selector, including the fallback. The compatibility MP4 profile stays at 1080p. New settings `settings.video.max_height` (default `null`) and `settings.archive.max_height` (default `1080`), editable from the settings menu.
```

Ve arşiv maddelerini doğru tut:
- eski `keyed by the real channel id (looked up with one flat request), so every URL form` → yeni `keyed by the real channel id (read from the flat listing that also feeds the size estimate), so every URL form`
- eski `The same check covers the channel id lookup.` → yeni `The same check covers the channel listing.`
- eski `- Archive mode sends no playlist-listing or skip-probe requests, and does not pass` → yeni `- Archive mode lists a channel or playlist once (a single video sends no listing request), sends no skip-probe requests, and does not pass`
- eski `For every video it keeps the video (up to 1080p, merged` → yeni `For every video it keeps the video (up to 1080p by default, merged`

`### Fixed` bölümünün başına ekle:

```markdown
- A bare channel URL is now listed as its videos: yt-dlp returns the Videos, Shorts and Live tabs as nested playlists, and the flat listing used to count the tabs instead of the videos (which also made the MP4 skip report wrong for channels).
```
(`### Fixed` başlığı satırı `### Fixed` olarak tek başına duruyor; hemen altına ekle. Dosyada başka `### Fixed` varsa yalnızca `[Unreleased]` altındakini düzenle.)

- [ ] **Adım 6: Doğrula ve commit**

Çalıştır: `.venv/bin/python -m pytest -q` (README/CHANGELOG'u test eden bir test varsa geçmeli).

```bash
git add README.md CHANGELOG.md TASKS.md
git commit -m "docs: document the size estimate, disk check and resolution limit" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Görev 10: Tam doğrulama, gerçek deneme, PR

**Dosyalar:** `TASKS.md`

- [ ] **Adım 1: Tam kapı**

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy ytdlp_app --ignore-missing-imports
```
Beklenen: pytest ≥ 346 geçer, ruff ve mypy temiz. Aksi halde dur; açıklayamadığın bir hata varsa kullanıcıya sor.

- [ ] **Adım 2: Bit hızı makullük kontrolü (izinli videoyla tek `-J`)**

```bash
.venv/bin/yt-dlp -J --no-playlist --skip-download "https://www.youtube.com/watch?v=izx6nkLpoOA" > "$SCRATCH/probe.json"
.venv/bin/python - <<'E'
import json, os
d = json.load(open(os.environ["SCRATCH"] + "/probe.json"))
print("duration:", d.get("duration"))
for f in d["formats"]:
    if f.get("vcodec") not in (None, "none") or f.get("acodec") not in (None, "none"):
        print(f["format_id"], f.get("height"), f.get("vcodec"), f.get("acodec"), f.get("tbr"), f.get("filesize") or f.get("filesize_approx"))
E
```
(`SCRATCH` = oturumun scratchpad dizini.) Çıktıdaki `tbr` değerlerini tablodaki 6000/12000/30000/160 ile karşılaştır; tek videonun tek örneği olduğunu ve tabloyu kanıtlamadığını not et. Sonucu (hangi yükseklikler mevcuttu, `tbr` aralıkları) rapora "doğrulama" satırı olarak yaz.

- [ ] **Adım 3: Gerçek deneme (yalnızca izinli video, izole uygulama dizini)**

Gerçek uygulamanın `config.json`, `archives/` ve `downloads/` dizinlerine dokunmamak için kurulu-mod yolu ve geçici veri dizini kullan:

```bash
export SCRATCH=<scratchpad>; export XDG_DATA_HOME="$SCRATCH/xdg"; export PATH="$PWD/.venv/bin:$PATH"
URL="https://www.youtube.com/watch?v=izx6nkLpoOA"
run() { .venv/bin/python -c "from ytdlp_app.app import run; raise SystemExit(run())"; }
```
İlk açılış dil ve klasör sorar. Önce `printf '' | run` ile soruları oku, sonra cevapları sırayla besle (dil, video klasörü, müzik klasörü: hepsini `$SCRATCH` altına yönlendir). Ekran çıktısını her denemede `tee "$SCRATCH/trial-<ad>.txt"` ile kaydet. Denemeler (soru sırası ekrandaki menüden okunur; aşağıdakiler beklenen dizilimlerdir):

1. **MP4 Kalite/MKV, tek video, 1440p, yalnızca bu indirme:** URL, mod 1, profil 2, kapsayıcı 1, çözünürlük 2, kayıt sorusu 1, sonra çıkış. Beklenen: tablo **yok**, çözünürlük sorusu var, indirme başlar ve komutta `[height<=1440]` (log dosyasında ya da yt-dlp çıktısında görülür).
2. **MP4 Uyumluluk, tek video:** URL, mod 1, profil 1, çıkış. Beklenen: çözünürlük sorusu yok, "Uyumluluk profili 1080p ... sinirlidir" notu.
3. **MP3, tek video:** URL, mod 2, çıkış. Beklenen: tahmin ve soru yok, indirme başlar.
4. **Arşiv, tek video:** URL, mod 3, çözünürlük 1, çıkış. Beklenen: soru var, arşiv klasörü oluşur.
5. **Varsayılan kaydet:** MP4 tek video, çözünürlük 2 ve kayıt sorusu 2. Beklenen: `$XDG_DATA_HOME/ytdlp-downloader/config.json` içinde `settings.video.max_height: 1440`.

Aynı video ikinci kez arşiv dosyasında "already recorded" ile atlanabilir; bu durumda denemeleri farklı mod/arşiv dosyasıyla yap ya da `$XDG_DATA_HOME` altındaki arşivi **silmeden** yeni bir `XDG_DATA_HOME` kullan. Her denemenin **ekran çıktısını raporda birebir göster** (kısaltma yok, yalnızca tekrarlayan yt-dlp ilerleme satırları elenebilir ve bu belirtilir).

Liste, kanal, tablo, disk kontrolü, süre uyarıları ve hız testi **gerçek ortamda denenmez** (izinli tek test videosu tek video). Bunu raporda "gerçek ortamda doğrulanmadı; fixture ve mock testleriyle doğrulandı" diye işaretle. Hız testi uç noktasına gerçek istek atmadan önce kullanıcıdan ayrıca izin iste (şu an plana dahil değil).

- [ ] **Adım 4: TASKS.md'yi tamamla**

Kutuları `[x]` yap; "Bulunanlar" altına: kanal düzleştirme hatası, `/b` yedeğine sınır (motor testi sonucu), arşiv seçicisinin metin değişimi (`ARCHIVE_DEFAULT_PREFIX`), bit hızı makullük sonucu, gerçek ortamda doğrulanmayanlar. Üstteki "Test durumu" bölümündeki test sayısını güncel sayıyla değiştir.

```bash
git add TASKS.md
git commit -m "docs: update TASKS.md for the size estimate and resolution limit" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Adım 5: Push ve PR**

```bash
git push -u origin feat/disk-space-and-resolution
gh pr create --base main --head feat/disk-space-and-resolution \
  --title "feat: size estimate, disk check and resolution limit" \
  --body-file "$SCRATCH/pr-body.md"
```
`$SCRATCH/pr-body.md`: Türkçe özet (ne değişti, kapsam daralması: tahmin yalnızca liste/kanal; `/b` yedeği ve arşiv seçici metni değişikliği; test sayısı ve ruff/mypy sonucu; gerçek deneme ekran çıktıları; **gerçek ortamda doğrulanmayanlar** listesi; bit hızı değerlerinin doğrulanmadığı notu) ve şu satırla biter: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. `gh pr edit` Projects (classic) hatası verirse açıklamayı `gh api -X PATCH repos/NECATKO/Yt-Dlp_YouTube_Media_Downlader/pulls/<N> -f body=@"$SCRATCH/pr-body.md"` ile düzelt. **Merge etme.**

---

## Kendi kendine gözden geçirme

**Spec kapsamı:** 
- Tahmin ve gereken alan → Görev 3, 7. 
- Tablo, "en fazla" etiketi, tek satır uyumluluk → Görev 7. 
- Tekrar eleme, arşiv düşme, süre varsayımı, "varsayımla" sayısı → Görev 3, 7. 
- MP3 tek rakam ve bit hızı → Görev 3, 7. 
- Boş alan, 1024 tabanı, *Yine de devam et / İptal*, iptalde `CONTINUE` ve log → Görev 7, 8. 
- Hesaplanamazsa devam, rc 130, ban → Görev 2 (`KeyboardInterrupt`), 7 (`guarded_listing`), 8. 
- Arşiv listesi `--sleep-requests` + `network_args`, kanal kimliği listeden, `resolve_channel_id` kalkar → Görev 5 (`listing_args`), 8. 
- Yeni metinler → Görev 1. 
- Çözünürlük sınırı ayarları, menü, örnek dosya, README → Görev 5, 9. 
- Seçici dönüşümü ve `/b` yedeği, motor doğrulaması → Görev 6. 
- Süre uyarıları (liste öncesi, arşiv "en az", tabloda süre) ve hız testi → Görev 4, 7, 8. 
- Kanal düzleştirme (önce test) → Görev 2. 
- Tek video: tahmin yok, soru var → Görev 7, 8. 
- Gerçek deneme, TASKS.md, PR → Görev 10.

**Yer tutucu taraması:** yok. Görev 10 adım 3'teki soru sırası ekrandaki menüden okunacak şekilde bilinçli olarak "beklenen dizilim" diye yazıldı; ilk açılış soruları yalnızca çalışırken görülebildiği için komut yerine yöntem verildi.

**Tür tutarlılığı:** `PlaylistListing(entries, channel_id)`, `fetch_listing(url, extra_args, runner)`, `guarded_listing(fetch, log_path)`, `ListingStatus`, `PreflightRequest` alanları, `run_preflight(..., persist_default, measure, disk_free)`, `CommandBuilder.set_max_height`, `video_format`/`compat_stage1_format`, `ArchiveSettings.listing_args` görevler arasında aynı adlarla kullanılıyor.

**Bilinen risk:** Görev 8'de mevcut testlerin `pick` dizilimleri değişiyor; her değişiklik gerekçesiyle listelendi. Test sayısı düşerse (`TestResolveChannelId` silinmesi yüzünden) Görev 2 ve 7-8'de eklenen testler bunu fazlasıyla karşılar; yine de tam paket sayısı Görev 8 ve 10'da doğrulanır.
