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

# Single source of truth for the version. pyproject.toml reads this attribute
# statically. app_version.txt holds the same version in git-tag form ("v" prefix)
# because the updaters compare it against the GitHub release tag_name; CI enforces
# that all three agree.
__version__ = "0.3.1"

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
