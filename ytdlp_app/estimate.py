"""Size, disk-space and time estimates for a listing, made before downloading.

Nothing here touches the network or the disk. The numbers are deliberately on
the high side: a flat listing carries a duration but no resolution, so the
bit rates below stand in for "a typical video at that resolution". Running out
of space mid-download is worse than being told to expect a bit more.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .i18n import t

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from .models import PlaylistEntry

#: The resolution caps the estimate table shows.
RESOLUTIONS: Final[tuple[int, ...]] = (1080, 1440, 2160)

#: Video bit rate in kbit/s per resolution. 1080p is YouTube's H.264 upper end
#: (60 fps), because the compatibility profile asks for H.264; 1440p and 2160p
#: are the upper end of typical VP9.
VIDEO_KBPS: Final[dict[int, int]] = {1080: 6000, 1440: 12000, 2160: 30000}

#: Bit rate of the audio stream YouTube pairs with the video (Opus ~130-160, m4a ~128).
AUDIO_KBPS: Final = 160

#: LAME's documented average bit rates for VBR quality 0 (best) to 9.
MP3_VBR_KBPS: Final = (245, 225, 190, 175, 165, 130, 115, 100, 85, 65)

#: Output bit rate for the other audio formats. wav is exact (48 kHz x 16 bit x 2
#: channels); flac is the decoded lossy source, so it is rough.
AUDIO_OUTPUT_KBPS: Final[dict[str, int]] = {
    "m4a": 160,
    "opus": 160,
    "best": 160,
    "flac": 1100,
    "wav": 1536,
}

#: Assumed length of a Short whose listing entry has no duration.
SHORT_SECONDS: Final = 180.0

_RATE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)([KMGT]?)$", re.IGNORECASE)
_RATE_UNITS: Final = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
_SIZE_UNITS: Final = ("B", "KiB", "MiB", "GiB", "TiB")


def audio_output_kbps(audio_format: str, audio_quality: int) -> int:
    """Bit rate of the file the audio settings produce."""
    if audio_format == "mp3":
        index = min(max(audio_quality, 0), len(MP3_VBR_KBPS) - 1)
        return MP3_VBR_KBPS[index]
    return AUDIO_OUTPUT_KBPS.get(audio_format, AUDIO_KBPS)


def size_bytes(seconds: float, kbps: int) -> int:
    """Bytes for a stream of the given length and bit rate."""
    return int(seconds * kbps * 1000 / 8)


@dataclass(frozen=True, slots=True)
class VideoSet:
    """The videos a run will download, with the length assumed for each.

    Attributes:
        seconds: One length per video still to download.
        assumed: How many of those lengths are assumptions, not listing data.
        archived: How many listed videos were left out as already archived.
    """

    seconds: tuple[float, ...]
    assumed: int
    archived: int

    @property
    def count(self) -> int:
        return len(self.seconds)

    @property
    def total_seconds(self) -> float:
        return sum(self.seconds)

    @property
    def longest_seconds(self) -> float:
        return max(self.seconds, default=0.0)


def plan_videos(entries: Iterable[PlaylistEntry], archived_ids: Collection[str]) -> VideoSet | None:
    """Work out which listed videos will be downloaded and how long each is.

    Duplicates (by id) count once and archived ids are left out. A missing
    duration is assumed: 180 s for a /shorts/ address, otherwise the median of
    the durations the listing does give.

    Returns:
        The set, or None when it cannot be estimated (an empty listing, or no
        known duration to take a median from).
    """
    seen: set[str] = set()
    todo: list[PlaylistEntry] = []
    known: list[float] = []
    archived = 0
    unique = 0

    for entry in entries:
        if entry.id:
            if entry.id in seen:
                continue
            seen.add(entry.id)
        unique += 1
        if entry.duration:
            known.append(entry.duration)
        if entry.id and entry.id in archived_ids:
            archived += 1
            continue
        todo.append(entry)

    if unique == 0:
        return None

    median = statistics.median(known) if known else None
    seconds: list[float] = []
    assumed = 0
    for entry in todo:
        if entry.duration:
            seconds.append(entry.duration)
        elif entry.is_short:
            seconds.append(SHORT_SECONDS)
            assumed += 1
        elif median is not None:
            seconds.append(float(median))
            assumed += 1
        else:
            return None
    return VideoSet(tuple(seconds), assumed, archived)


@dataclass(frozen=True, slots=True)
class SizeEstimate:
    """Estimated bytes for one row of the table.

    Attributes:
        height: The resolution cap this row is for; None for an audio row.
        total_bytes: Size of everything that stays on disk.
        required_bytes: total_bytes plus the largest single video, because the
            source and the output coexist while merging, recoding or converting.
        download_bytes: What crosses the network.
    """

    height: int | None
    total_bytes: int
    required_bytes: int
    download_bytes: int


def estimate_video(videos: VideoSet, height: int) -> SizeEstimate:
    """Estimate a video download capped at the given resolution."""
    kbps = VIDEO_KBPS[height] + AUDIO_KBPS
    total = sum(size_bytes(s, kbps) for s in videos.seconds)
    return SizeEstimate(height, total, total + size_bytes(videos.longest_seconds, kbps), total)


def estimate_audio(videos: VideoSet, output_kbps: int) -> SizeEstimate:
    """Estimate an audio extraction: the output stays, the source is downloaded."""
    total = sum(size_bytes(s, output_kbps) for s in videos.seconds)
    largest = size_bytes(videos.longest_seconds, output_kbps)
    downloaded = sum(size_bytes(s, AUDIO_KBPS) for s in videos.seconds)
    return SizeEstimate(None, total, total + largest, downloaded)


def parse_rate_limit(text: str | None) -> float | None:
    """Parse a yt-dlp rate limit such as '500K' or '4.2M' into bytes per second."""
    if not text:
        return None
    match = _RATE_PATTERN.match(text.strip())
    if match is None:
        return None
    value = float(match.group(1)) * _RATE_UNITS[match.group(2).upper()]
    return value if value > 0 else None


def effective_speed(measured: float | None, rate_limit: str | None) -> float | None:
    """The speed a download will get: the measurement, capped by the speed limit."""
    if measured is None or measured <= 0:
        return None
    limit = parse_rate_limit(rate_limit)
    return min(measured, limit) if limit is not None else measured


def download_seconds(download_bytes: int, bytes_per_second: float | None) -> float | None:
    """Time to move the bytes at the given speed, or None when the speed is unknown."""
    if bytes_per_second is None or bytes_per_second <= 0:
        return None
    return download_bytes / bytes_per_second


def archive_wait_seconds(count: int, sleep_interval: float, max_sleep_interval: float) -> float:
    """Lower bound for archive mode: the wait between videos, times the videos."""
    high = max(sleep_interval, max_sleep_interval)
    return count * (sleep_interval + high) / 2


def format_size(num_bytes: float) -> str:
    """Format a byte count in 1024-based units, matching Windows Explorer."""
    value = float(max(num_bytes, 0))
    for unit in _SIZE_UNITS[:-1]:
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {_SIZE_UNITS[-1]}"


def format_duration(seconds: float) -> str:
    """Format a length of time using the two largest units that apply."""
    total = max(round(seconds), 0)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return t("duration_days_hours", days=days, hours=hours)
    if hours:
        return t("duration_hours_minutes", hours=hours, minutes=minutes)
    if minutes:
        return t("duration_minutes", minutes=minutes)
    return t("duration_seconds", seconds=secs)
