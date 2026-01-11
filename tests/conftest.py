"""Test configuration and fixtures for ytdlp_app tests."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Return a sample configuration dictionary."""
    return {
        "app": "yt-dlp-downloader",
        "videos_dir": "C:\\Users\\Test\\Videos",
        "music_dir": "C:\\Users\\Test\\Music",
        "saved_at": "2025-01-01T00:00:00",
        "language": "en",
    }


@pytest.fixture
def sample_playlist_json() -> dict[str, Any]:
    """Return sample playlist JSON data from yt-dlp."""
    return {
        "id": "PLtest123",
        "title": "Test Playlist",
        "entries": [
            {"id": "vid1", "title": "Video 1", "url": "https://youtube.com/watch?v=vid1"},
            {"id": "vid2", "title": "Video 2", "url": "https://youtube.com/watch?v=vid2"},
            {"id": "vid3", "title": "Video 3", "url": "https://youtube.com/watch?v=vid3"},
        ],
    }
