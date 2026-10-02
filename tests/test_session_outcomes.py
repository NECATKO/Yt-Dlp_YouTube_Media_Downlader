"""Regression tests for session exit-code handling."""

from pathlib import Path

import ytdlp_app.session as session_module
from ytdlp_app.i18n import t
from ytdlp_app.models import ActionChoice, AppPaths, ModeChoice, UserConfig
from ytdlp_app.outcome import StageReport
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
    monkeypatch.setattr(session, "_execute_download", lambda *args: StageReport((1,)))
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


def test_a_rerun_single_video_whose_file_was_deleted_is_not_already_there(
    monkeypatch, tmp_path: Path
) -> None:
    """yt-dlp skips it (exit 0, nothing new) because the archive holds it; the file is gone."""
    session, ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)
    picks = iter([int(ModeChoice.AUDIO)])
    # The mode, then "exit" should the run (wrongly) reach the what-next question.
    monkeypatch.setattr(ui, "pick", lambda *_a: next(picks, int(ActionChoice.EXIT)))
    monkeypatch.setattr(ui, "prompt_exit_on_failure", lambda: False, raising=False)
    monkeypatch.setattr(session, "_execute_download", lambda *args: StageReport((0,)))
    archive = tmp_path / "archives" / "single_audios_mp3.txt"
    archive.parent.mkdir(parents=True)
    archive.write_text("youtube dQw4w9WgXcQ\n", encoding="utf-8")
    archive.with_name("single_audios_mp3.files.tsv").write_text(
        f"dQw4w9WgXcQ\t{tmp_path / 'music' / 'Song [dQw4w9WgXcQ].mp3'}\n", encoding="utf-8"
    )

    session._process_one_cycle()

    text = "\n".join(ui.messages)
    assert t("tasks_completed") not in text
    assert t("outcome_already", count=1) not in text
    assert "dQw4w9WgXcQ" in text
    assert t("archive_records_note") in text


def test_a_missing_file_is_not_reported_as_a_failed_download(monkeypatch, tmp_path: Path) -> None:
    """Nothing went wrong in yt-dlp: no "download failed" reason is made up from the log."""
    session, ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)
    monkeypatch.setattr(session, "handle_error", InteractiveSession.handle_error.__get__(session))
    monkeypatch.setattr(ui, "prompt_exit_on_failure", lambda: False, raising=False)
    monkeypatch.setattr(session, "_execute_download", lambda *args: StageReport((0,)))
    archive = tmp_path / "archives" / "single_audios_mp3.txt"
    archive.parent.mkdir(parents=True)
    archive.write_text("youtube dQw4w9WgXcQ\n", encoding="utf-8")
    archive.with_name("single_audios_mp3.files.tsv").write_text(
        f"dQw4w9WgXcQ\t{tmp_path / 'music' / 'Song [dQw4w9WgXcQ].mp3'}\n", encoding="utf-8"
    )

    assert session._process_one_cycle() == CycleOutcome.CONTINUE

    text = "\n".join(ui.messages)
    assert t("download_failed") not in text
    assert t("archive_records_note") in text


def urls(*answers):
    """An _ask_url stand-in: each answer in turn (None = empty URL); an exception is raised.

    Running out of answers is EOF, which ends the session instead of looping on an error.
    """
    queue = list(answers)

    def ask() -> str | None:
        if not queue:
            raise EOFError
        answer = queue.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    return ask


class TestSessionExitCode:
    """What run_loop returns describes the whole session, not its last cycle."""

    def test_a_clean_session_ends_with_0(self, monkeypatch, tmp_path: Path) -> None:
        session, _ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)
        monkeypatch.setattr(session, "_ask_url", urls(None))

        assert session.run_loop() == 0

    def test_a_failure_earlier_in_the_session_is_not_forgotten(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        session, _ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)
        monkeypatch.setattr(session, "_ask_url", urls("https://youtu.be/dQw4w9WgXcQ", None))

        assert session.run_loop() == 1

    def test_a_later_success_does_not_wipe_an_earlier_failure(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        session, _ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)
        reports = iter([StageReport((1,)), StageReport((0,))])
        monkeypatch.setattr(
            session,
            "_ask_url",
            urls("https://youtu.be/dQw4w9WgXcQ", "https://youtu.be/aaaaaaaaaaa", None),
        )
        archive = tmp_path / "archives" / "single_audios_mp3.txt"
        archive.parent.mkdir(parents=True)

        def archived(*args):
            archive.write_text("youtube aaaaaaaaaaa\n", encoding="utf-8")
            return next(reports)

        monkeypatch.setattr(session, "_execute_download", archived)
        answers = {
            t("prompt_mode"): int(ModeChoice.AUDIO),
            t("prompt_next"): int(ActionChoice.DOWNLOAD_ANOTHER),
        }
        monkeypatch.setattr(_ui, "pick", lambda prompt, _options: answers[prompt])

        assert session.run_loop() == 1

    def test_ctrl_c_is_130_even_after_a_failure(self, monkeypatch, tmp_path: Path) -> None:
        session, _ui = make_failed_session(monkeypatch, tmp_path, exit_on_failure=False)
        monkeypatch.setattr(
            session, "_ask_url", urls("https://youtu.be/dQw4w9WgXcQ", KeyboardInterrupt())
        )

        assert session.run_loop() == 130
