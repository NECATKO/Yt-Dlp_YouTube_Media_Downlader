"""Playlist detection and parsing utilities for ytdlp_app.

This module provides functions for detecting playlist URLs, extracting
playlist IDs, reading download archives, and fetching playlist entries.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from .exceptions import PlaylistError
from .i18n import t
from .models import CaptureRunner, PlaylistEntry

if TYPE_CHECKING:
    from pathlib import Path

# Regex pattern to detect YouTube channel URL paths
_CHANNEL_PATH_PATTERN = re.compile(r"^/(channel|c|user|@)")


def is_playlist_url(url: str) -> bool:
    """Check if the URL is a playlist or a channel (treated as playlist)."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # Standard playlist param
    if "list" in qs:
        return True

    path = parsed.path

    # Explicit /playlist path
    if path.startswith("/playlist"):
        return True

    # Channel patterns: /channel/, /c/, /user/, /@username
    return bool(_CHANNEL_PATH_PATTERN.match(path))


def get_playlist_id(url: str) -> str:
    """Extract a unique identifier for the playlist or channel."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # 1. Try standard 'list' param for playlists
    if "list" in qs:
        return qs["list"][0]

    # 2. For channel URLs, use the last path segment (e.g., @ChannelName, UCxxxxx)
    path = parsed.path.rstrip("/")
    if path:
        segment = path.split("/")[-1]
        # Sanitize: remove @ prefix if present for cleaner archive filenames
        return segment.lstrip("@") if segment.startswith("@") else segment

    return "unknown_playlist"


def read_archive_ids(archive_path: Path) -> set[str]:
    if not archive_path.exists():
        return set()

    ids: set[str] = set()
    for raw_line in archive_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        ids.add(parts[-1])
    return ids


def fetch_playlist_entries(
    url: str, js_args: list[str], runner: CaptureRunner
) -> list[PlaylistEntry]:
    cmd = ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", url, *js_args]
    rc, out, err = runner(cmd)
    if rc != 0 or not out.strip():
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))

    data = json.loads(out)
    entries = data.get("entries") or []
    result: list[PlaylistEntry] = []

    for idx, e in enumerate(entries, start=1):
        vid = e.get("id") or e.get("url")
        title = e.get("title") or ""
        result.append(
            PlaylistEntry(
                playlist_index=idx,
                id=vid or "",
                title=title,
                watch_url=f"https://www.youtube.com/watch?v={vid}" if vid else "",
            )
        )
    return result
