"""
Tests for exceptions module.
"""

import pytest

from ytdlp_app.exceptions import (
    InvalidURLError,
    PlaylistFetchError,
    YtDlpWrapperError,
)


class TestYtDlpWrapperError:
    """Tests for base exception class."""

    def test_is_exception(self):
        assert issubclass(YtDlpWrapperError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(YtDlpWrapperError):
            raise YtDlpWrapperError("test error")


class TestPlaylistFetchError:
    """Tests for PlaylistFetchError exception."""

    def test_inheritance(self):
        assert issubclass(PlaylistFetchError, YtDlpWrapperError)

    def test_default_values(self):
        error = PlaylistFetchError("test message")
        assert error.returncode == -1
        assert error.stderr == ""
        assert str(error) == "test message"

    def test_custom_values(self):
        error = PlaylistFetchError(
            "Failed to fetch",
            returncode=1,
            stderr="Some error output"
        )
        assert error.returncode == 1
        assert error.stderr == "Some error output"

    def test_can_catch_as_base_type(self):
        with pytest.raises(YtDlpWrapperError):
            raise PlaylistFetchError("test")


class TestInvalidURLError:
    """Tests for InvalidURLError exception."""

    def test_inheritance(self):
        assert issubclass(InvalidURLError, YtDlpWrapperError)

    def test_basic_message(self):
        error = InvalidURLError("https://example.com")
        assert "Invalid URL" in str(error)
        assert "https://example.com" in str(error)
        assert error.url == "https://example.com"

    def test_with_reason(self):
        error = InvalidURLError("bad-url", reason="Not a YouTube URL")
        assert "Not a YouTube URL" in str(error)
        assert error.reason == "Not a YouTube URL"

    def test_empty_reason(self):
        error = InvalidURLError("test-url", reason="")
        assert error.reason == ""
        # Should not have extra parentheses when reason is empty
        assert "()" not in str(error)
