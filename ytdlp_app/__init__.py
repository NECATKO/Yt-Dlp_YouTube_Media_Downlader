"""
ytdlp_app - A portable YouTube downloader wrapping yt-dlp.

This package provides a user-friendly console interface for downloading
videos and audio from YouTube and other supported platforms.
"""

from .app import run
from .exceptions import (
    CommandExecutionError,
    ConfigurationError,
    DownloadError,
    NetworkError,
    PlaylistError,
    ValidationError,
    YtDlpWrapperError,
)
from .validators import is_valid_url, is_youtube_url, validate_url

__version__ = "0.1.0"

__all__ = [
    # Main entry point
    "run",
    # Version
    "__version__",
    # Exceptions
    "YtDlpWrapperError",
    "CommandExecutionError",
    "ConfigurationError",
    "DownloadError",
    "NetworkError",
    "PlaylistError",
    "ValidationError",
    # Validators
    "is_valid_url",
    "is_youtube_url",
    "validate_url",
]
