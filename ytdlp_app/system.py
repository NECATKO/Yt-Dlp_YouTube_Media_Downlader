from __future__ import annotations

import shutil


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def deno_available() -> bool:
    """
    Detect whether the Deno runtime is on PATH.
    """
    return shutil.which("deno") is not None
