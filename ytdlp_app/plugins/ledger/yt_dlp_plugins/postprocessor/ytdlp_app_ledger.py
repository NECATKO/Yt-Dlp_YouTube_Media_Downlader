"""yt-dlp plugin that records where every finished download ended up.

The download archive only says *that* an id was downloaded, never *where*, so a
deleted or moved file cannot be told from a present one. This post-processor
appends ``<id><TAB><final path>`` to a manifest next to the archive file for each
item that got through every post-processing step, which is what the app's archive
check compares against the disk.

Use: ``--use-postprocessor "DownloadLedger:when=after_move;path=<file>"``. The path
is percent-encoded for ``%`` and ``;`` because yt-dlp splits the argument on ``;``.
It runs at ``after_move``: only reached when the earlier post-processors succeeded,
and ``filepath`` is then the final location.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote

from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import PostProcessingError


class DownloadLedgerPP(PostProcessor):
    """Append the finished item's id and final file path to a manifest."""

    def __init__(self, downloader: Any = None, path: str | None = None) -> None:
        super().__init__(downloader)
        self._path = Path(unquote(path)) if path else None

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        if self._path is None:
            return [], info
        item_id, filepath = info.get("id"), info.get("filepath")
        if not item_id or not filepath:
            return [], info
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8", newline="\n") as manifest:
                manifest.write(f"{item_id}\t{filepath}\n")
        except OSError as ex:
            # Not being able to record it means the archive check could not vouch for
            # the file later; better to fail the item now than to archive it blind.
            raise PostProcessingError(f"could not write the download manifest: {ex}") from ex
        return [], info
