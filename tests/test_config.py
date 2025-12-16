"""
Tests for config module.
"""

import json
import tempfile
from pathlib import Path

import pytest

from ytdlp_app.config import (
    default_dirs,
    delete_config,
    load_config,
    normalize_user_path,
    save_config,
)


class TestNormalizeUserPath:
    """Tests for normalize_user_path function."""

    def test_expands_home_tilde(self):
        result = normalize_user_path("~/Documents")
        assert "~" not in str(result)
        assert result.is_absolute()

    def test_handles_plain_path(self):
        result = normalize_user_path("C:\\Users\\Test")
        assert result == Path("C:\\Users\\Test")

    def test_handles_forward_slashes(self):
        result = normalize_user_path("C:/Users/Test")
        assert result == Path("C:/Users/Test")


class TestDefaultDirs:
    """Tests for default_dirs function."""

    def test_returns_tuple(self):
        result = default_dirs()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_paths(self):
        videos, music = default_dirs()
        assert isinstance(videos, Path)
        assert isinstance(music, Path)

    def test_videos_in_home(self):
        videos, _ = default_dirs()
        assert Path.home() in videos.parents or videos.parent == Path.home()

    def test_music_in_home(self):
        _, music = default_dirs()
        assert Path.home() in music.parents or music.parent == Path.home()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_empty_dict_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"
            result = load_config(config_path)
            assert result == {}

    def test_loads_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text('{"key": "value"}', encoding="utf-8")
            result = load_config(config_path)
            assert result == {"key": "value"}

    def test_returns_empty_dict_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("not valid json", encoding="utf-8")
            result = load_config(config_path)
            assert result == {}


class TestSaveConfig:
    """Tests for save_config function."""

    def test_saves_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config_path, {"app": "test", "version": 1})
            
            content = config_path.read_text(encoding="utf-8")
            data = json.loads(content)
            assert data["app"] == "test"
            assert data["version"] == 1

    def test_pretty_prints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config_path, {"key": "value"})
            
            content = config_path.read_text(encoding="utf-8")
            # Should have newlines (pretty printed)
            assert "\n" in content


class TestDeleteConfig:
    """Tests for delete_config function."""

    def test_deletes_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            
            assert config_path.exists()
            delete_config(config_path)
            assert not config_path.exists()

    def test_handles_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"
            # Should not raise
            delete_config(config_path)
