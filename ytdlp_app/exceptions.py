"""
Custom exceptions for yt-dlp-wrapper application.
"""

from __future__ import annotations


class YtDlpWrapperError(Exception):
    """Base exception for all yt-dlp-wrapper errors."""

    pass


class PlaylistFetchError(YtDlpWrapperError):
    """Raised when fetching playlist metadata fails."""

    def __init__(
        self, message: str, returncode: int = -1, stderr: str = ""
    ) -> None:
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


class InvalidURLError(YtDlpWrapperError):
    """Raised when a URL is invalid or unsupported."""

    def __init__(self, url: str, reason: str = "") -> None:
        self.url = url
        self.reason = reason
        message = f"Invalid URL: {url}"
        if reason:
            message += f" ({reason})"
        super().__init__(message)
