"""Session-level tests for archive mode: the right command, the right archive
file, no extra traffic, and a clear stop when YouTube starts blocking."""

import json
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.session as session_module
from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.exec import BAN_RETURN_CODE
from ytdlp_app.i18n import set_language, t
from ytdlp_app.models import ActionChoice, AppPaths, ModeChoice, UserConfig
from ytdlp_app.playlist import PlaylistListing
from ytdlp_app.session import CycleOutcome, InteractiveSession

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
CHANNEL_URL = "https://www.youtube.com/@ChannelHandle"
CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"


class ScriptedUI:
    def __init__(self, picks: list[int], *, exit_on_failure: bool = True) -> None:
        self.picks = list(picks)
        self.exit_on_failure = exit_on_failure
        self.messages: list[str] = []
        self.prompts: list[str] = []

    def print(self, text: object = "") -> None:
        self.messages.append(str(text))

    def print_panel(self, text: str, title: str | None = None, color: str = "") -> None:
        self.messages.append(text)

    def pick(self, prompt: str, options: list[str]) -> int:
        self.prompts.append(prompt)
        if not self.picks:
            raise AssertionError(f"unexpected pick(): {prompt!r} with {options!r}")
        return self.picks.pop(0)

    def ask_text(self, prompt: str) -> str:
        raise AssertionError(f"unexpected ask_text(): {prompt!r}")

    def prompt_exit_on_failure(self) -> bool:
        return self.exit_on_failure

    def text(self) -> str:
        return "\n".join(self.messages)


class Recorder:
    """Stands in for run_cmd_tee and records what it was asked to run.

    Like yt-dlp, a run that succeeds leaves its ids in the download archive named by
    ``--download-archive`` (``archive_writes``); the session judges the run by that, not
    by the exit code alone.
    """

    def __init__(self, rc: int = 0, archive_writes: list[str] | None = None) -> None:
        self.rc = rc
        self.archive_writes = list(archive_writes or [])
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
        self.calls.append(
            {
                "cmd": cmd,
                "log_path": log_path,
                "stop_on_ban": stop_on_ban,
                "sink": sink,
                "cancel": cancel,
            }
        )
        if self.archive_writes and "--download-archive" in cmd:
            archive = Path(cmd[cmd.index("--download-archive") + 1])
            archive.parent.mkdir(parents=True, exist_ok=True)
            with archive.open("a", encoding="utf-8") as handle:
                for ident in self.archive_writes:
                    handle.write(f"youtube {ident}\n")
        return self.rc


def _forbidden(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("archive mode must not send skip-report listing or skip-probe requests")


def _forbidden_probe(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("archive mode must not send skip-probe requests")


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(
        app_dir=tmp_path,
        config_file=tmp_path / "config.json",
        logs_dir=tmp_path / "logs",
        archives_dir=tmp_path / "archives",
    )


def _session(
    monkeypatch, tmp_path: Path, paths: AppPaths, ui: ScriptedUI, url: str, runner: Recorder
) -> InteractiveSession:
    config = UserConfig(
        app="yt-dlp-downloader",
        videos_dir=tmp_path / "videos",
        music_dir=tmp_path / "music",
    )
    session = InteractiveSession(ui, config, paths)  # type: ignore[arg-type]
    monkeypatch.setattr(session, "_ask_url", lambda: url)
    monkeypatch.setattr(session_module, "yt_dlp_available", lambda: True)
    monkeypatch.setattr(session_module, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(session_module, "deno_available", lambda: True)
    monkeypatch.setattr(session_module, "impersonation_available", lambda: True)
    monkeypatch.setattr(session_module, "run_cmd_tee", runner)
    monkeypatch.setattr(session_module, "probe_item", _forbidden_probe)
    return session


ARCHIVE = int(ModeChoice.ARCHIVE)
EXIT = int(ActionChoice.EXIT)


class TestArchiveDownload:
    def test_single_video(self, monkeypatch, tmp_path: Path, paths: AppPaths) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder(archive_writes=["dQw4w9WgXcQ"])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        (call,) = runner.calls
        cmd = call["cmd"]
        assert call["stop_on_ban"] is True
        assert "--write-info-json" in cmd
        assert "--no-playlist" in cmd
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / "single_videos_archive.txt"
        )
        template = cmd[cmd.index("-o") + 1]
        assert template == str(
            tmp_path
            / "videos"
            / "yt-dlp"
            / "%(channel)s/%(upload_date)s - %(title).80B [%(id)s]/%(title).80B.%(ext)s"
        )

    def test_channel_uses_the_channel_id_from_the_listing(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        # No playlist-vs-video question: a channel is always archived whole.
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()
        lookups: list[tuple[str, list[str]]] = []

        def fake_listing(url: str, extra_args: list[str], _runner: Any) -> PlaylistListing:
            lookups.append((url, extra_args))
            return PlaylistListing(entries=[], channel_id=CHANNEL_ID)

        monkeypatch.setattr(session_module, "fetch_listing", fake_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)
        session.settings.download.proxy = "http://proxy:3128"

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        cmd = runner.calls[0]["cmd"]
        assert "--yes-playlist" in cmd
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / f"channel_{CHANNEL_ID}_archive.txt"
        )
        # The listing goes through the same proxy as the download, with the archive's
        # request wait.
        ((url, extra_args),) = lookups
        assert url == CHANNEL_URL
        assert "http://proxy:3128" in extra_args
        assert extra_args[extra_args.index("--sleep-requests") + 1] == "1.5"
        assert t("prompt_playlist") not in ui.prompts

    def test_lookup_failure_falls_back_to_the_handle(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()

        def failing_listing(*_args: Any) -> PlaylistListing:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        monkeypatch.setattr(session_module, "fetch_listing", failing_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        cmd = runner.calls[0]["cmd"]
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / "channel_ChannelHandle_archive.txt"
        )
        assert t("estimate_unavailable") in ui.text()


TAB_URL = CHANNEL_URL + "/videos"


def _video(ident: str) -> dict[str, Any]:
    return {
        "_type": "url",
        "ie_key": "Youtube",
        "id": ident,
        "duration": 60,
        "url": f"https://www.youtube.com/watch?v={ident}",
        "title": ident,
    }


def _whole_channel_json() -> str:
    """yt-dlp's flat listing of a bare channel URL: each tab a nested, filled playlist."""
    tabs = {
        "videos": ["vid00000001", "vid00000002"],
        "shorts": ["sht00000001"],
        "streams": ["liv00000001"],
    }
    return json.dumps(
        {
            "_type": "playlist",
            "id": CHANNEL_ID,
            "channel_id": CHANNEL_ID,
            "entries": [
                {"_type": "playlist", "id": f"{tab}-tab", "entries": [_video(i) for i in ids]}
                for tab, ids in tabs.items()
            ],
        }
    )


class TestArchiveChannelScope:
    """D01: archiving a channel tab URL archives the whole channel, as README says."""

    def test_a_tab_url_is_listed_and_downloaded_as_the_whole_channel(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()
        listed: list[str] = []

        def fake_listing(url: str, *_args: Any) -> PlaylistListing:
            listed.append(url)
            return PlaylistListing(entries=[], channel_id=CHANNEL_ID)

        monkeypatch.setattr(session_module, "fetch_listing", fake_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, TAB_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        assert listed == [CHANNEL_URL]
        (call,) = runner.calls
        assert call["cmd"][-1] == CHANNEL_URL
        assert TAB_URL not in call["cmd"]
        assert call["cmd"][call["cmd"].index("--download-archive") + 1] == str(
            paths.archives_dir / f"channel_{CHANNEL_ID}_archive.txt"
        )
        # The user is told, and the log keeps both addresses.
        assert t("archive_channel_scope", entered=TAB_URL, effective=CHANNEL_URL) in ui.text()
        assert session.log_path is not None
        log = session.log_path.read_text(encoding="utf-8")
        assert f"entered_url={TAB_URL}" in log
        assert f"url={CHANNEL_URL}\n" in log
        assert t("prompt_playlist") not in ui.prompts

    def test_every_tab_of_the_listing_is_expected_from_the_run(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, 1, EXIT])
        all_ids = ["vid00000001", "vid00000002", "sht00000001", "liv00000001"]
        runner = Recorder(archive_writes=all_ids)
        listing_cmds: list[list[str]] = []
        expected: list[list[str] | None] = []
        real_evaluate = session_module.evaluate

        def fake_capture(cmd: list[str], **_kwargs: Any) -> tuple[int, str, str]:
            listing_cmds.append(cmd)
            return 0, _whole_channel_json(), ""

        def spy_evaluate(**kwargs: Any) -> Any:
            expected.append(kwargs["expected_ids"])
            return real_evaluate(**kwargs)

        monkeypatch.setattr(session_module, "run_capture", fake_capture)
        monkeypatch.setattr(session_module, "evaluate", spy_evaluate)
        session = _session(monkeypatch, tmp_path, paths, ui, TAB_URL + "?si=share", runner)

        session._process_one_cycle()

        (listing_cmd,) = listing_cmds
        assert CHANNEL_URL in listing_cmd
        assert runner.calls[0]["cmd"][-1] == CHANNEL_URL
        assert expected == [all_ids]

    def test_a_listing_failure_still_keys_the_channel_and_downloads_it_whole(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()

        def failing_listing(*_args: Any) -> PlaylistListing:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        monkeypatch.setattr(session_module, "fetch_listing", failing_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, TAB_URL, runner)

        session._process_one_cycle()

        cmd = runner.calls[0]["cmd"]
        assert cmd[-1] == CHANNEL_URL
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / "channel_ChannelHandle_archive.txt"
        )

    def test_the_bare_channel_url_is_used_as_is_without_a_notice(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing([], CHANNEL_ID)
        )
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)

        session._process_one_cycle()

        assert runner.calls[0]["cmd"][-1] == CHANNEL_URL
        assert "entered_url=" not in (session.log_path or Path()).read_text(encoding="utf-8")

    def test_the_live_address_stays_one_video(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        runner = Recorder()
        monkeypatch.setattr(session_module, "fetch_listing", _forbidden)
        live = CHANNEL_URL + "/live"
        session = _session(monkeypatch, tmp_path, paths, ui, live, runner)

        session._process_one_cycle()

        cmd = runner.calls[0]["cmd"]
        assert cmd[-1] == live
        assert "--no-playlist" in cmd

    def test_a_ban_while_listing_the_widened_channel_stops_before_downloading(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE], exit_on_failure=True)
        runner = Recorder()

        def banned_listing(url: str, *_args: Any) -> PlaylistListing:
            assert url == CHANNEL_URL
            raise PlaylistError("returncode=1\nstderr:\nERROR: HTTP Error 429: Too Many Requests")

        monkeypatch.setattr(session_module, "fetch_listing", banned_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, TAB_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE
        assert runner.calls == []


class TestBanProtection:
    def test_ban_during_download_explains_how_to_resume(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1], exit_on_failure=True)
        runner = Recorder(rc=BAN_RETURN_CODE)
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)
        monkeypatch.setattr(session, "handle_error", _forbidden)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE

        assert t("ban_retry_hint") in ui.text()
        assert t("tasks_completed") not in ui.messages

    def test_ban_can_return_to_the_prompt(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1], exit_on_failure=False)
        session = _session(
            monkeypatch, tmp_path, paths, ui, VIDEO_URL, Recorder(rc=BAN_RETURN_CODE)
        )

        assert session._process_one_cycle() == CycleOutcome.CONTINUE

    def test_ban_during_the_channel_listing_never_starts_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE], exit_on_failure=True)
        runner = Recorder()

        def banned_listing(*_args: Any) -> PlaylistListing:
            raise PlaylistError(
                "returncode=1\nstderr:\n"
                "ERROR: [youtube:tab] @ChannelHandle: Sign in to confirm you\u2019re not a bot."
            )

        monkeypatch.setattr(session_module, "fetch_listing", banned_listing)
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE

        assert runner.calls == []
        assert t("ban_retry_hint") in ui.text()
        assert session.log_path is not None
        assert "[BAN-GUARD" in session.log_path.read_text(encoding="utf-8")


class TestRegularModesUnchanged:
    def test_mp4_channel_still_asks_and_still_reports_skips(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        # Video, whole playlist, Quality profile, MKV, no resolution cap, then exit.
        ui = ScriptedUI([int(ModeChoice.VIDEO), 1, 2, 1, 4, EXIT])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)
        fetched: list[str] = []
        monkeypatch.setattr(
            session_module,
            "fetch_listing",
            lambda url, *_args: fetched.append(url) or PlaylistListing([], None),
        )

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        assert t("prompt_playlist") in ui.prompts
        assert fetched == [CHANNEL_URL]
        (call,) = runner.calls
        assert call["stop_on_ban"] is False
        assert "--write-info-json" not in call["cmd"]

    def test_an_mp4_tab_url_keeps_its_tab(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([int(ModeChoice.VIDEO), 1, 2, 1, 4, EXIT])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, TAB_URL, runner)
        fetched: list[str] = []
        monkeypatch.setattr(
            session_module,
            "fetch_listing",
            lambda url, *_args: fetched.append(url) or PlaylistListing([], None),
        )

        session._process_one_cycle()

        assert fetched == [TAB_URL]
        assert runner.calls[0]["cmd"][-1] == TAB_URL
        assert t("archive_channel_scope", entered=TAB_URL, effective=CHANNEL_URL) not in ui.text()


class TestImpersonationWarning:
    """A missing curl_cffi must not be mistaken for a ban: warn before starting."""

    def test_archive_mode_warns_when_it_is_missing(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, Recorder())
        monkeypatch.setattr(session_module, "impersonation_available", lambda: False)

        session._process_one_cycle()

        assert t("warn_impersonation_missing") in ui.text()

    @pytest.mark.parametrize("available", [True, None])
    def test_no_warning_when_present_or_unknown(
        self, monkeypatch, tmp_path: Path, paths: AppPaths, available: bool | None
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, Recorder())
        monkeypatch.setattr(session_module, "impersonation_available", lambda: available)

        session._process_one_cycle()

        assert t("warn_impersonation_missing") not in ui.text()

    def test_regular_modes_do_not_warn(self, monkeypatch, tmp_path: Path, paths: AppPaths) -> None:
        ui = ScriptedUI([int(ModeChoice.AUDIO), EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, Recorder())
        monkeypatch.setattr(session_module, "impersonation_available", lambda: False)

        session._process_one_cycle()

        assert t("warn_impersonation_missing") not in ui.text()
