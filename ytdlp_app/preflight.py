"""Everything between choosing what to download and starting it.

Two phases, both driven by session.py:

1. guarded_listing wraps the one flat listing request, turning Ctrl+C, a ban
   signal and any other failure into a status the caller can act on.
2. run_preflight shows the size estimate, asks for the resolution cap, checks
   free disk space and reports whether to go on.

The speed test and the free-space probe are passed in, so tests never reach the
network or the real disk. Nothing here blocks a download: a missing estimate,
an unmeasurable disk or a failed save all end in "carry on".
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar

from .estimate import (
    RESOLUTIONS,
    UNLIMITED_HEIGHT,
    SizeEstimate,
    VideoSet,
    archive_wait,
    audio_output_kbps,
    download_seconds,
    effective_speed,
    estimate_audio,
    estimate_video,
    format_duration,
    format_size,
    plan_videos,
)
from .exceptions import PlaylistError
from .exec import find_ban_signal
from .i18n import t
from .logging_utils import Colors, append_log, log_error, paint
from .models import DownloadMode, ProfileChoice
from .speedtest import measure_speed

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .models import PlaylistEntry
    from .settings import AppSettings
    from .ui import UI

_T = TypeVar("_T")

#: The compatibility profile asks for H.264, which YouTube mostly serves up to 1080p.
COMPAT_MAX_HEIGHT = 1080

#: The resolution question's options, in the order shown; None is "unlimited".
RESOLUTION_CHOICES: tuple[int | None, ...] = (1080, 1440, 2160, None)


def _stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def free_bytes(path: Path) -> int:
    """Free space, in bytes, on the disk that holds path."""
    return shutil.disk_usage(path).free


# -- phase 1: the listing -------------------------------------------------


class ListingStatus(Enum):
    OK = "ok"
    FAILED = "failed"
    BAN = "ban"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class GuardedListing(Generic[_T]):
    """The outcome of a listing request.

    Attributes:
        status: What happened.
        value: The listing, when status is OK.
        error: The failure text, when status is FAILED or BAN.
    """

    status: ListingStatus
    value: _T | None = None
    error: str = ""


def guarded_listing(fetch: Callable[[], _T], log_path: Path | None) -> GuardedListing[_T]:
    """Run a listing request and classify how it ended.

    A ban signal in the error text means YouTube is blocking us: the caller must
    not start the download (a [BAN-GUARD] line is logged, as for a download).
    """
    try:
        return GuardedListing(ListingStatus.OK, fetch())
    except KeyboardInterrupt:
        return GuardedListing(ListingStatus.INTERRUPTED)
    except PlaylistError as ex:
        signal = find_ban_signal(str(ex))
        if signal is not None:
            append_log(
                log_path,
                f"\n[WARN {_stamp()}] Playlist listing failed: {ex}\n"
                f"[BAN-GUARD {_stamp()}] Not starting the download: "
                f"{signal.value} during the playlist listing\n",
            )
            return GuardedListing(ListingStatus.BAN, error=str(ex))
        log_error(log_path, t("playlist_fetch_failed_log"), ex)
        return GuardedListing(ListingStatus.FAILED, error=str(ex))
    except Exception as ex:
        log_error(log_path, t("playlist_fetch_failed_log"), ex)
        return GuardedListing(ListingStatus.FAILED, error=str(ex))


# -- phase 2: estimate, resolution, space ----------------------------------


class PreflightAction(Enum):
    PROCEED = "proceed"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """What to do next and which resolution cap to download with.

    Attributes:
        action: Go on or cancel (the user declined to continue on low disk space).
        max_height: The cap for this download; None means no cap.
    """

    action: PreflightAction
    max_height: int | None = None


@dataclass(frozen=True, slots=True)
class PreflightRequest:
    """Everything run_preflight needs to know about the coming download.

    Attributes:
        mode: MP4, MP3 or archive.
        is_playlist: Whether a playlist or channel is being downloaded. Only then
            is there an estimate; a single video sends no listing request.
        entries: The listing, or None when it was not obtained (a failed request).
        archived_ids: Ids already in the download archive; they are not downloaded again.
        mp4_profile: The MP4 profile, or None outside MP4 mode.
        base_dir: Where the files go; its disk is the one checked.
        log_path: The session log, for the cancel record.
    """

    mode: DownloadMode
    is_playlist: bool
    entries: list[PlaylistEntry] | None
    archived_ids: frozenset[str]
    mp4_profile: ProfileChoice | None
    base_dir: Path
    log_path: Path | None


@dataclass(frozen=True, slots=True)
class _Sizes:
    rows: list[SizeEstimate]
    videos: VideoSet


def _default_height(mode: DownloadMode, settings: AppSettings) -> int | None:
    if mode == DownloadMode.ARCHIVE:
        return settings.archive.max_height
    if mode == DownloadMode.VIDEO:
        return settings.video.max_height
    return None


def _table_lines(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    widths = [max(len(line[i]) for line in [header, *rows]) for i in range(len(header))]
    return [
        "  "
        + "  ".join(cell.ljust(width) for cell, width in zip(line, widths, strict=True)).rstrip()
        for line in [header, *rows]
    ]


def _free_or_none(disk_free: Callable[[Path], int], path: Path) -> int | None:
    try:
        return disk_free(path)
    except OSError:
        return None


def _show_estimate(
    request: PreflightRequest,
    settings: AppSettings,
    ui: UI,
    measure: Callable[[str | None], float | None],
    compat: bool,
    free: int | None,
) -> _Sizes | None:
    """Print the estimate table; None when it cannot be calculated."""
    videos = (
        plan_videos(request.entries, request.archived_ids) if request.entries is not None else None
    )
    if videos is None:
        ui.print(paint(t("estimate_unavailable"), Colors.YELLOW))
        return None
    if videos.count == 0:
        ui.print(paint(t("estimate_nothing_new"), Colors.GREEN))
        return _Sizes([], videos)

    measured: float | None = None
    if settings.download.speed_test:
        ui.print(paint(t("preflight_measuring_speed"), Colors.CYAN))
        measured = measure(settings.download.proxy)
        if measured is None:
            ui.print(paint(t("preflight_speed_unknown"), Colors.YELLOW))
        else:
            ui.print(t("preflight_speed_measured", mbps=f"{measured * 8 / 1_000_000:.1f}"))
    else:
        ui.print(paint(t("preflight_speed_off"), Colors.YELLOW))
    speed = effective_speed(measured, settings.download.rate_limit)

    if request.mode == DownloadMode.AUDIO:
        kbps = audio_output_kbps(settings.audio.audio_format, settings.audio.audio_quality)
        rows = [estimate_audio(videos, kbps)]
        labels = [settings.audio.audio_format]
        first_column = t("estimate_col_format")
    else:
        heights: tuple[int | None, ...] = (COMPAT_MAX_HEIGHT,) if compat else (*RESOLUTIONS, None)
        rows = [estimate_video(videos, height) for height in heights]
        labels = []
        for height in heights:
            if height is None:
                labels.append(t("estimate_row_unlimited"))
            elif height == RESOLUTIONS[0]:
                labels.append(t("estimate_row_plain", height=height))
            else:
                labels.append(t("estimate_row_at_most", height=height))
        first_column = t("estimate_col_resolution")

    cells: list[tuple[str, ...]] = []
    for label, row in zip(labels, rows, strict=True):
        seconds = download_seconds(row.download_bytes, speed)
        cells.append(
            (
                label,
                format_size(row.total_bytes),
                format_size(row.required_bytes),
                format_duration(seconds) if seconds is not None else t("estimate_time_unknown"),
            )
        )
    header = (
        first_column,
        t("estimate_col_size"),
        t("estimate_col_needed"),
        t("estimate_col_time"),
    )

    ui.print("\n" + paint(t("estimate_title"), Colors.CYAN, Colors.BOLD))
    for line in _table_lines(header, cells):
        ui.print(line)
    ui.print(
        t(
            "estimate_summary",
            count=videos.count,
            archived=videos.archived,
            assumed=videos.assumed,
        )
    )
    if request.mode != DownloadMode.AUDIO and not compat:
        ui.print(paint(t("estimate_unlimited_note"), Colors.YELLOW))
    if free is None:
        ui.print(paint(t("estimate_free_unknown"), Colors.YELLOW))
    else:
        ui.print(t("estimate_free_space", free=format_size(free)))

    if request.mode == DownloadMode.ARCHIVE:
        archive = settings.archive
        wait = archive_wait(videos.count, archive.sleep_interval, archive.max_sleep_interval)
        ui.print(
            paint(
                t(
                    "archive_wait_estimate",
                    minimum=format_duration(wait.minimum),
                    expected=format_duration(wait.expected),
                    count=videos.count,
                    low=f"{archive.sleep_interval:g}",
                    high=f"{max(archive.sleep_interval, archive.max_sleep_interval):g}",
                ),
                Colors.YELLOW,
            )
        )
    return _Sizes(rows, videos)


def _height_label(height: int | None, default: int | None) -> str:
    label = t("resolution_unlimited") if height is None else t("resolution_option", height=height)
    return t("resolution_default_mark", label=label) if height == default else label


def _choose_height(
    request: PreflightRequest,
    settings: AppSettings,
    ui: UI,
    persist_default: Callable[[int | None], None],
    compat: bool,
) -> int | None:
    """Decide the resolution cap, asking only where a choice exists."""
    if request.mode == DownloadMode.AUDIO:
        return None
    if compat:
        ui.print(paint(t("estimate_compat_note"), Colors.YELLOW))
        return COMPAT_MAX_HEIGHT

    default = _default_height(request.mode, settings)
    options = [_height_label(height, default) for height in RESOLUTION_CHOICES]
    height = RESOLUTION_CHOICES[ui.pick(t("prompt_resolution"), options) - 1]

    if height != default:
        keep = ui.pick(
            t("prompt_resolution_save"),
            [t("resolution_save_once"), t("resolution_save_default")],
        )
        if keep == 2:
            try:
                persist_default(height)
            except OSError as ex:
                ui.print(paint(t("resolution_save_failed", error=ex), Colors.YELLOW))
    return height


def _row_for(rows: list[SizeEstimate], height: int | None) -> SizeEstimate:
    """The row for a cap; "unlimited" is judged by the unlimited row, not by 2160p."""
    wanted = UNLIMITED_HEIGHT if height is None else height
    for row in rows:
        if row.height == wanted:
            return row
    return rows[-1]


def _confirm_low_space(ui: UI, request: PreflightRequest, needed: int, free: int) -> bool:
    """Warn that the disk is too small; True to carry on, False to cancel."""
    ui.print(
        paint(
            t("disk_low_warning", needed=format_size(needed), free=format_size(free)),
            Colors.RED,
            Colors.BOLD,
        )
    )
    choice = ui.pick(t("disk_low_prompt"), [t("disk_low_continue"), t("disk_low_cancel")])
    if choice == 1:
        return True
    ui.print(paint(t("disk_low_cancelled"), Colors.YELLOW))
    append_log(
        request.log_path,
        f"\n[INFO {_stamp()}] Cancelled by the user: not enough free disk space "
        f"(needed about {needed} bytes, free {free} bytes)\n",
    )
    return False


def run_preflight(
    request: PreflightRequest,
    *,
    ui: UI,
    settings: AppSettings,
    persist_default: Callable[[int | None], None],
    measure: Callable[[str | None], float | None] = measure_speed,
    disk_free: Callable[[Path], int] = free_bytes,
) -> PreflightResult:
    """Show the estimate, ask the resolution cap and check the disk.

    Args:
        request: What is about to be downloaded.
        ui: Where to print and ask.
        settings: Saved settings (defaults, proxy, rate limit, waits, audio format).
        persist_default: Saves a cap as the default for the current mode; may raise OSError.
        measure: Measures the connection speed in bytes per second (None = unknown).
        disk_free: Returns the free bytes on a path's disk; may raise OSError.

    Returns:
        PROCEED with the cap to use, or CANCEL when the user declined to continue
        on too little free space.
    """
    compat = (
        request.mode == DownloadMode.VIDEO and request.mp4_profile == ProfileChoice.COMPATIBILITY
    )

    sizes: _Sizes | None = None
    free: int | None = None
    if request.is_playlist:
        free = _free_or_none(disk_free, request.base_dir)
        sizes = _show_estimate(request, settings, ui, measure, compat, free)
        if sizes is not None and sizes.videos.count == 0:
            if compat:
                return PreflightResult(PreflightAction.PROCEED, COMPAT_MAX_HEIGHT)
            return PreflightResult(PreflightAction.PROCEED, _default_height(request.mode, settings))

    height = _choose_height(request, settings, ui, persist_default, compat)

    if sizes is not None and free is not None:
        needed = _row_for(sizes.rows, height).required_bytes
        if free < needed and not _confirm_low_space(ui, request, needed, free):
            return PreflightResult(PreflightAction.CANCEL)

    return PreflightResult(PreflightAction.PROCEED, height)
