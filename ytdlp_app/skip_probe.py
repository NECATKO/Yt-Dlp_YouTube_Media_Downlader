from __future__ import annotations

import json

from .models import CaptureRunner


def probe_skip_reason(video_url: str, js_args: list[str], runner: CaptureRunner) -> str:
    """
    Try to explain why an item was skipped by asking yt-dlp for metadata only.
    """
    cmd = ["yt-dlp", "-J", "--no-playlist", "--skip-download", video_url] + js_args
    rc, out, err = runner(cmd)

    if rc == 130:
        return "Interrupted by user (Ctrl+C)"

    if rc != 0 or not out.strip():
        e = (err or "").lower()

        if "private video" in e or "this video is private" in e:
            return "Private video"
        if "members-only" in e or "join this channel" in e:
            return "Members-only (channel subscription required)"
        if "age-restricted" in e or "age restricted" in e or "confirm your age" in e:
            return "Age verification required (sign in)"
        if "not available in your country" in e or (
            "country" in e and "available" in e
        ):
            return "Region blocked"
        if "video unavailable" in e or "unavailable" in e:
            return "Video unavailable or removed"
        if "copyright" in e:
            return "Copyright blocked"
        if "sign in" in e or "login" in e:
            return "Sign-in required"
        if "requested format is not available" in e:
            return "Requested format not available (format list missing / JS challenge)"
        if (
            "unable to extract" in e
            or "nsig" in e
            or "signature" in e
            or "challenge" in e
        ):
            return "YouTube JS challenge or signature extraction issue"
        if "timed out" in e or "timeout" in e:
            return "Connection timed out"
        if "429" in e or "too many requests" in e:
            return "Rate limited (HTTP 429)"
        return f"Unknown error: {(err or '').strip()[:240]}"

    try:
        data = json.loads(out)
        formats = data.get("formats") or []
        has_video = any((f.get("vcodec") not in (None, "none")) for f in formats)
        if not has_video:
            return "No video track (audio-only entry)"
        return (
            "Formats available; download or post-processing failed "
            "(audio/ffmpeg/thumbnail/metadata)"
        )
    except Exception:
        return "Could not parse JSON (format detection failed)"
