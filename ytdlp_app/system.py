"""System dependency checks for ytdlp_app.

This module provides functions to check for required external tools
like ffmpeg, yt-dlp, and Deno.
"""

from __future__ import annotations

import shutil


def ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system PATH.

    ffmpeg is required for video/audio conversion and merging.

    Returns:
        True if ffmpeg is found, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


def yt_dlp_available() -> bool:
    """Check if yt-dlp is available on the system PATH.

    yt-dlp is the core download tool that this application wraps.

    Returns:
        True if yt-dlp is found, False otherwise.
    """
    return shutil.which("yt-dlp") is not None


def deno_available() -> bool:
    """Check if the Deno runtime is available on the system PATH.

    Deno is used to handle JavaScript challenges that some sites
    (especially YouTube) use for bot protection.

    Returns:
        True if Deno is found, False otherwise.
    """
    return shutil.which("deno") is not None
