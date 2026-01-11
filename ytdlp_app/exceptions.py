"""Custom exceptions for ytdlp_app."""

from __future__ import annotations


class YtDlpWrapperError(Exception):
    """Base exception for all ytdlp_app errors."""

    pass


class ConfigurationError(YtDlpWrapperError):
    """Raised when configuration is invalid or missing."""

    pass


class CommandExecutionError(YtDlpWrapperError):
    """Raised when a subprocess command fails to execute."""

    def __init__(
        self,
        message: str,
        *,
        command: list[str] | None = None,
        return_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.return_code = return_code
        self.stderr = stderr


class NetworkError(YtDlpWrapperError):
    """Raised when network operations fail."""

    pass


class ValidationError(YtDlpWrapperError):
    """Raised when input validation fails."""

    pass


class PlaylistError(YtDlpWrapperError):
    """Raised when playlist operations fail."""

    pass


class DownloadError(YtDlpWrapperError):
    """Raised when a download operation fails."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.reason = reason
