"""Where a download goes: the output folder, the file name template and the archive file.

Split out of the interactive session because none of it needs a UI, and because it is
what decides which files a later run will treat as already done. Every archive file name
is built from a sanitised identifier and checked to stay inside the archives folder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .exceptions import ValidationError
from .models import DownloadMode
from .playlist import safe_archive_token

if TYPE_CHECKING:
    from pathlib import Path

    from .models import UserConfig
    from .settings import AppSettings

#: The suffix each mode's archive files carry. Audio keeps "mp3" whatever format is chosen:
#: the archive says which ids are done, not in which format, and renaming it per format
#: would hide the records of everything already downloaded.
_MODE_SUFFIX = {
    DownloadMode.VIDEO: "mp4",
    DownloadMode.AUDIO: "mp3",
    DownloadMode.ARCHIVE: "archive",
}

_SINGLE_NAMES = {
    DownloadMode.VIDEO: "single_videos_mp4.txt",
    DownloadMode.AUDIO: "single_audios_mp3.txt",
    DownloadMode.ARCHIVE: "single_videos_archive.txt",
}


@dataclass(frozen=True, slots=True)
class Targets:
    """Where a run writes.

    Attributes:
        base_dir: The folder the downloads go under.
        output_template: yt-dlp's ``-o`` value (base_dir joined with the template).
        archive_path: The download archive file.
    """

    base_dir: Path
    output_template: str
    archive_path: Path


def archive_file_name(
    mode: DownloadMode, *, is_playlist: bool, is_channel: bool, key: str | None
) -> str:
    """The archive file name for a run.

    Args:
        mode: Video, audio or archive mode.
        is_playlist: Whether a playlist or channel is being downloaded.
        is_channel: Whether that is a channel (keyed by channel id) rather than a playlist.
        key: The playlist id or the channel id; ignored for single items.
    """
    if not is_playlist:
        return _SINGLE_NAMES[mode]
    kind = "channel" if is_channel else "playlist"
    return f"{kind}_{safe_archive_token(key or 'unknown')}_{_MODE_SUFFIX[mode]}.txt"


def ensure_within(root: Path, candidate: Path) -> Path:
    """Return ``candidate`` if, once normalised, it lies inside ``root`` (never equal to it).

    ``..`` segments and symlinks are resolved first, so a name that only looks harmless
    cannot write elsewhere.

    Raises:
        ValidationError: The candidate would end up outside the root.
    """
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ValidationError(f"{candidate} is not inside {root}")
    return candidate


def plan_targets(
    *,
    mode: DownloadMode,
    is_playlist: bool,
    is_channel: bool,
    key: str | None,
    config: UserConfig,
    settings: AppSettings,
    archives_dir: Path,
    legacy_key: str | None = None,
) -> Targets:
    """Work out the output folder, template and archive file for a run.

    Args:
        mode: Video, audio or archive mode.
        is_playlist: Whether a playlist or channel is being downloaded.
        is_channel: Whether it is a channel.
        key: The channel id, or the playlist id.
        config: The user's download folders.
        settings: The output templates.
        archives_dir: The folder holding every download archive.
        legacy_key: For a channel in video/audio mode, the identifier older versions
            named its archive by (its handle). If that file exists and the id-keyed one
            does not yet, it keeps being used, so an upgrade does not forget what was
            downloaded.

    Raises:
        ValidationError: The archive file would not lie inside ``archives_dir``.
    """
    templates = settings.output
    if mode == DownloadMode.ARCHIVE:
        base_dir = config.videos_dir / "yt-dlp"
        template = templates.archive_template
    elif mode == DownloadMode.VIDEO:
        if is_playlist:
            base_dir, template = config.videos_dir / "yt-dlp", templates.playlist_video_template
        else:
            base_dir = config.videos_dir / "Downloaded Videos"
            template = templates.single_video_template
    elif is_playlist:
        base_dir, template = config.music_dir / "yt-dlp", templates.playlist_audio_template
    else:
        base_dir = config.music_dir / "Downloaded Music"
        template = templates.single_audio_template

    name = archive_file_name(mode, is_playlist=is_playlist, is_channel=is_channel, key=key)
    archive_path = ensure_within(archives_dir, archives_dir / name)

    if is_channel and mode != DownloadMode.ARCHIVE and legacy_key and not archive_path.exists():
        legacy_name = archive_file_name(mode, is_playlist=True, is_channel=False, key=legacy_key)
        legacy = ensure_within(archives_dir, archives_dir / legacy_name)
        if legacy.exists():
            archive_path = legacy

    return Targets(base_dir, str(base_dir / template), archive_path)
