"""yt-dlp plugin that refuses to call a video done when a part it has could not be saved.

An archive is only worth as much as its completeness. yt-dlp, though, treats the optional
parts differently from the video itself: a subtitle that fails to download is reported as
an ERROR (exit code 1) and the video is still downloaded and recorded in the download
archive as done, so the missing subtitle is never fetched again. A thumbnail that cannot
be fetched only draws a warning, and is then dropped from the list of thumbnails, so
nothing afterwards shows that it was ever there.

This post-processor is registered twice for archive mode:

* ``ArchiveComplete:when=video;stage=snapshot`` runs before anything is written and notes
  how many thumbnails the video lists;
* ``ArchiveComplete:when=before_dl;stage=check`` runs once the subtitles and thumbnails
  have been written, before the video is downloaded, and stops the item when a part the
  video *has* is missing on disk:

  - every subtitle that was requested (an uploaded or automatic caption in a language
    asked for) must exist as a file. A video with no subtitles in those languages requests
    none, which is fine;
  - if thumbnails were listed, at least one must have been saved. yt-dlp walks the list
    from the best down and stops at the first that downloads, so a 404 on the best one, which
    is common, is not a failure as long as a lesser one arrived. A video that lists no
    thumbnail needs none.

Stopping is done with an ExtractorError, not a PostProcessingError: yt-dlp collects errors
of a ``before_dl`` step as "pending" and goes on to download and archive the video anyway.
An ExtractorError ends this item (no download, no archive entry, exit code 1) and the run
carries on with the next one, and the next run tries this one again.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import ExtractorError

SNAPSHOT_KEY = "__ytdlp_app_thumbnails_listed"


def _saved(entry: dict[str, Any]) -> bool:
    path = entry.get("filepath")
    return isinstance(path, str) and bool(path) and Path(path).exists()


def missing_parts(info: dict[str, Any], *, thumbnails_listed: int) -> list[str]:
    """Names of the parts a video has but that are not on disk (empty when complete)."""
    missing: list[str] = []
    for lang, sub in sorted((info.get("requested_subtitles") or {}).items()):
        if not _saved(sub):
            missing.append(f"subtitle {lang}")
    if thumbnails_listed and not any(_saved(t) for t in info.get("thumbnails") or []):
        missing.append("thumbnail")
    return missing


class ArchiveCompletePP(PostProcessor):
    """Note what a video has, then fail the item when a part of it was not saved."""

    def __init__(self, downloader: Any = None, stage: str = "check") -> None:
        super().__init__(downloader)
        self._stage = stage

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        wants_thumbnail = bool(
            self.get_param("writethumbnail") or self.get_param("write_all_thumbnails")
        )
        if self._stage == "snapshot":
            info[SNAPSHOT_KEY] = len(info.get("thumbnails") or []) if wants_thumbnail else 0
            return [], info

        listed = int(info.get(SNAPSHOT_KEY) or 0)
        missing = missing_parts(info, thumbnails_listed=listed)
        if missing:
            raise ExtractorError(
                "not complete: " + ", ".join(missing) + " could not be saved; "
                "the video is left for the next run",
                expected=True,
            )
        return [], info
