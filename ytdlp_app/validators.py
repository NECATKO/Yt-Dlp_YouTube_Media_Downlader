"""Input validation utilities for ytdlp_app."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .exceptions import ValidationError

# Supported video platforms
SUPPORTED_HOSTS = frozenset(
    {
        # YouTube
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "music.youtube.com",
        # Other popular platforms supported by yt-dlp
        "vimeo.com",
        "dailymotion.com",
        "twitch.tv",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "soundcloud.com",
        "bandcamp.com",
        "vk.com",
        "bilibili.com",
    }
)

# Pattern to detect common URL injection attempts
_DANGEROUS_PATTERN = re.compile(r"[;&|`$]")


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

    # Check for dangerous characters that could be shell injection
    if _DANGEROUS_PATTERN.search(url):
        return False

    # URL shouldn't start with dash (could be interpreted as flag)
    if url.startswith("-"):
        return False

    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def is_supported_url(url: str) -> bool:
    """
    Check if the URL is from a supported platform.

    Args:
        url: The URL string to validate.

    Returns:
        True if the URL is from a known supported platform, False otherwise.

    Note:
        yt-dlp supports many more sites, but this checks common ones.
        Returns True for unknown hosts as yt-dlp may still support them.
    """
    if not is_valid_url(url):
        return False

    try:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower()

        # Remove 'www.' prefix for comparison
        if host.startswith("www."):
            host = host[4:]

        # Check if it's a known supported host
        # Return True even for unknown hosts (yt-dlp supports many sites)
        return True
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

    if _DANGEROUS_PATTERN.search(url):
        raise ValidationError("URL contains potentially dangerous characters")

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
