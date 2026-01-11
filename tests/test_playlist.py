"""Tests for ytdlp_app.playlist module."""

from pathlib import Path

import pytest

from ytdlp_app.playlist import get_playlist_id, is_playlist_url, read_archive_ids


class TestIsPlaylistUrl:
    """Tests for is_playlist_url function."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/playlist?list=PLtest123",
            "https://www.youtube.com/watch?v=abc&list=PLtest123",
            "https://youtube.com/playlist?list=PLtest123",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ",
        ],
    )
    def test_returns_true_for_playlist_urls(self, url: str) -> None:
        """Test playlist URLs are detected correctly."""
        assert is_playlist_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/channel/UCtest123",
            "https://www.youtube.com/c/ChannelName",
            "https://www.youtube.com/user/username",
            "https://www.youtube.com/@ChannelHandle",
        ],
    )
    def test_returns_true_for_channel_urls(self, url: str) -> None:
        """Test channel URLs are treated as playlists."""
        assert is_playlist_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc123",
        ],
    )
    def test_returns_false_for_single_video_urls(self, url: str) -> None:
        """Test single video URLs are not detected as playlists."""
        assert is_playlist_url(url) is False


class TestGetPlaylistId:
    """Tests for get_playlist_id function."""

    def test_extracts_id_from_list_param(self) -> None:
        """Test extracting playlist ID from 'list' query param."""
        url = "https://www.youtube.com/playlist?list=PLtest123"
        assert get_playlist_id(url) == "PLtest123"

    def test_extracts_id_from_video_with_list(self) -> None:
        """Test extracting playlist ID from video URL with list param."""
        url = "https://www.youtube.com/watch?v=abc&list=PLtest456"
        assert get_playlist_id(url) == "PLtest456"

    def test_extracts_channel_id(self) -> None:
        """Test extracting channel ID from channel URL."""
        url = "https://www.youtube.com/channel/UCtest123"
        assert get_playlist_id(url) == "UCtest123"

    def test_extracts_handle_without_at(self) -> None:
        """Test extracting handle without @ prefix."""
        url = "https://www.youtube.com/@ChannelHandle"
        assert get_playlist_id(url) == "ChannelHandle"

    def test_returns_unknown_for_empty_path(self) -> None:
        """Test fallback for URLs without identifiable ID."""
        url = "https://www.youtube.com/"
        assert get_playlist_id(url) == "unknown_playlist"


class TestReadArchiveIds:
    """Tests for read_archive_ids function."""

    def test_returns_empty_set_for_missing_file(self, tmp_path: Path) -> None:
        """Test reading non-existent archive returns empty set."""
        archive_path = tmp_path / "nonexistent.txt"
        result = read_archive_ids(archive_path)
        assert result == set()

    def test_reads_video_ids_from_archive(self, tmp_path: Path) -> None:
        """Test reading video IDs from archive file."""
        archive_path = tmp_path / "archive.txt"
        archive_path.write_text(
            "youtube dQw4w9WgXcQ\nyoutube abc123def\nyoutube xyz789\n",
            encoding="utf-8",
        )

        result = read_archive_ids(archive_path)
        assert result == {"dQw4w9WgXcQ", "abc123def", "xyz789"}

    def test_ignores_empty_lines(self, tmp_path: Path) -> None:
        """Test empty lines are ignored."""
        archive_path = tmp_path / "archive.txt"
        archive_path.write_text(
            "youtube vid1\n\nyoutube vid2\n   \nyoutube vid3\n",
            encoding="utf-8",
        )

        result = read_archive_ids(archive_path)
        assert result == {"vid1", "vid2", "vid3"}

    def test_handles_different_formats(self, tmp_path: Path) -> None:
        """Test handling various archive line formats."""
        archive_path = tmp_path / "archive.txt"
        archive_path.write_text(
            "youtube vid1\nvimeo vid2\ndailymotion vid3\n",
            encoding="utf-8",
        )

        result = read_archive_ids(archive_path)
        # Should extract the last part (video ID) regardless of prefix
        assert result == {"vid1", "vid2", "vid3"}
