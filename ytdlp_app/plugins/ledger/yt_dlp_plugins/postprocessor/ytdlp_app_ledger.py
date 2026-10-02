"""yt-dlp plugin that records where every finished download ended up.

The download archive only says *that* an id was downloaded, never *where*, so a
deleted or moved file cannot be told from a present one. This post-processor
appends ``<id><TAB><final path>`` to a manifest next to the archive file for each
item that got through every post-processing step, which is what the app's archive
check compares against the disk.

Use: ``--use-postprocessor "DownloadLedger:when=after_move;path=<file>;root=<folder>"``.
The paths are percent-encoded for ``%`` and ``;`` because yt-dlp splits the argument on
``;``. ``root`` is the program folder: a file inside it is recorded relative to the
manifest's folder, so the whole folder can be moved; any other file (and every file when
``root`` is not given) is recorded with its absolute path.

It runs at ``after_move``: only reached when the earlier post-processors succeeded,
and ``filepath`` is then the final location.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import PostProcessingError

#: First line of a manifest this version creates. Older manifests have no header and only
#: absolute paths; readers decide line by line, so appending to an old one is fine.
MANIFEST_HEADER = "# ytdlp_app download manifest v2"


class DownloadLedgerPP(PostProcessor):
    """Append the finished item's id and final file path to a manifest."""

    def __init__(
        self, downloader: Any = None, path: str | None = None, root: str | None = None
    ) -> None:
        super().__init__(downloader)
        self._path = Path(unquote(path)) if path else None
        self._root = Path(unquote(root)) if root else None

    def _recorded(self, manifest: Path, filepath: str) -> str:
        """The path as written: relative to the manifest when inside the program folder."""
        if self._root is None:
            return filepath
        try:
            target = Path(filepath).resolve()
            target.relative_to(self._root.resolve())
            return Path(os.path.relpath(target, manifest.parent.resolve())).as_posix()
        except (ValueError, OSError):
            # Outside the program folder, or (Windows) on another drive than the manifest.
            return filepath

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        if self._path is None:
            return [], info
        item_id, filepath = info.get("id"), info.get("filepath")
        if not item_id or not filepath:
            return [], info
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fresh = not self._path.exists() or self._path.stat().st_size == 0
            with self._path.open("a", encoding="utf-8", newline="\n") as manifest:
                if fresh:
                    manifest.write(MANIFEST_HEADER + "\n")
                manifest.write(f"{item_id}\t{self._recorded(self._path, filepath)}\n")
        except OSError as ex:
            # Not being able to record it means the archive check could not vouch for
            # the file later; better to fail the item now than to archive it blind.
            raise PostProcessingError(f"could not write the download manifest: {ex}") from ex
        return [], info
