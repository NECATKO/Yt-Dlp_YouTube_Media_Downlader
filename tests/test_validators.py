"""
Tests for URL validation module.
"""

import pytest

from ytdlp_app.exceptions import InvalidURLError
from ytdlp_app.validators import (
    get_url_type,
    is_valid_url,
    is_youtube_url,
    validate_url,
)


class TestIsValidUrl:
    """Tests for is_valid_url function."""

    def test_valid_http_url(self):
        assert is_valid_url("http://example.com") is True

    def test_valid_https_url(self):
        assert is_valid_url("https://example.com") is True

    def test_invalid_no_scheme(self):
        assert is_valid_url("example.com") is False

    def test_invalid_empty_string(self):
        assert is_valid_url("") is False

    def test_invalid_random_text(self):
        assert is_valid_url("not a url") is False

    def test_invalid_ftp_scheme(self):
        assert is_valid_url("ftp://example.com") is False


class TestIsYoutubeUrl:
    """Tests for is_youtube_url function."""

    def test_standard_watch_url(self):
        assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_short_url(self):
        assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ") is True

    def test_playlist_url(self):
        assert is_youtube_url("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf") is True

    def test_channel_url(self):
        assert is_youtube_url("https://www.youtube.com/@username") is True

    def test_shorts_url(self):
        assert is_youtube_url("https://www.youtube.com/shorts/abcd1234xyz") is True

    def test_embed_url(self):
        assert is_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ") is True

    def test_live_url(self):
        assert is_youtube_url("https://www.youtube.com/live/abc123") is True

    def test_music_url(self):
        assert is_youtube_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_invalid_other_site(self):
        assert is_youtube_url("https://vimeo.com/123456") is False

    def test_invalid_empty(self):
        assert is_youtube_url("") is False


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_youtube_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_url(url) == url

    def test_strips_whitespace(self):
        url = "  https://www.youtube.com/watch?v=dQw4w9WgXcQ  "
        assert validate_url(url) == url.strip()

    def test_raises_on_empty(self):
        with pytest.raises(InvalidURLError) as exc_info:
            validate_url("")
        assert "empty" in exc_info.value.reason.lower()

    def test_raises_on_invalid_format(self):
        with pytest.raises(InvalidURLError) as exc_info:
            validate_url("not-a-url")
        assert "valid URL format" in exc_info.value.reason

    def test_raises_on_non_youtube(self):
        with pytest.raises(InvalidURLError) as exc_info:
            validate_url("https://vimeo.com/123456")
        assert "YouTube" in exc_info.value.reason


class TestGetUrlType:
    """Tests for get_url_type function."""

    def test_video_url(self):
        assert get_url_type("https://www.youtube.com/watch?v=abc123") == "video"

    def test_short_url(self):
        assert get_url_type("https://youtu.be/abc123") == "video"

    def test_playlist_url(self):
        assert get_url_type("https://www.youtube.com/playlist?list=abc123") == "playlist"

    def test_shorts_url(self):
        assert get_url_type("https://www.youtube.com/shorts/abc123") == "shorts"

    def test_live_url(self):
        assert get_url_type("https://www.youtube.com/live/abc123") == "live"

    def test_channel_url(self):
        assert get_url_type("https://www.youtube.com/@username") == "channel"

    def test_unknown_url(self):
        assert get_url_type("https://www.youtube.com/feed") == "unknown"
