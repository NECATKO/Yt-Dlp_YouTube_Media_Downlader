"""Playlist detection and parsing utilities for ytdlp_app.

This module provides functions for detecting playlist URLs, extracting
playlist IDs, reading download archives, and fetching playlist entries.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from .exceptions import PlaylistError
from .i18n import t
from .models import CaptureRunner, PlaylistEntry

if TYPE_CHECKING:
    from pathlib import Path

# The app is built around YouTube: playlist and channel handling, the size estimate and
# the archive naming all rest on YouTube's URL forms and ids. Any other site's URL is
# still handed to yt-dlp, but only ever as a single item.
_YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")

# A whole channel, or one of its listing tabs. A bare channel URL makes yt-dlp
# return the Videos, Shorts and Live tabs as nested playlists. "/live" is left
# out on purpose: it redirects to the channel's current stream, a single video.
_CHANNEL_URL_PATTERN = re.compile(
    r"^/(?:channel/[^/]+|c/[^/]+|user/[^/]+|@[^/]+)"
    r"(?:/(?:videos|shorts|streams|featured|podcasts|releases))?/?$",
    re.IGNORECASE,
)

# The first path segments that name a channel, with the segment after them being its id.
_CHANNEL_KINDS = ("channel", "c", "user")

# A channel's own tabs beyond the ones that list videos (its playlists, its community
# posts...) are still "the channel" for classification. "live" is not: it is one video.
_SINGLE_VIDEO_TABS = ("live",)

# YouTube channel ids: "UC" followed by 22 URL-safe base64 characters.
_CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")

# Anything outside this set is replaced when an id is used in a file name.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^\w.-]")


def is_youtube_host(url: str) -> bool:
    """Whether the URL is on one of YouTube's own hosts (the exact domain or a subdomain)."""
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in _YOUTUBE_HOSTS)


def _channel_segments(path: str) -> tuple[str, list[str]] | None:
    """Split a channel path into its identifier and the tab segments after it.

    Returns None when the path is not a channel's (``/watch``, ``/clip/...``, ``/cats``).
    """
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None
    head = parts[0]
    if head.startswith("@") and len(head) > 1:
        return head.removeprefix("@"), parts[1:]
    if head.lower() in _CHANNEL_KINDS and len(parts) >= 2:
        return parts[1], parts[2:]
    return None


def is_playlist_url(url: str) -> bool:
    """Check if the URL is a YouTube playlist or channel (treated as playlist).

    Other sites' URLs are never playlists here, and a channel's ``/live`` address is
    the single video it redirects to.
    """
    if not is_youtube_host(url):
        return False
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # Standard playlist param
    if "list" in qs:
        return True

    path = parsed.path

    # Explicit /playlist path
    if path == "/playlist" or path.startswith("/playlist/"):
        return True

    channel = _channel_segments(path)
    if channel is None:
        return False
    _ident, tabs = channel
    return not (tabs and tabs[0].lower() in _SINGLE_VIDEO_TABS)


def get_playlist_id(url: str) -> str:
    """Extract a unique identifier for the playlist or channel.

    A channel is identified by its handle, id or name, never by the tab of it that
    the URL points at: ``/@a/videos`` and ``/@b/videos`` must not share an identifier.
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # 1. Try standard 'list' param for playlists
    if "list" in qs:
        return qs["list"][0]

    # 2. For channel URLs, the channel's own identifier (@ChannelName -> ChannelName, UCxxxxx)
    channel = _channel_segments(parsed.path)
    if channel is not None:
        return channel[0]

    # 3. Anything else: the last path segment
    path = parsed.path.rstrip("/")
    if path:
        segment = path.split("/")[-1]
        return segment.lstrip("@") if segment.startswith("@") else segment

    return "unknown_playlist"


def is_channel_url(url: str) -> bool:
    """Check if the URL points at a whole YouTube channel or one of its tabs."""
    if not is_youtube_host(url):
        return False
    return bool(_CHANNEL_URL_PATTERN.match(urlparse(url).path))


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


#: Longest identifier kept verbatim in an archive file name.
_MAX_TOKEN = 80


def safe_archive_token(value: str) -> str:
    """Make an id safe to embed in an archive file name.

    Real YouTube ids (letters, digits, "-" and "_") pass through unchanged. Anything else
    is replaced, and because the replacement can make two different ids equal, a token
    that had to change gets a short hash of the original appended: different ids can then
    never share an archive file, and no id can carry a path separator into the name.
    """
    token = _UNSAFE_FILENAME_CHARS.sub("_", value)
    changed = token != value or not token.strip(".") or len(token) > _MAX_TOKEN
    if not changed:
        return token
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:8]
    base = token[:_MAX_TOKEN].strip(".") or "id"
    return f"{base}-{digest}"


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


#: yt-dlp's key for a channel tab or playlist that was listed but not expanded.
_TAB_IE_KEY = "YoutubeTab"


@dataclass(frozen=True, slots=True)
class PlaylistListing:
    """What one flat listing of a playlist or channel returned.

    Attributes:
        entries: The videos, with channel tabs flattened into one list.
        channel_id: The channel id when the URL or the listing carries one.
    """

    entries: list[PlaylistEntry]
    channel_id: str | None


def _leaf_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect the video entries of a flat listing, descending into nested playlists.

    A bare channel URL comes back as a playlist of tab playlists (Videos, Shorts,
    Live). Their contents are already there, so nothing extra is requested. A tab
    that is only a stub (an unexpanded YoutubeTab reference) has no videos to
    read and is skipped rather than fetched.
    """
    leaves: list[dict[str, Any]] = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("entries"), list):
            leaves.extend(_leaf_entries(entry))
        elif entry.get("ie_key") == _TAB_IE_KEY:
            continue
        else:
            leaves.append(entry)
    return leaves


def _as_duration(value: Any) -> float | None:
    """Return a usable duration in seconds, or None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value > 0 else None


def _watch_url(raw: dict[str, Any]) -> str:
    """The address to fetch an entry from.

    Only a YouTube entry (or one that does not say what it is) may have a watch URL
    built from its id. Another extractor's id means nothing to YouTube, so such an entry
    keeps the address its own extractor gave, or has none.
    """
    url = raw.get("url")
    vid = raw.get("id")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        # A YouTube address (a /shorts/ one too) is fetched through the canonical watch URL.
        if vid and is_youtube_host(url):
            return f"https://www.youtube.com/watch?v={vid}"
        return url
    ie_key = raw.get("ie_key")
    if vid and (ie_key is None or str(ie_key).lower() == "youtube"):
        return f"https://www.youtube.com/watch?v={vid}"
    return ""


def _to_entry(index: int, raw: dict[str, Any]) -> PlaylistEntry:
    vid = raw.get("id") or raw.get("url")
    url = raw.get("url")
    return PlaylistEntry(
        playlist_index=index,
        id=vid or "",
        title=raw.get("title") or "",
        watch_url=_watch_url(raw),
        duration=_as_duration(raw.get("duration")),
        is_short=isinstance(url, str) and "/shorts/" in url,
    )


def fetch_listing(url: str, extra_args: list[str], runner: CaptureRunner) -> PlaylistListing:
    """List a playlist or channel with one flat yt-dlp request.

    Args:
        url: The playlist or channel URL.
        extra_args: JS runtime, pacing, proxy and rate-limit arguments.
        runner: Executes yt-dlp and captures its output.

    Raises:
        PlaylistError: yt-dlp failed or returned unusable output.
        KeyboardInterrupt: the user pressed Ctrl+C during the request.
    """
    cmd = ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", url, *extra_args]
    rc, out, err = runner(cmd)
    if rc == 130:
        # run_capture turns Ctrl+C into a return code; carrying on would start
        # the download the user just cancelled.
        raise KeyboardInterrupt
    if rc != 0 or not out.strip():
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))

    try:
        data = json.loads(out)
    except json.JSONDecodeError as ex:
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=str(ex))) from ex
    if not isinstance(data, dict):
        raise PlaylistError(t("playlist_fetch_failed_detail", rc=rc, stderr=err))

    entries = [_to_entry(i, raw) for i, raw in enumerate(_leaf_entries(data), start=1)]
    return PlaylistListing(
        entries=entries,
        channel_id=channel_id_from_url(url) or _find_channel_id(data),
    )


def fetch_playlist_entries(
    url: str, js_args: list[str], runner: CaptureRunner
) -> list[PlaylistEntry]:
    """List the videos of a playlist or channel (see fetch_listing)."""
    return fetch_listing(url, js_args, runner).entries
