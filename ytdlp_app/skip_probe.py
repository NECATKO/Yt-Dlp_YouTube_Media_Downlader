from __future__ import annotations

import json

from .models import CaptureRunner


def probe_skip_reason(video_url: str, js_args: list[str], runner: CaptureRunner) -> str:
    cmd = ["yt-dlp", "-J", "--no-playlist", "--skip-download", video_url] + js_args
    rc, out, err = runner(cmd)

    if rc == 130:
        return "Kullanc tarafndan durduruldu (Ctrl+C)"

    if rc != 0 or not out.strip():
        e = (err or "").lower()

        if "private video" in e or "this video is private" in e:
            return "Private video"
        if "members-only" in e or "join this channel" in e:
            return "šyelere ”zel (members-only)"
        if "age-restricted" in e or "age restricted" in e or "confirm your age" in e:
            return "YaŸ do§rulamas gerekiyor (age-restricted)"
        if "not available in your country" in e or (
            "country" in e and "available" in e
        ):
            return "B”lge kst (region blocked)"
        if "video unavailable" in e or "unavailable" in e:
            return "Video unavailable / kaldrlmŸ"
        if "copyright" in e:
            return "Telif kst / copyright nedeniyle eriŸilemiyor"
        if "sign in" in e or "login" in e:
            return "Oturum/yaŸ do§rulamas gerekiyor (sign-in required)"
        if "requested format is not available" in e:
            return "˜stenen format bulunamad (format listesi eksik / JS challenge olabilir)"
        if (
            "unable to extract" in e
            or "nsig" in e
            or "signature" in e
            or "challenge" in e
        ):
            return "YouTube JS challenge/‡”zmleme sorunu - formatlar eksik geliyor olabilir"
        if "timed out" in e or "timeout" in e:
            return "Ba§lant/timeout"
        if "429" in e or "too many requests" in e:
            return "€ok fazla istek (429) - rate limit"
        return f"Bilinmeyen hata: {(err or '').strip()[:240]}"

    try:
        data = json.loads(out)
        formats = data.get("formats") or []
        has_video = any((f.get("vcodec") not in (None, "none")) for f in formats)
        if not has_video:
            return "Video track yok (audio-only)"
        return "Format mevcut ama indirme/postprocess baŸarsz (a§/ffmpeg/thumbnail/metadata)"
    except Exception:
        return "JSON parse edilemedi (format tespiti yaplamad)"
