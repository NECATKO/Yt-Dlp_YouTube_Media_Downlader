"""Tests for ytdlp_app.validators module."""

import pytest

from ytdlp_app.exceptions import ValidationError
from ytdlp_app.validators import (
    is_valid_url,
    is_youtube_url,
    validate_path_string,
    validate_url,
)


class TestIsValidUrl:
    """Tests for is_valid_url function."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://example.com/video",
            "https://vimeo.com/123456",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=abc&list=PLtest123&index=2",
        ],
    )
    def test_returns_true_for_valid_urls(self, url: str) -> None:
        """Test valid HTTP/HTTPS URLs are accepted."""
        assert is_valid_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not a url",
            "ftp://example.com/file",
            "file:///etc/passwd",
            "-v https://example.com",
            "https://example.com; rm -rf /",
            "https://example.com | cat /etc/passwd",
        ],
    )
    def test_returns_false_for_invalid_urls(self, url: str) -> None:
        """Test invalid or dangerous URLs are rejected."""
        assert is_valid_url(url) is False

    def test_returns_false_for_none(self) -> None:
        """Test None input returns False."""
        assert is_valid_url(None) is False  # type: ignore[arg-type]

    def test_returns_false_for_non_string(self) -> None:
        """Test non-string input returns False."""
        assert is_valid_url(123) is False  # type: ignore[arg-type]


class TestIsYoutubeUrl:
    """Tests for is_youtube_url function."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        ],
    )
    def test_returns_true_for_youtube_urls(self, url: str) -> None:
        """Test YouTube URLs are detected."""
        assert is_youtube_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://vimeo.com/123456",
            "https://dailymotion.com/video/abc",
            "https://twitter.com/user/status/123",
            "https://example.com/youtube.com",
        ],
    )
    def test_returns_false_for_non_youtube_urls(self, url: str) -> None:
        """Test non-YouTube URLs are not detected as YouTube."""
        assert is_youtube_url(url) is False


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_returns_sanitized_url(self) -> None:
        """Test valid URL is returned after sanitization."""
        url = "  https://www.youtube.com/watch?v=abc  "
        result = validate_url(url)
        assert result == "https://www.youtube.com/watch?v=abc"

    def test_raises_for_empty_url(self) -> None:
        """Test empty URL raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_url("")

    def test_raises_for_dash_prefix(self) -> None:
        """Test URL starting with dash raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot start with"):
            validate_url("-v https://example.com")

    def test_accepts_standard_playlist_query(self) -> None:
        """Query separators are URL syntax, not shell syntax."""
        url = "https://www.youtube.com/watch?v=abc&list=PLtest123&index=2"
        assert validate_url(url) == url

    def test_raises_for_unescaped_whitespace(self) -> None:
        """Spaces and control characters must be encoded before use."""
        with pytest.raises(ValidationError, match="whitespace or control"):
            validate_url("https://example.com/video name")


class TestValidatePathString:
    """Tests for validate_path_string function."""

    def test_returns_validated_path(self) -> None:
        """Test valid path is returned."""
        path = "  /home/user/downloads  "
        result = validate_path_string(path)
        assert result == "/home/user/downloads"

    def test_raises_for_empty_path(self) -> None:
        """Test empty path raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_path_string("")

    def test_raises_for_null_bytes(self) -> None:
        """Test path with null bytes raises ValidationError."""
        with pytest.raises(ValidationError, match="null bytes"):
            validate_path_string("/home/user\x00/downloads")
