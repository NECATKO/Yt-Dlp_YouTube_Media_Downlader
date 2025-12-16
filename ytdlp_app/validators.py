"""
URL validation utilities for yt-dlp-wrapper.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .exceptions import InvalidURLError

# Supported YouTube URL patterns
YOUTUBE_PATTERNS = [
    # Standard watch URLs
    r"^https?://(www\.)?youtube\.com/watch\?.*v=[\w-]+",
    # Shortened URLs
    r"^https?://youtu\.be/[\w-]+",
    # Playlist URLs
    r"^https?://(www\.)?youtube\.com/playlist\?.*list=[\w-]+",
    # Channel URLs
    r"^https?://(www\.)?youtube\.com/(c/|channel/|@)[\w-]+",
    # Embed URLs
    r"^https?://(www\.)?youtube\.com/embed/[\w-]+",
    # Shorts URLs
    r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
    # Live URLs
    r"^https?://(www\.)?youtube\.com/live/[\w-]+",
    # Music URLs
    r"^https?://music\.youtube\.com/watch\?.*v=[\w-]+",
]

# Compiled regex patterns for performance
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in YOUTUBE_PATTERNS]


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid URL with http/https scheme.
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def is_youtube_url(url: str) -> bool:
    """
    Check if a URL is a supported YouTube URL.
    """
    if not is_valid_url(url):
        return False
    return any(pattern.match(url) for pattern in _COMPILED_PATTERNS)


def validate_url(url: str) -> str:
    """
    Validate a URL and return it if valid, otherwise raise InvalidURLError.
    
    Args:
        url: The URL to validate
        
    Returns:
        The validated URL (stripped of whitespace)
        
    Raises:
        InvalidURLError: If the URL is invalid or unsupported
    """
    url = url.strip()
    
    if not url:
        raise InvalidURLError(url, "URL cannot be empty")
    
    if not is_valid_url(url):
        raise InvalidURLError(url, "Not a valid URL format")
    
    if not is_youtube_url(url):
        raise InvalidURLError(
            url, 
            "Not a recognized YouTube URL. Supported formats: "
            "youtube.com/watch, youtu.be, youtube.com/playlist, etc."
        )
    
    return url


def get_url_type(url: str) -> str:
    """
    Determine the type of YouTube URL.
    
    Returns:
        One of: 'video', 'playlist', 'channel', 'shorts', 'live', 'unknown'
    """
    url_lower = url.lower()
    
    if "/playlist?" in url_lower:
        return "playlist"
    if "/shorts/" in url_lower:
        return "shorts"
    if "/live/" in url_lower:
        return "live"
    if "/channel/" in url_lower or "/@" in url_lower or "/c/" in url_lower:
        return "channel"
    if "/watch?" in url_lower or "youtu.be/" in url_lower:
        return "video"
    
    return "unknown"
