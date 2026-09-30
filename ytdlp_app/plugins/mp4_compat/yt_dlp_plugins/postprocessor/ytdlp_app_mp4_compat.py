"""yt-dlp plugin that guarantees the MP4 compatibility profile's codecs.

The profile promises an MP4 file holding H.264 video and AAC audio. yt-dlp's own
``--recode-video mp4`` cannot promise that: it looks at the container only, so a
file that is already an ``.mp4`` (YouTube serves AV1 and VP9 in MP4 too) is
reported as "already in target format" and left alone.

This post-processor looks at the codecs instead. It probes the downloaded file
with ffprobe and

* leaves a file that already is H.264 + AAC in MP4 exactly as it is (no
  re-encode, so no quality loss),
* copies whichever stream is already right and re-encodes only the other one
  (H.264 video with an unsuitable audio codec keeps its video untouched),
* converts anything else, including a webm/mkv container, into MP4,

then probes the result again and fails the item if it is still not H.264 + AAC.
A failure here is a post-processing error: yt-dlp does not record the item in the
download archive, so a later run retries it.

It runs with ``--use-postprocessor Mp4Compat:when=post_process``. That is before
metadata, chapters, thumbnail and subtitle embedding, which therefore act on the
final MP4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
from yt_dlp.utils import PostProcessingError

TARGET_VIDEO = "h264"
TARGET_AUDIO = "aac"

#: ffprobe format names that mean an MP4-family container.
_MP4_FORMATS = ("mp4", "mov")


def _media_streams(streams: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """The real streams of one kind (cover art shows up as a video stream)."""
    return [
        s
        for s in streams
        if s.get("codec_type") == kind and not (s.get("disposition") or {}).get("attached_pic")
    ]


def plan_conversion(probe: dict[str, Any], path: str) -> dict[str, bool]:
    """Decide what has to change for the file to be H.264 + AAC in MP4.

    Args:
        probe: ffprobe's ``-show_format -show_streams`` JSON for the file.
        path: The file's path (its extension must be .mp4 too).

    Returns:
        ``{"video": bool, "audio": bool, "container": bool}``: which parts need work.
        All False means the file already meets the contract.
    """
    streams = probe.get("streams") or []
    videos = _media_streams(streams, "video")
    audios = _media_streams(streams, "audio")
    formats = str((probe.get("format") or {}).get("format_name", "")).split(",")
    container_ok = path.lower().endswith(".mp4") and any(f in _MP4_FORMATS for f in formats)
    return {
        "video": any(s.get("codec_name") != TARGET_VIDEO for s in videos),
        "audio": any(s.get("codec_name") != TARGET_AUDIO for s in audios),
        "container": not container_ok,
    }


def meets_contract(probe: dict[str, Any], path: str) -> bool:
    """Tell whether a probed file is MP4 with H.264 video and AAC audio."""
    streams = probe.get("streams") or []
    if not _media_streams(streams, "video"):
        return False
    return not any(plan_conversion(probe, path).values())


def ffmpeg_options(plan: dict[str, bool]) -> list[str]:
    """ffmpeg output options for a plan: copy what is fine, encode what is not."""
    options = ["-map", "0:v", "-map", "0:a?", "-sn", "-dn", "-map_metadata", "0"]
    if plan["video"]:
        options += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        options += ["-c:v", "copy"]
    if plan["audio"]:
        options += ["-c:a", "aac", "-b:a", "192k"]
    else:
        options += ["-c:a", "copy"]
    return options


class Mp4CompatPP(FFmpegPostProcessor):
    """Make the downloaded file MP4 + H.264 + AAC, touching it as little as possible."""

    def _probe(self, path: str) -> dict[str, Any]:
        return self.get_metadata_object(path)  # type: ignore[no-any-return]

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        if not self.available:
            raise PostProcessingError("ffmpeg not found; the MP4 compatibility profile needs it")
        source = info["filepath"]
        probe = self._probe(source)
        if not _media_streams(probe.get("streams") or [], "video"):
            raise PostProcessingError(f"{Path(source).name} has no video stream")

        plan = plan_conversion(probe, source)
        if not any(plan.values()):
            self.to_screen(f"{Path(source).name} is already H.264 + AAC in MP4; keeping it as is")
            return [], info

        target = str(Path(source).with_suffix(".mp4"))
        work = str(Path(source).with_suffix(".compat.mp4"))
        parts = [name for name, needed in plan.items() if needed]
        self.to_screen(
            f"Making {Path(source).name} H.264 + AAC in MP4 (fixing: {', '.join(parts)})"
        )
        try:
            self.run_ffmpeg(source, work, ffmpeg_options(plan))
            result = self._probe(work)
            if not meets_contract(result, target):
                raise PostProcessingError(
                    f"{Path(work).name} is not H.264 + AAC in MP4 after conversion"
                )
            Path(work).replace(target)
        finally:
            Path(work).unlink(missing_ok=True)

        info["filepath"] = target
        info["ext"] = "mp4"
        info["format"] = "mp4"
        # The original goes away once the converted file is in place; if it is the
        # same file (an .mp4 that only needed its streams fixed) there is nothing to delete.
        return ([] if Path(source).resolve() == Path(target).resolve() else [source]), info
