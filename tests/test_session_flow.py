"""The session's decisions: what counts as done, what a run does after a ban, a cancel or a
partial failure, and which arguments reach every kind of yt-dlp call."""

from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.session as session_module
from tests.test_session_archive import Recorder, ScriptedUI, _session
from ytdlp_app import preflight
from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.exec import BAN_RETURN_CODE
from ytdlp_app.i18n import t
from ytdlp_app.models import AppPaths, ModeChoice, PlaylistEntry
from ytdlp_app.netctx import LISTING_TIMEOUT_SECONDS
from ytdlp_app.playlist import PlaylistListing
from ytdlp_app.session import CycleOutcome

LIST_URL = "https://www.youtube.com/playlist?list=PLabc"
VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
CHANNEL_URL = "https://www.youtube.com/@ChannelHandle/videos"
CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"
VIDEO, AUDIO, ARCHIVE = (int(ModeChoice.VIDEO), int(ModeChoice.AUDIO), int(ModeChoice.ARCHIVE))
EXIT = 2  # the second option of the "what next" menu
FULL, QUALITY, MKV, COMPAT = 1, 2, 1, 1


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(tmp_path, tmp_path / "config.json", tmp_path / "logs", tmp_path / "archives")


def entries(count: int = 3) -> list[PlaylistEntry]:
    return [
        PlaylistEntry(i, f"v{i}", f"T{i}", f"https://www.youtube.com/watch?v=v{i}", 600.0)
        for i in range(1, count + 1)
    ]


class Script:
    """A run_cmd_tee stand-in whose successive calls each end differently."""

    def __init__(self, *steps: tuple[int, list[str]]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        cmd: list[str],
        log_path: Path,
        *,
        stop_on_ban: bool = False,
        sink: Any = None,
        cancel: Any = None,
    ) -> int:
        self.calls.append({"cmd": cmd, "stop_on_ban": stop_on_ban})
        rc, writes = self.steps.pop(0)
        archive = Path(cmd[cmd.index("--download-archive") + 1])
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("a", encoding="utf-8") as handle:
            for ident in writes:
                handle.write(f"youtube {ident}\n")
        return rc


def playlist_session(monkeypatch, tmp_path, paths, ui, runner, url=LIST_URL, listing=None):
    session = _session(monkeypatch, tmp_path, paths, ui, url, runner)
    monkeypatch.setattr(
        session_module,
        "fetch_listing",
        lambda *_a: listing if listing is not None else PlaylistListing(entries(), None),
    )
    return session


class TestJudgedByWhatWasLeftBehind:
    def test_every_item_archived_is_a_success(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT])
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        assert t("tasks_completed") in ui.text()
        assert "3 downloaded" in ui.text()

    def test_a_partly_finished_run_is_reported_as_partial_and_exits_nonzero(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT])
        runner = Recorder(rc=1, archive_writes=["v1", "v2"])
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        outcome = session._process_one_cycle()

        assert outcome == CycleOutcome.EXIT_FAILURE
        text = ui.text()
        assert t("outcome_partial") in text
        assert "2 downloaded" in text
        assert "v3" in text
        assert t("tasks_completed") not in text

    def test_a_run_where_nothing_finished_is_a_failure(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV], exit_on_failure=True)
        runner = Recorder(rc=1)
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE

        assert t("outcome_failed") in ui.text()
        assert t("tasks_completed") not in ui.text()

    def test_exit_code_zero_does_not_hide_items_that_were_never_archived(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT])
        runner = Recorder(rc=0, archive_writes=["v1"])
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE

        assert t("outcome_partial") in ui.text()

    def test_a_file_that_vanished_is_not_counted_as_downloaded(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT])

        class WithManifest(Recorder):
            def __call__(self, cmd, log_path, *, stop_on_ban=False, sink=None, cancel=None):
                rc = super().__call__(cmd, log_path, stop_on_ban=stop_on_ban)
                archive = Path(cmd[cmd.index("--download-archive") + 1])
                manifest = archive.with_name(archive.stem + ".files.tsv")
                manifest.write_text(
                    f"v1\t{tmp_path / 'gone.mkv'}\nv2\t{tmp_path / 'here.mkv'}\n"
                    f"v3\t{tmp_path / 'here.mkv'}\n",
                    encoding="utf-8",
                )
                (tmp_path / "here.mkv").write_bytes(b"x")
                return rc

        runner = WithManifest(archive_writes=["v1", "v2", "v3"])
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE

        assert t("outcome_partial") in ui.text()
        assert "2 downloaded" in ui.text()
        assert "the file is missing" in ui.text()


class TestCompatibilityProfile:
    def test_it_is_one_command_that_verifies_the_codecs(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, COMPAT, EXIT])
        runner = Script((0, ["dQw4w9WgXcQ"]))
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        (call,) = runner.calls
        assert "Mp4Compat:when=post_process" in call["cmd"]

    def test_it_is_capped_at_1080p(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, COMPAT, EXIT])
        runner = Script((0, ["dQw4w9WgXcQ"]))
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        session._process_one_cycle()

        cmd = runner.calls[0]["cmd"]
        assert cmd[cmd.index("-f") + 1].endswith("b[height<=1080]")

    def test_a_lower_saved_cap_is_kept(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, COMPAT, EXIT])
        runner = Script((0, ["dQw4w9WgXcQ"]))
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)
        session.settings.video.max_height = 720

        session._process_one_cycle()

        cmd = runner.calls[0]["cmd"]
        assert cmd[cmd.index("-f") + 1].endswith("b[height<=720]")

    def test_a_failed_run_is_a_failure(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, COMPAT], exit_on_failure=True)
        runner = Script((1, []))
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE

        assert t("tasks_completed") not in ui.text()


class TestBanAndCancel:
    def test_a_ban_stops_the_run_and_says_how_to_resume(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV], exit_on_failure=False)
        runner = Recorder(rc=BAN_RETURN_CODE, archive_writes=["v1"])
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.CONTINUE

        assert t("ban_retry_hint") in ui.text()

    def test_a_cancel_returns_interrupted(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV])
        runner = Recorder(rc=130, archive_writes=["v1"])
        session = playlist_session(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.INTERRUPTED

    def test_a_cancelled_compatibility_run_is_interrupted(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, COMPAT])
        runner = Script((130, []))
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.INTERRUPTED

        assert len(runner.calls) == 1


class TestLowDiskSpace:
    def low(self, monkeypatch) -> None:
        monkeypatch.setattr(
            session_module,
            "confirm_disk_space",
            lambda ui, base, log: preflight.confirm_disk_space(ui, base, log, lambda _p: 1024),
        )

    def test_declining_returns_to_the_url_prompt_without_downloading(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, QUALITY, MKV, 2])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)
        self.low(monkeypatch)

        assert session._process_one_cycle() == CycleOutcome.CONTINUE

        assert runner.calls == []
        assert t("disk_low_cancelled") in ui.text()

    def test_continuing_anyway_downloads(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, QUALITY, MKV, 1, EXIT])
        runner = Recorder(archive_writes=["dQw4w9WgXcQ"])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)
        self.low(monkeypatch)

        session._process_one_cycle()

        assert len(runner.calls) == 1

    def test_a_disk_that_cannot_be_measured_does_not_block(self, tmp_path) -> None:
        def broken(_path: Path) -> int:
            raise OSError("no such device")

        assert preflight.confirm_disk_space(ScriptedUI([]), tmp_path, None, broken)

    def test_enough_space_asks_nothing(self, tmp_path) -> None:
        enough = preflight.MIN_FREE_BYTES
        assert preflight.confirm_disk_space(ScriptedUI([]), tmp_path, None, lambda _p: enough)


class TestSharedNetworkArguments:
    PROXY = "http://user:s3cret@proxy.example:3128"

    def setup(self, monkeypatch, tmp_path, paths, mode_picks):
        ui = ScriptedUI(mode_picks)
        runner = Recorder(rc=1, archive_writes=["v1"])
        listing_calls: list[list[str]] = []
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        session.settings.download.proxy = self.PROXY
        monkeypatch.setattr(
            session_module,
            "fetch_listing",
            lambda _u, args, _r: listing_calls.append(args) or PlaylistListing(entries(), None),
        )
        return session, runner, listing_calls

    def test_the_proxy_reaches_the_download_and_the_listing(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        session, runner, listing_calls = self.setup(
            monkeypatch, tmp_path, paths, [VIDEO, FULL, QUALITY, MKV, EXIT]
        )

        session._process_one_cycle()

        for args in (runner.calls[0]["cmd"], listing_calls[0]):
            assert args[args.index("--proxy") + 1] == self.PROXY
            assert "--ignore-config" in args
            assert "--socket-timeout" in args

    def test_the_archive_listing_uses_it_too(self, monkeypatch, tmp_path, paths) -> None:
        session, _runner, listing_calls = self.setup(
            monkeypatch, tmp_path, paths, [ARCHIVE, FULL, EXIT]
        )

        session._process_one_cycle()

        assert listing_calls[0][listing_calls[0].index("--proxy") + 1] == self.PROXY

    def test_the_password_never_reaches_the_screen_or_the_log(
        self, monkeypatch, tmp_path, paths, capsys
    ) -> None:
        session, _runner, *_ = self.setup(
            monkeypatch, tmp_path, paths, [VIDEO, FULL, QUALITY, MKV, EXIT]
        )
        ui = session.ui
        session._process_one_cycle()

        assert "s3cret" not in ui.text()  # type: ignore[attr-defined]
        assert "s3cret" not in capsys.readouterr().out
        log = session.log_path
        assert log is not None and "s3cret" not in log.read_text(encoding="utf-8")

    def test_the_listing_has_a_time_limit(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT])
        runner = Recorder(rc=1, archive_writes=["v1"])
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        limits: list[float | None] = []
        monkeypatch.setattr(
            session_module,
            "run_capture",
            lambda cmd, timeout=None, cancel=None: limits.append(timeout) or (0, "", ""),
        )

        def listing(_url: str, _args: list[str], capture: Any) -> PlaylistListing:
            capture(["yt-dlp"])
            return PlaylistListing(entries(), None)

        monkeypatch.setattr(session_module, "fetch_listing", listing)

        session._process_one_cycle()

        assert limits == [LISTING_TIMEOUT_SECONDS]


class TestUrlHandling:
    def test_a_channel_live_url_is_a_single_video_with_no_question(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, QUALITY, MKV, EXIT])
        runner = Recorder(archive_writes=["live"])
        session = _session(
            monkeypatch, tmp_path, paths, ui, "https://www.youtube.com/@ChannelHandle/live", runner
        )
        monkeypatch.setattr(
            session_module,
            "fetch_listing",
            lambda *_a: (_ for _ in ()).throw(AssertionError("a live redirect is not listed")),
        )

        session._process_one_cycle()

        assert t("prompt_playlist") not in ui.prompts
        assert "--no-playlist" in runner.calls[0]["cmd"]

    def test_another_site_is_downloaded_as_a_single_item_with_a_notice(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, QUALITY, MKV, EXIT])
        runner = Recorder(archive_writes=["12345"])
        session = _session(
            monkeypatch, tmp_path, paths, ui, "https://vimeo.com/channels/staffpicks/12345", runner
        )
        monkeypatch.setattr(
            session_module,
            "fetch_listing",
            lambda *_a: (_ for _ in ()).throw(AssertionError("other sites are never listed")),
        )

        session._process_one_cycle()

        assert t("notice_non_youtube") in ui.text()
        assert t("prompt_playlist") not in ui.prompts
        assert "--no-playlist" in runner.calls[0]["cmd"]

    def test_a_hostile_playlist_id_stays_inside_the_archives_folder(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT])
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        session = playlist_session(
            monkeypatch,
            tmp_path,
            paths,
            ui,
            runner,
            url="https://www.youtube.com/playlist?list=/../../outside",
        )

        session._process_one_cycle()

        archive = Path(
            runner.calls[0]["cmd"][runner.calls[0]["cmd"].index("--download-archive") + 1]
        )
        assert archive.resolve().parent == paths.archives_dir.resolve()
        assert not (tmp_path.parent / "outside_mp4.txt").exists()

    @pytest.mark.parametrize("mode_picks", [[VIDEO, FULL, QUALITY, MKV, EXIT], [AUDIO, FULL, EXIT]])
    def test_channels_are_keyed_by_their_channel_id_in_video_and_audio_mode(
        self, monkeypatch, tmp_path, paths, mode_picks
    ) -> None:
        ui = ScriptedUI(mode_picks)
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        listing = PlaylistListing(entries(), CHANNEL_ID)
        session = playlist_session(
            monkeypatch, tmp_path, paths, ui, runner, url=CHANNEL_URL, listing=listing
        )

        session._process_one_cycle()

        cmd = runner.calls[0]["cmd"]
        name = Path(cmd[cmd.index("--download-archive") + 1]).name
        assert name.startswith(f"channel_{CHANNEL_ID}_")

    def test_a_listing_failure_in_video_mode_is_shown_without_credentials(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, EXIT], exit_on_failure=False)
        runner = Recorder(archive_writes=["v1"])
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        session.settings.download.proxy = "http://bob:hunter22@proxy:3128"
        from ytdlp_app.redact import register_proxy  # noqa: PLC0415

        register_proxy(session.settings.download.proxy)

        def failing(*_a: Any) -> PlaylistListing:
            raise PlaylistError("Unable to connect to proxy http://bob:hunter22@proxy:3128")

        monkeypatch.setattr(session_module, "fetch_listing", failing)

        session._process_one_cycle()

        assert "hunter22" not in ui.text()


class TestArchiveToolsShortcut:
    def test_typing_a_opens_the_archive_tools_and_asks_for_the_url_again(
        self, monkeypatch, tmp_path, paths
    ) -> None:
        from ytdlp_app.session import InteractiveSession  # noqa: PLC0415

        answers = iter(["a", ""])
        opened: list[str] = []

        class UI(ScriptedUI):
            def ask_text(self, prompt: str) -> str:
                return next(answers)

        session = InteractiveSession(
            UI([]),
            __import__("ytdlp_app.models", fromlist=["UserConfig"]).UserConfig(
                "x", tmp_path, tmp_path
            ),
            paths,
        )  # type: ignore[arg-type]
        monkeypatch.setattr(session_module, "run_archive_tools", lambda *_a: opened.append("tools"))

        assert session._ask_url() is None

        assert opened == ["tools"]
