"""Test configuration and fixtures for ytdlp_app tests."""

import shutil
from collections.abc import Iterator
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


@pytest.fixture(autouse=True)
def _no_speed_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session tests must never reach the network for a speed measurement."""
    import ytdlp_app.session as session_module  # noqa: PLC0415

    monkeypatch.setattr(session_module, "measure_speed", lambda _proxy, cancel=None: None)


@pytest.fixture
def windows_scratch() -> Iterator[Path]:
    """A fresh folder on the Windows file system, removed afterwards (see tests/windows.py)."""
    from tests.windows import make_scratch  # noqa: PLC0415

    folder = make_scratch()
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)
