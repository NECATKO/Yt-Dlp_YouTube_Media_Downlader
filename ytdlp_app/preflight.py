"""The two checks between choosing what to download and starting it.

1. guarded_listing wraps the one flat listing request, turning Ctrl+C, a ban
   signal and any other failure into a status the caller can act on.
2. confirm_disk_space warns when the target disk is nearly full and lets the user
   cancel. A disk that cannot be measured never blocks a download.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar

from .exceptions import PlaylistError
from .exec import find_ban_signal
from .i18n import t
from .logging_utils import Colors, append_log, log_error, paint

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .ui import UI

_T = TypeVar("_T")

#: Below this much free space a download is likely to fail part way: one 1080p video
#: needs its streams and the merged file on disk at the same time.
MIN_FREE_BYTES = 2 * 1024**3


def _stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def free_bytes(path: Path) -> int:
    """Free space, in bytes, on the disk that holds path."""
    return shutil.disk_usage(path).free


def format_size(num_bytes: float) -> str:
    """Format a byte count in 1024-based units, matching Windows Explorer."""
    value = float(max(num_bytes, 0))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


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


# -- phase 2: free space ----------------------------------------------------


def confirm_disk_space(
    ui: UI,
    base_dir: Path,
    log_path: Path | None,
    disk_free: Callable[[Path], int] = free_bytes,
) -> bool:
    """Warn when the disk holding ``base_dir`` is nearly full; False when the user cancels."""
    try:
        free = disk_free(base_dir)
    except OSError:
        return True
    if free >= MIN_FREE_BYTES:
        return True
    ui.print(
        paint(
            t("disk_low_warning", needed=format_size(MIN_FREE_BYTES), free=format_size(free)),
            Colors.RED,
            Colors.BOLD,
        )
    )
    if ui.pick(t("disk_low_prompt"), [t("disk_low_continue"), t("disk_low_cancel")]) == 1:
        return True
    ui.print(paint(t("disk_low_cancelled"), Colors.YELLOW))
    append_log(
        log_path,
        f"\n[INFO {_stamp()}] Cancelled by the user: not enough free disk space "
        f"(free {free} bytes)\n",
    )
    return False
