"""Explain why a playlist item was skipped.

The reasons are user-facing, so every branch returns a translated string.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .i18n import t

if TYPE_CHECKING:
    from .models import CaptureRunner

#: How much of an unrecognized stderr to quote back to the user.
_DETAIL_LIMIT = 240


def probe_skip_reason(video_url: str, js_args: list[str], runner: CaptureRunner) -> str:
    """
    Try to explain why an item was skipped by asking yt-dlp for metadata only.
    """
    cmd = ["yt-dlp", "-J", "--no-playlist", "--skip-download", video_url, *js_args]
    rc, out, err = runner(cmd)

    if rc == 130:
        return t("skip_reason_interrupted")

    if rc != 0 or not out.strip():
        e = (err or "").lower()

        if "private video" in e or "this video is private" in e:
            return t("skip_reason_private")
        if "members-only" in e or "join this channel" in e:
            return t("skip_reason_members_only")
        if "age-restricted" in e or "age restricted" in e or "confirm your age" in e:
            return t("skip_reason_age_restricted")
        if "not available in your country" in e or ("country" in e and "available" in e):
            return t("skip_reason_region_blocked")
        if "video unavailable" in e or "unavailable" in e:
            return t("skip_reason_unavailable")
        if "copyright" in e:
            return t("skip_reason_copyright")
        if "sign in" in e or "login" in e:
            return t("skip_reason_sign_in")
        if "requested format is not available" in e:
            return t("skip_reason_format")
        if "unable to extract" in e or "nsig" in e or "signature" in e or "challenge" in e:
            return t("skip_reason_js_challenge")
        if "timed out" in e or "timeout" in e:
            return t("skip_reason_timeout")
        if "429" in e or "too many requests" in e:
            return t("skip_reason_rate_limited")
        return t("skip_reason_unknown", detail=(err or "").strip()[:_DETAIL_LIMIT])

    try:
        data = json.loads(out)
        formats = data.get("formats") or []
        has_video = any((f.get("vcodec") not in (None, "none")) for f in formats)
        if not has_video:
            return t("skip_reason_no_video_track")
        return t("skip_reason_postprocess")
    except Exception:
        return t("skip_reason_json_parse")
