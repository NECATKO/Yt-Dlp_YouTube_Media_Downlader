"""Tests for ytdlp_app.playlist module."""

import json
from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.playlist import (
    channel_id_from_url,
    get_playlist_id,
    is_channel_url,
    is_playlist_url,
    read_archive_ids,
    resolve_channel_id,
    safe_archive_token,
)


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


class TestIsChannelUrl:
    """Archive mode treats these as a whole channel (nested tab playlists)."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@ChannelHandle",
            "https://www.youtube.com/@ChannelHandle/",
            "https://www.youtube.com/@ChannelHandle/videos",
            "https://www.youtube.com/@ChannelHandle/shorts",
            "https://www.youtube.com/@ChannelHandle/streams",
            "https://youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
            "https://m.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos",
            "https://www.youtube.com/c/ChannelName",
            "https://www.youtube.com/user/username",
        ],
    )
    def test_detects_channels_and_their_tabs(self, url: str) -> None:
        assert is_channel_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc123",
            "https://www.youtube.com/playlist?list=PLtest123",
            # Redirects to the current live stream: a single video.
            "https://www.youtube.com/@ChannelHandle/live",
            # Right path shape, wrong site.
            "https://example.com/@ChannelHandle",
        ],
    )
    def test_rejects_everything_else(self, url: str) -> None:
        assert is_channel_url(url) is False

    def test_every_channel_url_is_also_a_playlist_url(self) -> None:
        """The session relies on this to download with --yes-playlist."""
        assert is_playlist_url("https://www.youtube.com/@ChannelHandle/videos") is True


class TestChannelIdFromUrl:
    def test_reads_the_id_from_a_channel_url(self) -> None:
        url = "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos"
        assert channel_id_from_url(url) == "UCuAXFkgsw1L7xaCfnd5JJOw"

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@ChannelHandle",
            "https://www.youtube.com/channel/not-a-channel-id",
        ],
    )
    def test_returns_none_without_a_real_id(self, url: str) -> None:
        assert channel_id_from_url(url) is None


CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"


def _nested_channel_json(top_level_id: bool = True) -> dict[str, Any]:
    """What yt-dlp --flat-playlist -J returns for a bare channel URL: the
    Videos/Shorts/Live tabs as nested playlist entries."""
    data: dict[str, Any] = {
        "_type": "playlist",
        "title": "Channel Name",
        "entries": [
            {
                "_type": "url",
                "ie_key": "YoutubeTab",
                "url": "https://www.youtube.com/@ChannelHandle/videos",
                "title": "Channel Name - Videos",
                "channel_id": CHANNEL_ID,
            },
            {
                "_type": "url",
                "ie_key": "YoutubeTab",
                "url": "https://www.youtube.com/@ChannelHandle/shorts",
                "title": "Channel Name - Shorts",
            },
        ],
    }
    if top_level_id:
        data["id"] = CHANNEL_ID
        data["channel_id"] = CHANNEL_ID
    return data


class FakeRunner:
    def __init__(self, rc: int = 0, out: str = "", err: str = "") -> None:
        self.rc, self.out, self.err = rc, out, err
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> tuple[int, str, str]:
        self.calls.append(cmd)
        return self.rc, self.out, self.err


class TestResolveChannelId:
    URL = "https://www.youtube.com/@ChannelHandle"

    def test_reads_the_top_level_channel_id(self) -> None:
        runner = FakeRunner(out=json.dumps(_nested_channel_json()))
        assert resolve_channel_id(self.URL, [], runner) == CHANNEL_ID

    def test_falls_back_to_the_nested_tab_entries(self) -> None:
        runner = FakeRunner(out=json.dumps(_nested_channel_json(top_level_id=False)))
        assert resolve_channel_id(self.URL, [], runner) == CHANNEL_ID

    def test_lookup_is_flat_limited_and_uses_the_extra_args(self) -> None:
        runner = FakeRunner(out=json.dumps(_nested_channel_json()))
        resolve_channel_id(self.URL, ["--proxy", "http://p:1"], runner)

        (cmd,) = runner.calls
        assert "--flat-playlist" in cmd
        assert cmd[cmd.index("--playlist-items") + 1] == "1"
        assert cmd[cmd.index("--proxy") + 1] == "http://p:1"

    def test_channel_url_with_id_needs_no_request(self) -> None:
        runner = FakeRunner(rc=1)
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}"
        assert resolve_channel_id(url, [], runner) == CHANNEL_ID
        assert runner.calls == []

    def test_failure_raises_with_stderr(self) -> None:
        err = "ERROR: [youtube:tab] x: HTTP Error 429: Too Many Requests"
        with pytest.raises(PlaylistError, match="429"):
            resolve_channel_id(self.URL, [], FakeRunner(rc=1, err=err))

    def test_json_without_a_channel_id_raises(self) -> None:
        runner = FakeRunner(out=json.dumps({"id": "not-a-channel", "entries": []}))
        with pytest.raises(PlaylistError):
            resolve_channel_id(self.URL, [], runner)

    def test_ctrl_c_is_not_swallowed(self) -> None:
        with pytest.raises(KeyboardInterrupt):
            resolve_channel_id(self.URL, [], FakeRunner(rc=130))


class TestSafeArchiveToken:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (CHANNEL_ID, CHANNEL_ID),
            ("Some Handle/..\\x", "Some_Handle_.._x"),
            ("", "unknown"),
        ],
    )
    def test_sanitizes(self, value: str, expected: str) -> None:
        assert safe_archive_token(value) == expected
