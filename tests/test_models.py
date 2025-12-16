"""
Tests for models module.
"""

from pathlib import Path

import pytest

from ytdlp_app.models import AppPaths, DownloadPlan, Mode, PlaylistEntry, UserConfig


class TestAppPaths:
    """Tests for AppPaths dataclass."""

    def test_create_instance(self):
        paths = AppPaths(
            app_dir=Path("/app"),
            config_file=Path("/app/config.json"),
            logs_dir=Path("/app/logs"),
            archives_dir=Path("/app/archives"),
        )
        assert paths.app_dir == Path("/app")
        assert paths.config_file == Path("/app/config.json")
        assert paths.logs_dir == Path("/app/logs")
        assert paths.archives_dir == Path("/app/archives")

    def test_is_frozen(self):
        paths = AppPaths(
            app_dir=Path("/app"),
            config_file=Path("/app/config.json"),
            logs_dir=Path("/app/logs"),
            archives_dir=Path("/app/archives"),
        )
        with pytest.raises(AttributeError):
            paths.app_dir = Path("/other")


class TestUserConfig:
    """Tests for UserConfig dataclass."""

    def test_create_instance(self):
        config = UserConfig(
            app="test-app",
            videos_dir=Path("/videos"),
            music_dir=Path("/music"),
            saved_at="2025-01-01",
        )
        assert config.app == "test-app"
        assert config.videos_dir == Path("/videos")
        assert config.music_dir == Path("/music")
        assert config.saved_at == "2025-01-01"

    def test_saved_at_default(self):
        config = UserConfig(
            app="test-app",
            videos_dir=Path("/videos"),
            music_dir=Path("/music"),
        )
        assert config.saved_at is None


class TestPlaylistEntry:
    """Tests for PlaylistEntry dataclass."""

    def test_create_instance(self):
        entry = PlaylistEntry(
            playlist_index=1,
            id="abc123",
            title="Test Video",
            watch_url="https://www.youtube.com/watch?v=abc123",
        )
        assert entry.playlist_index == 1
        assert entry.id == "abc123"
        assert entry.title == "Test Video"
        assert entry.watch_url == "https://www.youtube.com/watch?v=abc123"


class TestDownloadPlan:
    """Tests for DownloadPlan dataclass."""

    def test_create_mp4_instance(self):
        plan = DownloadPlan(
            url="https://youtube.com/watch?v=test",
            mode="mp4",
            is_playlist=False,
            playlist_id=None,
            mp4_profile=1,
            remux_container=None,
            base_dir=Path("/downloads"),
            output_template="/downloads/%(title)s.%(ext)s",
            archive_path=Path("/archives/single.txt"),
            log_path=Path("/logs/log.txt"),
            playlist_flag="--no-playlist",
            js_args=["--js-runtime", "deno"],
            stability_args=["--retries", "3"],
            post_args=["--embed-metadata"],
            common_args=["-o", "template"],
        )
        assert plan.mode == "mp4"
        assert plan.is_playlist is False
        assert plan.mp4_profile == 1

    def test_create_mp3_instance(self):
        plan = DownloadPlan(
            url="https://youtube.com/watch?v=test",
            mode="mp3",
            is_playlist=True,
            playlist_id="PLtest123",
            mp4_profile=None,
            remux_container=None,
            base_dir=Path("/music"),
            output_template="/music/%(title)s.%(ext)s",
            archive_path=Path("/archives/playlist.txt"),
            log_path=Path("/logs/log.txt"),
            playlist_flag="--yes-playlist",
            js_args=[],
            stability_args=[],
            post_args=[],
            common_args=[],
        )
        assert plan.mode == "mp3"
        assert plan.is_playlist is True
        assert plan.playlist_id == "PLtest123"


class TestModeType:
    """Tests for Mode type alias."""

    def test_mp4_is_valid(self):
        mode: Mode = "mp4"
        assert mode == "mp4"

    def test_mp3_is_valid(self):
        mode: Mode = "mp3"
        assert mode == "mp3"
