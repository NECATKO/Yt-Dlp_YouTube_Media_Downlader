"""System dependency checks for ytdlp_app.

This module provides functions to check for required external tools
like ffmpeg, yt-dlp, and Deno.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system PATH.

    ffmpeg is required for video/audio conversion and merging.

    Returns:
        True if ffmpeg is found, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


@lru_cache(maxsize=1)
def ytdlp_command() -> tuple[str, ...] | None:
    """Return how to launch yt-dlp, or None if it cannot be found.

    The yt-dlp installed next to this app's own interpreter wins: that is the
    one in the portable runtime (or the venv), and it is not on PATH, because
    the launchers start that interpreter directly instead of activating it.
    Running it as a module also avoids console-script wrappers, which record
    absolute paths and break when the folder is moved.
    """
    if importlib.util.find_spec("yt_dlp") is not None:
        return (sys.executable, "-m", "yt_dlp")
    found = shutil.which("yt-dlp")
    return (found,) if found else None


def yt_dlp_available() -> bool:
    """Check if yt-dlp can be launched.

    yt-dlp is the core download tool that this application wraps.

    Returns:
        True if yt-dlp is found, False otherwise.
    """
    return ytdlp_command() is not None


@lru_cache(maxsize=1)
def deno_available() -> bool:
    """Check if the Deno runtime is available on the system PATH.

    Deno is used to handle JavaScript challenges that some sites
    (especially YouTube) use for bot protection.

    Returns:
        True if Deno is found, False otherwise.
    """
    return shutil.which("deno") is not None


def refresh_tool_cache() -> None:
    """Forget cached tool lookups.

    The checks above are cached so a single download cycle does not re-scan
    PATH repeatedly. That cache must not outlive the cycle: the app tells users
    to install a missing tool and keep going, and it would otherwise keep
    reporting the tool as missing for the rest of the session.
    """
    ffmpeg_available.cache_clear()
    ytdlp_command.cache_clear()
    deno_available.cache_clear()
