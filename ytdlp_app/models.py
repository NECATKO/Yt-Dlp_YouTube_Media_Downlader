"""Data models for ytdlp_app.

This module defines the core data structures used throughout the application,
including configuration containers, playlist entries, and download plans.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

#: Type alias for download mode - either video (mp4) or audio (mp3).
Mode = Literal["mp4", "mp3"]


class CaptureRunner(Protocol):
    """Protocol for functions that execute commands and capture output.

    This protocol defines the interface for command execution functions,
    allowing for dependency injection and easier testing.
    """

    def __call__(self, cmd: list[str]) -> tuple[int, str, str]:
        """Execute a command and return the result.

        Args:
            cmd: The command and arguments to execute.

        Returns:
            A tuple of (return_code, stdout, stderr).
        """
        ...


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Application directory paths.

    Immutable container for all paths used by the application,
    including configuration, logs, and download archives.

    Attributes:
        app_dir: Root directory of the application.
        config_file: Path to the configuration JSON file.
        logs_dir: Directory for session log files.
        archives_dir: Directory for download archive files.
    """

    app_dir: Path
    config_file: Path
    logs_dir: Path
    archives_dir: Path


@dataclass(frozen=True, slots=True)
class UserConfig:
    """User configuration settings.

    Stores user preferences for download directories and other settings.

    Attributes:
        app: Application identifier string.
        videos_dir: Directory for video downloads.
        music_dir: Directory for audio downloads.
        saved_at: ISO timestamp when config was saved, or None.
    """

    app: str
    videos_dir: Path
    music_dir: Path
    saved_at: str | None = None


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    """A single entry in a playlist.

    Represents one video/audio item within a playlist, with its
    position, identifier, and watch URL.

    Attributes:
        playlist_index: 1-based position in the playlist.
        id: Video/audio identifier (e.g., YouTube video ID).
        title: Display title of the entry.
        watch_url: Direct URL to watch/play this entry.
    """

    playlist_index: int
    id: str
    title: str
    watch_url: str


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    """Complete plan for a download operation.

    Contains all information needed to execute a download, including
    URL, mode, output paths, and command-line arguments.

    Attributes:
        url: The URL to download from.
        mode: Download mode ('mp4' for video, 'mp3' for audio).
        is_playlist: Whether the URL is a playlist.
        playlist_id: Playlist identifier, or None for single items.
        mp4_profile: MP4 quality profile (1=compatibility, 2=quality), or None.
        remux_container: Container choice for quality mode (1=MKV, 2=MP4), or None.
        base_dir: Base directory for downloaded files.
        output_template: yt-dlp output template string.
        archive_path: Path to the download archive file.
        log_path: Path to the session log file.
        playlist_flag: yt-dlp playlist flag ('--yes-playlist' or '--no-playlist').
        js_args: Arguments for JavaScript runtime configuration.
        stability_args: Arguments for retry and stability settings.
        post_args: Arguments for post-processing (metadata, thumbnails).
        common_args: Common arguments including output and archive settings.
    """

    url: str
    mode: Mode
    is_playlist: bool
    playlist_id: str | None
    mp4_profile: int | None
    remux_container: int | None
    base_dir: Path
    output_template: str
    archive_path: Path
    log_path: Path
    playlist_flag: str
    js_args: list[str]
    stability_args: list[str]
    post_args: list[str]
    common_args: list[str]
