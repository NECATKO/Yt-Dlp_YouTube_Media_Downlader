"""Tests for ytdlp_app.config module."""

import json
from pathlib import Path
from typing import Any

from ytdlp_app.config import (
    default_dirs,
    delete_config,
    ensure_dirs_interactive,
    load_config,
    load_settings,
    normalize_user_path,
    save_config,
    save_settings,
    to_config_path,
)
from ytdlp_app.settings import AppSettings


class TestNormalizeUserPath:
    """Tests for normalize_user_path function."""

    def test_expands_home_tilde(self) -> None:
        """Test that ~ is expanded to user home directory."""
        result = normalize_user_path("~/Documents")
        assert result == Path.home() / "Documents"

    def test_handles_absolute_path(self, tmp_path: Path) -> None:
        """Test that absolute paths are preserved."""
        path_str = str(tmp_path / "test")
        result = normalize_user_path(path_str)
        assert result == tmp_path / "test"

    def test_handles_empty_string(self) -> None:
        """Test handling of empty string."""
        result = normalize_user_path("")
        assert result == Path()


class TestDefaultDirs:
    """Tests for default_dirs function."""

    def test_returns_videos_and_music_dirs(self) -> None:
        """Test that default directories are under user home."""
        videos, music = default_dirs()
        assert videos == Path.home() / "Videos"
        assert music == Path.home() / "Music"

    def test_returns_tuple_of_paths(self) -> None:
        """Test return type is tuple of Path objects."""
        result = default_dirs()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(p, Path) for p in result)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path) -> None:
        """Test loading non-existent config returns empty dict."""
        config_file = tmp_path / "nonexistent.json"
        result = load_config(config_file)
        assert result == {}

    def test_loads_valid_json(self, tmp_path: Path, sample_config: dict[str, Any]) -> None:
        """Test loading valid JSON config."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(sample_config), encoding="utf-8")

        result = load_config(config_file)
        assert result == sample_config

    def test_returns_empty_dict_for_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON returns empty dict."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json }", encoding="utf-8")

        result = load_config(config_file)
        assert result == {}


class TestSaveConfig:
    """Tests for save_config function."""

    def test_saves_config_to_file(self, tmp_path: Path, sample_config: dict[str, Any]) -> None:
        """Test config is saved as JSON."""
        config_file = tmp_path / "config.json"
        save_config(config_file, sample_config)

        assert config_file.exists()
        loaded = json.loads(config_file.read_text(encoding="utf-8"))
        assert loaded == sample_config

    def test_overwrites_existing_config(self, tmp_path: Path) -> None:
        """Test saving overwrites existing config."""
        config_file = tmp_path / "config.json"

        # Save initial config
        save_config(config_file, {"key": "old_value"})

        # Save new config
        new_config = {"key": "new_value"}
        save_config(config_file, new_config)

        loaded = json.loads(config_file.read_text(encoding="utf-8"))
        assert loaded == new_config

    def test_uses_utf8_encoding(self, tmp_path: Path) -> None:
        """Test config is saved with UTF-8 encoding."""
        config_file = tmp_path / "config.json"
        config_with_unicode = {"title": "Test Video"}
        save_config(config_file, config_with_unicode)

        content = config_file.read_text(encoding="utf-8")
        assert "Test Video" in content


class TestDeleteConfig:
    """Tests for delete_config function."""

    def test_deletes_existing_config(self, tmp_path: Path) -> None:
        """Test deleting an existing config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}", encoding="utf-8")
        assert config_file.exists()

        delete_config(config_file)
        assert not config_file.exists()

    def test_no_error_for_missing_file(self, tmp_path: Path) -> None:
        """Test deleting non-existent file doesn't raise error."""
        config_file = tmp_path / "nonexistent.json"
        # Should not raise
        delete_config(config_file)


class TestSettingsPersistence:
    """Tests for load_settings / save_settings."""

    def test_missing_key_yields_defaults(self) -> None:
        """A config written before settings existed must still load."""
        settings = load_settings({"app": "yt-dlp-downloader", "language": "tr"})
        assert settings.download.concurrent_fragments == 4
        assert settings.audio.audio_format == "mp3"

    def test_non_dict_value_yields_defaults(self) -> None:
        """A corrupt settings value must not break startup."""
        assert load_settings({"settings": "nonsense"}).download.proxy is None

    def test_roundtrip_through_file(self, tmp_path: Path) -> None:
        """Saved settings come back unchanged after a reload."""
        config_file = tmp_path / "config.json"
        cfg: dict[str, Any] = {"app": "yt-dlp-downloader", "language": "tr"}

        settings = AppSettings()
        settings.download.proxy = "http://proxy:8080"
        settings.audio.audio_format = "opus"
        save_settings(config_file, cfg, settings)

        reloaded = load_settings(load_config(config_file))
        assert reloaded.download.proxy == "http://proxy:8080"
        assert reloaded.audio.audio_format == "opus"

    def test_save_preserves_unrelated_keys(self, tmp_path: Path) -> None:
        """Saving settings must not drop the language or directories."""
        config_file = tmp_path / "config.json"
        cfg: dict[str, Any] = {"language": "tr", "videos_dir": "/videos"}

        save_settings(config_file, cfg, AppSettings())

        stored = load_config(config_file)
        assert stored["language"] == "tr"
        assert stored["videos_dir"] == "/videos"
        assert "settings" in stored


class TestPortablePaths:
    """Folders inside the app folder are stored relative so they move with it."""

    def test_relative_input_resolves_against_base(self, tmp_path: Path) -> None:
        assert normalize_user_path("downloads/Videos", tmp_path) == tmp_path / "downloads/Videos"

    def test_absolute_input_ignores_base(self, tmp_path: Path) -> None:
        other = tmp_path / "elsewhere"
        assert normalize_user_path(str(other), tmp_path / "app") == other

    def test_home_input_ignores_base(self, tmp_path: Path) -> None:
        assert normalize_user_path("~/Videos", tmp_path) == Path.home() / "Videos"

    def test_to_config_path_inside_is_relative_posix(self, tmp_path: Path) -> None:
        assert to_config_path(tmp_path / "downloads" / "Videos", tmp_path) == "downloads/Videos"

    def test_to_config_path_outside_is_absolute(self, tmp_path: Path) -> None:
        other = tmp_path / "other"
        assert to_config_path(other, tmp_path / "app") == str(other)

    def test_portable_defaults_live_next_to_the_app(self, tmp_path: Path) -> None:
        videos, music = default_dirs(tmp_path)
        assert videos == tmp_path / "downloads" / "Videos"
        assert music == tmp_path / "downloads" / "Music"


class _AcceptDefaultsUI:
    def __init__(self) -> None:
        self.printed: list[str] = []

    def print(self, text: str = "") -> None:
        self.printed.append(text)

    def ask_text(self, _prompt: str) -> str:
        return ""


class TestFirstRunFolders:
    def test_portable_first_run_stores_relative_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        cfg: dict[str, Any] = {}

        videos, music, new_cfg = ensure_dirs_interactive(
            _AcceptDefaultsUI(), cfg, config_file=config_file, app_name="x", portable=True
        )

        assert videos == tmp_path / "downloads" / "Videos"
        assert videos.is_dir() and music.is_dir()
        stored = json.loads(config_file.read_text(encoding="utf-8"))
        assert stored["videos_dir"] == "downloads/Videos"
        assert stored["music_dir"] == "downloads/Music"
        assert new_cfg["videos_dir"] == "downloads/Videos"

    def test_moved_folder_still_finds_its_downloads(self, tmp_path: Path) -> None:
        """The same relative config, read from a new location, follows the move."""
        moved = tmp_path / "usb" / "app"
        moved.mkdir(parents=True)
        cfg = {"videos_dir": "downloads/Videos", "music_dir": "downloads/Music"}

        videos, _music, _cfg = ensure_dirs_interactive(
            _AcceptDefaultsUI(), cfg, config_file=moved / "config.json", app_name="x"
        )

        assert videos == moved / "downloads" / "Videos"

    def test_installed_first_run_keeps_the_user_folders(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        config_file = tmp_path / "data" / "config.json"
        config_file.parent.mkdir()

        videos, _music, _cfg = ensure_dirs_interactive(
            _AcceptDefaultsUI(), {}, config_file=config_file, app_name="x"
        )

        assert videos == tmp_path / "home" / "Videos"
