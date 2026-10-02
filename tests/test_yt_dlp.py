"""Tests for ytdlp_app.yt_dlp command construction."""

from pathlib import Path
from urllib.parse import unquote

import pytest

from ytdlp_app.models import DownloadMode
from ytdlp_app.settings import AppSettings
from ytdlp_app.yt_dlp import (
    PLUGINS_DIR,
    CommandBuilder,
    compat_stage1_format,
    ledger_args,
    video_format,
)

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# The retry and error-handling arguments of the regular modes with default settings,
# pinned verbatim. They differ from the pre-0.4 ones in two deliberate ways:
#   --ignore-errors became --no-abort-on-error. -i makes yt-dlp count a failed
#     post-processing step as success and record the item in the download archive;
#     the default it is replaced with still continues past a failed download.
#   --abort-on-unavailable-fragments is new: a missing HLS/DASH fragment used to be
#     skipped, leaving a file with a hole in it that was archived as complete.
STABILITY_ARGS = [
    "--continue",
    "--no-abort-on-error",
    "--abort-on-unavailable-fragments",
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

    def test_stability_args_are_pinned(self, builder: CommandBuilder) -> None:
        assert builder.stability_args == STABILITY_ARGS
        assert "--ignore-errors" not in builder.stability_args

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
        args = self._builder(tmp_path, settings).build_mp4_quality_mkv()
        assert args[args.index("--proxy") + 1] == "http://proxy:8080"

    def test_rate_limit(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.download.rate_limit = "1M"
        args = self._builder(tmp_path, settings).build_mp4_quality_mkv()
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
def archive_default(tmp_path: Path) -> list[str]:
    return [
        "yt-dlp",
        "--ignore-config",
        "--js-runtime",
        "deno",
        "--remote-components",
        "ejs:github",
        "--socket-timeout",
        "30",
        "-f",
        "bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format",
        "mkv",
        "--remux-video",
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
        "--plugin-dirs",
        str(PLUGINS_DIR),
        "--use-postprocessor",
        "OriginalSubsOnly:when=video",
        "--use-postprocessor",
        "ArchiveComplete:when=video;stage=snapshot",
        "--use-postprocessor",
        "ArchiveComplete:when=before_dl;stage=check",
        *ledger_args(tmp_path / "archive.files.tsv"),
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
            *archive_default(tmp_path),
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
        assert builder.stability_args == STABILITY_ARGS
        for cmd in (builder.build_mp4_quality_mkv(), builder.build_mp3()):
            assert "--sleep-requests" not in cmd
            assert "--write-info-json" not in cmd


def _selector(cmd: list[str]) -> str:
    return cmd[cmd.index("-f") + 1]


class TestSelectors:
    def test_no_cap_gives_todays_selectors(self) -> None:
        assert video_format(None) == "bv*+ba/b"
        assert compat_stage1_format(None) == (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]"
        )

    def test_the_cap_is_applied_to_every_alternative(self) -> None:
        assert video_format(1440) == "bv*[height<=1440]+ba/b[height<=1440]"
        assert compat_stage1_format(1080) == (
            "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]"
            "/best[vcodec^=avc1][height<=1080]"
        )


class TestBuilderResolutionCap:
    def test_defaults_do_not_change_the_video_commands(self, builder: CommandBuilder) -> None:
        assert _selector(builder.build_mp4_quality_mkv()) == "bv*+ba/b"
        assert _selector(builder.build_mp4_quality_remux()) == "bv*+ba/b"
        assert _selector(builder.build_mp4_compatibility_stage2()) == "bv*+ba/b"
        assert _selector(builder.build_mp4_compatibility_stage1()) == (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]"
        )

    def test_the_saved_video_cap_applies_without_a_choice(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        builder = CommandBuilder(
            URL, "%(title)s.%(ext)s", tmp_path / "a.txt", False, settings=settings
        )
        assert _selector(builder.build_mp4_quality_mkv()) == video_format(1440)

    def test_a_choice_overrides_the_saved_cap(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        builder = CommandBuilder(
            URL, "%(title)s.%(ext)s", tmp_path / "a.txt", False, settings=settings
        )
        builder.set_max_height(None)
        assert _selector(builder.build_mp4_quality_mkv()) == "bv*+ba/b"

    def test_the_choice_reaches_every_video_command(self, builder: CommandBuilder) -> None:
        builder.set_max_height(2160)
        for cmd in (
            builder.build_mp4_quality_mkv(),
            builder.build_mp4_quality_remux(),
            builder.build_mp4_compatibility_stage2(),
        ):
            assert _selector(cmd) == "bv*[height<=2160]+ba/b[height<=2160]"
        assert "[height<=2160]" in _selector(builder.build_mp4_compatibility_stage1())

    def test_audio_ignores_the_cap(self, builder: CommandBuilder) -> None:
        builder.set_max_height(1080)
        assert _selector(builder.build_mp3()) == "bestaudio/best"

    def test_archive_defaults_to_1080(self, builder: CommandBuilder) -> None:
        assert _selector(builder.build_archive()) == "bv*[height<=1080]+ba/b[height<=1080]"

    @pytest.mark.parametrize(
        ("choice", "expected"),
        [
            (1440, "bv*[height<=1440]+ba/b[height<=1440]"),
            (None, "bv*+ba/b"),
        ],
    )
    def test_archive_follows_the_choice(
        self, builder: CommandBuilder, choice: int | None, expected: str
    ) -> None:
        builder.set_max_height(choice)
        assert _selector(builder.build_archive()) == expected

    def test_archive_uses_its_own_saved_cap(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.archive.max_height = 2160
        builder = CommandBuilder(
            URL, "%(title)s.%(ext)s", tmp_path / "a.txt", False, settings=settings
        )
        assert _selector(builder.build_archive()) == video_format(2160)


yt_dlp = pytest.importorskip("yt_dlp")


def _format(fid: str, height: int | None, vcodec: str, acodec: str, ext: str = "mp4") -> dict:
    return {
        "format_id": fid,
        "height": height,
        "width": 1,
        "vcodec": vcodec,
        "acodec": acodec,
        "ext": ext,
        "protocol": "https",
        "url": "http://example.invalid/x",
        "tbr": height or 1,
    }


def _pick(selector: str, formats: list[dict]) -> list[str]:
    """Run a selector through yt-dlp's own engine, offline, on synthetic formats."""
    ydl = yt_dlp.YoutubeDL({"quiet": True})
    chosen = ydl.build_format_selector(selector)({"formats": formats, "incomplete_formats": False})
    return [f["format_id"] for f in chosen]


_SPLIT = [
    _format("a", None, "none", "opus", "webm"),
    _format("v720", 720, "avc1", "none"),
    _format("v1080", 1080, "avc1", "none"),
    _format("v2160", 2160, "vp09", "none"),
]


class TestSelectorsAgainstYtDlp:
    def test_the_cap_picks_the_best_stream_within_it(self) -> None:
        assert _pick(video_format(1080), _SPLIT) == ["v1080+a"]
        assert _pick(video_format(None), _SPLIT) == ["v2160+a"]

    def test_the_cap_holds_in_the_fallback(self) -> None:
        # Only a 2160p combined stream exists: the old "/b" fallback would take it.
        progressive = [_format("p", 2160, "avc1", "mp4a")]
        assert _pick(video_format(None), progressive) == ["p"]
        assert _pick(video_format(1080), progressive) == []

    def test_the_fallback_still_serves_streams_within_the_cap(self) -> None:
        progressive = [_format("p", 360, "avc1", "mp4a")]
        assert _pick(video_format(1080), progressive) == ["p"]

    def test_the_compatibility_selector_prefers_avc1_within_the_cap(self) -> None:
        formats = [
            _format("a", None, "none", "mp4a.40.2", "m4a"),
            _format("h264", 1080, "avc1.640028", "none"),
            _format("vp9", 1080, "vp09", "none"),
        ]
        assert _pick(compat_stage1_format(1080), formats) == ["h264+a"]


class TestCodecAndContainerContract:
    """The command-level half of the guarantees checked end to end in test_engine_contract."""

    def test_compatibility_stage2_does_not_rely_on_recode_video(
        self, builder: CommandBuilder
    ) -> None:
        cmd = builder.build_mp4_compatibility_stage2()

        assert "--recode-video" not in cmd
        assert "Mp4Compat:when=post_process" in cmd

    def test_compatibility_stage1_verifies_the_codecs_too(self, builder: CommandBuilder) -> None:
        assert "Mp4Compat:when=post_process" in builder.build_mp4_compatibility_stage1()

    def test_mkv_commands_remux_a_single_stream(self, builder: CommandBuilder) -> None:
        cmd = builder.build_mp4_quality_mkv()

        assert cmd[cmd.index("--merge-output-format") + 1] == "mkv"
        assert cmd[cmd.index("--remux-video") + 1] == "mkv"

    def test_archive_remuxes_to_mkv(self, tmp_path: Path) -> None:
        cmd = TestArchiveMode()._builder(tmp_path).build_archive()

        assert cmd[cmd.index("--remux-video") + 1] == "mkv"

    def test_the_quality_mp4_choice_still_remuxes_to_mp4(self, builder: CommandBuilder) -> None:
        cmd = builder.build_mp4_quality_remux()

        assert cmd[cmd.index("--remux-video") + 1] == "mp4"

    @pytest.mark.parametrize(
        "method",
        [
            "build_mp4_compatibility_stage1",
            "build_mp4_compatibility_stage2",
            "build_mp4_quality_mkv",
            "build_mp4_quality_remux",
            "build_mp3",
            "build_archive",
        ],
    )
    def test_every_download_runs_under_the_apps_config_policy_and_records_its_files(
        self, builder: CommandBuilder, method: str
    ) -> None:
        cmd = getattr(builder, method)()

        assert cmd[1] == "--ignore-config"
        assert any(arg.startswith("DownloadLedger:when=after_move;path=") for arg in cmd)
        assert "--abort-on-unavailable-fragments" in cmd
        assert "--ignore-errors" not in cmd
        assert cmd[-1] == URL

    def test_the_manifest_sits_beside_the_archive(self, builder: CommandBuilder) -> None:
        assert builder.manifest_path == builder.archive_path.with_name("archive.files.tsv")

    def test_manifest_path_is_escaped_for_the_option_syntax(self) -> None:
        path = Path("a;b") / "100%" / "x.files.tsv"

        value = ledger_args(path)[1].split("path=", 1)[1]

        assert ";" not in value
        assert value == str(path).replace("%", "%25").replace(";", "%3B")
        assert unquote(value) == str(path)

    def test_the_program_folder_is_passed_to_the_ledger(self, tmp_path: Path) -> None:
        value = ledger_args(tmp_path / "a.files.tsv", tmp_path / "app;x")[1]

        assert value.endswith(";root=" + str(tmp_path / "app%3Bx"))

    def test_without_a_program_folder_there_is_no_root(self, tmp_path: Path) -> None:
        assert ";root=" not in ledger_args(tmp_path / "a.files.tsv")[1]

    def test_the_builder_hands_its_program_folder_to_every_ledger(self, tmp_path: Path) -> None:
        builder = CommandBuilder(
            url=URL,
            output_template="%(title)s.%(ext)s",
            archive_path=tmp_path / "archives" / "archive.txt",
            is_playlist=False,
            app_dir=tmp_path,
        )

        for cmd in (builder.build_mp4_quality_mkv(), builder.build_archive(), builder.build_mp3()):
            ledger = next(a for a in cmd if a.startswith("DownloadLedger:"))
            assert ledger.endswith(f";root={tmp_path}")

    def test_opting_in_to_external_config_removes_the_isolation(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.download.allow_external_config = True
        b = CommandBuilder(URL, "%(id)s.%(ext)s", tmp_path / "a.txt", False, settings=settings)

        for cmd in (b.build_mp3(), b.build_archive(), b.build_mp4_quality_mkv()):
            assert "--ignore-config" not in cmd
