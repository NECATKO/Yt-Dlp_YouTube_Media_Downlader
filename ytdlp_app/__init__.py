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

__version__ = "0.3.0"

__all__ = [
    "CommandExecutionError",
    "ConfigurationError",
    "DownloadError",
    "NetworkError",
    "PlaylistError",
    "ValidationError",
    # Exceptions
    "YtDlpWrapperError",
    # Version
    "__version__",
    # Validators
    "is_valid_url",
    "is_youtube_url",
    # Main entry point
    "run",
    "validate_url",
]
