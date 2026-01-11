"""Tests for ytdlp_app.settings module."""

import pytest

from ytdlp_app.settings import (
    AppSettings,
    AudioSettings,
    DownloadSettings,
    OutputSettings,
    VideoSettings,
)


class TestDownloadSettings:
    """Tests for DownloadSettings dataclass."""

    def test_default_values(self) -> None:
        """Test default settings values."""
        settings = DownloadSettings()
        assert settings.concurrent_fragments == 4
        assert settings.sleep_interval == 1
        assert settings.max_sleep_interval == 3
        assert settings.retries == "infinite"
        assert settings.rate_limit is None
        assert settings.proxy is None

    def test_to_args_basic(self) -> None:
        """Test conversion to command-line arguments."""
        settings = DownloadSettings()
        args = settings.to_args()

        assert "--continue" in args
        assert "--concurrent-fragments" in args
        assert "4" in args
        assert "--retries" in args
        assert "infinite" in args

    def test_to_args_with_rate_limit(self) -> None:
        """Test rate limit is included in args."""
        settings = DownloadSettings(rate_limit="1M")
        args = settings.to_args()

        assert "--limit-rate" in args
        assert "1M" in args

    def test_to_args_with_proxy(self) -> None:
        """Test proxy is included in args."""
        settings = DownloadSettings(proxy="http://proxy:8080")
        args = settings.to_args()

        assert "--proxy" in args
        assert "http://proxy:8080" in args


class TestAudioSettings:
    """Tests for AudioSettings dataclass."""

    def test_default_values(self) -> None:
        """Test default audio settings."""
        settings = AudioSettings()
        assert settings.audio_quality == 0
        assert settings.audio_format == "mp3"
        assert settings.embed_thumbnail is True
        assert settings.embed_metadata is True

    def test_to_args(self) -> None:
        """Test conversion to command-line arguments."""
        settings = AudioSettings()
        args = settings.to_args()

        assert "--extract-audio" in args
        assert "--audio-format" in args
        assert "mp3" in args
        assert "--audio-quality" in args
        assert "0" in args
        assert "--embed-metadata" in args
        assert "--embed-thumbnail" in args


class TestVideoSettings:
    """Tests for VideoSettings dataclass."""

    def test_default_values(self) -> None:
        """Test default video settings."""
        settings = VideoSettings()
        assert settings.embed_thumbnail is True
        assert settings.embed_metadata is True
        assert settings.embed_subtitles is False

    def test_to_args_with_subtitles(self) -> None:
        """Test subtitle options are included."""
        settings = VideoSettings(embed_subtitles=True, subtitle_languages="en,tr")
        args = settings.to_args()

        assert "--write-subs" in args
        assert "--sub-langs" in args
        assert "en,tr" in args
        assert "--embed-subs" in args


class TestAppSettings:
    """Tests for AppSettings dataclass."""

    def test_default_values(self) -> None:
        """Test default app settings."""
        settings = AppSettings()
        assert settings.use_deno is True
        assert settings.default_mode == "mp4"
        assert settings.default_mp4_profile == 1
        assert settings.language == "en"

    def test_from_dict_empty(self) -> None:
        """Test loading from empty dict uses defaults."""
        settings = AppSettings.from_dict({})
        assert settings.download.concurrent_fragments == 4
        assert settings.audio.audio_quality == 0

    def test_from_dict_partial(self) -> None:
        """Test loading from partial dict."""
        data = {
            "download": {"concurrent_fragments": 8},
            "language": "tr",
        }
        settings = AppSettings.from_dict(data)

        assert settings.download.concurrent_fragments == 8
        assert settings.language == "tr"
        # Other defaults preserved
        assert settings.download.sleep_interval == 1

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        settings = AppSettings()
        data = settings.to_dict()

        assert "download" in data
        assert "audio" in data
        assert "video" in data
        assert "output" in data
        assert data["download"]["concurrent_fragments"] == 4
        assert data["use_deno"] is True

    def test_roundtrip(self) -> None:
        """Test dict -> settings -> dict preserves values."""
        original = {
            "download": {"concurrent_fragments": 8, "rate_limit": "2M"},
            "audio": {"audio_quality": 5},
            "language": "de",
        }

        settings = AppSettings.from_dict(original)
        result = settings.to_dict()

        assert result["download"]["concurrent_fragments"] == 8
        assert result["download"]["rate_limit"] == "2M"
        assert result["audio"]["audio_quality"] == 5
        assert result["language"] == "de"
