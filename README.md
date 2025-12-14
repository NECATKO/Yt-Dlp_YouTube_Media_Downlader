# yt-dlp Downloader (portable)

Small Windows console helper around yt-dlp/ffmpeg. Prompts for folders on first run, lets you pick MP4/MP3, handles playlists, keeps archives, and writes logs.

## How it works
- Launch `Run.bat`. First run installs Python 3.10+, yt-dlp inside `.venv`, ffmpeg, and Deno through winget.
- You are asked once for base download folders (defaults: `Videos` and `Music`). Choices are saved to `config.json`.
- Each session: enter a URL, choose MP4 or MP3, decide whether a playlist URL should grab the whole list or only that video, then pick the MP4 profile when relevant.
- yt-dlp runs with resume/retry flags; archive files prevent duplicates; a log captures the full command output.
- When a playlist is used, skipped items are probed and reasons are printed (private, region blocked, missing formats, etc.).
- After finishing, you can immediately start another download from the same session.

## Output layout
- MP4 playlist: `<Videos>/yt-dlp/<playlist_title>/<index> - <title>.mp4`, archive `archives/playlist_<playlist_id>_mp4.txt`
- MP4 single: `<Videos>/Downloaded Videos/<title>.mp4`, archive `archives/single_videos_mp4.txt`
- MP3 playlist: `<Music>/yt-dlp/<playlist_title>/<index> - <title>.mp3`, archive `archives/playlist_<playlist_id>_mp3.txt`
- MP3 single: `<Music>/Downloaded Music/<title>.mp3`, archive `archives/single_audios_mp3.txt`
- Logs: `logs/yt-dlp_<mode>_<playlist|single>_<timestamp>.log`

## MP4 profiles
- Compatibility: try avc1/mp4a lossless merges first, then recode remaining items to MP4.
- Quality: no recode; keep best streams and mux. Container choice: safe MKV, or MP4 remux (may fail if codecs are incompatible).
- MP3 mode always downloads bestaudio, converts to MP3, and embeds metadata/thumbnail.

## Config and state
- `config.json` stores `videos_dir`, `music_dir`, `app`, `saved_at`. Delete it to be prompted again.
- Archive text files in `archives/` drive `--download-archive`; removing one forces re-download for that scope.
- Logs in `logs/` mirror the console output for troubleshooting.

## Files in this folder
- `Run.bat`: one-click start plus silent `update.ps1` check (preserves `.venv`, `config.json`, `logs`, `archives`).
- `install.ps1`: installs dependencies and creates `.venv` with yt-dlp.
- `downloader.py`: entry point that calls the app in `ytdlp_app/`.
- `ytdlp_app/`: Python modules for prompts, yt-dlp command builders, playlist probing, and logging utilities.

## Troubleshooting
- If install fails, run `Run.bat` as Administrator and ensure winget/internet access.
- If yt-dlp or ffmpeg is not found, rerun `install.ps1` or open a new terminal after installation.
- Delete `config.json` to change the download folders on next launch.

---

## yt-dlp Downloader (taşınabilir) — Türkçe

Küçük Windows konsol yardımcısı: yt-dlp/ffmpeg üzerinde çalışır. İlk açılışta klasör sorar, MP4/MP3 seçtirir, playlist veya tek video indirir, arşiv ve log tutar.

### Nasıl çalışır
- `Run.bat` ile başlat. İlk çalıştırmada winget ile Python 3.10+, `.venv` içinde yt-dlp, ffmpeg ve Deno kurulur.
- İlk seferde video/müzik klasörlerini sorar (varsayılan: `Videolar`, `Müzik`). Tercihler `config.json` içine kaydedilir.
- Her oturumda: URL gir, MP4/MP3 seç, playlist URL’si için tüm liste mi tek video mu karar ver, MP4 ise profil seç.
- yt-dlp devam/tekrar dene bayraklarıyla çalışır; arşiv dosyaları tekrar indirmeyi engeller; konsol çıktısı log’a yazılır.
- Playlist indirirken atlananlar için sebep yoklama (özel, bölge kısıtı, format eksik vb.) yapılır ve ekrana yazılır.
- İndirme bitince aynı oturumda hemen yeni URL indirebilirsin.

### Çıktı düzeni
- MP4 playlist: `<Videos>/yt-dlp/<playlist_title>/<index> - <title>.mp4`, arşiv `archives/playlist_<playlist_id>_mp4.txt`
- MP4 tek video: `<Videos>/Downloaded Videos/<title>.mp4`, arşiv `archives/single_videos_mp4.txt`
- MP3 playlist: `<Music>/yt-dlp/<playlist_title>/<index> - <title>.mp3`, arşiv `archives/playlist_<playlist_id>_mp3.txt`
- MP3 tek parça: `<Music>/Downloaded Music/<title>.mp3`, arşiv `archives/single_audios_mp3.txt`
- Loglar: `logs/yt-dlp_<mode>_<playlist|single>_<timestamp>.log`

### MP4 profilleri
- Uyumluluk: önce avc1/mp4a kayıpsız birleştirme dener, kalanları MP4’e yeniden kodlar.
- Kalite: yeniden kodlama yok; en iyi akışları korur ve mux eder. Kapsayıcı seçimi: güvenli MKV veya MP4 remux (codec uyumsuzsa hata verebilir).
- MP3 modu en iyi sesi indirir, MP3’e çevirir, metadata/thumbnail gömer.

### Ayarlar ve durum
- `config.json` içinde `videos_dir`, `music_dir`, `app`, `saved_at` saklanır. Silersen klasör sorusu yeniden çıkar.
- `archives/` içindeki metin dosyaları `--download-archive` için kullanılır; silersen ilgili kapsam yeniden indirilir.
- `logs/` konsol çıktısını sorun gidermek için saklar.

### Bu klasörde neler var
- `Run.bat`: tek tık başlatma, sessiz `update.ps1` kontrolü (`.venv`, `config.json`, `logs`, `archives` korunur).
- `install.ps1`: bağımlılıkları kurar, yt-dlp içeren `.venv` oluşturur.
- `downloader.py`: `ytdlp_app/` içindeki uygulamayı çağıran giriş noktası.
- `ytdlp_app/`: prompt’lar, yt-dlp komut inşası, playlist yoklama ve log yardımcıları.

### Sorun giderme
- Kurulum hata verirse `Run.bat`’i Yönetici olarak çalıştır; winget ve internet erişimini doğrula.
- yt-dlp veya ffmpeg bulunamazsa `install.ps1`’i tekrar çalıştır veya yeni bir terminal aç.
- İndirme klasörlerini değiştirmek için `config.json` dosyasını sil ve programı yeniden başlat.
