"""Tests for ytdlp_app.models module."""

from pathlib import Path

from ytdlp_app.models import (
    AppPaths,
    DownloadPlan,
    PlaylistEntry,
    ProfileChoice,
    UserConfig,
)


class TestAppPaths:
    """Tests for AppPaths dataclass."""

    def test_app_paths_creation(self, tmp_path: Path) -> None:
        """Test AppPaths can be created with valid paths."""
        paths = AppPaths(
            app_dir=tmp_path,
            config_file=tmp_path / "config.json",
            logs_dir=tmp_path / "logs",
            archives_dir=tmp_path / "archives",
        )
        assert paths.app_dir == tmp_path
        assert paths.config_file == tmp_path / "config.json"
        assert paths.logs_dir == tmp_path / "logs"
        assert paths.archives_dir == tmp_path / "archives"

    def test_app_paths_is_frozen(self, tmp_path: Path) -> None:
        """Test AppPaths is immutable."""
        paths = AppPaths(
            app_dir=tmp_path,
            config_file=tmp_path / "config.json",
            logs_dir=tmp_path / "logs",
            archives_dir=tmp_path / "archives",
        )
        try:
            paths.app_dir = tmp_path / "new"  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass  # Expected behavior


class TestUserConfig:
    """Tests for UserConfig dataclass."""

    def test_user_config_creation(self, tmp_path: Path) -> None:
        """Test UserConfig can be created with valid data."""
        config = UserConfig(
            app="yt-dlp-downloader",
            videos_dir=tmp_path / "Videos",
            music_dir=tmp_path / "Music",
            saved_at="2025-01-01T00:00:00",
        )
        assert config.app == "yt-dlp-downloader"
        assert config.videos_dir == tmp_path / "Videos"
        assert config.music_dir == tmp_path / "Music"
        assert config.saved_at == "2025-01-01T00:00:00"

    def test_user_config_optional_saved_at(self, tmp_path: Path) -> None:
        """Test UserConfig saved_at is optional."""
        config = UserConfig(
            app="yt-dlp-downloader",
            videos_dir=tmp_path / "Videos",
            music_dir=tmp_path / "Music",
        )
        assert config.saved_at is None


class TestPlaylistEntry:
    """Tests for PlaylistEntry dataclass."""

    def test_playlist_entry_creation(self) -> None:
        """Test PlaylistEntry can be created with valid data."""
        entry = PlaylistEntry(
            playlist_index=1,
            id="dQw4w9WgXcQ",
            title="Test Video",
            watch_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        assert entry.playlist_index == 1
        assert entry.id == "dQw4w9WgXcQ"
        assert entry.title == "Test Video"
        assert entry.watch_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class TestDownloadPlan:
    """Tests for DownloadPlan dataclass."""

    def test_download_plan_mp4_single(self, tmp_path: Path) -> None:
        """Test DownloadPlan for single MP4 download."""
        plan = DownloadPlan(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            mode="mp4",
            is_playlist=False,
            playlist_id=None,
            mp4_profile=ProfileChoice.COMPATIBILITY,
            remux_container=None,
            base_dir=tmp_path / "Videos",
            output_template="%(title)s.%(ext)s",
            archive_path=tmp_path / "archives" / "single_videos_mp4.txt",
            log_path=tmp_path / "logs" / "test.log",
            js_args=["--js-runtime", "deno"],
        )
        assert plan.mode == "mp4"
        assert plan.is_playlist is False
        assert plan.mp4_profile == ProfileChoice.COMPATIBILITY

    def test_download_plan_mp3_playlist(self, tmp_path: Path) -> None:
        """Test DownloadPlan for playlist MP3 download."""
        plan = DownloadPlan(
            url="https://www.youtube.com/playlist?list=PLtest",
            mode="mp3",
            is_playlist=True,
            playlist_id="PLtest",
            mp4_profile=None,
            remux_container=None,
            base_dir=tmp_path / "Music",
            output_template="%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s",
            archive_path=tmp_path / "archives" / "playlist_PLtest_mp3.txt",
            log_path=tmp_path / "logs" / "test.log",
            js_args=[],
        )
        assert plan.mode == "mp3"
        assert plan.is_playlist is True
        assert plan.playlist_id == "PLtest"
