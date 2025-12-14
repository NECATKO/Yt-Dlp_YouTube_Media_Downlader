from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .models import CaptureRunner, PlaylistEntry


def is_playlist_url(url: str) -> bool:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return ("list" in qs) or parsed.path.startswith("/playlist")


def get_playlist_id(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return qs.get("list", ["unknown_playlist"])[0]


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


def fetch_playlist_entries(
    url: str, js_args: list[str], runner: CaptureRunner
) -> list[PlaylistEntry]:
    cmd = ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", url] + js_args
    rc, out, err = runner(cmd)
    if rc != 0 or not out.strip():
        raise RuntimeError(f"Playlist JSON alnamad.\nreturncode={rc}\nstderr:\n{err}")

    data = json.loads(out)
    entries = data.get("entries") or []
    result: list[PlaylistEntry] = []

    idx = 0
    for e in entries:
        idx += 1
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
