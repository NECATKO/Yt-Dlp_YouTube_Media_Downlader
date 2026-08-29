"""Regression tests for session exit-code handling."""

from pathlib import Path

import ytdlp_app.session as session_module
from ytdlp_app.i18n import t
from ytdlp_app.models import AppPaths, ModeChoice, UserConfig
from ytdlp_app.session import CycleOutcome, InteractiveSession


class StubUI:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, message: object = "") -> None:
        self.messages.append(str(message))

    def pick(self, _prompt: str, _options: list[str]) -> int:
        return int(ModeChoice.AUDIO)


def make_failed_session(
    monkeypatch, tmp_path: Path, *, exit_on_failure: bool
) -> tuple[InteractiveSession, StubUI]:
    ui = StubUI()
    paths = AppPaths(
        app_dir=tmp_path,
        config_file=tmp_path / "config.json",
        logs_dir=tmp_path / "logs",
        archives_dir=tmp_path / "archives",
    )
    config = UserConfig(
        app="yt-dlp-downloader",
        videos_dir=tmp_path / "videos",
        music_dir=tmp_path / "music",
    )
    session = InteractiveSession(ui, config, paths)

    monkeypatch.setattr(session, "_ask_url", lambda: "https://youtu.be/dQw4w9WgXcQ")
    monkeypatch.setattr(session, "_print_summary_panel", lambda *args: None)
    monkeypatch.setattr(session, "_execute_download", lambda *args: 1)
    monkeypatch.setattr(session, "handle_error", lambda _path: exit_on_failure)
    monkeypatch.setattr(session_module, "yt_dlp_available", lambda: True)
    monkeypatch.setattr(session_module, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(session_module, "deno_available", lambda: True)

    return session, ui


def test_failed_download_exits_nonzero_when_user_stops(monkeypatch, tmp_path: Path) -> None:
    session, ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=True)

    assert session._process_one_cycle() == CycleOutcome.EXIT_FAILURE
    assert t("tasks_completed") not in ui.messages


def test_failed_download_returns_to_prompt_without_success_banner(
    monkeypatch, tmp_path: Path
) -> None:
    session, ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)

    assert session._process_one_cycle() == CycleOutcome.CONTINUE
    assert t("tasks_completed") not in ui.messages


def test_run_loop_propagates_failure_exit_code(monkeypatch, tmp_path: Path) -> None:
    session, _ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=True)
    outcomes = iter([CycleOutcome.CONTINUE, CycleOutcome.EXIT_FAILURE])
    monkeypatch.setattr(session, "_process_one_cycle", lambda: next(outcomes))

    assert session.run_loop() == 1
