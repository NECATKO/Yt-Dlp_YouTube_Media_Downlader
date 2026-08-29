"""Input validation utilities for ytdlp_app."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .exceptions import ValidationError

# Raw whitespace and control characters are never valid inside an HTTP URL.
# Shell metacharacters such as "&" are deliberately allowed: commands are
# executed with shell=False, and "&" is required by ordinary query strings.
_INVALID_URL_CHAR_PATTERN = re.compile(r"[\x00-\x20\x7f]")


def is_valid_url(url: str) -> bool:
    """
    Check if the URL is a valid HTTP/HTTPS URL.

    Args:
        url: The URL string to validate.

    Returns:
        True if the URL is valid, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    # Spaces must be percent-encoded, and control characters are never safe.
    if _INVALID_URL_CHAR_PATTERN.search(url):
        return False

    # URL shouldn't start with dash (could be interpreted as flag)
    if url.startswith("-"):
        return False

    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_url(url: str) -> str:
    """
    Validate and sanitize a URL for use with yt-dlp.

    Args:
        url: The URL string to validate.

    Returns:
        The sanitized URL string.

    Raises:
        ValidationError: If the URL is invalid or potentially dangerous.
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    url = url.strip()

    if url.startswith("-"):
        raise ValidationError("URL cannot start with '-' (potential command injection)")

    if _INVALID_URL_CHAR_PATTERN.search(url):
        raise ValidationError("URL contains unescaped whitespace or control characters")

    if not is_valid_url(url):
        raise ValidationError(f"Invalid URL format: {url}")

    return url


def is_youtube_url(url: str) -> bool:
    """
    Check if the URL is a YouTube URL.

    Args:
        url: The URL string to check.

    Returns:
        True if the URL is a YouTube URL, False otherwise.
    """
    if not is_valid_url(url):
        return False

    try:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower()
        youtube_hosts = {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "music.youtube.com",
        }
        return host in youtube_hosts
    except Exception:
        return False


def validate_path_string(path: str) -> str:
    """
    Validate a path string for basic safety.

    Args:
        path: The path string to validate.

    Returns:
        The validated path string.

    Raises:
        ValidationError: If the path is invalid.
    """
    if not path:
        raise ValidationError("Path cannot be empty")

    path = path.strip()

    # Check for null bytes
    if "\x00" in path:
        raise ValidationError("Path cannot contain null bytes")

    return path
