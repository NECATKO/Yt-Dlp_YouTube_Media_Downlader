import json
import os
import shutil
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_NAME = "yt-dlp-downloader"
CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


# -----------------------------
# Error logging / failure UX
# -----------------------------
def _append_log(log_path: Path | None, text: str) -> None:
    """
    Best-effort logging. Never raises.
    """
    try:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write(text)
    except Exception:
        # logging must never crash the app
        pass


def log_error(
    log_path: Path | None, title: str, ex: BaseException | None = None
) -> None:
    """
    Prints a readable error and writes full details (including traceback) to log file.
    """
    stamp = datetime.now().isoformat(timespec="seconds")
    header = f"\n[ERROR {stamp}] {title}\n"
    print(header.strip())

    details = header
    if ex is not None:
        details += f"Exception: {type(ex).__name__}: {ex}\n"
        details += "Traceback:\n"
        details += "".join(traceback.format_exception(type(ex), ex, ex.__traceback__))
    details += "\n"

    _append_log(log_path, details)


def prompt_exit_on_failure() -> bool:
    """
    Returns True if user wants to exit.
    """
    ans = input("\nHata oluştu. Programdan çıkmak ister misin? (E/H): ").strip().lower()
    return ans in ("e", "evet", "y", "yes")


# -----------------------------
# UI Helpers (sadece rakamla seçim)
# -----------------------------
def pick(prompt: str, options: list[str]) -> int:
    while True:
        print("\n" + prompt)
        for i, opt in enumerate(options, start=1):
            print(f"  {i}) {opt}")
        ans = input("Seçim (sadece sayı): ").strip()
        if ans.isdigit():
            n = int(ans)
            if 1 <= n <= len(options):
                return n
        print("Geçersiz seçim. Lütfen sadece listedeki sayılardan birini gir.")


def ask_text(prompt: str) -> str:
    return input(prompt).strip()


def normalize_user_path(s: str) -> Path:
    expanded = os.path.expandvars(s)
    return Path(expanded).expanduser()


# -----------------------------
# Config (config.json)
# -----------------------------
def default_dirs() -> tuple[Path, Path]:
    return Path.home() / "Videos", Path.home() / "Music"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        print("UYARI: config.json okunamadı/bozuk. Yeniden oluşturulacak.")
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def delete_config() -> None:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


def ensure_dirs_interactive(existing_cfg: dict) -> tuple[Path, Path, dict]:
    """
    config.json yoksa/eksikse kullanıcıdan yolları ister ve kaydeder.
    """
    def_videos, def_music = default_dirs()

    # config'ten çek
    v_raw = (existing_cfg.get("videos_dir") or "").strip()
    m_raw = (existing_cfg.get("music_dir") or "").strip()

    videos_dir = normalize_user_path(v_raw) if v_raw else def_videos
    music_dir = normalize_user_path(m_raw) if m_raw else def_music

    # Eğer config doluysa direkt kullanma seçeneği verelim
    if v_raw or m_raw:
        choice = pick(
            "Kayıt klasörleri bulundu. Ne yapmak istiyorsun?",
            [
                f"Kaydedilmiş ayarları kullan (Videos: {videos_dir} | Music: {music_dir})",
                "Klasörleri değiştir",
                "Ayarları sıfırla (config.json sil)",
            ],
        )
        if choice == 1:
            videos_dir.mkdir(parents=True, exist_ok=True)
            music_dir.mkdir(parents=True, exist_ok=True)
            return videos_dir, music_dir, existing_cfg
        if choice == 3:
            delete_config()
            existing_cfg = {}
            v_raw = ""
            m_raw = ""
            videos_dir, music_dir = def_videos, def_music
            print("✅ Ayarlar sıfırlandı (config.json silindi).")

    # Buraya geldiysek: ya config yoktu ya da kullanıcı “değiştir” dedi.
    choice2 = pick(
        "Kayıt klasörlerini ayarla:",
        [
            f"Varsayılanları kullan (Videos: {def_videos} | Music: {def_music})",
            "Sadece Videos klasörünü değiştir",
            "Sadece Music klasörünü değiştir",
            "İkisini de değiştir",
        ],
    )

    def ask_path(label: str, default: Path) -> Path:
        print(f"\n{label} için klasör yolu gir (boş Enter = varsayılan):")
        print(f"Varsayılan: {default}")
        s = ask_text("Yol: ")
        if not s:
            return default
        return normalize_user_path(s)

    if choice2 == 1:
        videos_dir, music_dir = def_videos, def_music
    elif choice2 == 2:
        videos_dir = ask_path("VIDEOS", def_videos)
        music_dir = music_dir if m_raw else def_music
    elif choice2 == 3:
        music_dir = ask_path("MUSIC", def_music)
        videos_dir = videos_dir if v_raw else def_videos
    else:
        videos_dir = ask_path("VIDEOS", def_videos)
        music_dir = ask_path("MUSIC", def_music)

    videos_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)

    new_cfg = {
        "app": APP_NAME,
        "videos_dir": str(videos_dir),
        "music_dir": str(music_dir),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_config(new_cfg)

    print("\n✅ Ayarlar kaydedildi:")
    print(f"  Videos: {videos_dir}")
    print(f"  Music : {music_dir}")
    print(f"  Config: {CONFIG_FILE}\n")

    return videos_dir, music_dir, new_cfg


# -----------------------------
# System Helpers
# -----------------------------
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def is_playlist_url(url: str) -> bool:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return ("list" in qs) or parsed.path.startswith("/playlist")


def get_playlist_id(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return qs.get("list", ["unknown_playlist"])[0]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# -----------------------------
# Command runners (log + konsola akıtma)
# -----------------------------
def run_capture(cmd: list[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, shell=False, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    except KeyboardInterrupt:
        return 130, "", "Interrupted by user"
    except Exception as ex:
        # Keep behavior predictable for callers; provide something useful in stderr.
        return 1, "", f"{type(ex).__name__}: {ex}"


def run_cmd_tee(cmd: list[str], log_path: Path) -> int:
    print("\n=== ÇALIŞTIRILIYOR ===")
    print(" ".join(cmd))
    print("======================\n")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] CMD: {' '.join(cmd)}\n"
            )
            f.write("=" * 80 + "\n")

            p = subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert p.stdout is not None
            for line in p.stdout:
                print(line, end="")
                f.write(line)

            rc = p.wait()
            print(f"\n>>> Komut bitti. returncode = {rc}\n")
            f.write(f"\n>>> returncode = {rc}\n")
            return rc

    except KeyboardInterrupt:
        print("\n>>> İşlem kullanıcı tarafından durduruldu (Ctrl+C).")
        _append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] Interrupted by user (Ctrl+C)\n",
        )
        return 130
    except Exception as ex:
        log_error(log_path, "Komut çalıştırma sırasında beklenmeyen hata", ex)
        return 1


# -----------------------------
# Archive & playlist mapping
# -----------------------------
def read_archive_ids(archive_path: Path) -> set[str]:
    if not archive_path.exists():
        return set()

    ids: set[str] = set()
    for line in archive_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        ids.add(parts[-1])
    return ids


def fetch_playlist_entries(url: str, js_args: list[str]) -> list[dict]:
    cmd = ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", url] + js_args
    rc, out, err = run_capture(cmd)
    if rc != 0 or not out.strip():
        raise RuntimeError(f"Playlist JSON alınamadı.\nreturncode={rc}\nstderr:\n{err}")

    data = json.loads(out)
    entries = data.get("entries") or []
    result: list[dict] = []

    idx = 0
    for e in entries:
        idx += 1
        vid = e.get("id") or e.get("url")
        title = e.get("title") or ""
        result.append(
            {
                "playlist_index": idx,
                "id": vid,
                "title": title,
                "watch_url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            }
        )
    return result


# -----------------------------
# Skip reason probe
# -----------------------------
def probe_skip_reason(video_url: str, js_args: list[str]) -> str:
    cmd = ["yt-dlp", "-J", "--no-playlist", "--skip-download", video_url] + js_args
    rc, out, err = run_capture(cmd)

    if rc == 130:
        return "Kullanıcı tarafından durduruldu (Ctrl+C)"

    if rc != 0 or not out.strip():
        e = (err or "").lower()

        if "private video" in e or "this video is private" in e:
            return "Private video"
        if "members-only" in e or "join this channel" in e:
            return "Üyelere özel (members-only)"
        if "age-restricted" in e or "age restricted" in e or "confirm your age" in e:
            return "Yaş doğrulaması gerekiyor (age-restricted)"
        if "not available in your country" in e or (
            "country" in e and "available" in e
        ):
            return "Bölge kısıtı (region blocked)"
        if "video unavailable" in e or "unavailable" in e:
            return "Video unavailable / kaldırılmış"
        if "copyright" in e:
            return "Telif kısıtı / copyright nedeniyle erişilemiyor"
        if "sign in" in e or "login" in e:
            return "Oturum/yaş doğrulaması gerekiyor (sign-in required)"
        if "requested format is not available" in e:
            return "İstenen format bulunamadı (format listesi eksik / JS challenge olabilir)"
        if (
            "unable to extract" in e
            or "nsig" in e
            or "signature" in e
            or "challenge" in e
        ):
            return "YouTube JS challenge/çözümleme sorunu – formatlar eksik geliyor olabilir"
        if "timed out" in e or "timeout" in e:
            return "Bağlantı/timeout"
        if "429" in e or "too many requests" in e:
            return "Çok fazla istek (429) – rate limit"
        return f"Bilinmeyen hata: {(err or '').strip()[:240]}"

    try:
        data = json.loads(out)
        formats = data.get("formats") or []
        has_video = any((f.get("vcodec") not in (None, "none")) for f in formats)
        if not has_video:
            return "Video track yok (audio-only)"
        return "Format mevcut ama indirme/postprocess başarısız (ağ/ffmpeg/thumbnail/metadata)"
    except Exception:
        return "JSON parse edilemedi (format tespiti yapılamadı)"


# -----------------------------
# Main
# -----------------------------
def main():
    log_path: Path | None = None
    try:
        # 0) config: yolları al / yükle
        cfg = load_config()
        videos_base, music_base, _cfg = ensure_dirs_interactive(cfg)

        # 1) URL
        url = ask_text("Video veya oynatma listesi URL'sini girin: ")
        if not url:
            print("Boş URL girdin, çıkılıyor.")
            return

        # 2) Mod seçimi
        mode_choice = pick("Ne indirmek istiyorsun?", ["Video (MP4)", "Ses (MP3)"])
        mode = "mp4" if mode_choice == 1 else "mp3"

        # 3) Araç kontrolleri (kurulum scripti bunu zaten halledecek ama yine de kontrol)
        if not yt_dlp_available():
            print(
                "HATA: 'yt-dlp' bulunamadı. Kurulum scriptini (install.ps1) çalıştır."
            )
            return

        if not ffmpeg_available():
            print(
                "\nUYARI: ffmpeg bulunamadı.\n"
                "- MP3 modunda dönüştürme genelde çalışmaz.\n"
                "- MP4 modunda birleştirme/recode ve thumbnail işlemleri hata verebilir.\n"
                "Çözüm: install.ps1 ile kur veya ffmpeg kurup PATH'e ekle.\n"
            )

        # 4) Playlist / tek video netleştirme
        playlist_like = is_playlist_url(url)
        force_single = False
        if playlist_like:
            what = pick(
                "URL playlist içeriyor gibi görünüyor. Ne yapmak istiyorsun?",
                [
                    "Playlist'i indir (tüm liste)",
                    "Sadece bu videoyu indir (playlist'i yok say)",
                ],
            )
            if what == 2:
                force_single = True

        is_playlist = playlist_like and (not force_single)
        playlist_id = get_playlist_id(url) if is_playlist else None

        # 5) MP4 profili
        mp4_profile = None
        remux_container = None
        if mode == "mp4":
            mp4_profile = pick(
                "MP4 davranışı (profil) seç:",
                [
                    "Uyumluluk: Her şeyi MP4 yap (uygunsa kayıpsız, değilse RECODE)",
                    "Kalite: Yeniden encode YOK (RECODE yok). Uygunsa remux; değilse container kalabilir",
                ],
            )
            if mp4_profile == 2:
                remux_container = pick(
                    "Kalite profilinde container tercihi:",
                    [
                        "Güvenli (önerilen): MKV",
                        "MP4 dene (sadece remux; codec uymazsa başarısız olabilir)",
                    ],
                )

        # 6) Dizinler & şablonlar
        # Programin bulundugu klasor
        app_dir = Path(__file__).resolve().parent

        # Archive dosyalari (portable)
        archive_base = app_dir / "archives"
        archive_base.mkdir(parents=True, exist_ok=True)

        # Log dosyalari (portable)
        logs_base = app_dir / "logs"
        logs_base.mkdir(parents=True, exist_ok=True)

        if mode == "mp4":
            if is_playlist:
                base_dir = videos_base / "yt-dlp"
                output_template = str(
                    base_dir
                    / "%(playlist_title)s"
                    / "%(playlist_index)03d - %(title)s.%(ext)s"
                )
                archive_path = archive_base / f"playlist_{playlist_id}_mp4.txt"
            else:
                base_dir = videos_base / "İndirilen Videolar"
                output_template = str(base_dir / "%(title)s.%(ext)s")
                archive_path = archive_base / "single_videos_mp4.txt"
        else:
            if is_playlist:
                base_dir = music_base / "yt-dlp"
                output_template = str(
                    base_dir
                    / "%(playlist_title)s"
                    / "%(playlist_index)03d - %(title)s.%(ext)s"
                )
                archive_path = archive_base / f"playlist_{playlist_id}_mp3.txt"
            else:
                base_dir = music_base / "İndirilen Müzikler"
                output_template = str(base_dir / "%(title)s.%(ext)s")
                archive_path = archive_base / "single_audios_mp3.txt"

        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = (
            logs_base
            / f"yt-dlp_{mode}_{'playlist' if is_playlist else 'single'}_{now_stamp()}.log"
        )

        print("\n------------------------------")
        print(f"Mod: {mode}")
        print(f"Playlist mi?: {is_playlist}")
        print(f"Çıkış klasörü: {base_dir}")
        print(f"Output template: {output_template}")
        print(f"Arşiv dosyası: {archive_path}")
        print(f"Log dosyası: {log_path}")
        if mode == "mp4":
            print(f"MP4 profil: {'Uyumluluk' if mp4_profile == 1 else 'Kalite'}")
        print("------------------------------\n")

        _append_log(
            log_path,
            (
                "\n" + "=" * 80 + "\n"
                f"[{datetime.now().isoformat(timespec='seconds')}] START\n"
                f"mode={mode} is_playlist={is_playlist} url={url}\n"
                f"base_dir={base_dir}\n"
                f"output_template={output_template}\n"
                f"archive_path={archive_path}\n"
                f"ffmpeg_available={ffmpeg_available()} yt_dlp_available={yt_dlp_available()}\n"
                + "=" * 80
                + "\n"
            ),
        )

        # 7) yt-dlp argümanları
        playlist_flag = "--yes-playlist" if is_playlist else "--no-playlist"
        js_args = ["--js-runtime", "deno", "--remote-components", "ejs:github"]

        stability_args = [
            "--continue",
            "--ignore-errors",
            "--retries",
            "infinite",
            "--fragment-retries",
            "infinite",
            "--concurrent-fragments",
            "4",
            "--sleep-interval",
            "1",
            "--max-sleep-interval",
            "3",
        ]

        common_args = [
            "-o",
            output_template,
            "--download-archive",
            str(archive_path),
            "--progress",
            playlist_flag,
            url,
        ]

        post_args = ["--embed-metadata", "--add-metadata"]
        if mode == "mp3":
            post_args += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]
        else:
            post_args += ["--embed-thumbnail"]

        # 8) Playlist mapping (skip raporu)
        entries: list[dict] = []
        if is_playlist:
            try:
                entries = fetch_playlist_entries(url, js_args)
            except Exception as ex:
                log_error(
                    log_path,
                    "Playlist listesi alınamadı (skip raporu sınırlı olabilir)",
                    ex,
                )
                print(
                    f"Playlist listesi alınamadı, skip raporu sınırlı olabilir.\n{ex}\n"
                )
                if prompt_exit_on_failure():
                    return

        # 9) DOWNLOAD
        final_rc: int | None = None

        if mode == "mp4":
            if mp4_profile == 1:
                cmd_stage1 = (
                    [
                        "yt-dlp",
                        "-f",
                        "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]",
                        "--merge-output-format",
                        "mp4",
                    ]
                    + stability_args
                    + js_args
                    + post_args
                    + common_args
                )
                print("### 1. AŞAMA (Uyumluluk): avc1+mp4a varsa kayıpsız MP4...")
                rc1 = run_cmd_tee(cmd_stage1, log_path)
                final_rc = rc1
                if rc1 == 130:
                    return
                if rc1 != 0 and prompt_exit_on_failure():
                    return

                cmd_stage2 = (
                    ["yt-dlp", "-f", "bv*+ba/b", "--recode-video", "mp4"]
                    + stability_args
                    + js_args
                    + post_args
                    + common_args
                )
                print(
                    "### 2. AŞAMA (Uyumluluk): Kalanlar indiriliyor ve MP4'e RECODE ediliyor..."
                )
                rc2 = run_cmd_tee(cmd_stage2, log_path)
                final_rc = rc2
                if rc2 == 130:
                    return
                if rc2 != 0 and prompt_exit_on_failure():
                    return

            else:
                if remux_container == 1:
                    cmd_quality = (
                        ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mkv"]
                        + stability_args
                        + js_args
                        + post_args
                        + common_args
                    )
                    print("### KALİTE: RECODE yok. Çıkış container: MKV")
                    rc = run_cmd_tee(cmd_quality, log_path)
                    final_rc = rc
                    if rc == 130:
                        return
                    if rc != 0 and prompt_exit_on_failure():
                        return
                else:
                    cmd_quality_mp4 = (
                        [
                            "yt-dlp",
                            "-f",
                            "bv*+ba/b",
                            "--merge-output-format",
                            "mp4",
                            "--remux-video",
                            "mp4",
                        ]
                        + stability_args
                        + js_args
                        + post_args
                        + common_args
                    )
                    print("### KALİTE: RECODE yok. MP4 remux denenecek.")
                    rc = run_cmd_tee(cmd_quality_mp4, log_path)
                    final_rc = rc
                    if rc == 130:
                        return
                    if rc != 0 and prompt_exit_on_failure():
                        return
        else:
            cmd_audio = (
                [
                    "yt-dlp",
                    "-f",
                    "bestaudio/best",
                    "--extract-audio",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    "0",
                ]
                + stability_args
                + js_args
                + post_args
                + common_args
            )
            print("### MP3: En iyi ses indiriliyor ve MP3'e dönüştürülüyor...")
            rc = run_cmd_tee(cmd_audio, log_path)
            final_rc = rc
            if rc == 130:
                return
            if rc != 0 and prompt_exit_on_failure():
                return

        _append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] DOWNLOAD_FINISHED returncode={final_rc}\n",
        )

        # 10) Skip report
        if is_playlist and entries:
            downloaded_ids = read_archive_ids(Path(archive_path))
            skipped = [
                e for e in entries if e.get("id") and e["id"] not in downloaded_ids
            ]

            if skipped:
                print("\n==============================")
                print("SKIP EDİLENLER (indirilemeyenler)")
                print("==============================")

                for e in skipped:
                    idx = e["playlist_index"]
                    vid = e["id"]
                    title = e.get("title", "")
                    vurl = e.get("watch_url", "")
                    reason = probe_skip_reason(vurl, js_args)

                    print(f"- #{idx:03d}  ({vid})")
                    print(f"  Başlık: {title}")
                    print(f"  Neden:  {reason}\n")
            else:
                print(
                    "\n✅ Playlist'teki tüm öğeler arşive yazılmış görünüyor (skip yok)."
                )

        print("\nTüm işlemler tamamlandı. 🎉")
        print(f"Log: {log_path}")
        print(f"Config: {CONFIG_FILE}")

    except KeyboardInterrupt:
        if log_path:
            _append_log(
                log_path,
                f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] Interrupted by user (Ctrl+C) at top-level\n",
            )
        print("\n>>> İşlem kullanıcı tarafından durduruldu (Ctrl+C).")
        return
    except Exception as ex:
        log_error(log_path, "Beklenmeyen hata (top-level)", ex)
        if log_path:
            print(f"Detaylar log dosyasına yazıldı: {log_path}")
        if prompt_exit_on_failure():
            return


if __name__ == "__main__":
    main()
