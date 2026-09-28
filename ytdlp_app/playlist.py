"""Playlist detection and parsing utilities for ytdlp_app.

This module provides functions for detecting playlist URLs, extracting
playlist IDs, reading download archives, and fetching playlist entries.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from .exceptions import PlaylistError
from .i18n import t
from .models import CaptureRunner, PlaylistEntry

if TYPE_CHECKING:
    from pathlib import Path

# Regex pattern to detect YouTube channel URL paths
_CHANNEL_PATH_PATTERN = re.compile(r"^/(channel|c|user|@)")

# A whole channel, or one of its listing tabs. A bare channel URL makes yt-dlp
# return the Videos, Shorts and Live tabs as nested playlists. "/live" is left
# out on purpose: it redirects to the channel's current stream, a single video.
_CHANNEL_URL_PATTERN = re.compile(
    r"^/(?:channel/[^/]+|c/[^/]+|user/[^/]+|@[^/]+)"
    r"(?:/(?:videos|shorts|streams|featured|podcasts|releases))?/?$",
    re.IGNORECASE,
)

# YouTube channel ids: "UC" followed by 22 URL-safe base64 characters.
_CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")

# Anything outside this set is replaced when an id is used in a file name.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^\w.-]")


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


def is_channel_url(url: str) -> bool:
    """Check if the URL points at a whole YouTube channel or one of its tabs."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != "youtube.com" and not host.endswith(".youtube.com"):
        return False
    return bool(_CHANNEL_URL_PATTERN.match(parsed.path))


def channel_id_from_url(url: str) -> str | None:
    """Return the channel id when the URL already carries one (/channel/UC...)."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) >= 2 and parts[0].lower() == "channel" and _CHANNEL_ID_PATTERN.match(parts[1]):
        return parts[1]
    return None


def _find_channel_id(data: dict[str, Any]) -> str | None:
    """Pull the channel id out of yt-dlp's JSON for a channel or channel tab.

    A bare channel URL comes back as a playlist whose entries are themselves the
    Videos/Shorts/Live playlists, so when the top level carries no id the nested
    entries are searched too.
    """
    channel_id = data.get("channel_id")
    if isinstance(channel_id, str) and _CHANNEL_ID_PATTERN.match(channel_id):
        return channel_id

    playlist_id = data.get("id")
    if isinstance(playlist_id, str) and _CHANNEL_ID_PATTERN.match(playlist_id):
        return playlist_id

    for entry in data.get("entries") or []:
        if isinstance(entry, dict):
            found = _find_channel_id(entry)
            if found:
                return found
    return None


def resolve_channel_id(url: str, extra_args: list[str], runner: CaptureRunner) -> str:
    """Ask yt-dlp for the channel id behind a channel URL.

    Handles, /c/ and /user/ URLs do not contain the id, and the archive file is
    keyed by it so that every URL form of a channel (and a later handle change)
    resumes the same archive. The request is kept as small as possible: flat
    listing and a single item, so a tab URL does not page through the channel.

    Args:
        url: The channel URL.
        extra_args: JS runtime, proxy and rate-limit arguments; the lookup must
            go through the same proxy as the download.
        runner: Executes yt-dlp and captures its output.

    Raises:
        PlaylistError: yt-dlp failed or returned no usable channel id.
        KeyboardInterrupt: the user pressed Ctrl+C during the lookup.
    """
    known = channel_id_from_url(url)
    if known:
        return known

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "-J",
        "--playlist-items",
        "1",
        "--yes-playlist",
        url,
        *extra_args,
    ]
    rc, out, err = runner(cmd)
    if rc == 130:
        # run_capture turns Ctrl+C into a return code. Re-raise it: treating it
        # as a failed lookup would fall back and start the download anyway.
        raise KeyboardInterrupt
    if rc != 0 or not out.strip():
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))

    try:
        data = json.loads(out)
    except json.JSONDecodeError as ex:
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=str(ex))) from ex

    channel_id = _find_channel_id(data) if isinstance(data, dict) else None
    if not channel_id:
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))
    return channel_id


def safe_archive_token(value: str) -> str:
    """Make an id safe to embed in an archive file name."""
    return _UNSAFE_FILENAME_CHARS.sub("_", value) or "unknown"


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
