"""
Tests for playlist module.
"""

import pytest

from ytdlp_app.exceptions import PlaylistFetchError
from ytdlp_app.playlist import get_playlist_id, is_playlist_url


class TestIsPlaylistUrl:
    """Tests for is_playlist_url function."""

    def test_playlist_url_with_list_param(self):
        url = "https://www.youtube.com/watch?v=abc&list=PLtest123"
        assert is_playlist_url(url) is True

    def test_playlist_path(self):
        url = "https://www.youtube.com/playlist?list=PLtest123"
        assert is_playlist_url(url) is True

    def test_video_only_url(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert is_playlist_url(url) is False

    def test_short_url(self):
        url = "https://youtu.be/abc123"
        assert is_playlist_url(url) is False


class TestGetPlaylistId:
    """Tests for get_playlist_id function."""

    def test_extracts_playlist_id(self):
        url = "https://www.youtube.com/playlist?list=PLtest123"
        assert get_playlist_id(url) == "PLtest123"

    def test_extracts_from_video_with_list(self):
        url = "https://www.youtube.com/watch?v=abc&list=PLother456"
        assert get_playlist_id(url) == "PLother456"

    def test_returns_unknown_for_missing_list(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert get_playlist_id(url) == "unknown_playlist"
