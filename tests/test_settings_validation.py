"""Hand-edited config.json must never crash the app or reach yt-dlp as a bad argument."""

import math
from typing import Any

import pytest

from ytdlp_app.settings import (
    AUDIO_FORMATS,
    AppSettings,
    OutputSettings,
    SettingsIssue,
)


def load(data: dict[str, Any]) -> tuple[AppSettings, list[SettingsIssue]]:
    issues: list[SettingsIssue] = []
    return AppSettings.from_dict(data, issues), issues


def fields(issues: list[SettingsIssue]) -> set[str]:
    return {issue.field for issue in issues}


def every_argument_is_text(settings: AppSettings) -> bool:
    args = [
        *settings.download.to_args(),
        *settings.audio.to_args(),
        *settings.video.to_args(),
        *settings.archive.to_args(),
    ]
    return all(isinstance(arg, str) for arg in args)


class TestSections:
    @pytest.mark.parametrize("section", ["download", "audio", "video", "output", "archive"])
    @pytest.mark.parametrize("bad", [None, [], "bad", False, 7])
    def test_a_section_of_the_wrong_type_is_reported_and_defaulted(
        self, section: str, bad: object
    ) -> None:
        settings, issues = load({section: bad})

        assert section in fields(issues)
        assert settings.to_dict() == AppSettings().to_dict()

    def test_a_bad_section_does_not_spoil_its_neighbours(self) -> None:
        settings, _ = load({"audio": None, "download": {"concurrent_fragments": 8}})

        assert settings.download.concurrent_fragments == 8

    def test_a_valid_config_reports_nothing(self) -> None:
        _, issues = load(AppSettings().to_dict())

        assert issues == []


class TestNumbers:
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, "nan", "inf", "-1", -1, 10**9])
    def test_archive_waits_reject_non_finite_and_out_of_range(self, bad: object) -> None:
        settings, issues = load({"archive": {"sleep_interval": bad}})

        assert settings.archive.sleep_interval == 15
        assert "archive.sleep_interval" in fields(issues)
        assert "inf" not in settings.archive.to_args()

    @pytest.mark.parametrize("bad", [0, 65, -3, 2.5, "4", True, None, math.nan])
    def test_concurrent_fragments_needs_a_whole_number_in_range(self, bad: object) -> None:
        settings, issues = load({"download": {"concurrent_fragments": bad}})

        assert settings.download.concurrent_fragments == 4
        assert every_argument_is_text(settings)
        if bad is not None:
            assert "download.concurrent_fragments" in fields(issues)

    def test_download_sleep_accepts_fractions(self) -> None:
        settings, issues = load({"download": {"sleep_interval": 1.5, "max_sleep_interval": 4}})

        assert issues == []
        assert (
            settings.download.to_args()[settings.download.to_args().index("--sleep-interval") + 1]
            == "1.5"
        )

    def test_download_sleep_window_is_never_inverted(self) -> None:
        settings, _ = load({"download": {"sleep_interval": 9, "max_sleep_interval": 2}})
        args = settings.download.to_args()

        assert args[args.index("--max-sleep-interval") + 1] == "9"


class TestRetries:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (5, "5"),
            ("7", "7"),
            (0, "0"),
            ("infinite", "infinite"),
            ("INF", "infinite"),
            ("Infinity", "infinite"),
        ],
    )
    def test_numbers_and_the_infinite_spelling_are_normalised(
        self, value: object, expected: str
    ) -> None:
        settings, issues = load({"download": {"retries": value, "fragment_retries": value}})

        assert issues == []
        assert settings.download.retries == expected
        args = settings.download.to_args()
        assert args[args.index("--retries") + 1] == expected
        assert args[args.index("--fragment-retries") + 1] == expected

    @pytest.mark.parametrize("bad", [-1, 2.5, True, "many", [], None, math.inf, 10**7])
    def test_anything_else_falls_back_to_infinite(self, bad: object) -> None:
        settings, issues = load({"download": {"retries": bad}})

        assert settings.download.retries == "infinite"
        assert every_argument_is_text(settings)
        if bad is not None:
            assert "download.retries" in fields(issues)


class TestStrings:
    @pytest.mark.parametrize("bad", ["-x", "1 M", "fast", "1MB/s", 12.5, [], "-"])
    def test_rate_limit_must_look_like_a_yt_dlp_rate(self, bad: object) -> None:
        settings, issues = load({"download": {"rate_limit": bad}})

        assert settings.download.rate_limit is None
        assert "download.rate_limit" in fields(issues)

    @pytest.mark.parametrize("good", ["500K", "1M", "4.2M", "2G", "1024"])
    def test_rate_limit_accepts_the_usual_forms(self, good: str) -> None:
        settings, issues = load({"download": {"rate_limit": good}})

        assert issues == []
        assert settings.download.rate_limit == good

    @pytest.mark.parametrize("bad", ["--exec rm", "-x", "a\nb", "a\x00b", 5, ["p"], "with space"])
    def test_proxy_cannot_smuggle_a_flag_or_control_characters(self, bad: object) -> None:
        settings, issues = load({"download": {"proxy": bad}})

        assert settings.download.proxy is None
        assert "download.proxy" in fields(issues)

    def test_blank_proxy_means_none_without_complaint(self) -> None:
        settings, issues = load({"download": {"proxy": "  "}})

        assert settings.download.proxy is None
        assert issues == []

    @pytest.mark.parametrize("bad", ["ogg", "MP3 ", 3, None, [], "-x"])
    def test_audio_format_must_be_an_offered_one(self, bad: object) -> None:
        settings, issues = load({"audio": {"audio_format": bad}})

        assert settings.audio.audio_format == "mp3"
        if bad is not None:
            assert "audio.audio_format" in fields(issues)

    @pytest.mark.parametrize("fmt", AUDIO_FORMATS)
    def test_every_offered_audio_format_is_kept(self, fmt: str) -> None:
        settings, issues = load({"audio": {"audio_format": fmt}})

        assert issues == []
        assert settings.audio.audio_format == fmt

    @pytest.mark.parametrize("bad", [10, -1, "3", 1.5, True])
    def test_audio_quality_is_a_whole_number_from_0_to_9(self, bad: object) -> None:
        settings, issues = load({"audio": {"audio_quality": bad}})

        assert settings.audio.audio_quality == 0
        assert "audio.audio_quality" in fields(issues)

    @pytest.mark.parametrize("bad", ["bmp", 3, "-x"])
    def test_thumbnail_format_is_restricted(self, bad: object) -> None:
        settings, issues = load({"audio": {"convert_thumbnails": bad}})

        assert settings.audio.convert_thumbnails == "jpg"
        assert "audio.convert_thumbnails" in fields(issues)

    @pytest.mark.parametrize("bad", ["", "-x", 5, "a\nb", None])
    def test_subtitle_languages_need_usable_text(self, bad: object) -> None:
        settings, _ = load({"video": {"subtitle_languages": bad, "write_subtitles": True}})

        assert settings.video.subtitle_languages == "en"
        assert every_argument_is_text(settings)


class TestBooleans:
    @pytest.mark.parametrize(
        ("section", "key"),
        [
            ("audio", "embed_thumbnail"),
            ("audio", "embed_metadata"),
            ("video", "embed_thumbnail"),
            ("video", "embed_metadata"),
            ("video", "embed_subtitles"),
            ("video", "write_subtitles"),
            ("download", "allow_external_config"),
            ("download", "speed_test"),
        ],
    )
    @pytest.mark.parametrize("bad", ["false", 0, 1, [], "yes"])
    def test_only_real_booleans_are_accepted(self, section: str, key: str, bad: object) -> None:
        default = getattr(getattr(AppSettings(), section), key)
        settings, issues = load({section: {key: bad}})

        assert getattr(getattr(settings, section), key) is default
        assert f"{section}.{key}" in fields(issues)


class TestTemplates:
    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "   ",
            5,
            None,
            "/etc/%(id)s.%(ext)s",
            "C:\\x\\%(id)s.%(ext)s",
            "../%(id)s.%(ext)s",
            "a/../../%(id)s.%(ext)s",
            "a\\..\\%(id)s.%(ext)s",
            "~/%(id)s.%(ext)s",
            "%(id)s",
            "a\x00b%(ext)s",
        ],
    )
    def test_unusable_templates_fall_back_to_the_default(self, bad: object) -> None:
        settings, issues = load({"output": {"single_video_template": bad}})

        assert settings.output.single_video_template == OutputSettings().single_video_template
        if bad is not None:
            assert "output.single_video_template" in fields(issues)

    def test_a_custom_template_without_the_id_is_kept_but_flagged(self) -> None:
        settings, issues = load({"output": {"single_audio_template": "%(title)s.%(ext)s"}})

        assert settings.output.single_audio_template == "%(title)s.%(ext)s"
        flagged = [i for i in issues if i.field == "output.single_audio_template"]
        assert flagged
        assert flagged[0].fallback is None

    def test_a_custom_template_with_the_id_is_left_alone(self) -> None:
        settings, issues = load({"output": {"single_audio_template": "%(id)s.%(ext)s"}})

        assert settings.output.single_audio_template == "%(id)s.%(ext)s"
        assert issues == []

    def test_the_default_templates_carry_the_content_id(self) -> None:
        output = OutputSettings()

        for template in (
            output.single_video_template,
            output.single_audio_template,
            output.playlist_video_template,
            output.playlist_audio_template,
        ):
            assert "%(id)s" in template
        # The playlist position stays as a prefix; it just no longer stands in for the id.
        assert "%(playlist_index)03d" in output.playlist_video_template


class TestDefaultsSurviveTheRoundTrip:
    def test_to_dict_output_is_valid_input(self) -> None:
        settings = AppSettings()
        settings.download.retries = "12"
        settings.download.allow_external_config = True
        settings.download.speed_test = False

        again, issues = load(settings.to_dict())

        assert issues == []
        assert again.to_dict() == settings.to_dict()
