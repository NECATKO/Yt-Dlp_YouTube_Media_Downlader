"""Session-level tests for the estimate, resolution question and disk check."""

import json
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.session as session_module
from tests.test_session_archive import Recorder, ScriptedUI, _session
from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.i18n import set_language, t
from ytdlp_app.models import ActionChoice, AppPaths, ModeChoice, PlaylistEntry
from ytdlp_app.playlist import PlaylistListing
from ytdlp_app.session import CycleOutcome
from ytdlp_app.skip_probe import ProbeResult, ProbeStatus

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
LIST_URL = "https://www.youtube.com/playlist?list=PLabc"
CHANNEL_URL = "https://www.youtube.com/@ChannelHandle"
CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"

VIDEO, AUDIO, ARCHIVE = (int(ModeChoice.VIDEO), int(ModeChoice.AUDIO), int(ModeChoice.ARCHIVE))
EXIT = int(ActionChoice.EXIT)
FULL_PLAYLIST = 1
QUALITY, MKV, COMPAT = 2, 1, 1
UNLIMITED = 4
BAN_TEXT = "ERROR: [youtube:tab] @Handle: Sign in to confirm you\u2019re not a bot."


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


@pytest.fixture(autouse=True)
def _plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    """The estimate is compared with the real disk; make that independent of the machine."""
    monkeypatch.setattr(session_module, "free_bytes", lambda _path: 10**15)


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(
        app_dir=tmp_path,
        config_file=tmp_path / "config.json",
        logs_dir=tmp_path / "logs",
        archives_dir=tmp_path / "archives",
    )


def _entries(count: int = 3) -> list[PlaylistEntry]:
    return [
        PlaylistEntry(i, f"v{i}", "t", f"https://www.youtube.com/watch?v=v{i}", 600.0)
        for i in range(1, count + 1)
    ]


def _selector(cmd: list[str]) -> str:
    return cmd[cmd.index("-f") + 1]


class TestMp4Playlist:
    def _start(self, monkeypatch, tmp_path, paths, ui, runner, url: str = LIST_URL):
        session = _session(monkeypatch, tmp_path, paths, ui, url, runner)
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing(_entries(), None)
        )
        # The probe itself is not what these tests are about.
        monkeypatch.setattr(
            session_module, "probe_item", lambda *_a: ProbeResult(ProbeStatus.REASON, "test")
        )
        return session

    def test_the_estimate_is_shown_before_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, EXIT])
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        text = ui.text()
        assert t("preflight_listing_warning") in text
        assert "1440p (at most)" in text
        assert "3 videos to download" in text
        assert _selector(runner.calls[0]["cmd"]) == "bv*+ba/b"

    def test_the_chosen_cap_reaches_the_command(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, 2, 1, EXIT])  # 1440p, once
        runner = Recorder()
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)

        session._process_one_cycle()

        assert _selector(runner.calls[0]["cmd"]) == "bv*[height<=1440]+ba/b[height<=1440]"
        assert session.settings.video.max_height is None

    def test_saving_the_choice_updates_the_settings_and_the_config_file(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, 2, 2, EXIT])  # 1440p, default
        session = self._start(monkeypatch, tmp_path, paths, ui, Recorder())

        session._process_one_cycle()

        assert session.settings.video.max_height == 1440
        stored = json.loads(paths.config_file.read_text(encoding="utf-8"))
        assert stored["settings"]["video"]["max_height"] == 1440

    def test_too_little_space_can_cancel_without_downloading(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, 2])  # cancel
        runner = Recorder()
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)
        monkeypatch.setattr(session_module, "free_bytes", lambda _path: 1000)

        assert session._process_one_cycle() == CycleOutcome.CONTINUE

        assert runner.calls == []
        assert session.log_path is not None
        assert "Cancelled" in session.log_path.read_text(encoding="utf-8")

    def test_too_little_space_can_continue_anyway(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, 1, EXIT])
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        session = self._start(monkeypatch, tmp_path, paths, ui, runner)
        monkeypatch.setattr(session_module, "free_bytes", lambda _path: 1000)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS
        assert len(runner.calls) == 1

    def test_compatibility_is_capped_at_1080_without_a_question(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, COMPAT, EXIT])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, runner)

        session._process_one_cycle()

        assert len(runner.calls) == 2  # stage 1 and stage 2
        assert "[height<=1080]" in _selector(runner.calls[0]["cmd"])
        assert "[height<=1080]" in _selector(runner.calls[1]["cmd"])
        assert t("prompt_resolution") not in ui.prompts

    def test_a_failed_listing_is_reported_and_can_stop_the_run(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV], exit_on_failure=True)
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def failing(*_a: Any) -> list[PlaylistEntry]:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        monkeypatch.setattr(session_module, "fetch_listing", failing)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE
        assert t("playlist_fetch_failed") in ui.text()
        assert runner.calls == []

    def test_a_failed_listing_can_continue_without_an_estimate(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI(
            [VIDEO, FULL_PLAYLIST, QUALITY, MKV, UNLIMITED, EXIT], exit_on_failure=False
        )
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def failing(*_a: Any) -> list[PlaylistEntry]:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        monkeypatch.setattr(session_module, "fetch_listing", failing)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS
        assert t("estimate_unavailable") in ui.text()
        assert len(runner.calls) == 1

    def test_a_ban_during_the_listing_never_starts_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV], exit_on_failure=True)
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def banned(*_a: Any) -> list[PlaylistEntry]:
            raise PlaylistError(f"returncode=1\nstderr:\n{BAN_TEXT}")

        monkeypatch.setattr(session_module, "fetch_listing", banned)

        assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE
        assert runner.calls == []
        assert t("ban_retry_hint") in ui.text()

    def test_ctrl_c_during_the_listing_stops_before_the_download(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([VIDEO, FULL_PLAYLIST, QUALITY, MKV])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)

        def interrupted(*_a: Any) -> list[PlaylistEntry]:
            raise KeyboardInterrupt

        monkeypatch.setattr(session_module, "fetch_listing", interrupted)

        assert session._process_one_cycle() == CycleOutcome.INTERRUPTED
        assert runner.calls == []


class TestMp3Playlist:
    def test_one_row_and_no_resolution_question(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([AUDIO, FULL_PLAYLIST, EXIT])
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing(_entries(), None)
        )
        monkeypatch.setattr(
            session_module, "probe_item", lambda *_a: ProbeResult(ProbeStatus.REASON, "test")
        )

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        assert "mp3" in ui.text()
        assert t("prompt_resolution") not in ui.prompts
        assert "height" not in " ".join(runner.calls[0]["cmd"])


class TestArchive:
    def test_a_playlist_is_listed_once_for_the_estimate(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, FULL_PLAYLIST, 2, 1, EXIT])  # 1440p, only this once
        runner = Recorder(archive_writes=["v1", "v2", "v3"])
        seen: list[tuple[str, list[str]]] = []

        def listing(url: str, extra_args: list[str], _runner: Any) -> PlaylistListing:
            seen.append((url, extra_args))
            return PlaylistListing(_entries(), None)

        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, runner)
        monkeypatch.setattr(session_module, "fetch_listing", listing)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS

        ((url, extra_args),) = seen
        assert url == LIST_URL
        assert extra_args[extra_args.index("--sleep-requests") + 1] == "1.5"
        cmd = runner.calls[0]["cmd"]
        assert cmd[cmd.index("--download-archive") + 1] == str(
            paths.archives_dir / "playlist_PLabc_archive.txt"
        )
        assert _selector(cmd) == "bv*[height<=1440]+ba/b[height<=1440]"
        assert "at least" in ui.text()  # the wait warning

    def test_videos_already_in_the_archive_are_not_counted(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        paths.archives_dir.mkdir(parents=True)
        (paths.archives_dir / "playlist_PLabc_archive.txt").write_text(
            "youtube v1\nyoutube v2\n", encoding="utf-8"
        )
        ui = ScriptedUI([ARCHIVE, FULL_PLAYLIST, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, LIST_URL, Recorder())
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing(_entries(), None)
        )

        session._process_one_cycle()

        assert "1 videos to download, 2 already in the archive" in ui.text()

    def test_the_listing_warning_mentions_the_request_wait(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, Recorder())
        monkeypatch.setattr(
            session_module, "fetch_listing", lambda *_a: PlaylistListing(_entries(), CHANNEL_ID)
        )

        session._process_one_cycle()

        assert t("preflight_listing_warning") in ui.text()
        assert "waits 1.5 s" in ui.text()

    def test_a_single_video_sends_no_listing_request(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        def forbidden(*_a: Any) -> Any:
            raise AssertionError("a single video must not be listed")

        ui = ScriptedUI([ARCHIVE, 1, EXIT])
        session = _session(monkeypatch, tmp_path, paths, ui, VIDEO_URL, Recorder())
        monkeypatch.setattr(session_module, "fetch_listing", forbidden)

        assert session._process_one_cycle() == CycleOutcome.EXIT_SUCCESS
        assert "Estimated size" not in ui.text()

    def test_ctrl_c_during_the_channel_listing_stops_everything(
        self, monkeypatch, tmp_path: Path, paths: AppPaths
    ) -> None:
        def interrupted(*_a: Any) -> Any:
            raise KeyboardInterrupt

        ui = ScriptedUI([ARCHIVE])
        runner = Recorder()
        session = _session(monkeypatch, tmp_path, paths, ui, CHANNEL_URL, runner)
        monkeypatch.setattr(session_module, "fetch_listing", interrupted)

        assert session._process_one_cycle() == CycleOutcome.INTERRUPTED
        assert runner.calls == []
