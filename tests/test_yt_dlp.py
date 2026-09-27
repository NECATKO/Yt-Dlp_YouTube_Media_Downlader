"""Tests for ytdlp_app.yt_dlp command construction."""

from pathlib import Path

import pytest

from ytdlp_app.models import DownloadMode
from ytdlp_app.settings import AppSettings
from ytdlp_app.yt_dlp import CommandBuilder

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# The arguments the builder emitted before the settings were wired in. Defaults
# must keep producing exactly these, so an upgrade cannot silently change how
# downloads behave.
LEGACY_STABILITY_ARGS = [
    "--continue",
    "--ignore-errors",
    "--retries",
    "infinite",
    "--fragment-retries",
    "infinite",
    "--concurrent-fragments",
    "4",
    "--sleep-interval",
    "1",
    "--max-sleep-interval",
    "3",
]


@pytest.fixture
def builder(tmp_path: Path) -> CommandBuilder:
    """A builder for a single (non-playlist) download with default settings."""
    return CommandBuilder(
        url=URL,
        output_template="%(title)s.%(ext)s",
        archive_path=tmp_path / "archive.txt",
        is_playlist=False,
    )


class TestDefaults:
    """The default settings must reproduce the pre-settings behavior."""

    def test_stability_args_unchanged(self, builder: CommandBuilder) -> None:
        assert builder.stability_args == LEGACY_STABILITY_ARGS

    def test_video_post_args_unchanged(self, builder: CommandBuilder) -> None:
        assert builder.build_post_args(DownloadMode.VIDEO) == [
            "--embed-metadata",
            "--add-metadata",
            "--embed-thumbnail",
        ]

    def test_mp3_keeps_its_extraction_flags(self, builder: CommandBuilder) -> None:
        """The flags moved into AudioSettings must still reach the command."""
        cmd = builder.build_mp3()
        for flag in ("--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"):
            assert flag in cmd

    def test_no_subtitles_by_default(self, builder: CommandBuilder) -> None:
        assert "--write-subs" not in builder.build_post_args(DownloadMode.VIDEO)


class TestCommandShape:
    """Structural guarantees every command relies on."""

    @pytest.mark.parametrize(
        "method",
        [
            "build_mp4_compatibility_stage1",
            "build_mp4_compatibility_stage2",
            "build_mp4_quality_mkv",
            "build_mp4_quality_remux",
            "build_mp3",
        ],
    )
    def test_url_is_last_and_program_is_first(self, builder: CommandBuilder, method: str) -> None:
        """yt-dlp reads the URL positionally, so it must terminate the argv."""
        cmd = getattr(builder, method)()
        assert cmd[0] == "yt-dlp"
        assert cmd[-1] == URL

    def test_single_download_disables_playlist(self, builder: CommandBuilder) -> None:
        assert "--no-playlist" in builder.common_args
        assert "--yes-playlist" not in builder.common_args

    def test_playlist_download_enables_playlist(self, tmp_path: Path) -> None:
        playlist_builder = CommandBuilder(
            url=URL,
            output_template="%(title)s.%(ext)s",
            archive_path=tmp_path / "archive.txt",
            is_playlist=True,
        )
        assert "--yes-playlist" in playlist_builder.common_args

    def test_deno_runtime_is_requested_when_available(self, builder: CommandBuilder) -> None:
        assert builder.js_args[:2] == ["--js-runtime", "deno"]

    def test_deno_runtime_is_omitted_when_missing(self, tmp_path: Path) -> None:
        no_deno = CommandBuilder(
            url=URL,
            output_template="%(title)s.%(ext)s",
            archive_path=tmp_path / "archive.txt",
            is_playlist=False,
            use_deno=False,
        )
        assert "--js-runtime" not in no_deno.js_args


class TestSettingsAreApplied:
    """Settings the user configures have to reach the command line."""

    def _builder(self, tmp_path: Path, settings: AppSettings) -> CommandBuilder:
        return CommandBuilder(
            url=URL,
            output_template="%(title)s.%(ext)s",
            archive_path=tmp_path / "archive.txt",
            is_playlist=False,
            settings=settings,
        )

    def test_proxy(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.download.proxy = "http://proxy:8080"
        args = self._builder(tmp_path, settings).stability_args
        assert args[args.index("--proxy") + 1] == "http://proxy:8080"

    def test_rate_limit(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.download.rate_limit = "1M"
        args = self._builder(tmp_path, settings).stability_args
        assert args[args.index("--limit-rate") + 1] == "1M"

    def test_concurrent_fragments(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.download.concurrent_fragments = 16
        args = self._builder(tmp_path, settings).stability_args
        assert args[args.index("--concurrent-fragments") + 1] == "16"

    def test_audio_format_changes_the_mp3_command(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.audio.audio_format = "opus"
        cmd = self._builder(tmp_path, settings).build_mp3()
        assert cmd[cmd.index("--audio-format") + 1] == "opus"

    def test_subtitles(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.embed_subtitles = True
        settings.video.subtitle_languages = "en,tr"
        args = self._builder(tmp_path, settings).build_post_args(DownloadMode.VIDEO)
        assert "--embed-subs" in args
        assert args[args.index("--sub-langs") + 1] == "en,tr"

    def test_thumbnail_can_be_turned_off(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.embed_thumbnail = False
        args = self._builder(tmp_path, settings).build_post_args(DownloadMode.VIDEO)
        assert "--embed-thumbnail" not in args


# The exact command archive mode produces with default settings for a
# single video when Deno is available. Any change here changes what gets
# archived or how hard YouTube is hit, so it is pinned verbatim.
ARCHIVE_DEFAULT_PREFIX = [
    "yt-dlp",
    "-f",
    "bv*[height<=1080]+ba/b",
    "--merge-output-format",
    "mkv",
    "--write-description",
    "--write-info-json",
    "--write-thumbnail",
    "--write-subs",
    "--write-auto-subs",
    "--sub-langs",
    "tr.*,en.*",
    "--convert-subs",
    "srt",
    "--embed-metadata",
    "--embed-chapters",
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
    "--js-runtime",
    "deno",
    "--remote-components",
    "ejs:github",
    "-o",
    "%(title)s.%(ext)s",
    "--download-archive",
]


class TestArchiveMode:
    """Archive mode has its own flag set and must not inherit the MP4 policy."""

    def _builder(
        self, tmp_path: Path, settings: AppSettings | None = None, *, is_playlist: bool = False
    ) -> CommandBuilder:
        return CommandBuilder(
            url=URL,
            output_template="%(title)s.%(ext)s",
            archive_path=tmp_path / "archive.txt",
            is_playlist=is_playlist,
            settings=settings,
        )

    def test_exact_default_argument_list(self, tmp_path: Path) -> None:
        cmd = self._builder(tmp_path).build_archive()
        assert cmd == [
            *ARCHIVE_DEFAULT_PREFIX,
            str(tmp_path / "archive.txt"),
            "--progress",
            "--no-playlist",
            URL,
        ]

    def test_never_retries_forever(self, tmp_path: Path) -> None:
        cmd = self._builder(tmp_path).build_archive()
        assert "infinite" not in cmd
        assert cmd[cmd.index("--retries") + 1] == "10"
        assert cmd[cmd.index("--fragment-retries") + 1] == "10"

    def test_does_not_inherit_the_regular_download_policy(self, tmp_path: Path) -> None:
        """No duplicate sleep flags, no --ignore-errors, no parallel fragments."""
        cmd = self._builder(tmp_path).build_archive()
        assert cmd.count("--sleep-interval") == 1
        assert cmd.count("--max-sleep-interval") == 1
        assert "--ignore-errors" not in cmd
        assert "--concurrent-fragments" not in cmd

    def test_rate_limit_and_proxy_still_apply(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.download.rate_limit = "2M"
        settings.download.proxy = "socks5://127.0.0.1:9050"
        cmd = self._builder(tmp_path, settings).build_archive()
        assert cmd[cmd.index("--limit-rate") + 1] == "2M"
        assert cmd[cmd.index("--proxy") + 1] == "socks5://127.0.0.1:9050"
        assert cmd[-1] == URL

    def test_waits_come_from_settings(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.archive.sleep_requests = 3
        settings.archive.sleep_interval = 20.5
        settings.archive.max_sleep_interval = 60
        settings.archive.sleep_subtitles = 8
        cmd = self._builder(tmp_path, settings).build_archive()
        assert cmd[cmd.index("--sleep-requests") + 1] == "3"
        assert cmd[cmd.index("--sleep-interval") + 1] == "20.5"
        assert cmd[cmd.index("--max-sleep-interval") + 1] == "60"
        assert cmd[cmd.index("--sleep-subtitles") + 1] == "8"

    def test_max_wait_below_min_is_raised(self, tmp_path: Path) -> None:
        """A hand-edited config must not produce a window yt-dlp rejects."""
        settings = AppSettings()
        settings.archive.sleep_interval = 30
        settings.archive.max_sleep_interval = 10
        cmd = self._builder(tmp_path, settings).build_archive()
        assert cmd[cmd.index("--max-sleep-interval") + 1] == "30"

    def test_channel_download_enables_playlist(self, tmp_path: Path) -> None:
        cmd = self._builder(tmp_path, is_playlist=True).build_archive()
        assert "--yes-playlist" in cmd
        assert "--no-playlist" not in cmd

    def test_regular_modes_are_unchanged(self, builder: CommandBuilder) -> None:
        """Adding archive mode must not leak into the MP4/MP3 commands."""
        assert builder.stability_args == LEGACY_STABILITY_ARGS
        for cmd in (builder.build_mp4_quality_mkv(), builder.build_mp3()):
            assert "--sleep-requests" not in cmd
            assert "--write-info-json" not in cmd
