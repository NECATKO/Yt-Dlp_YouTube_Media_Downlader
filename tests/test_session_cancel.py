"""The session hands its sink and cancel event to everything that runs or waits:
downloads, the listing, the skip probes and the speed test. Also the warnings that
used to bypass the UI: settings issues and an unreadable config.json."""

import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.session as session_module
from tests.test_exec_cancel import RecordingSink, cancel_when_ready, quiet_child
from tests.test_exec_lifecycle import pids_from, posix_only, wait_gone
from tests.test_session_archive import Recorder, ScriptedUI, _session
from ytdlp_app import app, speedtest
from ytdlp_app.config import load_config
from ytdlp_app.exec import run_cmd_tee
from ytdlp_app.i18n import set_language, t
from ytdlp_app.models import ActionChoice, AppPaths, ModeChoice, PlaylistEntry, UserConfig
from ytdlp_app.playlist import PlaylistListing
from ytdlp_app.session import CycleOutcome, InteractiveSession
from ytdlp_app.settings import SettingsIssue
from ytdlp_app.skip_probe import ProbeResult, ProbeStatus

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
LIST_URL = "https://www.youtube.com/playlist?list=PL0123456789abcdef"
VIDEO = int(ModeChoice.VIDEO)
FULL = 1
QUALITY = 2
MKV = 1
UNLIMITED = 4
EXIT = int(ActionChoice.EXIT)


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(tmp_path, tmp_path / "config.json", tmp_path / "logs", tmp_path / "archives")


def _wired(monkeypatch, tmp_path, paths, ui, url, runner) -> InteractiveSession:
    """A test session with a sink and a cancel event, as the TUI would create it."""
    session = _session(monkeypatch, tmp_path, paths, ui, url, runner)
    session.sink = RecordingSink()
    session.cancel = threading.Event()
    return session


class TestForwarding:
    def test_downloads_get_the_sink_and_the_event(self, monkeypatch, tmp_path, paths) -> None:
        runner = Recorder(archive_writes=["dQw4w9WgXcQ"])
        session = _wired(
            monkeypatch,
            tmp_path,
            paths,
            ScriptedUI([VIDEO, QUALITY, MKV, UNLIMITED, EXIT]),
            VIDEO_URL,
            runner,
        )

        session._process_one_cycle()

        (call,) = runner.calls
        assert call["sink"] is session.sink
        assert call["cancel"] is session.cancel

    def test_the_console_session_passes_neither(self, monkeypatch, tmp_path, paths) -> None:
        runner = Recorder(archive_writes=["dQw4w9WgXcQ"])
        session = _session(
            monkeypatch,
            tmp_path,
            paths,
            ScriptedUI([VIDEO, QUALITY, MKV, UNLIMITED, EXIT]),
            VIDEO_URL,
            runner,
        )

        session._process_one_cycle()

        (call,) = runner.calls
        assert call["sink"] is None
        assert call["cancel"] is None

    def test_listing_and_probes_get_the_event(self, monkeypatch, tmp_path, paths) -> None:
        ui = ScriptedUI([VIDEO, FULL, QUALITY, MKV, UNLIMITED, EXIT])
        session = _wired(
            monkeypatch, tmp_path, paths, ui, LIST_URL, Recorder(rc=1, archive_writes=["v1"])
        )
        seen: list[Any] = []
        monkeypatch.setattr(
            session_module,
            "run_capture",
            lambda cmd, timeout=None, cancel=None: seen.append(cancel) or (0, "", ""),
        )
        entries = [
            PlaylistEntry(i, f"v{i}", f"T{i}", f"https://www.youtube.com/watch?v=v{i}", 60.0)
            for i in (1, 2)
        ]

        def listing(_url: str, _args: list[str], capture: Any) -> PlaylistListing:
            capture(["yt-dlp"])
            return PlaylistListing(entries, None)

        def probe(_url: str, _args: list[str], capture: Any) -> ProbeResult:
            capture(["yt-dlp"])
            return ProbeResult(ProbeStatus.REASON, "r")

        monkeypatch.setattr(session_module, "fetch_listing", listing)
        monkeypatch.setattr(session_module, "probe_item", probe)

        session._process_one_cycle()

        assert len(seen) == 2  # the listing and the one probe for v2
        assert all(event is session.cancel for event in seen)

    def test_the_speed_test_gets_the_event(self, monkeypatch, tmp_path, paths) -> None:
        session = _wired(monkeypatch, tmp_path, paths, ScriptedUI([]), VIDEO_URL, Recorder())
        seen: list[Any] = []
        monkeypatch.setattr(
            session_module,
            "measure_speed",
            lambda proxy, cancel=None: seen.append((proxy, cancel)) or 1.0,
        )

        assert session._measure_speed("http://p:1") == 1.0
        assert seen == [("http://p:1", session.cancel)]


class TestCancelBelongsToItsCycle:
    def test_each_cycle_starts_with_the_event_cleared(self, monkeypatch, tmp_path, paths) -> None:
        session = _wired(monkeypatch, tmp_path, paths, ScriptedUI([]), VIDEO_URL, Recorder())
        assert session.cancel is not None
        session.cancel.set()
        states: list[bool] = []
        outcomes = iter([CycleOutcome.CONTINUE, CycleOutcome.EXIT_SUCCESS])

        def cycle() -> CycleOutcome:
            assert session.cancel is not None
            states.append(session.cancel.is_set())
            session.cancel.set()  # a cancel during this cycle
            return next(outcomes)

        monkeypatch.setattr(session, "_process_one_cycle", cycle)

        assert session.run_loop() == 0
        assert states == [False, False]


@posix_only
def test_a_cancel_during_a_silent_download_ends_the_cycle_as_interrupted(
    monkeypatch, tmp_path: Path, paths: AppPaths
) -> None:
    """End to end through the real run_cmd_tee: the session's event stops the child."""
    marker = tmp_path / "pids"

    def silent_download(_cmd: list[str], log_path: Path, **kwargs: Any) -> int:
        return run_cmd_tee(quiet_child(marker), log_path, **kwargs)

    ui = ScriptedUI([VIDEO, QUALITY, MKV, UNLIMITED])
    session = _wired(monkeypatch, tmp_path, paths, ui, VIDEO_URL, silent_download)  # type: ignore[arg-type]
    assert session.cancel is not None
    cancel_when_ready(marker, session.cancel)

    started = time.monotonic()
    outcome = session._process_one_cycle()

    assert outcome == CycleOutcome.INTERRUPTED
    assert time.monotonic() - started < 5
    assert wait_gone(pids_from(marker), seconds=1.0) == []


class TestSpeedTestCancel:
    def test_a_cancel_abandons_a_hanging_measurement(self, monkeypatch) -> None:
        release = threading.Event()
        cancel = threading.Event()

        def hangs(_request: urllib.request.Request, _timeout: float) -> Any:
            release.wait(30)
            raise OSError("gave up")

        threading.Timer(0.2, cancel.set).start()
        started = time.monotonic()
        with pytest.raises(KeyboardInterrupt):
            speedtest.measure_speed(None, open_url=hangs, cancel=cancel)
        elapsed = time.monotonic() - started
        release.set()

        assert elapsed < 2

    def test_an_unset_event_changes_nothing(self, monkeypatch) -> None:
        release = threading.Event()
        monkeypatch.setattr(speedtest, "TOTAL_BUDGET_SECONDS", 0.3)

        def hangs(_request: urllib.request.Request, _timeout: float) -> Any:
            release.wait(30)
            raise OSError("gave up")

        assert speedtest.measure_speed(None, open_url=hangs, cancel=threading.Event()) is None
        release.set()


class TestWarningsGoThroughTheUI:
    def test_settings_issues_are_printed_by_the_ui(self, capsys) -> None:
        ui = ScriptedUI([])

        app._print_settings_issues(
            ui,  # type: ignore[arg-type]
            [SettingsIssue("audio", "expected an object", "defaults")],
        )

        assert any("audio" in message for message in ui.messages)
        assert capsys.readouterr().out == ""

    def test_config_warnings_can_be_collected(self, tmp_path: Path, capsys) -> None:
        path = tmp_path / "config.json"
        path.write_text("{not json", encoding="utf-8")
        warnings: list[str] = []

        assert load_config(path, warnings.append) == {}

        assert capsys.readouterr().out == ""
        assert any(t("config_read_warning") in w for w in warnings)
        kept = next(tmp_path.glob("config.json.corrupt*"))
        assert any(kept.name in w for w in warnings)

    def test_config_warnings_still_reach_the_console_at_once(self, tmp_path: Path, capsys) -> None:
        path = tmp_path / "config.json"
        path.write_text("[1, 2]", encoding="utf-8")

        assert load_config(path) == {}

        assert "config.json.corrupt" in capsys.readouterr().out


def test_old_call_sites_get_no_sink_and_no_event(tmp_path: Path, paths: AppPaths) -> None:
    """The new arguments are keyword-only and optional: old call sites keep working."""
    config = UserConfig("a", tmp_path / "v", tmp_path / "m")
    session = InteractiveSession(ScriptedUI([]), config, paths)  # type: ignore[arg-type]

    assert session.sink is None
    assert session.cancel is None
