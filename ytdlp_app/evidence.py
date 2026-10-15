"""Whether a download's file is really on disk: one answer for the archive check and the run.

An archive record says an id is done, and the manifest says where its file went. Neither
proves the file is there. A folder named after the id, the info JSON or thumbnail beside it,
a ``.part`` left by an interrupted download, or another mode's file of the same video are all
on disk long after the video itself is gone. Only a finished media file of the kind the
mode produces counts here.

The archive check (archive_audit) and the run outcome (outcome.evaluate) both ask locate(),
so they cannot disagree about the same file.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from .models import DownloadMode

if TYPE_CHECKING:
    from collections.abc import Iterable

#: The "[id]" group a name ends with: where every default template puts %(id)s. Earlier
#: bracket groups belong to the title ("Reaction to [<another id>]") and are never ids.
_TRAILING_ID = re.compile(r"\[([^\[\]/\\]+)\]$")

#: An archive mode item folder: "<upload_date> - <title> [<id>]".
_DATED_FOLDER = re.compile(r"^\d{8} - ")

#: What each mode leaves behind as its finished file. Archive mode writes MKV, video mode
#: MP4 or MKV (or the source container when the user keeps it); audio mode the chosen
#: format, or the source's own for "best".
VIDEO_SUFFIXES = frozenset({".mp4", ".mkv", ".webm", ".mov", ".m4v"})
AUDIO_SUFFIXES = frozenset(
    {".mp3", ".m4a", ".opus", ".ogg", ".oga", ".flac", ".wav", ".aac", ".webm", ".mka"}
)
_SUFFIXES: dict[DownloadMode | None, frozenset[str]] = {
    DownloadMode.VIDEO: VIDEO_SUFFIXES,
    DownloadMode.ARCHIVE: VIDEO_SUFFIXES,
    DownloadMode.AUDIO: AUDIO_SUFFIXES,
    None: VIDEO_SUFFIXES | AUDIO_SUFFIXES,
}

#: Intermediate files: yt-dlp's unmerged format streams (``.f137.mp4``) and ``.temp`` files,
#: and the MP4 compatibility step's work file (``.compat.mp4``), left behind when a
#: conversion is killed. ``.part`` and ``.ytdl`` never end in a media suffix, so the suffix
#: check drops them.
_LEFTOVER = re.compile(r"\.(?:f\d+(?:-\w+)?|temp|compat)\.[^.]+$", re.IGNORECASE)

#: The archive name suffix of each mode (see planning.archive_file_name).
_ARCHIVE_SUFFIX_MODES = (
    ("_mp4", DownloadMode.VIDEO),
    ("_mp3", DownloadMode.AUDIO),
    ("_archive", DownloadMode.ARCHIVE),
)


class EvidenceStatus(StrEnum):
    """What the disk says about one archived item."""

    PRESENT = "present"
    MISSING = "missing"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class Evidence:
    """The verdict on one item and the file it rests on (None when there is none)."""

    status: EvidenceStatus
    path: Path | None = None


def mode_of_archive(archive: Path) -> DownloadMode | None:
    """The download mode an archive file belongs to, read from its name (None if unknown)."""
    stem = archive.stem
    for suffix, mode in _ARCHIVE_SUFFIX_MODES:
        if stem.endswith(suffix):
            return mode
    return None


def _is_media_name(name: str, mode: DownloadMode | None) -> bool:
    return Path(name).suffix.lower() in _SUFFIXES[mode] and not _LEFTOVER.search(name)


def is_media_file(path: Path, mode: DownloadMode | None) -> bool:
    """Whether ``path`` is a finished media file of the kind ``mode`` produces."""
    if not _is_media_name(path.name, mode):
        return False
    try:
        return path.is_file()
    except OSError:
        return False


def _trailing_id(name: str) -> str | None:
    match = _TRAILING_ID.search(name)
    return match.group(1) if match else None


def _id_of(folder: str, file: str) -> str | None:
    """The id a media file is evidence for, from its name and its folder's, or None.

    Video and audio modes end the file name in ``[id]``. Archive mode ends the folder name
    in it and names the file after the title alone, so the title the folder repeats before
    its id is the file's whole name, brackets of its own included. When a dated archive
    folder and the file name otherwise end in different ids, the file proves neither.
    """
    stem = Path(file).stem
    own = _trailing_id(stem)
    folder_id = _trailing_id(folder)
    if folder_id is None:
        return own
    if own is None or own == folder_id or folder.endswith(f"{stem} [{folder_id}]"):
        return folder_id
    # Two different ids: a dated folder is an archive item folder, which this file
    # contradicts; any other folder (a playlist's title) is no id at all.
    return None if _DATED_FOLDER.match(folder) else own


class MediaIndex:
    """Media files under the download folders, by the id their name carries (see _id_of).

    The folders are walked once, on the first lookup.
    """

    def __init__(self, roots: Iterable[Path]) -> None:
        self._roots = [r for r in roots if r.is_dir()]
        self._files: dict[str, list[Path]] | None = None

    def _build(self) -> dict[str, list[Path]]:
        found: dict[str, list[Path]] = {}
        for root in self._roots:
            for folder, dirs, files in os.walk(root):
                dirs.sort()
                folder_name = Path(folder).name
                for name in sorted(files):
                    if not _is_media_name(name, None):
                        continue
                    ident = _id_of(folder_name, name)
                    if ident is not None:
                        found.setdefault(ident, []).append(Path(folder) / name)
        return found

    def files_for(self, ident: str, mode: DownloadMode | None) -> tuple[Path, ...]:
        """The media files that carry ``ident`` and suit ``mode``."""
        if self._files is None:
            self._files = self._build()
        return tuple(p for p in self._files.get(ident, ()) if _is_media_name(p.name, mode))


def locate(
    ident: str, recorded: Path | None, *, mode: DownloadMode | None, index: MediaIndex
) -> Evidence:
    """Decide whether item ``ident`` is on disk.

    The recorded path wins when it is a media file. Otherwise a media file carrying the id
    (a moved file, or an old record with no path) is accepted. A recorded path with nothing
    to back it is MISSING; a record that never had a path and matches nothing is UNVERIFIED,
    because files named after their title alone cannot be told apart.
    """
    if recorded is not None and is_media_file(recorded, mode):
        return Evidence(EvidenceStatus.PRESENT, recorded)
    matches = index.files_for(ident, mode)
    if matches:
        return Evidence(EvidenceStatus.PRESENT, matches[0])
    if recorded is not None:
        return Evidence(EvidenceStatus.MISSING, recorded)
    return Evidence(EvidenceStatus.UNVERIFIED)


__all__ = [
    "AUDIO_SUFFIXES",
    "VIDEO_SUFFIXES",
    "Evidence",
    "EvidenceStatus",
    "MediaIndex",
    "is_media_file",
    "locate",
    "mode_of_archive",
]
