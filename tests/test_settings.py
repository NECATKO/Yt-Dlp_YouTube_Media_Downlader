"""Tests for ytdlp_app.settings module."""

import pytest

from ytdlp_app.settings import (
    AppSettings,
    ArchiveSettings,
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

    def test_network_args_carry_the_rate_limit(self) -> None:
        settings = DownloadSettings(rate_limit="1M")

        assert settings.network_args() == ["--limit-rate", "1M"]

    def test_network_args_carry_the_proxy(self) -> None:
        settings = DownloadSettings(proxy="http://proxy:8080")

        assert settings.network_args() == ["--proxy", "http://proxy:8080"]

    def test_to_args_leave_the_network_to_the_shared_context(self) -> None:
        """Proxy and speed limit are added once, by NetworkContext, for every call."""
        args = DownloadSettings(rate_limit="1M", proxy="http://proxy:8080").to_args()

        assert "--limit-rate" not in args
        assert "--proxy" not in args

    def test_errors_do_not_count_as_success(self) -> None:
        args = DownloadSettings().to_args()

        assert "--ignore-errors" not in args
        assert "--no-abort-on-error" in args
        assert "--abort-on-unavailable-fragments" in args


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
        assert settings.download.concurrent_fragments == 4
        assert settings.audio.audio_format == "mp3"
        assert settings.video.embed_subtitles is False
        # Not the bare title: two videos with one title would share a file (see
        # OutputSettings). The content id makes the name unique.
        assert settings.output.single_video_template == "%(title).150B [%(id)s].%(ext)s"

    def test_from_dict_empty(self) -> None:
        """Test loading from empty dict uses defaults."""
        settings = AppSettings.from_dict({})
        assert settings.download.concurrent_fragments == 4
        assert settings.audio.audio_quality == 0

    def test_from_dict_partial(self) -> None:
        """Test loading from partial dict."""
        data = {"download": {"concurrent_fragments": 8}}
        settings = AppSettings.from_dict(data)

        assert settings.download.concurrent_fragments == 8
        # Other defaults preserved
        assert settings.download.sleep_interval == 1
        assert settings.audio.audio_format == "mp3"

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        settings = AppSettings()
        data = settings.to_dict()

        assert set(data) == {"download", "audio", "video", "output", "archive"}
        assert data["download"]["concurrent_fragments"] == 4

    def test_roundtrip(self) -> None:
        """Test dict -> settings -> dict preserves values."""
        original = {
            "download": {"concurrent_fragments": 8, "rate_limit": "2M"},
            "audio": {"audio_quality": 5},
            "video": {"subtitle_languages": "en,tr"},
        }

        settings = AppSettings.from_dict(original)
        result = settings.to_dict()

        assert result["download"]["concurrent_fragments"] == 8
        assert result["download"]["rate_limit"] == "2M"
        assert result["audio"]["audio_quality"] == 5
        assert result["video"]["subtitle_languages"] == "en,tr"


class TestArchiveSettings:
    """Archive pacing is persisted and survives a bad hand edit."""

    def test_defaults(self) -> None:
        archive = ArchiveSettings()
        assert archive.to_args() == [
            "--sleep-requests",
            "1.5",
            "--sleep-interval",
            "15",
            "--max-sleep-interval",
            "45",
            "--sleep-subtitles",
            "5",
            "--retries",
            "10",
            "--fragment-retries",
            "10",
            "--abort-on-unavailable-fragments",
        ]

    def test_roundtrip_through_app_settings(self) -> None:
        settings = AppSettings()
        settings.archive.sleep_requests = 2.5
        settings.archive.sleep_subtitles = 9

        restored = AppSettings.from_dict(settings.to_dict())

        assert restored.archive == settings.archive

    def test_configs_without_the_section_get_defaults(self) -> None:
        """Configs written before archive mode existed need no migration."""
        assert AppSettings.from_dict({"download": {}}).archive == ArchiveSettings()

    @pytest.mark.parametrize("bad", ["fast", -3, None, True, [1]])
    def test_unusable_values_fall_back(self, bad: object) -> None:
        restored = ArchiveSettings.from_dict({"sleep_interval": bad, "sleep_requests": "4"})
        assert restored.sleep_interval == 15
        # A numeric string is still a usable number.
        assert restored.sleep_requests == 4

    def test_archive_template_is_configurable(self) -> None:
        default = OutputSettings().archive_template
        assert default == (
            "%(channel)s/%(upload_date)s - %(title).80B [%(id)s]/%(title).80B.%(ext)s"
        )
        custom = AppSettings.from_dict({"output": {"archive_template": "%(id)s.%(ext)s"}})
        assert custom.output.archive_template == "%(id)s.%(ext)s"


class TestMaxHeight:
    def test_defaults_keep_todays_behaviour(self) -> None:
        settings = AppSettings()
        assert settings.video.max_height is None
        assert settings.archive.max_height == 1080

    @pytest.mark.parametrize("value", [1080, 1440, 2160, None])
    def test_the_offered_caps_are_accepted(self, value: int | None) -> None:
        settings = AppSettings.from_dict(
            {"video": {"max_height": value}, "archive": {"max_height": value}}
        )
        assert settings.video.max_height == value
        assert settings.archive.max_height == value

    @pytest.mark.parametrize("bad", [720, "1080", True, 1080.5, [], 0, -1080])
    def test_anything_else_falls_back_to_the_default(self, bad: object) -> None:
        settings = AppSettings.from_dict(
            {"video": {"max_height": bad}, "archive": {"max_height": bad}}
        )
        assert settings.video.max_height is None
        assert settings.archive.max_height == 1080

    def test_archive_without_the_key_keeps_1080(self) -> None:
        settings = AppSettings.from_dict({"archive": {"sleep_requests": 2}})
        assert settings.archive.max_height == 1080

    def test_video_without_the_key_stays_unlimited(self) -> None:
        settings = AppSettings.from_dict({"video": {"embed_thumbnail": False}})
        assert settings.video.max_height is None

    def test_round_trip(self) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        settings.archive.max_height = None

        restored = AppSettings.from_dict(settings.to_dict())

        assert restored.video.max_height == 1440
        assert restored.archive.max_height is None

    def test_listing_args_carry_only_the_request_wait(self) -> None:
        assert ArchiveSettings(sleep_requests=2.5).listing_args() == ["--sleep-requests", "2.5"]
        assert ArchiveSettings().listing_args() == ["--sleep-requests", "1.5"]
